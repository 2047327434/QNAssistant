"""文本注入模块 - 将文本填充到千牛输入框。

优先链路：
1. 通过千牛聊天窗口句柄获取 UIA 根节点
2. 在控件树中查找最像消息输入框的元素
3. 优先取输入框对应的 NativeWindowHandle；若没有独立 HWND，则使用 UIA BoundingRectangle
4. 对目标输入框执行 SetFocus / 精准点击，再 Ctrl+V

降级链路：
- EnumChildWindows 查找子句柄
- ClientRect 底部估算
"""

import time
import ctypes
from ctypes import wintypes, byref, sizeof

import win32gui
import comtypes
import comtypes.client

from .clipboard_ops import ClipboardOps
from .window_tracker import WindowTracker


try:
    from comtypes.gen.UIAutomationClient import (
        CUIAutomation,
        IUIAutomation,
        TreeScope_Descendants,
        UIA_ControlTypePropertyId,
        UIA_EditControlTypeId,
        UIA_DocumentControlTypeId,
        UIA_CustomControlTypeId,
        UIA_PaneControlTypeId,
    )
except ImportError:
    comtypes.client.GetModule("UIAutomationCore.dll")
    from comtypes.gen.UIAutomationClient import (
        CUIAutomation,
        IUIAutomation,
        TreeScope_Descendants,
        UIA_ControlTypePropertyId,
        UIA_EditControlTypeId,
        UIA_DocumentControlTypeId,
        UIA_CustomControlTypeId,
        UIA_PaneControlTypeId,
    )


user32 = ctypes.windll.user32

INPUT_MOUSE = 0
_EV_MOVE = 0x0001
_EV_LEFTDOWN = 0x0002
_EV_LEFTUP = 0x0004
_EV_ABS = 0x8000

VK_CONTROL = 0x11
VK_V = 0x56
VK_A = 0x41
VK_DELETE = 0x2E


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
    class _U(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT)]

    _anonymous_ = ("_u",)
    _fields_ = [("type", wintypes.DWORD), ("_u", _U)]


class UIAHelper:
    """使用 UI Automation 从聊天窗口句柄定位输入框。"""

    INPUT_CONTROL_TYPES = {
        UIA_EditControlTypeId,
        UIA_DocumentControlTypeId,
        UIA_CustomControlTypeId,
        UIA_PaneControlTypeId,
    }

    def __init__(self):
        self._uia = None
        self._coinit_done = False

    @property
    def uia(self):
        if self._uia is None:
            if not self._coinit_done:
                comtypes.CoInitialize()
                self._coinit_done = True
            self._uia = comtypes.client.CreateObject(CUIAutomation, interface=IUIAutomation)
        return self._uia

    def find_input_target(self, chat_hwnd):
        """返回最像消息输入框的目标信息。

        Returns:
            {
                "input_hwnd": int | None,
                "rect": (left, top, right, bottom),
                "center": (x, y),
                "name": str,
                "control_type": int,
                "score": float,
                "element": IUIAutomationElement,
            } | None
        """
        if not chat_hwnd or not win32gui.IsWindow(chat_hwnd):
            return None

        try:
            root = self.uia.ElementFromHandle(chat_hwnd)
            if not root:
                return None

            condition = self.uia.CreateTrueCondition()
            results = root.FindAll(TreeScope_Descendants, condition)
            if not results or results.Length == 0:
                return None

            parent_rect = win32gui.GetWindowRect(chat_hwnd)
            pw = max(parent_rect[2] - parent_rect[0], 1)
            ph = max(parent_rect[3] - parent_rect[1], 1)

            best = None
            best_score = float("-inf")

            for i in range(results.Length):
                elem = results.GetElement(i)
                target = self._score_element(elem, parent_rect, pw, ph)
                if not target:
                    continue
                if target["score"] > best_score:
                    best = target
                    best_score = target["score"]

            return best
        except Exception:
            return None

    def _score_element(self, elem, parent_rect, pw, ph):
        try:
            rect = elem.CurrentBoundingRectangle
            left = int(rect.left)
            top = int(rect.top)
            right = int(rect.right)
            bottom = int(rect.bottom)
            control_type = int(elem.CurrentControlType)
            name = (elem.CurrentName or "").strip()
            focusable = bool(elem.CurrentIsKeyboardFocusable)
            has_focus = bool(elem.CurrentHasKeyboardFocus)
            native_hwnd = int(elem.CurrentNativeWindowHandle or 0)
        except Exception:
            return None

        width = right - left
        height = bottom - top
        if width <= 0 or height <= 0:
            return None

        rel_top = top - parent_rect[1]
        rel_bottom = bottom - parent_rect[1]
        if rel_bottom < ph * 0.45:
            return None
        if width < pw * 0.25:
            return None
        if height < 16 or height > max(220, int(ph * 0.45)):
            return None

        score = 0.0
        if control_type == UIA_EditControlTypeId:
            score += 55
        elif control_type == UIA_DocumentControlTypeId:
            score += 45
        elif control_type == UIA_CustomControlTypeId:
            score += 28
        elif control_type == UIA_PaneControlTypeId:
            score += 20
        else:
            return None

        if focusable:
            score += 22
        if has_focus:
            score += 35
        if native_hwnd and win32gui.IsWindow(native_hwnd):
            score += 18

        score += min(width / pw, 1.0) * 22
        score += min(rel_top / ph, 1.0) * 18

        if 24 <= height <= 120:
            score += 10
        if name:
            score += 4
            lowered = name.lower()
            if any(keyword in lowered for keyword in ("输入", "消息", "chat", "message", "edit", "reply")):
                score += 12

        center_x = (left + right) // 2
        center_y = (top + bottom) // 2

        return {
            "input_hwnd": native_hwnd if native_hwnd and win32gui.IsWindow(native_hwnd) else None,
            "rect": (left, top, right, bottom),
            "center": (center_x, center_y),
            "name": name,
            "control_type": control_type,
            "score": score,
            "element": elem,
        }


