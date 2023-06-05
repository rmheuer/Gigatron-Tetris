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

#[derive(PrimitiveEnum_u8, Clone, Copy, Debug, PartialEq)]
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
#[derive(PrimitiveEnum_u8, Clone, Copy, Debug, PartialEq)]
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

#[derive(PrimitiveEnum_u8, Clone, Copy, Debug, PartialEq)]
pub enum Bus {
    Data = 0,
    Ram = 1,
    Acc = 2,
    In = 3,
}
