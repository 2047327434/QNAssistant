"""文本注入模块 - 将文本填充到千牛输入框"""
import time
import ctypes
import win32gui

from .clipboard_ops import ClipboardOps
from .keyboard_ops import ctrl_v
from .window_tracker import WindowTracker


class TextInjector:
    """将文本注入千牛聊天输入框"""

    def __init__(self, tracker: WindowTracker):
        self.tracker = tracker
        self.clipboard = ClipboardOps()

    def inject_to_active_or_chat(self, text):
        """优先不改焦点，直接向当前仍处于焦点的千牛输入框粘贴。

        配合主窗口的 WS_EX_NOACTIVATE：用户点击工具内话术时，Windows 前台窗口
        理论上仍然是千牛聊天窗口，输入框光标不会丢。此时只需要写入剪贴板并
        发送 Ctrl+V，不再点击千牛输入框，也不还原剪贴板。

        如果当前前台不是千牛聊天窗口，则退回到旧方案：找到聊天窗口、置前、
        点击输入区域后粘贴。
        """
        if not text:
            return False

        self.clipboard.write(text)
        time.sleep(0.03)

        foreground = win32gui.GetForegroundWindow()
        if self.is_qianniu_chat_window(foreground):
            ctrl_v(delay=0.05)
            return True

        # 前台不是千牛时，退回旧的主动聚焦方案；不还原剪贴板，便于失败后手动粘贴
        chat_hwnd = self.tracker.find_chat_window()
        if not chat_hwnd:
            return False

        self.tracker.bring_to_front(chat_hwnd)
        time.sleep(0.08)
        input_area = self.tracker.get_chat_input_area()
        if input_area:
            self._click_position(input_area[0], input_area[1])
            time.sleep(0.08)
        ctrl_v(delay=0.05)
        return True

    def inject_to_last_or_chat(self, text, last_chat_hwnd=None):
        """使用缓存的千牛聊天窗口上屏，解决点击工具后前台窗口变化的问题。"""
        if not text:
            return False

        self.clipboard.write(text)
        time.sleep(0.03)

        # 1. 如果当前前台仍是千牛，直接粘贴，最大限度保留原输入框焦点
        foreground = win32gui.GetForegroundWindow()
        if self.is_qianniu_chat_window(foreground):
            ctrl_v(delay=0.05)
            return True

        # 2. 如果有最近记录的千牛聊天窗口，优先恢复该窗口并粘贴
        if last_chat_hwnd and win32gui.IsWindow(last_chat_hwnd):
            self.tracker.bring_to_front(last_chat_hwnd)
            time.sleep(0.08)
            ctrl_v(delay=0.05)
            return True

        # 3. 最后退回查找窗口 + 点击输入区域方案
        return self.inject_to_active_or_chat(text)

    def is_qianniu_chat_window(self, hwnd):
        """判断窗口是否为千牛聊天窗口。"""
        if not hwnd or not win32gui.IsWindow(hwnd):
            return False
        try:
            title = win32gui.GetWindowText(hwnd)
            class_name = win32gui.GetClassName(hwnd)
        except Exception:
            return False
        return class_name == "Qt5152QWindowIcon" and ":" in title and self.tracker.CHAT_KEYWORD in title

    def _is_qianniu_chat_window(self, hwnd):
        """兼容旧调用。"""
        return self.is_qianniu_chat_window(hwnd)

    def inject_text(self, text, click_input=True):
        """
        将文本注入千牛输入框
        
        流程:
        1. 保存剪贴板
        2. 将文本写入剪贴板
        3. 置千牛前台
        4. 点击输入框区域使其获得焦点
        5. Ctrl+V 粘贴
        6. 还原剪贴板
        
        Args:
            text: 要注入的文本
            click_input: 是否先点击输入框（默认True）
            
        Returns:
            bool: 是否成功
        """
        if not text:
            return False

        # 定位聊天窗口
        chat_hwnd = self.tracker.find_chat_window()
        if not chat_hwnd:
            return False

        # 1. 保存剪贴板
        self.clipboard.save()

        # 2. 将文本写入剪贴板
        self.clipboard.write(text)

        # 3. 置千牛前台
        self.tracker.bring_to_front(chat_hwnd)
        time.sleep(0.1)

        # 4. 点击输入框区域
        if click_input:
            input_area = self.tracker.get_chat_input_area()
            if input_area:
                self._click_position(input_area[0], input_area[1])
                time.sleep(0.1)

        # 5. Ctrl+V 粘贴
        ctrl_v(delay=0.08)

        # 6. 延时后还原剪贴板
        time.sleep(0.1)
        self.clipboard.restore()

        return True

    def inject_text_with_clear(self, text, click_input=True):
        """注入文本前先清空输入框（Ctrl+A → 删除 → Ctrl+V）"""
        if not text:
            return False

        chat_hwnd = self.tracker.find_chat_window()
        if not chat_hwnd:
            return False

        # 保存剪贴板
        self.clipboard.save()

        # 将文本写入剪贴板
        self.clipboard.write(text)

        # 置千牛前台
        self.tracker.bring_to_front(chat_hwnd)
        time.sleep(0.1)

        # 点击输入框
        if click_input:
            input_area = self.tracker.get_chat_input_area()
            if input_area:
                self._click_position(input_area[0], input_area[1])
                time.sleep(0.1)

        # 清空输入框：Ctrl+A → Backspace/Delete
        from .keyboard_ops import ctrl_a
        ctrl_a(delay=0.05)
        time.sleep(0.02)
        # 发送 Delete 键
        ctypes.windll.user32.keybd_event(0x2E, 0, 0, 0)  # VK_DELETE
        time.sleep(0.02)
        ctypes.windll.user32.keybd_event(0x2E, 0, 2, 0)
        time.sleep(0.05)

        # Ctrl+V 粘贴
        ctrl_v(delay=0.08)

        # 还原剪贴板
        time.sleep(0.1)
        self.clipboard.restore()

        return True

    def _click_position(self, x, y):
        """模拟鼠标左键点击"""
        user32 = ctypes.windll.user32
        abs_x = int(x * 65535 / user32.GetSystemMetrics(0))
        abs_y = int(y * 65535 / user32.GetSystemMetrics(1))
        user32.SetCursorPos(x, y)
        time.sleep(0.02)
        user32.mouse_event(0x8000 | 0x0002, abs_x, abs_y, 0, 0)
        time.sleep(0.01)
        user32.mouse_event(0x8000 | 0x0004, abs_x, abs_y, 0, 0)