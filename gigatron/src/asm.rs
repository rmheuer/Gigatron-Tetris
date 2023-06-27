use enum_display_derive::Display;
use std::{collections::BTreeMap, fmt::Display};

use packed_struct::prelude::{PackedStruct, PrimitiveEnum_u8};

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
    pub fn disassemble(&self, rom_addr: u16, data: u8, labels: &BTreeMap<u16, String>) -> String {
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

        let (ac, out) = if self.op == Operation::Store {
            ("", "")
        } else {
            (",ac", ",out")
        };

        let (addr, reg) = if self.op == Operation::Jump {
            (format!("[{:02x}]", data), "")
        } else {
            match self.mode {
                Mode::Acc_D_Far => (format!("[${:02x}]", data), ac),
                Mode::Acc_X_Gt => ("[x]".to_string(), ac),
                Mode::Acc_Y_D_Lt => (format!("[y,${:02x}]", data), ac),
                Mode::Acc_Y_X_Ne => ("[y,x]".to_string(), ac),
                Mode::X_D_Eq => (format!("[${:02x}]", data), ",x"),
                Mode::Y_D_Ge => (format!("[${:02x}]", data), ",y"),
                Mode::Out_D_Le => (format!("[${:02x}]", data), out),
                Mode::Out_Y_Xpp_Bra => ("[y,x++]".to_string(), out),
            }
        };

        let mut bus = match self.bus {
            Bus::Data => format!("${:02x}", data),
            Bus::Ram => addr,
            Bus::Acc => "ac".to_string(),
            Bus::In => "in".to_string(),
        };

        if self.op == Operation::Jump && self.mode != Mode::Acc_D_Far && self.bus == Bus::Data {
            let lo = rom_addr & 255;
            let mut hi = rom_addr >> 8;
            if lo == 255 {
                hi = (hi + 1) & 255;
            }
            let dest = (hi << 8) + data as u16;

            bus = match labels.get(&dest) {
                Some(name) => format!("'{}'", name),
                None => format!("${:04x}", dest),
            };
        }

        format!("{:04x}  {}{}{}", rom_addr, op_name, bus, reg)
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
