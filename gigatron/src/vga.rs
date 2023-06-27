use std::{borrow::Cow, cell::Cell, rc::Rc};

use glium::texture::RawImage2d;

use crate::{cpu::RegisterFile, ui_context::RenderContext};

pub const VSYNC: u8 = 0x80;
pub const HSYNC: u8 = 0x40;

pub struct SyncTiming {
    pub front_porch: i32,
    pub pulse: i32,
    pub back_porch: i32,
    pub visible: i32,
}

pub struct Vga {
    pub tex_id: Option<imgui::TextureId>,
    framebuffer: Cell<Vec<u8>>,
    size: (u32, u32),
    pixel_count: usize,

    min_row: i32,
    max_row: i32,
    min_col: i32,
    max_col: i32,

    prev_out: u8,
    row: i32,
    col: i32,
    pixel: usize,
}

pub struct TimingResult {
    pub should_render: bool,
    pub horiz_cycle_err: bool,
}

impl Vga {
    pub fn new(horiz_timing: &SyncTiming, vert_timing: &SyncTiming) -> Self {
        let min_row = vert_timing.back_porch + vert_timing.pulse;
        let min_col = horiz_timing.back_porch + horiz_timing.pulse;

        let pixel_count = (horiz_timing.visible * vert_timing.visible * 4) as usize;

        Self {
            tex_id: None,
            framebuffer: Cell::new(vec![0; pixel_count]),
            size: (horiz_timing.visible as u32, vert_timing.visible as u32),
            pixel_count,

            min_row,
            max_row: min_row + vert_timing.visible,
            min_col,
            max_col: min_col + horiz_timing.visible,

            prev_out: 0,
            row: 0,
            col: 0,
            pixel: 0,
        }
    }

    fn render(&mut self, ctx: &mut RenderContext) {
        // Swap framebuffers
        let fb = self.framebuffer.replace(vec![0; self.pixel_count]);

        let tex_data: RawImage2d<u8> = RawImage2d {
            data: Cow::Owned(fb),
            width: self.size.0,
            height: self.size.1,
            format: glium::texture::ClientFormat::U8U8U8U8,
        };

        let tex_opt = glium::Texture2d::with_format(
            &ctx.gl_ctx,
            tex_data,
            glium::texture::UncompressedFloatFormat::F32F32F32F32,
            glium::texture::MipmapsOption::NoMipmap,
        )
        .ok();

        if let Some(tex_2d) = tex_opt {
            let tex = imgui_glium_renderer::Texture {
                texture: Rc::new(tex_2d),
                sampler: glium::uniforms::SamplerBehavior {
                    magnify_filter: glium::uniforms::MagnifySamplerFilter::Nearest,
                    minify_filter: glium::uniforms::MinifySamplerFilter::Nearest,
                    ..Default::default()
                },
            };

            let textures = ctx.imgui_renderer.textures();
            match self.tex_id {
                Some(id) => {
                    textures.replace(id, tex);
                }
                None => {
                    self.tex_id = Some(textures.insert(tex));
                }
            }
        }
    }

    pub fn show_ui(&self, ui: &mut imgui::Ui) {
        ui.window("VGA Monitor").build(|| match self.tex_id {
            Some(tex) => {
                imgui::Image::new(tex, [self.size.0 as f32, self.size.1 as f32]).build(ui);
            }
            None => {
                ui.text("Image go here");
            }
        });
    }

    // Returns whether the next frame should be rendered now
    pub fn update(&mut self, ctx: &mut RenderContext, reg: &RegisterFile) -> TimingResult {
        let out = reg.out;
        let falling = self.prev_out & !out;
        self.prev_out = out;

        let render = falling & VSYNC != 0;
        if render {
            self.row = -1;
            self.pixel = 0;
            self.render(ctx);
        }

        let mut horiz_cycle_err = false;
        if falling & HSYNC != 0 {
            if self.col != 800 {
                horiz_cycle_err = true;
            }
            self.col = 0;
            self.row += 1;
        }

        if (self.row >= self.min_row && self.row < self.max_row)
            && (self.col >= self.min_col && self.col < self.max_col)
        {
            let r = 85 * (out & 3);
            let g = 85 * ((out >> 2) & 3);
            let b = 85 * ((out >> 4) & 3);

            let fb = self.framebuffer.get_mut();
            for _ in 0..4 {
                fb[self.pixel] = r;
                fb[self.pixel + 1] = g;
                fb[self.pixel + 2] = b;
                fb[self.pixel + 3] = 255;
                self.pixel += 4;
            }
        }

        self.col += 4;

        TimingResult {
            should_render: render,
            horiz_cycle_err,
        }
    }
}
