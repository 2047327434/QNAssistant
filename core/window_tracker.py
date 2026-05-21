"""千牛窗口追踪模块 - 定位/跟随/大小监听"""
import win32gui
import win32con
import ctypes
import time


class WindowTracker:
    """追踪千牛窗口位置，提供悬浮窗吸附坐标"""

    # 千牛窗口特征
    RECEPTION_TITLE = "千牛接待台"  # 接待台主窗口
    CHAT_KEYWORD = "-千牛工作台"    # 聊天窗口标题后缀
    PROCESS_NAME = "AliWorkbench.exe"

    def __init__(self):
        self._reception_hwnd = None
        self._chat_hwnd = None
        self._last_rect = None

    def find_reception_window(self):
        """查找千牛接待台窗口"""
        self._reception_hwnd = win32gui.FindWindow(
            "Qt5152QWindowIcon", self.RECEPTION_TITLE
        )
        return self._reception_hwnd

    def find_chat_window(self):
        """查找当前活跃的千牛聊天窗口（店铺:客服-千牛工作台）"""
        result = None

        def callback(hwnd, extra):
            title = win32gui.GetWindowText(hwnd)
            class_name = win32gui.GetClassName(hwnd)
            # 聊天窗口特征：标题含 ":" 和 "-千牛工作台"，类名 Qt5152QWindowIcon
            if class_name == "Qt5152QWindowIcon" and ":" in title and self.CHAT_KEYWORD in title:
                if win32gui.IsWindowVisible(hwnd):
                    rect = win32gui.GetWindowRect(hwnd)
                    # 优先选择较大的可见窗口（主聊天窗口）
                    w = rect[2] - rect[0]
                    h = rect[3] - rect[1]
                    if w > 300 and h > 300:
                        extra.append((hwnd, title, rect, w * h))

        results = []
        win32gui.EnumWindows(callback, results)

        if results:
            # 按面积排序，选最大的（主聊天窗口）
            results.sort(key=lambda x: x[3], reverse=True)
            self._chat_hwnd = results[0][0]
            return self._chat_hwnd

        return None

    def get_reception_rect(self):
        """获取接待台窗口位置"""
        if not self._reception_hwnd or not win32gui.IsWindow(self._reception_hwnd):
            self.find_reception_window()
        if self._reception_hwnd:
            return win32gui.GetWindowRect(self._reception_hwnd)
        return None

    def get_chat_rect(self):
        """获取聊天窗口位置"""
        if not self._chat_hwnd or not win32gui.IsWindow(self._chat_hwnd):
            self.find_chat_window()
        if self._chat_hwnd:
            return win32gui.GetWindowRect(self._chat_hwnd)
        return None

    def get_floating_position(self, panel_width=280):
        """计算悬浮窗应该吸附的位置（千牛接待台右侧）"""
        rect = self.get_reception_rect()
        if rect:
            left, top, right, bottom = rect
            screen_w = ctypes.windll.user32.GetSystemMetrics(0)
            screen_h = ctypes.windll.user32.GetSystemMetrics(1)

            # 优先吸附在接待台右侧；如果超出屏幕，则吸附在接待台内部右边缘
            x = right
            if x + panel_width > screen_w:
                x = max(left, screen_w - panel_width)

            # 底部对齐千牛窗口，高度至少 400
            target_bottom = min(bottom, screen_h)
            h = min(bottom - top, screen_h)
            h = max(h, 400)
            y = max(0, target_bottom - h)

            return (x, y, panel_width, h)
        return None

    def get_chat_input_area(self):
        """获取千牛聊天窗口输入框的大致区域坐标（底部15%区域中心）"""
        rect = self.get_chat_rect()
        if rect:
            left, top, right, bottom = rect
            # 输入框在窗口底部约 15% 区域
            input_top = bottom - int((bottom - top) * 0.15)
            input_bottom = bottom - int((bottom - top) * 0.02)  # 留点边距
            center_x = (left + right) // 2
            center_y = (input_top + input_bottom) // 2
            return (center_x, center_y)
        return None

    def get_chat_display_area(self):
        """获取聊天记录显示区域的大致坐标（中间偏右60%区域中心）"""
        rect = self.get_chat_rect()
        if rect:
            left, top, right, bottom = rect
            # 聊天记录区域：右侧60%，从顶部20%到底部80%
            area_left = left + int((right - left) * 0.4)
            area_right = right
            area_top = top + int((bottom - top) * 0.2)
            area_bottom = bottom - int((bottom - top) * 0.2)
            center_x = (area_left + area_right) // 2
            center_y = (area_top + area_bottom) // 2
            return (center_x, center_y)
        return None

    def is_window_minimized(self):
        """检查千牛窗口是否最小化"""
        if self._reception_hwnd:
            style = win32gui.GetWindowLong(self._reception_hwnd, win32con.GWL_STYLE)
            return bool(style & win32con.WS_MINIMIZE)
        return True

    def bring_to_front(self, hwnd=None):
        """将千牛窗口置前台"""
        target = hwnd or self._reception_hwnd
        if target and win32gui.IsWindow(target):
            # 如果最小化，先恢复
            if self.is_window_minimized():
                win32gui.ShowWindow(target, win32con.SW_RESTORE)
            # 置前台
            try:
                win32gui.SetForegroundWindow(target)
                time.sleep(0.05)
            except Exception:
                # SetForegroundWindow 可能受限，用 AttachThreadInput 绕过
                foreground = win32gui.GetForegroundWindow()
                foreground_tid = win32gui.GetWindowThreadProcessId(foreground)[0]
                target_tid = win32gui.GetWindowThreadProcessId(target)[0]
                if foreground_tid != target_tid:
                    ctypes.windll.user32.AttachThreadInput(foreground_tid, target_tid, True)
                    win32gui.SetForegroundWindow(target)
                    ctypes.windll.user32.AttachThreadInput(foreground_tid, target_tid, False)

    def get_chat_title(self):
        """获取当前聊天窗口标题（含店铺名和客服名）"""
        if self._chat_hwnd and win32gui.IsWindow(self._chat_hwnd):
            return win32gui.GetWindowText(self._chat_hwnd)
        return None

    def refresh(self):
        """刷新窗口引用（千牛可能切换了聊天窗口）"""
        self._chat_hwnd = None
        self.find_chat_window()
        if not self._reception_hwnd or not win32gui.IsWindow(self._reception_hwnd):
            self._reception_hwnd = None
            self.find_reception_window()