use std::time::Instant;

use copypasta::{ClipboardContext, ClipboardProvider};
use glium::Surface;
use winit::{
    event::{Event, WindowEvent},
    event_loop::ControlFlow,
};

pub struct UiContext {
    event_loop: winit::event_loop::EventLoop<()>,
    imgui: imgui::Context,
    imgui_platform: imgui_winit_support::WinitPlatform,
    render_ctx: RenderContext,
}

pub struct RenderContext {
    pub gl_ctx: glium::Display,
    pub imgui_renderer: imgui_glium_renderer::Renderer,
}

impl UiContext {
    pub fn new(width: u32, height: u32, title: &str) -> Self {
        let event_loop = winit::event_loop::EventLoop::new();
        let gl_ctx_builder = glium::glutin::ContextBuilder::new().with_vsync(true);
        let window_builder = winit::window::WindowBuilder::new()
            .with_title(title)
            .with_inner_size(glium::glutin::dpi::LogicalSize::new(width, height));
        let gl_ctx = glium::Display::new(window_builder, gl_ctx_builder, &event_loop)
            .expect("Failed to initialize display");

        let mut imgui = imgui::Context::create();
        imgui.io_mut().config_flags |= imgui::ConfigFlags::DOCKING_ENABLE;

        if let Some(backend) = ClipboardSupport::new() {
            imgui.set_clipboard_backend(backend);
        } else {
            eprintln!("Failed to initialize clipboard backend");
        }

        let mut imgui_platform = imgui_winit_support::WinitPlatform::init(&mut imgui);
        {
            let gl_window = gl_ctx.gl_window();
            let window = gl_window.window();
            imgui_platform.attach_window(
                imgui.io_mut(),
                window,
                imgui_winit_support::HiDpiMode::Default,
            );
        }

        let imgui_renderer = imgui_glium_renderer::Renderer::init(&mut imgui, &gl_ctx)
            .expect("Failed to initialize renderer");

        Self {
            event_loop,
            imgui,
            imgui_platform,
            render_ctx: RenderContext {
                gl_ctx,
                imgui_renderer,
            },
        }
    }

    pub fn run_main_loop<F>(self, mut draw_frame_fn: F)
    where
        F: FnMut(&mut RenderContext, &mut imgui::Ui) + 'static,
    {
        let Self {
            event_loop,
            mut imgui,
            mut imgui_platform,
            mut render_ctx,
        } = self;

        let mut last_frame = Instant::now();
        event_loop.run(move |event, _, control_flow| match event {
            Event::NewEvents(_) => {
                let now = Instant::now();
                imgui.io_mut().update_delta_time(now - last_frame);
                last_frame = now;
            }
            Event::MainEventsCleared => {
                let gl_window = render_ctx.gl_ctx.gl_window();
                imgui_platform
                    .prepare_frame(imgui.io_mut(), gl_window.window())
                    .expect("Failed to prepare frame");
                gl_window.window().request_redraw();
            }
            Event::RedrawRequested(_) => {
                let ui = imgui.frame();
                draw_frame_fn(&mut render_ctx, ui);

                let gl_window = render_ctx.gl_ctx.gl_window();
                let mut target = render_ctx.gl_ctx.draw();
                target.clear_color_srgb(1.0, 1.0, 1.0, 1.0);
                imgui_platform.prepare_render(ui, gl_window.window());
                let draw_data = imgui.render();
                render_ctx
                    .imgui_renderer
                    .render(&mut target, draw_data)
                    .expect("Rendering failed");
                target.finish().expect("Failed to swap buffers");
            }
            Event::WindowEvent {
                event: WindowEvent::CloseRequested,
                ..
            } => *control_flow = ControlFlow::Exit,
            event => {
                let gl_window = render_ctx.gl_ctx.gl_window();
                imgui_platform.handle_event(imgui.io_mut(), gl_window.window(), &event);
            }
        });
    }
}

struct ClipboardSupport(ClipboardContext);

impl ClipboardSupport {
    fn new() -> Option<Self> {
        ClipboardContext::new().ok().map(ClipboardSupport)
    }
}

impl imgui::ClipboardBackend for ClipboardSupport {
    fn get(&mut self) -> Option<String> {
        self.0.get_contents().ok()
    }

    fn set(&mut self, value: &str) {
        let _ = self.0.set_contents(value.to_owned());
    }
}
