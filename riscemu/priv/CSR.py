from typing import Dict, Union, Callable
from collections import defaultdict
from functools import wraps

MSTATUS_OFFSETS = {
    'uie': 0,
    'sie': 1,
    'mie': 3,
    'upie': 4,
    'spie': 5,
    'mpie': 7,
    'spp': 8,
    'mpp': 11,
    'fs': 13,
    'xs': 15,
    'mpriv': 17,
    'sum': 18,
    'mxr': 19,
    'tvm': 20,
    'tw': 21,
    'tsr': 22,
    'sd': 31
}
"""
Offsets for all mstatus bits
"""

MSTATUS_LEN_2 = ('mpp', 'fs', 'xs')
"""
All mstatus parts that have length 2. All other mstatus parts have length 1
"""


class CSR:
    """
    This holds all Control and Status Registers (CSR)
    """
    regs: Dict[int, int]
    """
    All Control and Status Registers are stored here
    """

    name_to_addr: Dict[str, int] = {
        'mstatus': 0x300,
        'misa': 0x301,
        'mie': 0x304,
        'mtvec': 0x305,
        'mepc': 0x341,
        'mcause': 0x342,
        'mtval': 0x343,
        'mip': 0x344,
        'mvendorid': 0xF11,
        'marchid': 0xF12,
        'mimpid': 0xF13,
        'mhartid': 0xF14,
        'time': 0xc01,
        'timeh': 0xc81,
        'halt': 0x789
    }
    """
    Translation for named registers
    """

    listeners: Dict[int, Callable[[int, int], None]]

    def __init__(self):
        self.regs = defaultdict(lambda: 0)
        self.listeners = defaultdict(lambda: (lambda x, y: ()))

    def set(self, addr: Union[str, int], val: int):
        if isinstance(addr, str):
            if not addr in self.name_to_addr:
                print("Unknown CSR register {}".format(addr))
            addr = self.name_to_addr[addr]
        self.listeners[addr](self.regs[addr], val)
        self.regs[addr] = val

    def get(self, addr: Union[str, int]):
        if isinstance(addr, str):
            if not addr in self.name_to_addr:
                print("Unknown CSR register {}".format(addr))
            addr = self.name_to_addr[addr]
        return self.regs[addr]

    def set_listener(self, addr: Union[str, int], listener: Callable[[int, int], None]):
        if isinstance(addr, str):
            if not addr in self.name_to_addr:
                print("Unknown CSR register {}".format(addr))
            addr = self.name_to_addr[addr]
        self.listeners[addr] = listener

    # mstatus properties
    def set_mstatus(self, name: str, val: int):
        """
        Set mstatus bits using this helper. mstatus is a 32 bit register, holding various machine status flags
        Setting them by hand is super painful, so this helper allows you to set specific bits.

        Please make sure your supplied value has the correct width!

        :param name:
        :param val:
        :return:
        """
        size = 2 if name in MSTATUS_LEN_2 else 1
        off = MSTATUS_OFFSETS[name]
        mask = (2**size - 1) << off
        old_val = self.get('mstatus')
        erased = old_val & (~mask)
        new_val = erased | (val << off)
        self.set('mstatus', new_val)

    def get_mstatus(self, name):
        size = 2 if name in MSTATUS_LEN_2 else 1
        off = MSTATUS_OFFSETS[name]
        mask = (2**size - 1) << off
        return (self.get('mstatus') & mask) >> off

    def callback(self, addr: Union[str, int]):
        def inner(func: Callable[[int, int], None]):
            self.set_listener(addr, func)
            return func
        return inner