use enum_display_derive::Display;
use std::fmt::Display;

use packed_struct::prelude::{PackedStruct, PrimitiveEnum_u8};

use crate::Placeholder;

pub const NOP: Instruction = Instruction {
    op: Operation::Load,
    mode: Mode::Acc_D_Far,
    bus: Bus::Acc,
};

#[derive(PackedStruct, Clone, Copy, Debug)]
#[packed_struct(bit_numbering = "msb0")]
pub struct Instruction {
    #[packed_field(bits = "0..=2", ty = "enum")]
    pub op: Operation,
    #[packed_field(bits = "3..=5", ty = "enum")]
    pub mode: Mode,
    #[packed_field(bits = "6..=7", ty = "enum")]
    pub bus: Bus,
}

impl Instruction {
    pub fn disassemble(
        &self,
        rom_addr: u16,
        data: u8,
        placeholder: Option<&Placeholder>,
    ) -> String {
        let op_name = match self.op {
            Operation::Load => "ld   ",
            Operation::And => "anda ",
            Operation::Or => "ora  ",
            Operation::Xor => "xora ",
            Operation::Add => "adda ",
            Operation::Sub => "suba ",
            Operation::Store => "st   ",
            Operation::Jump => match self.mode {
                Mode::Acc_D_Far => "jmp y,",
                Mode::Acc_X_Gt => "bgt  ",
                Mode::Acc_Y_D_Lt => "blt  ",
                Mode::Acc_Y_X_Ne => "bne  ",
                Mode::X_D_Eq => "beq  ",
                Mode::Y_D_Ge => "bge  ",
                Mode::Out_D_Le => "ble  ",
                Mode::Out_Y_Xpp_Bra => "bra  ",
            },
        };

        let out = if self.op == Operation::Store {
            ""
        } else {
            ",out"
        };

        let data_str = match placeholder {
            Some(p) => p.to_string(),
            None => format!("${:02x}", data),
        };

        let (addr, reg) = if self.op == Operation::Jump {
            (format!("[{}]", data_str), "")
        } else {
            match self.mode {
                Mode::Acc_D_Far => (format!("[{}]", data_str), ""),
                Mode::Acc_X_Gt => ("[x]".to_string(), ""),
                Mode::Acc_Y_D_Lt => (format!("[y,{}]", data_str), ""),
                Mode::Acc_Y_X_Ne => ("[y,x]".to_string(), ""),
                Mode::X_D_Eq => (format!("[{}]", data_str), ",x"),
                Mode::Y_D_Ge => (format!("[{}]", data_str), ",y"),
                Mode::Out_D_Le => (format!("[{}]", data_str), out),
                Mode::Out_Y_Xpp_Bra => ("[y,x++]".to_string(), out),
            }
        };

        let bus = match self.bus {
            Bus::Data => data_str,
            Bus::Ram => addr.clone(),
            Bus::Acc => "ac".to_string(),
            Bus::In => "in".to_string(),
        };

        if self.op == Operation::Store {
            if self.bus == Bus::Acc {
                format!("{:04x}  {}{}{}", rom_addr, op_name, addr, reg)
            } else {
                format!("{:04x}  {}{},{}{}", rom_addr, op_name, bus, addr, reg)
            }
        } else {
            format!("{:04x}  {}{}{}", rom_addr, op_name, bus, reg)
        }
    }
}

#[derive(PrimitiveEnum_u8, Clone, Copy, Debug, PartialEq, Display)]
pub enum Operation {
    Load = 0,
    And = 1,
    Or = 2,
    Xor = 3,
    Add = 4,
    Sub = 5,
    Store = 6,
    Jump = 7,
}

#[allow(non_camel_case_types)]
#[derive(PrimitiveEnum_u8, Clone, Copy, Debug, PartialEq, Display)]
pub enum Mode {
    Acc_D_Far = 0,
    Acc_X_Gt = 1,
    Acc_Y_D_Lt = 2,
    Acc_Y_X_Ne = 3,
    X_D_Eq = 4,
    Y_D_Ge = 5,
    Out_D_Le = 6,
    Out_Y_Xpp_Bra = 7,
}

#[derive(PrimitiveEnum_u8, Clone, Copy, Debug, PartialEq, Display)]
pub enum Bus {
    Data = 0,
    Ram = 1,
    Acc = 2,
    In = 3,
}
