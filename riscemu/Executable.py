from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Union, Optional
from .Exceptions import *
from .helpers import *

import typing

if typing.TYPE_CHECKING:
    from .Tokenizer import RiscVInstructionToken


@dataclass(frozen=True)
class MemoryFlags:
    read_only: bool
    executable: bool

    def __repr__(self):
        return "{}({},{})".format(
            self.__class__.__name__,
            'ro' if self.read_only else 'rw',
            'x' if self.executable else '-'
        )


@dataclass
class MemorySection:
    name: str
    flags: MemoryFlags
    size: int = 0
    content: List[bytearray] = field(default_factory=list)

    def add(self, data: bytearray):
        self.content.append(data)
        self.size += len(data)

    def continuous_content(self, parent: 'LoadedExecutable'):
        """
        converts the content into one continuous bytearray
        """
        if self.size == 0:
            return bytearray(0)
        content = self.content[0]
        for b in self.content[1:]:
            content += b
        return content


@dataclass
class InstructionMemorySection(MemorySection):
    content: List['RiscVInstructionToken'] = field(default_factory=list)

    def add_insn(self, insn: 'RiscVInstructionToken'):
        self.content.append(insn)
        self.size += 1

    def continuous_content(self, parent: 'LoadedExecutable'):
        return [
            LoadedInstruction(ins.instruction, ins.args, parent)
            for ins in self.content
        ]


@dataclass()
class Executable:
    run_ptr: Tuple[str, int]
    sections: Dict[str, MemorySection]
    symbols: Dict[str, Tuple[str, int]]
    stack_pref: Optional[int]
    name: str

    def __repr__(self):
        return "{}(sections = {}, symbols = {}, stack = {}, run_ptr = {})".format(
            self.__class__.__name__,
            " ".join(self.sections.keys()),
            " ".join(self.symbols.keys()),
            self.stack_pref,
            self.run_ptr
        )


### LOADING CODE


@dataclass(frozen=True)
class LoadedInstruction:
    """
    An instruction which is loaded into memory. It knows the binary it belongs to to resolve symbols
    """
    name: str
    args: List[str]
    bin: 'LoadedExecutable'

    def get_imm(self, num: int):
        """
        parse and get immediate argument
        """
        if len(self.args) <= num:
            raise ParseException("Instruction {} expected argument at {} (args: {})".format(self.name, num, self.args))
        arg = self.args[num]
        # look up symbols
        if arg in self.bin.symbols:
            return self.bin.symbols[arg]
        return parse_numeric_argument(arg)

    def get_imm_reg(self, num: int):
        """
        parse and get an argument imm(reg)
        """
        if len(self.args) <= num:
            raise ParseException("Instruction {} expected argument at {} (args: {})".format(self.name, num, self.args))
        arg = self.args[num]
        ASSERT_IN("(", arg)
        imm, reg = arg[:-1].split("(")
        if imm in self.bin.symbols:
            return self.bin.symbols[imm], reg
        return parse_numeric_argument(imm), reg

    def get_reg(self, num: int):
        """
        parse and get an register argument
        """
        if len(self.args) <= num:
            raise ParseException("Instruction {} expected argument at {} (args: {})".format(self.name, num, self.args))
        return self.args[num]

    def __repr__(self):
        return "{} {}".format(self.name, ", ".join(self.args))


