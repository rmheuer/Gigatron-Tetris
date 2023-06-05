use std::io::BufRead;

use cpu::{OpCode, RomWord};
use itertools::Itertools;
use packed_struct::PackedStruct;

use crate::vga::{SyncTiming, Vga};

pub mod asm;
pub mod cpu;
pub mod ui_context;
pub mod vga;

fn load_rom(file_name: &str) -> Result<Vec<RomWord>, std::io::Error> {
    let bytes = std::fs::read(file_name)?;

    let rom = bytes
        .into_iter()
        .tuples()
        .map(|(opcode, data)| RomWord {
            inst: OpCode(opcode),
            data,
        })
        .collect_vec();

    Ok(rom)
}

struct ZeroPageVariable {
    address: u8,
    length: u8,
    name: String,
}

struct SymbolTable {
    zero_page: Vec<ZeroPageVariable>,
}

impl SymbolTable {
    fn load(file_name: &str) -> Result<Self, std::io::Error> {
        // TODO: Clean up

        let file = std::fs::File::open(file_name)?;
        let lines = std::io::BufReader::new(file).lines();

        let zero_page = lines
            .filter_map(Result::ok)
            .filter_map(|line| {
                let tokens = line.split(" ").collect_vec();
                if tokens.is_empty() {
                    return None;
                }

                match tokens[0] {
                    "z" => {
                        if tokens.len() == 4 {
                            tokens[1]
                                .parse::<u8>()
                                .and_then(|addr| {
                                    Ok(ZeroPageVariable {
                                        address: addr,
                                        length: tokens[2].parse()?,
                                        name: tokens[3].to_string(),
                                    })
                                })
                                .ok()
                        } else {
                            None
                        }
                    }
                    _ => None,
                }
            })
            .collect_vec();

        Ok(Self { zero_page })
    }
}

fn show_ram_view(ui: &imgui::Ui, ram: &mut Vec<u8>) {
    ui.window("RAM View").build(|| {
        for row in 0..(cpu::RAM_SIZE / 16) {
            let addr_base = row * 16;
            ui.text(format!("{:04x}: ", addr_base));
            for col in 0..16 {
                let addr = addr_base + col;
                ui.same_line();
                ui.text(format!("{:02x}", ram[addr]));
            }
        }
    });
}

fn show_zero_page_vars(ui: &imgui::Ui, ram: &mut Vec<u8>, sym_tbl: &SymbolTable) {
    ui.window("Zero Page Variables").build(|| {
        if let Some(_t) = ui.begin_table_with_flags("vars", 6, imgui::TableFlags::RESIZABLE) {
            ui.table_setup_column("Addr");
            ui.table_setup_column("Name");
            ui.table_setup_column("Hex");
            ui.table_setup_column("Bin");
            ui.table_setup_column("UDec");
            ui.table_setup_column("SDec");
            ui.table_headers_row();

            for var in sym_tbl.zero_page.iter() {
                ui.table_next_column();
                ui.text(format!("{:02x}", var.address));
                ui.table_next_column();
                ui.text(var.name.as_str());

                // TODO: Handle longer than 1 byte variables
                let value = ram[var.address as usize];
                ui.table_next_column();
                ui.text(format!("{:02x}", value));
                ui.table_next_column();
                ui.text(format!("{:08b}", value));
                ui.table_next_column();
                ui.text(format!("{}", value));
                ui.table_next_column();
                ui.text(format!("{}", value as i8));
            }
        }
    });
}

enum RunState {
    FullSpeed,
    Step,
    Paused,
}

struct RunControl {
    paused: bool,
}

impl RunControl {
    fn new() -> Self {
        Self { paused: false }
    }

    fn show_ui(&mut self, ui: &imgui::Ui, cpu: &mut cpu::Cpu) -> RunState {
        let mut step = false;
        if let Some(_w) = ui.window("Run Control").begin() {
            if self.paused {
                if ui.button("Resume") {
                    self.paused = false;
                } else {
                    ui.same_line();
                    if ui.button("Step") {
                        step = true;
                    }
                }
            } else {
                if ui.button("Pause") {
                    self.paused = true;
                }
            }

            ui.spacing();
            ui.text("Reset:");
            ui.same_line();
            if ui.button("Soft") {
                cpu.soft_reset();
            }
            ui.same_line();
            if ui.button("Hard") {
                cpu.hard_reset();
            }
        }

        if step {
            RunState::Step
        } else if self.paused {
            RunState::Paused
        } else {
            RunState::FullSpeed
        }
    }
}

