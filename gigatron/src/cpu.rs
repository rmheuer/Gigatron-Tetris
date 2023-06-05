use std::fmt::Debug;

use packed_struct::{PackedStruct, PrimitiveEnum};
use rand::Rng;

use crate::asm::{Bus, Instruction, Mode, Operation, NOP};

#[derive(Clone, Debug)]
pub struct RegisterFile {
    pub pc: u16,    // Program counter
    pub ir: OpCode, // Instruction register
    pub d: u8,      // Data register
    pub ac: u8,     // Accumulator
    pub x: u8,      // Address X register
    pub y: u8,      // Address Y register
    pub out: u8,    // Output register
    pub undef: u8,  // Undefined value (floating bus)
}

impl RegisterFile {
    pub fn new_random() -> Self {
        let mut r = rand::thread_rng();
        Self {
            pc: r.gen(),
            ir: OpCode(r.gen()),
            d: r.gen(),
            ac: r.gen(),
            x: r.gen(),
            y: r.gen(),
            out: r.gen(),
            undef: r.gen(),
        }
    }
}

#[derive(Clone, Copy)]
pub struct OpCode(pub u8);
impl Debug for OpCode {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}=", self.0)?;
        Instruction::unpack(&[self.0]).fmt(f)
    }
}

pub const RAM_SIZE: usize = 1 << 15;
pub const ROM_SIZE: usize = 1 << 16;

#[derive(Debug)]
pub struct RomWord {
    pub inst: OpCode,
    pub data: u8,
}

pub struct Cpu {
    pub reg: RegisterFile,
    pub ram: Vec<u8>,
    pub rom: Vec<RomWord>,

    pub input: u8,
}

enum ResultDest {
    AC,
    X,
    Y,
    OUT,
    None,
}

impl ResultDest {
    fn mask_write(self, write: bool) -> Self {
        if !write {
            return self;
        }

        match self {
            Self::AC => Self::None,
            Self::OUT => Self::None,
            Self::X => Self::X,
            Self::Y => Self::Y,
            Self::None => Self::None,
        }
    }
}

impl Cpu {
    pub fn new(mut rom: Vec<RomWord>) -> Self {
        let mut cpu = Self {
            reg: RegisterFile::new_random(),
            ram: Vec::with_capacity(RAM_SIZE),
            rom: Vec::with_capacity(ROM_SIZE),
            input: 0,
        };

        let mut r = rand::thread_rng();
        for _ in 0..RAM_SIZE {
            cpu.ram.push(r.gen());
        }

        cpu.rom.append(&mut rom);
        for _ in cpu.rom.len()..ROM_SIZE {
            // Fill remaining space with random garbage
            cpu.rom.push(RomWord {
                inst: OpCode(r.gen()),
                data: r.gen(),
            });
        }

        cpu.reset();
        cpu
    }

    pub fn reset(&mut self) {
        self.reg.pc = 0;
        self.clock();
        self.reg.pc = 0;
    }

    pub fn clock(&mut self) {
        let mut new_reg = self.reg.clone();
        new_reg.undef = rand::random();

        let word = &self.rom[self.reg.pc as usize];
        new_reg.ir = word.inst;
        new_reg.d = word.data;

        let Instruction {
            op: inst,
            mode,
            bus,
        } = Instruction::unpack(&[self.reg.ir.0]).unwrap_or(NOP);

        let write = inst == Operation::Store;
        let jump = inst == Operation::Jump;

        let mut lo = self.reg.d;
        let mut hi = 0;
        let mut to = ResultDest::None;
        let mut inc_x = false;
        if !jump {
            match mode {
                Mode::Acc_D_Far => to = ResultDest::AC,
                Mode::Acc_X_Gt => {
                    to = ResultDest::AC;
                    lo = self.reg.x;
                }
                Mode::Acc_Y_D_Lt => {
                    to = ResultDest::AC;
                    hi = self.reg.y;
                }
                Mode::Acc_Y_X_Ne => {
                    to = ResultDest::AC;
                    lo = self.reg.x;
                    hi = self.reg.y;
                }
                Mode::X_D_Eq => to = ResultDest::X,
                Mode::Y_D_Ge => to = ResultDest::Y,
                Mode::Out_D_Le => to = ResultDest::OUT,
                Mode::Out_Y_Xpp_Bra => {
                    to = ResultDest::OUT;
                    lo = self.reg.x;
                    hi = self.reg.y;
                    inc_x = true;
                }
            }
            to = to.mask_write(write);
        }
        let addr: u16 = ((hi as u16) << 8) | (lo as u16);

        let b = match bus {
            Bus::Data => self.reg.d,
            Bus::Ram => {
                if write {
                    self.reg.undef
                } else {
                    self.ram[(addr & 0x7fff) as usize]
                }
            }
            Bus::Acc => self.reg.ac,
            Bus::In => self.input,
        };
        if write {
            self.ram[(addr & 0x7fff) as usize] = b;
        }

        let alu = match inst {
            Operation::Load => b,
            Operation::And => self.reg.ac & b,
            Operation::Or => self.reg.ac | b,
            Operation::Xor => self.reg.ac ^ b,
            Operation::Add => self.reg.ac.wrapping_add(b),
            Operation::Sub => self.reg.ac.wrapping_sub(b),
            Operation::Store => self.reg.ac,
            Operation::Jump => self.reg.ac.wrapping_neg(),
        };

        match to {
            ResultDest::AC => new_reg.ac = alu,
            ResultDest::X => new_reg.x = alu,
            ResultDest::Y => new_reg.y = alu,
            ResultDest::OUT => new_reg.out = alu,
            ResultDest::None => {}
        }
        if inc_x {
            new_reg.x = self.reg.x.wrapping_add(1);
        }

        new_reg.pc = self.reg.pc.wrapping_add(1);
        if jump {
            let mode_bits = mode.to_primitive();
            if mode_bits != 0 {
                let cond = (self.reg.ac >> 7) + if self.reg.ac == 0 { 2 } else { 0 };
                if mode_bits & (1 << cond) != 0 {
                    new_reg.pc = (self.reg.pc & 0xff00) | (b as u16);
                }
            } else {
                new_reg.pc = ((self.reg.y as u16) << 8) | (b as u16);
            }
        }

        self.reg = new_reg;
    }
}
