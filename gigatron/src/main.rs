// TODO: Move things out of this file

use std::{
    collections::{BTreeMap, LinkedList},
    error::Error,
    fmt::Display,
    io::BufRead,
};

use bit_set::BitSet;
use cpu::{MemAccess, MemOperation, OpCode, RomWord};
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

pub enum Placeholder {
    Literal {
        val: String,
    },
    Unary {
        name: String,
        val: Box<Placeholder>,
    },
    Binary {
        name: String,
        lhs: Box<Placeholder>,
        rhs: Box<Placeholder>,
    },
}

impl Display for Placeholder {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Literal { val } => write!(f, "{}", val),
            Self::Unary { name, val } => write!(f, "{}({})", name, val),
            Self::Binary { name, lhs, rhs } => write!(f, "{} {} {}", lhs, name, rhs),
        }
    }
}

impl Placeholder {
    fn parse(tokens: &[&str]) -> Result<(Self, usize), Box<dyn Error>> {
        match tokens[0] {
            token @ ("hi" | "lo") => {
                let (val, val_len) = Self::parse(&tokens[1..])?;
                Ok((
                    Self::Unary {
                        name: token.to_string(),
                        val: Box::new(val),
                    },
                    val_len + 1,
                ))
            }
            token @ "add" => {
                let (lhs, lhs_len) = Self::parse(&tokens[1..])?;
                let (rhs, rhs_len) = Self::parse(&tokens[(1 + lhs_len)..])?;
                Ok((
                    Self::Binary {
                        name: token.to_string(),
                        lhs: Box::new(lhs),
                        rhs: Box::new(rhs),
                    },
                    lhs_len + rhs_len + 1,
                ))
            }
            "zp" => {
                let (val, val_len) = Self::parse(&tokens[1..])?;
                Ok((val, val_len + 1))
            }
            token => Ok((
                Self::Literal {
                    val: token.to_string(),
                },
                1,
            )),
        }
    }
}

struct SymbolTable {
    zero_page: Vec<ZeroPageVariable>,
    labels: BTreeMap<u16, String>, // FIXME there can be multiple labels on same address
    placeholders: BTreeMap<u16, Placeholder>,
}

impl SymbolTable {
    fn load(file_name: &str) -> Result<Self, std::io::Error> {
        // TODO: Clean up

        let file = std::fs::File::open(file_name)?;
        let lines = std::io::BufReader::new(file).lines();

        let mut zero_page = vec![];
        let mut labels = BTreeMap::new();
        let mut placeholders = BTreeMap::new();

        for line in lines.filter_map(Result::ok) {
            let tokens = line.split(" ").collect_vec();
            if tokens.is_empty() {
                continue;
            }

            match tokens[0] {
                "z" => {
                    if tokens.len() != 4 {
                        continue;
                    }

                    if let Ok(addr) = tokens[1].parse() {
                        if let Ok(length) = tokens[2].parse() {
                            zero_page.push(ZeroPageVariable {
                                address: addr,
                                length,
                                name: tokens[3].to_string(),
                            })
                        }
                    }
                }
                "l" => {
                    if tokens.len() != 3 {
                        continue;
                    }

                    if let Ok(addr) = tokens[1].parse() {
                        labels.insert(addr, tokens[2].to_string());
                    }
                }
                "p" => {
                    if let Ok(addr) = tokens[1].parse() {
                        if let Ok((placeholder, _)) = Placeholder::parse(&tokens[2..]) {
                            placeholders.insert(addr, placeholder);
                        }
                    }
                }
                _ => {}
            }
        }

        Ok(Self {
            zero_page,
            labels,
            placeholders,
        })
    }