@dataclass(frozen=True)
class LoadedMemorySection:
    """
    A section which is loaded into memory
    """
    name: str
    base: int
    size: int
    content: Union[List[LoadedInstruction], bytearray] = field(repr=False)
    flags: MemoryFlags
    owner: str

    def read(self, offset: int, size: int):
        if offset < 0:
            raise MemoryAccessException('Invalid offset {}'.format(offset), self.base + offset, size, 'read')
        if offset + size >= self.size:
            raise MemoryAccessException('Outside section boundary of section {}'.format(self.name), self.base + offset,
                                        size, 'read')
        return self.content[offset: offset + size]

    def read_instruction(self, offset):
        if not self.flags.executable:
            raise MemoryAccessException('Section not executable!', self.base + offset, 1, 'read exec')

        if offset < 0:
            raise MemoryAccessException('Invalid offset {}'.format(offset), self.base + offset, 1, 'read exec')
        if offset >= self.size:
            raise MemoryAccessException('Outside section boundary of section {}'.format(self.name), self.base + offset,
                                        1, 'read exec')
        return self.content[offset]

    def write(self, offset, size, data):
        if self.flags.read_only:
            raise MemoryAccessException('Section not writeable {}'.format(self.name), self.base + offset, size, 'write')

        if offset < 0:
            raise MemoryAccessException('Invalid offset {}'.format(offset), self.base + offset, 1, 'write')
        if offset >= self.size:
            raise MemoryAccessException('Outside section boundary of section {}'.format(self.name), self.base + offset,
                                        size, 'write')

        for i in range(size):
            self.content[offset + i] = data[i]

    def dump(self, at_addr=None, fmt='hex', max_rows=10, group=4, bytes_per_row=16, all=False):
        highlight = -1
        if at_addr is None:
            at_addr = self.base
        else:
            highlight = at_addr - self.base

        at_off = at_addr - self.base
        start = max(align_addr(at_off - ((max_rows * bytes_per_row) // 2), 8) - 8, 0)
        if all:
            end = self.size
        else:
            end = min(start + (max_rows * bytes_per_row), self.size)


        fmt_str = "    0x{:0" + str(ceil(log(self.base + end, 16))) + "X}:  {}"

        if self.flags.executable:
            # this section holds instructions!
            start = max(self.base - at_addr - (max_rows // 2), 0)
            end = min(self.size, start + max_rows)
            print(FMT_BOLD + FMT_MAGENTA + "{}, viewing {} instructions:".format(
                self, end - start
            ) + FMT_NONE)
            for i in range(start, end):
                if i == highlight:
                    ins = FMT_UNDERLINE + FMT_ORANGE + repr(self.content[i]) + FMT_NONE
                else:
                    ins = repr(self.content[i])
                print(fmt_str.format(self.base + i, ins))
        else:
            print(FMT_BOLD + FMT_MAGENTA + "{}, viewing {} bytes:".format(
                self, end - start
            ) + FMT_NONE)
            for i in range(start, end, bytes_per_row):
                data = self.content[start + i: min(start + i + bytes_per_row, end)]
                if start + i <= highlight <= start + i + bytes_per_row:
                    # do hightlight here!
                    hi_ind = (highlight - start - i) // group
                    print(fmt_str.format(self.base + start + i, format_bytes(data, fmt, group, highlight=hi_ind)))
                else:
                    print(fmt_str.format(self.base + start + i, format_bytes(data, fmt, group)))
        if end == self.size:
            print(FMT_BOLD + FMT_MAGENTA + "End of section!" + FMT_NONE)
        else:
            print(FMT_BOLD + FMT_MAGENTA + "..." + FMT_NONE)

    def __repr__(self):
        return "{} at 0x{:08X} (size={}bytes, flags={}, owner={})".format(
            self.__class__.__name__,
            self.base,
            self.size,
            self.flags,
            self.owner
        )

class LoadedExecutable:
    """
    This represents an executable which is loaded into memory at address base_addr

    This is basicalle the "loader" in normal system environments
    It initializes the stack and heap

    It still holds a symbol table, that is not accessible memory since I don't want to deal with
    binary strings in memory etc.
    """
    name: str
    base_addr: int
    sections_by_name: Dict[str, LoadedMemorySection]
    sections: List[LoadedMemorySection]
    symbols: Dict[str, int]
    run_ptr: int
    stack_heap: Tuple[int, int]  # pointers to stack and heap, are nullptr if no stack/heap is available

    def __init__(self, exe: Executable, base_addr: int):
        self.name = exe.name
        self.base_addr = base_addr
        self.sections = list()
        self.sections_by_name = dict()
        self.symbols = dict()

        # stack/heap if wanted
        if exe.stack_pref is not None:
            self.sections.append(LoadedMemorySection(
                'stack',
                base_addr,
                exe.stack_pref,
                bytearray(exe.stack_pref),
                MemoryFlags(read_only=False, executable=False),
                self.name
            ))
            self.stack_heap = (self.base_addr, self.base_addr + exe.stack_pref)
        else:
            self.stack_heap = (0, 0)

        curr = base_addr
        for sec in exe.sections.values():
            loaded_sec = LoadedMemorySection(
                sec.name,
                curr,
                sec.size,
                sec.continuous_content(self),
                sec.flags,
                self.name
            )
            self.sections.append(loaded_sec)
            self.sections_by_name[loaded_sec.name] = loaded_sec
            curr = align_addr(loaded_sec.size + curr)

        for name, (sec_name, offset) in exe.symbols.items():
            ASSERT_IN(sec_name, self.sections_by_name)
            self.symbols[name] = self.sections_by_name[sec_name].base + offset

        self.size = curr - base_addr

        # translate run_ptr from executable
        run_ptr_sec, run_ptr_off = exe.run_ptr
        self.run_ptr = self.sections_by_name[run_ptr_sec].base + run_ptr_off

    def __repr__(self):
        return '{}[{}](base=0x{:08X}, size={}bytes, sections={}, run_ptr=0x{:08X})'.format(
            self.__class__.__name__,
            self.name,
            self.base_addr,
            self.size,
            " ".join(self.sections_by_name.keys()),
            self.run_ptr
        )
