"""文本注入模块 - 将文本填充到千牛输入框"""
import time
import ctypes
import win32gui
import win32con

from .clipboard_ops import ClipboardOps
from .window_tracker import WindowTracker

user32 = ctypes.windll.user32
VK_CONTROL = 0x11
VK_V = 0x56
VK_TAB = 0x09


class TextInjector:
    """将文本注入千牛聊天输入框。

    核心策略：不点击（Qt 5 alien widgets 无独立 HWND，坐标猜不准反会失焦），
    只做窗口置前 + Ctrl+V。聊天应用激活后输入框默认拥有焦点。
    """

    def __init__(self, tracker: WindowTracker):
        self.tracker = tracker
        self.clipboard = ClipboardOps()

    # ── 对外入口 ──────────────────────────────────────────

    def inject_to_last_or_chat(self, text, last_chat_hwnd=None):
        """主上屏路径（悬浮窗点击话术时调用）。

        链路：
        1. 当前前台仍是千牛 → 直接 Ctrl+V（最优，焦点不丢）
        2. 有缓存聊天窗口 hwnd → 置前 + 粘贴
        3. 兜底：查找聊天窗口 → 置前 + 粘贴
        """
        if not text:
            return False

        self.clipboard.write(text)
        time.sleep(0.04)

        # 1. 前台仍是千牛 → 直接粘贴
        foreground = win32gui.GetForegroundWindow()
        if self.is_qianniu_chat_window(foreground):
            self._ctrl_v()
            return True

        # 2. 缓存窗口
        target = last_chat_hwnd if (last_chat_hwnd and win32gui.IsWindow(last_chat_hwnd)) else None
        # 3. 兜底查找
        if not target:
            target = self.tracker.find_chat_window()

        if not target:
            return False

        self._bring_and_paste(target)
        return True

    def inject_to_active_or_chat(self, text):
        """旧兼容入口，逻辑同上。"""
        if not text:
            return False

        self.clipboard.write(text)
        time.sleep(0.04)

        foreground = win32gui.GetForegroundWindow()
        if self.is_qianniu_chat_window(foreground):
            self._ctrl_v()
            return True

        chat_hwnd = self.tracker.find_chat_window()
        if not chat_hwnd:
            return False

        self._bring_and_paste(chat_hwnd)
        return True

    def inject_text(self, text, click_input=True):
        """旧兼容入口。"""
        if not text:
            return False

        chat_hwnd = self.tracker.find_chat_window()
        if not chat_hwnd:
            return False

        self.clipboard.save()
        self.clipboard.write(text)
        self._bring_and_paste(chat_hwnd)
        time.sleep(0.1)
        self.clipboard.restore()
        return True

    def inject_text_with_clear(self, text, click_input=True):
        """注入前清空输入框（Ctrl+A → Delete → Ctrl+V）。"""
        if not text:
            return False

        chat_hwnd = self.tracker.find_chat_window()
        if not chat_hwnd:
            return False

        self.clipboard.save()
        self.clipboard.write(text)
        self._bring_and_paste(chat_hwnd, clear_first=True)
        time.sleep(0.1)
        self.clipboard.restore()
        return True

    # ── 内部工具 ──────────────────────────────────────────

    def _bring_and_paste(self, hwnd, clear_first=False):
        """将窗口置前，有必要时 Tab 导航到输入框，再 Ctrl+V。"""
        self.tracker.bring_to_front(hwnd)
        time.sleep(0.15)

        if clear_first:
            self._ctrl_a()
            time.sleep(0.05)
            self._press_delete()

        # 试一把直接粘贴；如果不成，Tab 后再试
        self._ctrl_v()

    def _ctrl_v(self):
        """发送 Ctrl+V（keybd_event 方式）。"""
        user32.keybd_event(VK_CONTROL, 0, 0, 0)
        time.sleep(0.03)
        user32.keybd_event(VK_V, 0, 0, 0)
        time.sleep(0.03)
        user32.keybd_event(VK_V, 0, 2, 0)
        time.sleep(0.03)
        user32.keybd_event(VK_CONTROL, 0, 2, 0)
        time.sleep(0.05)

    def _ctrl_a(self):
        user32.keybd_event(VK_CONTROL, 0, 0, 0)
        time.sleep(0.03)
        user32.keybd_event(0x41, 0, 0, 0)
        time.sleep(0.03)
        user32.keybd_event(0x41, 0, 2, 0)
        time.sleep(0.03)
        user32.keybd_event(VK_CONTROL, 0, 2, 0)
        time.sleep(0.05)

    def _press_delete(self):
        user32.keybd_event(0x2E, 0, 0, 0)
        time.sleep(0.03)
        user32.keybd_event(0x2E, 0, 2, 0)
        time.sleep(0.03)

    def _press_tab(self):
        user32.keybd_event(VK_TAB, 0, 0, 0)
        time.sleep(0.03)
        user32.keybd_event(VK_TAB, 0, 2, 0)
        time.sleep(0.03)

    # ── 保留的点击辅助（降级方案，不再在主路径中使用） ──

    def _click_input_box(self):
        """降级方案：枚举子窗口找输入框或估算坐标点击。"""
        input_hwnd, input_rect = self.tracker.find_chat_input_hwnd()
        if input_hwnd and input_rect:
            cx = (input_rect[0] + input_rect[2]) // 2
            cy = (input_rect[1] + input_rect[3]) // 2
            self._click_position(cx, cy)
            time.sleep(0.05)
            return
        input_area = self.tracker.get_chat_input_area()
        if input_area:
            self._click_position(input_area[0], input_area[1])
            time.sleep(0.05)

    def _click_position(self, x, y):
        """模拟鼠标左键点击（全局坐标）。"""
        abs_x = int(x * 65535 / user32.GetSystemMetrics(0))
        abs_y = int(y * 65535 / user32.GetSystemMetrics(1))
        user32.SetCursorPos(x, y)
        time.sleep(0.02)
        user32.mouse_event(0x8000 | 0x0002, abs_x, abs_y, 0, 0)
        time.sleep(0.01)
        user32.mouse_event(0x8000 | 0x0004, abs_x, abs_y, 0, 0)

    # ── 窗口判断 ──────────────────────────────────────────

    def is_qianniu_chat_window(self, hwnd):
        if not hwnd or not win32gui.IsWindow(hwnd):
            return False
        try:
            title = win32gui.GetWindowText(hwnd)
            class_name = win32gui.GetClassName(hwnd)
        except Exception:
            return False
        return class_name == "Qt5152QWindowIcon" and ":" in title and self.tracker.CHAT_KEYWORD in title

    def _is_qianniu_chat_window(self, hwnd):
        return self.is_qianniu_chat_window(hwnd)