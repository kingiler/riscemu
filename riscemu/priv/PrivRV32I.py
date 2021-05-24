"""
RiscEmu (c) 2021 Anton Lydike

SPDX-License-Identifier: MIT
"""

from ..instructions.RV32I import *
from ..Exceptions import INS_NOT_IMPLEMENTED
from .Exceptions import *
from .privmodes import PrivModes
import typing

if typing.TYPE_CHECKING:
    from riscemu.priv.PrivCPU import PrivCPU


class PrivRV32I(RV32I):
    cpu: 'PrivCPU'
    """
    This is an extension of RV32I, written for the PrivCPU class
    """

    def instruction_csrrw(self, ins: 'LoadedInstruction'):
        rd, rs, ind = self.parse_crs_ins(ins)
        if rd != 'zero':
            old_val = int_from_bytes(self.cpu.csr[ind])
            self.regs.set(rd, old_val)
        self.cpu.csr.set(ind, rs)

    def instruction_csrrs(self, ins: 'LoadedInstruction'):
        INS_NOT_IMPLEMENTED(ins)

    def instruction_csrrc(self, ins: 'LoadedInstruction'):
        INS_NOT_IMPLEMENTED(ins)

    def instruction_csrrsi(self, ins: 'LoadedInstruction'):
        INS_NOT_IMPLEMENTED(ins)

    def instruction_csrrwi(self, ins: 'LoadedInstruction'):
        INS_NOT_IMPLEMENTED(ins)

    def instruction_csrrci(self, ins: 'LoadedInstruction'):
        INS_NOT_IMPLEMENTED(ins)

    def instruction_mret(self, ins: 'LoadedInstruction'):
        if self.cpu.mode != PrivModes.MACHINE:
            print("MRET not inside machine level code!")
            raise IllegalInstructionTrap()
        # retore mie
        mpie = self.cpu.csr.get_mstatus('mpie')
        self.cpu.csr.set_mstatus('mie', mpie)
        # restore priv
        mpp = self.cpu.csr.get_mstatus('mpp')
        self.cpu.mode = PrivModes(mpp)
        # restore pc
        mepc = self.cpu.csr.get('mepc')
        self.cpu.pc = mepc

    def instruction_uret(self, ins: 'LoadedInstruction'):
        raise IllegalInstructionTrap()

    def instruction_sret(self, ins: 'LoadedInstruction'):
        raise IllegalInstructionTrap()

    def instruction_scall(self, ins: 'LoadedInstruction'):
        """
        Overwrite the scall from userspace RV32I
        """
        if self.cpu.mode == PrivModes.USER:
            raise CpuTrap(0, 8)  # ecall from U mode
        elif self.cpu.mode == PrivModes.SUPER:
            raise CpuTrap(0, 9)  # ecall from S mode - should not happen
        elif self.cpu.mode == PrivModes.MACHINE:
            raise CpuTrap(0, 11)  # ecall from M mode

    def instruction_beq(self, ins: 'LoadedInstruction'):
        rs1, rs2, dst = self.parse_rs_rs_imm(ins)
        if rs1 == rs2:
            self.pc += dst - 4

    def instruction_bne(self, ins: 'LoadedInstruction'):
        rs1, rs2, dst = self.parse_rs_rs_imm(ins)
        if rs1 != rs2:
            self.pc += dst - 4

    def instruction_blt(self, ins: 'LoadedInstruction'):
        rs1, rs2, dst = self.parse_rs_rs_imm(ins)
        if rs1 < rs2:
            self.pc += dst

    def instruction_bge(self, ins: 'LoadedInstruction'):
        rs1, rs2, dst = self.parse_rs_rs_imm(ins)
        if rs1 >= rs2:
            self.pc += dst - 4

    def instruction_bltu(self, ins: 'LoadedInstruction'):
        rs1, rs2, dst = self.parse_rs_rs_imm(ins, signed=False)
        if rs1 < rs2:
            self.pc += dst - 4

    def instruction_bgeu(self, ins: 'LoadedInstruction'):
        rs1, rs2, dst = self.parse_rs_rs_imm(ins, signed=False)
        if rs1 >= rs2:
            self.pc += dst - 4

    # technically deprecated
    def instruction_j(self, ins: 'LoadedInstruction'):
        raise NotImplementedError("Should never be reached!")

    def instruction_jal(self, ins: 'LoadedInstruction'):
        ASSERT_LEN(ins.args, 2)
        reg = ins.get_reg(0)
        addr = ins.get_imm(1)
        self.regs.set(reg, self.pc)
        self.pc += addr - 4

    def instruction_jalr(self, ins: 'LoadedInstruction'):
        ASSERT_LEN(ins.args, 3)
        rd, rs, imm = self.parse_rd_rs_imm(ins)
        self.regs.set(rd, self.pc)
        self.pc = rs + imm - 4

    def parse_crs_ins(self, ins: 'LoadedInstruction'):
        ASSERT_LEN(ins.args, 3)
        return ins.get_reg(0), self.get_reg_content(ins, 1), ins.get_imm(2)

    def parse_mem_ins(self, ins: 'LoadedInstruction') -> Tuple[str, int]:
        ASSERT_LEN(ins.args, 3)
        print("dop")
        return ins.get_reg(1), self.get_reg_content(ins, 0) + ins.get_imm(2)