    fn find_label_before(&self, addr: u16) -> Option<u16> {
        self.labels
            .range(..addr)
            .next_back()
            .map(|t| t.0.to_owned())
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

fn show_rom_view(
    ui: &imgui::Ui,
    rom: &Vec<RomWord>,
    symbols: &SymbolTable,
    highlight: u16,
    debugger: &mut Debugger,
) {
    ui.window("ROM View").build(|| {
        if let Some(_t) = ui.begin_table_with_flags("rom", 2, imgui::TableFlags::BORDERS_V) {
            ui.table_setup_column("Instruction");
            let mut bp_col = imgui::TableColumnSetup::new("Breakpoint");
            bp_col.flags = imgui::TableColumnFlags::WIDTH_FIXED;
            bp_col.init_width_or_weight = 50.0;
            ui.table_setup_column_with(bp_col);

            let mut addr = 0;

            let highlight_label = symbols.find_label_before(highlight);

            ui.table_next_column();
            let mut current_tree = ui
                .tree_node_config("start:")
                .selected(highlight_label.is_none())
                .push();
            ui.table_next_column();
            ui.text_disabled("--");
            for word in rom {
                if let Some(label) = symbols.labels.get(&addr) {
                    ui.table_next_column();
                    if let Some(t) = current_tree {
                        t.pop();
                    }

                    current_tree = ui
                        .tree_node_config(format!("{}:", label))
                        .selected(highlight_label.map_or(false, |a| addr == a))
                        .push();
                    ui.table_next_column();
                    ui.text_disabled("--");
                }

                if let Some(_) = current_tree {
                    let inst = asm::Instruction::unpack(&[word.inst.0]).unwrap();
                    let data = word.data;

                    ui.table_next_column();
                    let _id = ui.push_id_int(addr as i32);
                    ui.align_text_to_frame_padding();
                    ui.tree_node_config(inst.disassemble(
                        addr,
                        data,
                        symbols.placeholders.get(&addr),
                    ))
                    .leaf(true)
                    .tree_push_on_open(false)
                    .selected(addr == highlight)
                    .push();
                    ui.table_next_column();

                    let mut bp = debugger.has_breakpoint(addr);
                    if ui.checkbox("##bp", &mut bp) {
                        debugger.set_breakpoint(addr, bp);
                    }
                }

                addr += 1;
            }
        }
    });
}

fn show_zero_page_vars(
    ui: &imgui::Ui,
    ram: &mut Vec<u8>,
    sym_tbl: &SymbolTable,
    watches: &mut WatchesPanel,
) {
    ui.window("Zero Page Variables").build(|| {
        if let Some(_t) = ui.begin_table_with_flags("vars", 7, imgui::TableFlags::RESIZABLE) {
            ui.table_setup_column("Addr");
            ui.table_setup_column("Name");
            ui.table_setup_column("Hex");
            ui.table_setup_column("Bin");
            ui.table_setup_column("UDec");
            ui.table_setup_column("SDec");
            ui.table_setup_column("Watch");
            ui.table_headers_row();

            for var in sym_tbl.zero_page.iter() {
                let _id = ui.push_id_int(var.address as i32);

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

                ui.table_next_column();
                if ui.button("Watch") {
                    watches.add_watch(var.address as u16, WatchType::Write);
                }
            }
        }
    });
}

enum RunState {
    FullSpeed,
    Step,
    Paused,
}

enum PauseReason {
    Manual,
    Breakpoint,
    FrameTimeout,
    HorizCycleErr,
}

impl Display for PauseReason {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(match self {
            Self::Manual => "Manual",
            Self::Breakpoint => "Hit Breakpoint",
            Self::FrameTimeout => "Frame Timeout",
            Self::HorizCycleErr => "Horizontal Cycle Error",
        })
    }
}

// TODO: Merge with debugger?
struct RunControl {
    paused: Option<PauseReason>,
    break_on_horiz_cycle_errors: bool,
}

impl RunControl {
    fn new() -> Self {
        Self {
            paused: None,
            break_on_horiz_cycle_errors: false,
        }
    }

    fn pause(&mut self, reason: PauseReason) {
        self.paused = Some(reason);
    }

