"""千牛话术助手 - 无边框悬浮窗，点击话术自动填充到千牛输入框"""
import os
import sys
import tkinter as tk

import win32con
import win32gui

from core.defaults import get_app_root, ensure_phrases_file
from core.window_tracker import WindowTracker
from core.text_inject import TextInjector
from ui.phrases_panel import PhrasesPanel


class FloatingWindow:
    """千牛话术助手悬浮窗"""

    PANEL_WIDTH = 260
    DEFAULT_HEIGHT = 620
    TRACK_INTERVAL = 250
    ICON_SIZE = 56
    TRANSPARENT_COLOR = "#ff00ff"

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
        self.root.overrideredirect(True)  # 无系统边框
        self.root.attributes("-topmost", True)
        self._make_no_activate_window()
        self.root.configure(bg="#d7dce2")
        self.root.geometry(f"{self.PANEL_WIDTH}x{self.DEFAULT_HEIGHT}+120+120")
        self.root.minsize(self.PANEL_WIDTH, 400)

        self._build_ui()
        self._bind_keys()
        self.root.after(100, self._apply_click_through_focus_fix)
        self._initial_position()
        self._track_loop()

    def _build_ui(self):
        # 外层边框
        self.outer = tk.Frame(self.root, bg="#d7dce2", bd=0)
        self.outer.pack(fill=tk.BOTH, expand=True)

        # 自定义标题栏
        self.title_bar = tk.Frame(self.outer, bg="#2f80ed", height=34)
        self.title_bar.pack(fill=tk.X, padx=1, pady=(1, 0))
        self.title_bar.pack_propagate(False)
        self.title_bar.bind("<ButtonPress-1>", self._start_drag)
        self.title_bar.bind("<B1-Motion>", self._on_drag)
        self.title_bar.bind("<Double-Button-1>", self._toggle_auto_track)

        self.title_label = tk.Label(
            self.title_bar,
            text="千牛话术助手",
            font=("Microsoft YaHei UI", 10, "bold"),
            bg="#2f80ed",
            fg="white"
        )
        self.title_label.pack(side=tk.LEFT, padx=10)
        self.title_label.bind("<ButtonPress-1>", self._start_drag)
        self.title_label.bind("<B1-Motion>", self._on_drag)
        self.title_label.bind("<Double-Button-1>", self._toggle_auto_track)

        tk.Button(
            self.title_bar,
            text="×",
            font=("Microsoft YaHei UI", 12, "bold"),
            bg="#2f80ed",
            fg="white",
            activebackground="#d9534f",
            activeforeground="white",
            relief=tk.FLAT,
            command=self.root.destroy,
            width=3
        ).pack(side=tk.RIGHT)

        tk.Button(
            self.title_bar,
            text="—",
            font=("Microsoft YaHei UI", 12, "bold"),
            bg="#2f80ed",
            fg="white",
            activebackground="#1d6fd4",
            activeforeground="white",
            relief=tk.FLAT,
            command=self._minimize,
            width=3
        ).pack(side=tk.RIGHT)

        self.track_btn = tk.Button(
            self.title_bar,
            text="吸附",
            font=("Microsoft YaHei UI", 8),
            bg="#2f80ed",
            fg="white",
            activebackground="#1d6fd4",
            activeforeground="white",
            relief=tk.FLAT,
            command=self._toggle_auto_track,
            width=5
        )
        self.track_btn.pack(side=tk.RIGHT)

        # 内容区域
        body = tk.Frame(self.outer, bg="white")
        body.pack(fill=tk.BOTH, expand=True, padx=1)

        self.phrases_panel = PhrasesPanel(
            body,
            self.phrases_path,
            on_phrase_click=self._on_phrase_copied
        )

        # 底部状态栏
        status_frame = tk.Frame(self.outer, bg="#f7f8fa", height=24)
        status_frame.pack(fill=tk.X, padx=1, pady=(0, 1))
        status_frame.pack_propagate(False)

        self.status_label = tk.Label(
            status_frame,
            text=f"话术文件：{os.path.basename(self.phrases_path)}",
            font=("Microsoft YaHei UI", 8),
            bg="#f7f8fa",
            fg="#666",
            anchor="w"
        )
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)

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
            # 某些环境下设置扩展样式可能失败，不影响程序启动
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
        # MA_NOACTIVATE = 3。允许鼠标点击消息继续传给按钮/列表，但不要激活工具窗口。
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
        self.track_btn.config(text="吸附" if self._auto_track else "手动")

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
            bd=0
        )
        self.icon_canvas.pack(fill=tk.BOTH, expand=True)
        self.icon_canvas.create_oval(3, 3, self.ICON_SIZE - 3, self.ICON_SIZE - 3, fill="#2f80ed", outline="#ffffff", width=2)
        self.icon_canvas.create_text(self.ICON_SIZE // 2, 20, text="千", fill="white", font=("Microsoft YaHei UI", 14, "bold"))
        self.icon_canvas.create_text(self.ICON_SIZE // 2, 38, text="话术", fill="white", font=("Microsoft YaHei UI", 8, "bold"))

        for widget in (self.icon_window, self.icon_canvas):
            widget.bind("<ButtonPress-1>", self._start_icon_drag)
            widget.bind("<B1-Motion>", self._on_icon_drag)
            widget.bind("<ButtonRelease-1>", self._on_icon_release)

    def _get_icon_position(self):
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        try:
            x = self.root.winfo_x() + self.PANEL_WIDTH - self.ICON_SIZE - 8
            y = self.root.winfo_y() + 44
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

    def _initial_position(self):
        pos = self.tracker.get_floating_position(self.PANEL_WIDTH)
        if pos:
            x, y, w, h = pos
            self.root.geometry(f"{w}x{h}+{x}+{y}")
            self.status_label.config(text=f"已吸附千牛 · 话术文件：{os.path.basename(self.phrases_path)}", fg="#2b8a3e")
        else:
            self.status_label.config(text="未找到千牛，可手动拖动窗口 · 双击标题栏切换吸附", fg="#cc7a00")

    def _track_loop(self):
        self._remember_active_chat_window()
        if self._auto_track:
            pos = self.tracker.get_floating_position(self.PANEL_WIDTH)
            if pos and not self.tracker.is_window_minimized():
                x, y, w, h = pos
                self.root.geometry(f"{w}x{h}+{x}+{y}")
                self.status_label.config(text=f"已吸附千牛 · 点击话术自动上屏", fg="#2b8a3e")
            elif not pos:
                self.status_label.config(text="未找到千牛，可手动拖动窗口", fg="#cc7a00")
            self.tracker.refresh()
        self.root.after(self.TRACK_INTERVAL, self._track_loop)

    def _on_phrase_copied(self, content):
        preview = content.replace("\n", " ")[:24]
        self.status_label.config(text=f"正在上屏：{preview}", fg="#2f80ed")
        self.root.update_idletasks()

        ok = self.injector.inject_to_last_or_chat(content, self._last_chat_hwnd)
        if ok:
            self.status_label.config(text=f"已上屏：{preview}", fg="#2b8a3e")
        else:
            self.status_label.config(text="未找到千牛聊天窗口，已复制到剪贴板", fg="#cc7a00")

        self.root.after(1800, lambda: self.status_label.config(text="点击话术自动填充到千牛输入框", fg="#666"))

    def run(self):
        self.root.mainloop()


def main():
    app = FloatingWindow()
    app.run()


if __name__ == "__main__":
    main()
