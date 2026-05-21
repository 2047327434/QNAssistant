"""千牛话术助手 - 美化无边框悬浮窗，点击话术自动填充到千牛输入框"""
import os
import tkinter as tk

import win32con
import win32gui

from core.defaults import get_app_root, ensure_phrases_file
from core.window_tracker import WindowTracker
from core.text_inject import TextInjector
from ui.phrases_panel import PhrasesPanel


class FloatingWindow:
    """千牛话术助手悬浮窗"""

    PANEL_WIDTH = 300
    DEFAULT_HEIGHT = 640
    TRACK_INTERVAL = 80
    ICON_SIZE = 60
    TRANSPARENT_COLOR = "#ff00ff"

    COLOR_PRIMARY = "#5b6af0"
    COLOR_PRIMARY_DARK = "#4a5ad9"
    COLOR_TITLE = "#181a29"
    COLOR_BG = "#eef0f6"
    COLOR_CARD = "#ffffff"
    COLOR_MUTED = "#8c8ea3"
    COLOR_BORDER = "#e4e5ee"
    COLOR_SUCCESS = "#22c55e"
    COLOR_WARN = "#f59e0b"

    def __init__(self):
        self.app_root = get_app_root()
        self.phrases_path = ensure_phrases_file(self.app_root)
        self.tracker = WindowTracker()
        self.injector = TextInjector(self.tracker)
        self._last_chat_hwnd = None
        self._old_wnd_proc = None
        self._wnd_proc_ref = None
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._auto_track = True
        self._icon_drag_start_x = 0
        self._icon_drag_start_y = 0
        self._icon_dragged = False
        self.icon_window = None
        self.icon_canvas = None

        self.root = tk.Tk()
        self.root.title("千牛话术助手")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self._make_no_activate_window()
        self.root.configure(bg=self.COLOR_BG)
        self.root.geometry(f"{self.PANEL_WIDTH}x{self.DEFAULT_HEIGHT}+120+120")
        self.root.minsize(self.PANEL_WIDTH, 320)

        self._build_ui()
        self._bind_keys()
        self.root.after(100, self._apply_click_through_focus_fix)
        self._initial_position()
        self._track_loop()

    def _build_ui(self):
        self.outer = tk.Frame(self.root, bg=self.COLOR_BG, bd=0)
        self.outer.pack(fill=tk.BOTH, expand=True)

        self.shell = tk.Frame(
            self.outer,
            bg=self.COLOR_CARD,
            bd=0,
            highlightthickness=1,
            highlightbackground=self.COLOR_BORDER,
            highlightcolor=self.COLOR_BORDER
        )
        self.shell.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        self.title_bar = tk.Frame(self.shell, bg=self.COLOR_TITLE, height=46)
        self.title_bar.pack(fill=tk.X)
        self.title_bar.pack_propagate(False)
        self.title_bar.bind("<ButtonPress-1>", self._start_drag)
        self.title_bar.bind("<B1-Motion>", self._on_drag)
        self.title_bar.bind("<Double-Button-1>", self._toggle_auto_track)

        brand = tk.Frame(self.title_bar, bg=self.COLOR_TITLE)
        brand.pack(side=tk.LEFT, fill=tk.Y, padx=(12, 4))
        brand.bind("<ButtonPress-1>", self._start_drag)
        brand.bind("<B1-Motion>", self._on_drag)
        brand.bind("<Double-Button-1>", self._toggle_auto_track)

        logo = tk.Label(
            brand,
            text="千",
            font=("Microsoft YaHei UI", 10, "bold"),
            bg=self.COLOR_PRIMARY,
            fg="white",
            width=2,
            height=1
        )
        logo.pack(side=tk.LEFT, pady=10)
        logo.bind("<ButtonPress-1>", self._start_drag)
        logo.bind("<B1-Motion>", self._on_drag)
        logo.bind("<Double-Button-1>", self._toggle_auto_track)

        title_wrap = tk.Frame(brand, bg=self.COLOR_TITLE)
        title_wrap.pack(side=tk.LEFT, padx=(8, 0), pady=6)
        title_wrap.bind("<ButtonPress-1>", self._start_drag)
        title_wrap.bind("<B1-Motion>", self._on_drag)
        title_wrap.bind("<Double-Button-1>", self._toggle_auto_track)

        self.title_label = tk.Label(
            title_wrap,
            text="千牛话术助手",
            font=("Microsoft YaHei UI", 10, "bold"),
            bg=self.COLOR_TITLE,
            fg="white",
            anchor="w"
        )
        self.title_label.pack(anchor="w")
        self.title_label.bind("<ButtonPress-1>", self._start_drag)
        self.title_label.bind("<B1-Motion>", self._on_drag)
        self.title_label.bind("<Double-Button-1>", self._toggle_auto_track)

        subtitle = tk.Label(
            title_wrap,
            text="常用回复 · 一键上屏",
            font=("Microsoft YaHei UI", 7),
            bg=self.COLOR_TITLE,
            fg="#9ca3af",
            anchor="w"
        )
        subtitle.pack(anchor="w")
        subtitle.bind("<ButtonPress-1>", self._start_drag)
        subtitle.bind("<B1-Motion>", self._on_drag)
        subtitle.bind("<Double-Button-1>", self._toggle_auto_track)

        close_btn = self._make_title_button("×", self.root.destroy, hover_bg="#ef4444", width=3)
        close_btn.pack(side=tk.RIGHT, padx=(0, 6), pady=8)

        min_btn = self._make_title_button("—", self._minimize, hover_bg="#374151", width=3)
        min_btn.pack(side=tk.RIGHT, pady=8)

        self.track_btn = self._make_title_button("自动", self._toggle_auto_track, hover_bg="#374151", width=5)
        self.track_btn.pack(side=tk.RIGHT, padx=(0, 4), pady=8)

        body = tk.Frame(self.shell, bg=self.COLOR_BG)
        body.pack(fill=tk.BOTH, expand=True)

        self.phrases_panel = PhrasesPanel(
            body,
            self.phrases_path,
            on_phrase_click=self._on_phrase_copied
        )

        status_frame = tk.Frame(self.shell, bg="#ffffff", height=30)
        status_frame.pack(fill=tk.X)
        status_frame.pack_propagate(False)

        self.status_dot = tk.Label(
            status_frame,
            text="●",
            font=("Microsoft YaHei UI", 8),
            bg="#ffffff",
            fg=self.COLOR_MUTED
        )
        self.status_dot.pack(side=tk.LEFT, padx=(10, 4))

        self.status_label = tk.Label(
            status_frame,
            text=f"话术文件：{os.path.basename(self.phrases_path)}",
            font=("Microsoft YaHei UI", 8),
            bg="#ffffff",
            fg=self.COLOR_MUTED,
            anchor="w"
        )
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

    def _make_title_button(self, text, command, hover_bg, width=3):
        btn = tk.Button(
            self.title_bar,
            text=text,
            font=("Microsoft YaHei UI", 9, "bold"),
            bg=self.COLOR_TITLE,
            fg="#f9fafb",
            activebackground=hover_bg,
            activeforeground="white",
            relief=tk.FLAT,
            bd=0,
            command=command,
            width=width,
            cursor="hand2"
        )
        btn.bind("<Enter>", lambda e, b=btn: b.configure(bg=hover_bg))
        btn.bind("<Leave>", lambda e, b=btn: b.configure(bg=self.COLOR_TITLE))
        return btn

    def _bind_keys(self):
        self.root.bind("<Escape>", lambda e: self.root.destroy())
        self.root.bind("<F5>", lambda e: self.phrases_panel.reload())

    def _make_no_activate_window(self):
        """让悬浮窗点击时尽量不抢走千牛输入框焦点。"""
        try:
            self.root.update_idletasks()
            hwnd = self.root.winfo_id()
            ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            ex_style |= win32con.WS_EX_NOACTIVATE | win32con.WS_EX_TOOLWINDOW
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex_style)
        except Exception:
            pass

    def _apply_click_through_focus_fix(self):
        """拦截 WM_MOUSEACTIVATE，防止 Tk 子控件被点击时激活整个工具窗口。"""
        try:
            hwnd = self.root.winfo_id()
            self._make_no_activate_window()
            self._wnd_proc_ref = self._wnd_proc
            self._old_wnd_proc = win32gui.SetWindowLong(hwnd, win32con.GWL_WNDPROC, self._wnd_proc_ref)
        except Exception:
            pass

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg == win32con.WM_MOUSEACTIVATE:
            return 3
        if self._old_wnd_proc:
            return win32gui.CallWindowProc(self._old_wnd_proc, hwnd, msg, wparam, lparam)
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def _remember_active_chat_window(self):
        """记录最近仍处于前台的千牛聊天窗口。"""
        try:
            hwnd = win32gui.GetForegroundWindow()
            if self.injector.is_qianniu_chat_window(hwnd):
                self._last_chat_hwnd = hwnd
        except Exception:
            pass

    def _start_drag(self, event):
        self._drag_start_x = event.x_root - self.root.winfo_x()
        self._drag_start_y = event.y_root - self.root.winfo_y()
        self._auto_track = False
        self._update_track_button()

    def _on_drag(self, event):
        x = event.x_root - self._drag_start_x
        y = event.y_root - self._drag_start_y
        self.root.geometry(f"+{x}+{y}")

    def _toggle_auto_track(self, event=None):
        self._auto_track = not self._auto_track
        self._update_track_button()
        if self._auto_track:
            self._initial_position()

    def _update_track_button(self):
        if hasattr(self, "track_btn"):
            self.track_btn.config(text="自动" if self._auto_track else "手动")

    def _minimize(self):
        """隐藏主界面，显示可拖动圆形图标。"""
        self.root.withdraw()
        self._show_icon_window()

    def _show_icon_window(self):
        if self.icon_window and self.icon_window.winfo_exists():
            self.icon_window.deiconify()
            return

        self.icon_window = tk.Toplevel(self.root)
        self.icon_window.overrideredirect(True)
        self.icon_window.attributes("-topmost", True)
        self.icon_window.configure(bg=self.TRANSPARENT_COLOR)
        try:
            self.icon_window.attributes("-transparentcolor", self.TRANSPARENT_COLOR)
        except Exception:
            pass

        x, y = self._get_icon_position()
        self.icon_window.geometry(f"{self.ICON_SIZE}x{self.ICON_SIZE}+{x}+{y}")

        self.icon_canvas = tk.Canvas(
            self.icon_window,
            width=self.ICON_SIZE,
            height=self.ICON_SIZE,
            bg=self.TRANSPARENT_COLOR,
            highlightthickness=0,
            bd=0,
            cursor="hand2"
        )
        self.icon_canvas.pack(fill=tk.BOTH, expand=True)
        self._draw_icon(normal=True)

        for widget in (self.icon_window, self.icon_canvas):
            widget.bind("<ButtonPress-1>", self._start_icon_drag)
            widget.bind("<B1-Motion>", self._on_icon_drag)
            widget.bind("<ButtonRelease-1>", self._on_icon_release)
            widget.bind("<Enter>", lambda e: self._draw_icon(normal=False))
            widget.bind("<Leave>", lambda e: self._draw_icon(normal=True))

    def _draw_icon(self, normal=True):
        if not self.icon_canvas:
            return
        self.icon_canvas.delete("all")
        fill = self.COLOR_PRIMARY if normal else self.COLOR_PRIMARY_DARK
        self.icon_canvas.create_oval(4, 6, self.ICON_SIZE - 2, self.ICON_SIZE, fill="#a5b0f7", outline="")
        self.icon_canvas.create_oval(3, 3, self.ICON_SIZE - 5, self.ICON_SIZE - 5, fill=fill, outline="#ffffff", width=2)
        self.icon_canvas.create_text(self.ICON_SIZE // 2 - 1, 21, text="千", fill="white", font=("Microsoft YaHei UI", 15, "bold"))
        self.icon_canvas.create_text(self.ICON_SIZE // 2 - 1, 40, text="话术", fill="white", font=("Microsoft YaHei UI", 8, "bold"))

    def _get_icon_position(self):
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        try:
            x = self.root.winfo_x() + self.PANEL_WIDTH - self.ICON_SIZE - 10
            y = self.root.winfo_y() + 52
        except Exception:
            x = screen_w - self.ICON_SIZE - 20
            y = screen_h // 2
        x = max(0, min(x, screen_w - self.ICON_SIZE))
        y = max(0, min(y, screen_h - self.ICON_SIZE))
        return x, y

    def _start_icon_drag(self, event):
        self._icon_drag_start_x = event.x_root - self.icon_window.winfo_x()
        self._icon_drag_start_y = event.y_root - self.icon_window.winfo_y()
        self._icon_dragged = False

    def _on_icon_drag(self, event):
        x = event.x_root - self._icon_drag_start_x
        y = event.y_root - self._icon_drag_start_y
        self.icon_window.geometry(f"+{x}+{y}")
        self._icon_dragged = True

    def _on_icon_release(self, event):
        if not self._icon_dragged:
            self._restore_from_icon()
        self._icon_dragged = False

    def _restore_from_icon(self):
        if self.icon_window and self.icon_window.winfo_exists():
            self.icon_window.withdraw()
        self.root.deiconify()
        self.root.lift()
        self._auto_track = True
        self._update_track_button()
        self._initial_position()

    def _set_status(self, text, color=None):
        color = color or self.COLOR_MUTED
        self.status_label.config(text=text, fg=color)
        self.status_dot.config(fg=color)

    def _initial_position(self):
        pos = self.tracker.get_floating_position(self.PANEL_WIDTH)
        if pos:
            x, y, w, h = pos
            self.root.geometry(f"{w}x{h}+{x}+{y}")
            self._set_status(f"已吸附千牛 · 话术文件：{os.path.basename(self.phrases_path)}", self.COLOR_SUCCESS)
        else:
            self._set_status("未找到千牛，可手动拖动窗口 · 双击标题栏切换吸附", self.COLOR_WARN)

    def _track_loop(self):
        self._remember_active_chat_window()
        if self._auto_track and self.root.state() != "withdrawn":
            pos = self.tracker.get_floating_position(self.PANEL_WIDTH)
            if pos and not self.tracker.is_window_minimized():
                x, y, w, h = pos
                self.root.geometry(f"{w}x{h}+{x}+{y}")
                self._set_status("已吸附千牛 · 点击话术自动上屏", self.COLOR_SUCCESS)
            elif not pos:
                self._set_status("未找到千牛，可手动拖动窗口", self.COLOR_WARN)
            self.tracker.refresh()
        self.root.after(self.TRACK_INTERVAL, self._track_loop)

    def _on_phrase_copied(self, content):
        preview = content.replace("\n", " ")[:24]
        self._set_status(f"正在上屏：{preview}", self.COLOR_PRIMARY)
        self.root.update_idletasks()

        ok = self.injector.inject_to_last_or_chat(content, self._last_chat_hwnd)
        if ok:
            self._set_status(f"已上屏：{preview}", self.COLOR_SUCCESS)
        else:
            self._set_status("未找到千牛聊天窗口，已复制到剪贴板", self.COLOR_WARN)

        self.root.after(1800, lambda: self._set_status("点击话术自动填充到千牛输入框", self.COLOR_MUTED))

    def run(self):
        self.root.mainloop()


def main():
    app = FloatingWindow()
    app.run()


if __name__ == "__main__":
    main()