    fn show_ui(&mut self, ui: &imgui::Ui, cpu: &mut cpu::Cpu) -> RunState {
        let mut step = false;
        if let Some(_w) = ui.window("Run Control").begin() {
            if let Some(reason) = &self.paused {
                ui.text(format!("Paused: {}", reason));
                if ui.button("Resume") {
                    self.paused = None;
                } else {
                    ui.same_line();
                    if ui.button("Step") {
                        step = true;
                    }
                }
            } else {
                ui.text("Running");
                if ui.button("Pause") {
                    self.paused = Some(PauseReason::Manual);
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

            ui.checkbox(
                "Break on horizontal cycle errors",
                &mut self.break_on_horiz_cycle_errors,
            );
        }

        if step {
            RunState::Step
        } else if let Some(_) = self.paused {
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

fn show_controller_input(ui: &imgui::Ui) -> u8 {
    if let Some(_w) = ui.window("Controller").begin() {
        let input = |name: &str, bit: u8, key: imgui::Key| {
            ui.button(name);
            if ui.is_item_active() || (ui.is_window_focused() && ui.is_key_down(key)) {
                0
            } else {
                bit
            }
        };

        let val = input("Right", 0b00000001, imgui::Key::RightArrow)
            | input("Left", 0b00000010, imgui::Key::LeftArrow)
            | input("Down", 0b00000100, imgui::Key::DownArrow)
            | input("Up", 0b00001000, imgui::Key::UpArrow)
            | input("Start", 0b00010000, imgui::Key::Enter)
            | input("Select", 0b00100000, imgui::Key::RightShift)
            | input("B", 0b01000000, imgui::Key::Z)
            | input("A", 0b10000000, imgui::Key::X);

        ui.text(format!("Value: {:02x}: {:08b}", val, val));

        val
    } else {
        255
    }
}

enum WatchType {
    Read,
    Write,
}

struct Watch {
    read: bool,
    write: bool,
}

struct WatchEntry {
    pc: u16,
    access: MemAccess,
}

struct WatchesPanel {
    watches: BTreeMap<u16, Watch>,
    log: LinkedList<WatchEntry>,

    new_op_idx: usize,
    new_addr: u16,
}

impl WatchesPanel {
    fn new() -> Self {
        Self {
            watches: BTreeMap::new(),
            log: LinkedList::new(),
            new_op_idx: 0,
            new_addr: 0,
        }
    }

    fn add_watch(&mut self, addr: u16, ty: WatchType) {
        let mut entry = self.watches.entry(addr).or_insert(Watch {
            read: false,
            write: false,
        });

        match ty {
            WatchType::Read => entry.read = true,
            WatchType::Write => entry.write = true,
        }
    }

    fn append_log(&mut self, entry: WatchEntry) {
        self.log.push_back(entry);
        while self.log.len() > 100 {
            self.log.pop_front();
        }
    }
}

fn show_watches_panel(ui: &mut imgui::Ui, panel: &mut WatchesPanel) {
    ui.window("Watches").build(|| {
        if let Some(_t) = ui.begin_table("inputs", 3) {
            ui.table_next_column();
            ui.combo_simple_string("##op", &mut panel.new_op_idx, &["Read", "Write"]);
            ui.table_next_column();
            ui.input_scalar("##addr", &mut panel.new_addr).build();
            ui.table_next_column();
            if ui.button("Add") {
                let ty = if panel.new_op_idx != 0 {
                    WatchType::Write
                } else {
                    WatchType::Read
                };

                panel.add_watch(panel.new_addr, ty);
            }
        }

        if ui.collapsing_header("Current Watches", imgui::TreeNodeFlags::empty()) {
            if let Some(_t) = ui.begin_table_with_flags("watches", 3, imgui::TableFlags::BORDERS) {
                ui.table_setup_column("Addr");
                ui.table_setup_column("Read");
                ui.table_setup_column("Write");
                ui.table_headers_row();

                let mut i = 0;
                for watch in panel.watches.iter_mut() {
                    let _id = ui.push_id_int(i);
                    i += 1;

                    ui.table_next_column();
                    ui.text(format!("{:04x}", watch.0));
                    ui.table_next_column();
                    ui.checkbox("##read", &mut watch.1.read);
                    ui.table_next_column();
                    ui.checkbox("##write", &mut watch.1.write);
                }
            }
        }

        ui.child_window("log").build(|| {
            if let Some(_t) = ui.begin_table("log", 4) {
                ui.table_setup_column("Type");
                ui.table_setup_column("Value");
                ui.table_setup_column("Prev");
                ui.table_setup_column("PC");
                ui.table_headers_row();

                for entry in &panel.log {
                    let WatchEntry { pc, access } = entry;

                    ui.table_next_column();
                    ui.text(format!("{:04x}", access.addr));
                    ui.table_next_column();
                    match access.op {
                        MemOperation::Read { val } => {
                            ui.text(format!("{:02x}", val));
                            ui.table_next_column();
                            ui.text_disabled("--");
                        }
                        MemOperation::Write { prev_val, new_val } => {
                            ui.text(format!("{:02x}", new_val));
                            ui.table_next_column();
                            ui.text(format!("{:02x}", prev_val));
                        }
                    }
                    ui.table_next_column();
                    ui.text(format!("{:04x}", pc))
                }
            }
        });
    });
}

// TODO: Each breakpoint should have option: Break, Log, Ignore
//       Add mem read/write breakpoints, then watches are integrated into debugger
struct Debugger {
    breakpoints: BitSet,
    breakpoints_enabled: bool,

    new_addr: u16,
}

impl Debugger {
    fn new() -> Self {
        Self {
            breakpoints: BitSet::with_capacity(cpu::ROM_SIZE),
            breakpoints_enabled: true,
            new_addr: 0,
        }
    }

    fn set_breakpoint(&mut self, addr: u16, enabled: bool) {
        if enabled {
            self.breakpoints.insert(addr as usize);
        } else {
            self.breakpoints.remove(addr as usize);
        }
    }

    fn should_break(&self, addr: u16) -> bool {
        self.breakpoints_enabled && self.has_breakpoint(addr)
    }

    fn has_breakpoint(&self, addr: u16) -> bool {
        self.breakpoints.contains(addr as usize)
    }

    fn show_ui(&mut self, ui: &imgui::Ui) {
        ui.window("Debugger").build(|| {
            ui.text("Breakpoints:");
            ui.checkbox("Enabled", &mut self.breakpoints_enabled);

            ui.input_scalar("##addr", &mut self.new_addr)
                .display_format("%04x")
                .chars_hexadecimal(true)
                .build();
            ui.same_line();
            if ui.button("Add") {
                self.set_breakpoint(self.new_addr, true);
            }

            if let Some(_t) =
                ui.begin_table_with_flags("breakpoints", 2, imgui::TableFlags::BORDERS)
            {
                ui.table_setup_column("Addr");
                ui.table_setup_column("Remove");
                ui.table_headers_row();

                for addr_usize in self.breakpoints.iter() {
                    let addr = addr_usize as u16;
                    let _id = ui.push_id_usize(addr_usize);

                    ui.table_next_column();
                    ui.text(format!("{:04x}", addr));
                    ui.table_next_column();
                    if ui.button("Remove") {
                        // TODO
                    }
                }
            }
        });
    }
}

fn clock_cpu(cpu: &mut cpu::Cpu, watches: &mut WatchesPanel) {
    let pc = cpu.queued_pc;
    let info = cpu.clock();

    if let Some(access) = info.mem_access {
        if let Some(watch) = watches.watches.get(&access.addr) {
            let entry = WatchEntry { pc, access };

            match entry.access.op {
                MemOperation::Read { .. } if watch.read => {
                    watches.append_log(entry);
                }
                MemOperation::Write { .. } if watch.write => {
                    watches.append_log(entry);
                }
                _ => {}
            }
        }
    }
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

    let total_frame_cycles = (horiz_timing.front_porch
        + horiz_timing.pulse
        + horiz_timing.back_porch
        + horiz_timing.visible)
        * (vert_timing.front_porch
            + vert_timing.pulse
            + vert_timing.back_porch
            + vert_timing.visible)
        / 4;

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

    let mut vga = Vga::new(&horiz_timing, &vert_timing);
    let mut run_control = RunControl::new();

    let mut watches = WatchesPanel::new();
    let mut debugger = Debugger::new();

    let mut open = true;
    ctx.run_main_loop(move |ctx, ui| {
        ui.dockspace_over_main_viewport();

        ui.show_demo_window(&mut open);

        cpu.input = show_controller_input(ui);
        match run_control.show_ui(ui, &mut cpu) {
            RunState::FullSpeed => {
                let mut i = 0;
                loop {
                    if debugger.should_break(cpu.queued_pc) {
                        run_control.pause(PauseReason::Breakpoint);
                        break;
                    }
                    clock_cpu(&mut cpu, &mut watches);

                    let vga_timing = vga.update(ctx, &cpu.reg);
                    if run_control.break_on_horiz_cycle_errors && vga_timing.horiz_cycle_err {
                        run_control.pause(PauseReason::HorizCycleErr);
                        break;
                    }
                    if vga_timing.should_render {
                        break;
                    }

                    i += 1;
                    if i >= total_frame_cycles * 2 {
                        eprintln!("CPU failed to produce frame in time!");
                        run_control.pause(PauseReason::FrameTimeout);
                        break;
                    }
                }
            }
            RunState::Step => {
                clock_cpu(&mut cpu, &mut watches);
                vga.update(ctx, &cpu.reg);
            }
            RunState::Paused => {}
        }
        vga.show_ui(ui);
        show_registers(ui, &mut cpu.reg);
        show_ram_view(ui, &mut cpu.ram);
        show_rom_view(ui, &cpu.rom, &sym_tbl, cpu.reg.pc, &mut debugger);
        show_zero_page_vars(ui, &mut cpu.ram, &sym_tbl, &mut watches);
        show_watches_panel(ui, &mut watches);
        debugger.show_ui(ui);
    });
}