class TextInjector:
    """将文本注入千牛聊天输入框。"""

    def __init__(self, tracker: WindowTracker):
        self.tracker = tracker
        self.clipboard = ClipboardOps()
        self.uia = UIAHelper()

    def inject_to_last_or_chat(self, text, last_chat_hwnd=None):
        if not text:
            return False

        self.clipboard.write(text)
        time.sleep(0.04)

        foreground = win32gui.GetForegroundWindow()
        if self.is_qianniu_chat_window(foreground):
            self._ctrl_v()
            return True

        target = last_chat_hwnd if (last_chat_hwnd and win32gui.IsWindow(last_chat_hwnd)) else self.tracker.find_chat_window()
        if not target:
            return False

        return self._bring_focus_and_paste(target)

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

        return self._bring_focus_and_paste(target)

    def inject_text(self, text, click_input=True):
        if not text:
            return False
        target = self.tracker.find_chat_window()
        if not target:
            return False

        self.clipboard.save()
        self.clipboard.write(text)
        ok = self._bring_focus_and_paste(target)
        time.sleep(0.1)
        self.clipboard.restore()
        return ok

    def inject_text_with_clear(self, text, click_input=True):
        if not text:
            return False
        target = self.tracker.find_chat_window()
        if not target:
            return False

        self.clipboard.save()
        self.clipboard.write(text)
        ok = self._bring_focus_and_paste(target, clear_first=True)
        time.sleep(0.1)
        self.clipboard.restore()
        return ok

    def _bring_focus_and_paste(self, chat_hwnd, clear_first=False):
        self.tracker.bring_to_front(chat_hwnd)
        time.sleep(0.25)

        self._activate_input(chat_hwnd)
        time.sleep(0.1)

        if clear_first:
            self._ctrl_a()
            time.sleep(0.04)
            self._press_delete()
            time.sleep(0.04)

        self._ctrl_v()
        return True

    def _activate_input(self, chat_hwnd):
        """优先使用 UIA 输入框句柄/元素定位，再退回子句柄和估算坐标。"""
        target = self.uia.find_input_target(chat_hwnd)
        if target:
            element = target.get("element")
            if element is not None:
                try:
                    element.SetFocus()
                    time.sleep(0.05)
                except Exception:
                    pass

            input_hwnd = target.get("input_hwnd")
            if input_hwnd and win32gui.IsWindow(input_hwnd):
                rect = win32gui.GetWindowRect(input_hwnd)
                self._send_click((rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2)
                return

            center = target.get("center")
            if center:
                self._send_click(center[0], center[1])
                return

        child_hwnd, child_rect = self.tracker.find_chat_input_hwnd()
        if child_hwnd and child_rect:
            self._send_click((child_rect[0] + child_rect[2]) // 2, (child_rect[1] + child_rect[3]) // 2)
            return

        guess = self._guess_client(chat_hwnd)
        if guess:
            self._send_click(guess[0], guess[1])

    def _guess_client(self, hwnd):
        try:
            left, top, right, bottom = win32gui.GetClientRect(hwnd)
            width = right - left
            height = bottom - top
            if width < 100 or height < 100:
                return None
            return win32gui.ClientToScreen(hwnd, (width // 2, height - max(18, int(height * 0.08))))
        except Exception:
            return None

    def _send_click(self, x, y):
        screen_w = user32.GetSystemMetrics(0)
        screen_h = user32.GetSystemMetrics(1)
        if screen_w <= 0 or screen_h <= 0:
            return

        abs_x = int(x * 65535 / screen_w)
        abs_y = int(y * 65535 / screen_h)

        inp = INPUT()
        inp.type = INPUT_MOUSE
        inp.mi.dx = abs_x
        inp.mi.dy = abs_y
        inp.mi.mouseData = 0
        inp.mi.time = 0
        inp.mi.dwExtraInfo = None

        inp.mi.dwFlags = _EV_MOVE | _EV_ABS
        user32.SendInput(1, byref(inp), sizeof(INPUT))
        time.sleep(0.03)

        inp.mi.dwFlags = _EV_LEFTDOWN
        user32.SendInput(1, byref(inp), sizeof(INPUT))
        time.sleep(0.03)

        inp.mi.dwFlags = _EV_LEFTUP
        user32.SendInput(1, byref(inp), sizeof(INPUT))
        time.sleep(0.03)

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

    def is_qianniu_chat_window(self, hwnd):
        if not hwnd or not win32gui.IsWindow(hwnd):
            return False
        try:
            title = win32gui.GetWindowText(hwnd)
            class_name = win32gui.GetClassName(hwnd)
        except Exception:
            return False
        return class_name == "Qt5152QWindowIcon" and ":" in title and self.tracker.CHAT_KEYWORD in title