fn show_registers(ui: &imgui::Ui, reg: &mut cpu::RegisterFile) {
    ui.window("CPU Registers").build(|| {
        if let Some(_t) = ui.begin_table_with_flags("registers", 5, imgui::TableFlags::RESIZABLE) {
            ui.table_setup_column("Name");
            ui.table_setup_column("Hex");
            ui.table_setup_column("Bin");
            ui.table_setup_column("UDec");
            ui.table_setup_column("SDec");
            ui.table_headers_row();

            let pc = reg.pc;
            ui.table_next_column();
            ui.text("PC");
            ui.table_next_column();
            ui.text(format!("{:04x}", pc));
            ui.table_next_column();
            ui.text(format!("{:016b}", pc));
            ui.table_next_column();
            ui.text(format!("{}", pc));
            ui.table_next_column();
            ui.text(format!("{}", pc as i16));

            fn show(ui: &imgui::Ui, name: &str, value: u8) {
                ui.table_next_column();
                ui.text(name);
                ui.table_next_column();
                ui.text(format!("{:02x}", value));
                ui.table_next_column();
                ui.text(format!("{:08b}", value));
                ui.table_next_column();
                ui.text(format!("{}", value));
                ui.table_next_column();
                ui.text(format!("{}", value as i8));
            }

            show(ui, "IR", reg.ir.0);
            // TODO: Show detailed instruction info

            show(ui, "D", reg.d);
            show(ui, "AC", reg.ac);
            show(ui, "X", reg.x);
            show(ui, "Y", reg.y);
            show(ui, "OUT", reg.out);
        }

        ui.spacing();

        match asm::Instruction::unpack(&[reg.ir.0]) {
            Ok(inst) => {
                ui.text("Instruction:");
                ui.text(format!("Op: {}", inst.op));
                ui.text(format!("Mode: {}", inst.mode));
                ui.text(format!("Bus: {}", inst.bus));
            }
            Err(e) => {
                ui.text("Invalid instruction???");
                ui.text(format!("{}", e));
            }
        }
    });
}

fn main() {
    let ctx = ui_context::UiContext::new(1280, 720, "Gigatron Emulator");

    let vert_timing = SyncTiming {
        front_porch: 6,
        pulse: 8,
        back_porch: 27,
        visible: 480,
    };
    let horiz_timing = SyncTiming {
        front_porch: 16,
        pulse: 96,
        back_porch: 48,
        visible: 640,
    };

    let args = std::env::args().collect_vec();
    let rom_file = if args.len() < 2 {
        "../main.rom"
    } else {
        &args[1]
    };
    println!("Loading {}", rom_file);
    let sym_tbl = SymbolTable::load("../main.sym").expect("Failed to read symbols file"); // TODO: arg

    let rom = load_rom(&rom_file).expect("Failed to read ROM file");
    let mut cpu = cpu::Cpu::new(rom);
    cpu.input = 0xFF;

    let mut vga = Vga::new(&horiz_timing, &vert_timing);
    let mut run_control = RunControl::new();

    let mut open = true;
    ctx.run_main_loop(move |ctx, ui| {
        ui.dockspace_over_main_viewport();

        ui.show_demo_window(&mut open);

        match run_control.show_ui(ui, &mut cpu) {
            RunState::FullSpeed => loop {
                cpu.clock();
                if vga.update(ctx, &cpu.reg) {
                    break;
                }
            },
            RunState::Step => {
                cpu.clock();
                vga.update(ctx, &cpu.reg);
            }
            RunState::Paused => {}
        }
        vga.show_ui(ui);
        show_registers(ui, &mut cpu.reg);
        show_ram_view(ui, &mut cpu.ram);
        show_zero_page_vars(ui, &mut cpu.ram, &sym_tbl);
    });
}
