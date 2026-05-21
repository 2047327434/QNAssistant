"""文本注入模块 - 将文本填充到千牛输入框"""
import time
import ctypes
from ctypes import wintypes
import win32gui
import win32con

from .clipboard_ops import ClipboardOps
from .window_tracker import WindowTracker

user32 = ctypes.windll.user32

# 虚拟键码
VK_CONTROL = 0x11
VK_V = 0x56
VK_TAB = 0x09
VK_A = 0x41
VK_DELETE = 0x2E

# SendInput 常量
INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_ABSOLUTE = 0x8000


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
    ]


class INPUT(ctypes.Structure):
    class _UNION(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT)]
    _anonymous_ = ("_union",)
    _fields_ = [("type", wintypes.DWORD), ("_union", _UNION)]


class TextInjector:
    """将文本注入千牛聊天输入框。

    策略: 置前 → 用 ClientRect 精算输入框坐标 → SendInput 点击 → Ctrl+V
    Qt 5 alien widget 无独立 HWND, 必须通过屏幕坐标点击来聚焦输入框。
    """

    def __init__(self, tracker: WindowTracker):
        self.tracker = tracker
        self.clipboard = ClipboardOps()

    # ── 对外入口 ──────────────────────────────────────────

    def inject_to_last_or_chat(self, text, last_chat_hwnd=None):
        """主上屏路径。

        1. 当前前台=千牛 → 直接 Ctrl+V
        2. 缓存 hwnd → 置前 + 点击输入框 + Ctrl+V
        3. 兜底查找 → 置前 + 点击输入框 + Ctrl+V
        """
        if not text:
            return False

        self.clipboard.write(text)
        time.sleep(0.04)

        foreground = win32gui.GetForegroundWindow()
        if self.is_qianniu_chat_window(foreground):
            self._ctrl_v()
            return True

        target = last_chat_hwnd if (last_chat_hwnd and win32gui.IsWindow(last_chat_hwnd)) else None
        if not target:
            target = self.tracker.find_chat_window()
        if not target:
            return False

        self._bring_click_paste(target)
        return True

    def inject_to_active_or_chat(self, text):
        if not text:
            return False
        self.clipboard.write(text)
        time.sleep(0.04)

        foreground = win32gui.GetForegroundWindow()
        if self.is_qianniu_chat_window(foreground):
            self._ctrl_v()
            return True

        target = self.tracker.find_chat_window()
        if not target:
            return False
        self._bring_click_paste(target)
        return True

    def inject_text(self, text, click_input=True):
        if not text:
            return False
        target = self.tracker.find_chat_window()
        if not target:
            return False
        self.clipboard.save()
        self.clipboard.write(text)
        self._bring_click_paste(target)
        time.sleep(0.1)
        self.clipboard.restore()
        return True

    def inject_text_with_clear(self, text, click_input=True):
        if not text:
            return False
        target = self.tracker.find_chat_window()
        if not target:
            return False
        self.clipboard.save()
        self.clipboard.write(text)
        self._bring_click_paste(target, clear_first=True)
        time.sleep(0.1)
        self.clipboard.restore()
        return True

    # ── 核心流程 ──────────────────────────────────────────

    def _bring_click_paste(self, hwnd, clear_first=False):
        """置前 → 精算坐标点击输入框 → Ctrl+V。"""
        self.tracker.bring_to_front(hwnd)
        time.sleep(0.2)  # 等千牛完全显示

        # 点击输入框区域
        self._click_input_client(hwnd)
        time.sleep(0.08)

        if clear_first:
            self._ctrl_a()
            time.sleep(0.05)
            self._press_delete()
            time.sleep(0.05)

        self._ctrl_v()

    # ── 点击 ──────────────────────────────────────────────

    def _click_input_client(self, hwnd):
        """用 ClientRect + ClientToScreen 精算输入框坐标，SendInput 点击。"""
        try:
            cr = win32gui.GetClientRect(hwnd)
            cw = cr[2] - cr[0]   # 客户区宽度
            ch = cr[3] - cr[1]   # 客户区高度
        except Exception:
            return

        if cw < 100 or ch < 100:
            return

        # 输入框位置：底部 10% 区域，水平居中
        cx = cw // 2
        cy = ch - int(ch * 0.05)  # 距离底部 5%，确保在输入框内

        pt = win32gui.ClientToScreen(hwnd, (cx, cy))
        self._send_click(pt[0], pt[1])

    def _send_click(self, x, y):
        """SendInput(MOUSEINPUT) 点击屏幕坐标。比 mouse_event 更可靠。"""
        sw = user32.GetSystemMetrics(0)
        sh = user32.GetSystemMetrics(1)

        # 归一化到 0-65535
        abs_x = int(x * 65535 / sw) if sw > 0 else 0
        abs_y = int(y * 65535 / sh) if sh > 0 else 0

        # Move
        inp = INPUT()
        inp.type = INPUT_MOUSE
        inp.mi.dx = abs_x
        inp.mi.dy = abs_y
        inp.mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
        time.sleep(0.03)

        # Left down
        inp.mi.dwFlags = MOUSEEVENTF_LEFTDOWN
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
        time.sleep(0.03)

        # Left up
        inp.mi.dwFlags = MOUSEEVENTF_LEFTUP
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
        time.sleep(0.03)

    # ── 键盘 ──────────────────────────────────────────────

    def _ctrl_v(self):
        self._key_combo(VK_CONTROL, VK_V)

    def _ctrl_a(self):
        self._key_combo(VK_CONTROL, VK_A)

    def _key_combo(self, mod, key):
        user32.keybd_event(mod, 0, 0, 0)
        time.sleep(0.03)
        user32.keybd_event(key, 0, 0, 0)
        time.sleep(0.03)
        user32.keybd_event(key, 0, 2, 0)
        time.sleep(0.03)
        user32.keybd_event(mod, 0, 2, 0)
        time.sleep(0.05)

    def _press_delete(self):
        user32.keybd_event(VK_DELETE, 0, 0, 0)
        time.sleep(0.03)
        user32.keybd_event(VK_DELETE, 0, 2, 0)
        time.sleep(0.03)

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