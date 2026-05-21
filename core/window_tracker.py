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
        """计算悬浮窗应该吸附的位置（强制贴在千牛接待台右侧）。"""
        rect = self.get_reception_rect()
        if rect:
            left, top, right, bottom = rect

            # 吸附模式下始终贴在千牛右侧，允许超出屏幕范围，不做横向裁剪
            x = right

            # 纵向仍按千牛窗口高度对齐；允许超出屏幕，不做屏幕裁剪
            h = max(bottom - top, 320)
            if h > bottom - top:
                # 工具比千牛高时退化为顶部对齐，但不再按屏幕高度裁剪
                y = top
            else:
                y = bottom - h

            return (x, y, panel_width, h)
        return None

    def get_chat_input_area(self):
        """获取千牛聊天窗口输入框的大致区域坐标（底部15%区域中心）"""
        rect = self.get_chat_rect()
        if rect:
            left, top, right, bottom = rect
            input_top = bottom - int((bottom - top) * 0.15)
            input_bottom = bottom - int((bottom - top) * 0.02)
            center_x = (left + right) // 2
            center_y = (input_top + input_bottom) // 2
            return (center_x, center_y)
        return None

    def find_chat_input_hwnd(self):
        """枚举聊天窗口子控件，用位置+尺寸评分找出输入框 HWND。

        Qt 5.15 子控件类名通常也是 Qt5152QWindowIcon，但位置固定在窗口底部、
        宽度几乎撑满、高度 20-80px 且无子窗口（叶子节点）。

        Returns:
            (hwnd, rect) 或 (None, None)
        """
        if not self._chat_hwnd or not win32gui.IsWindow(self._chat_hwnd):
            self.find_chat_window()
        if not self._chat_hwnd:
            return None, None

        parent = self._chat_hwnd
        parent_rect = win32gui.GetWindowRect(parent)
        pw = parent_rect[2] - parent_rect[0]
        ph = parent_rect[3] - parent_rect[1]

        candidates = []

        def enum_child(hwnd, _):
            rect = win32gui.GetWindowRect(hwnd)
            x, y, r, b = rect
            w = r - x
            h = b - y
            # 相对于父窗口的 top
            rel_top = y - parent_rect[1]
            rel_bottom = b - parent_rect[1]

            # 过滤：必须在窗口下半区（50%以下）
            if rel_top < ph * 0.45:
                return True
            # 高度合理：12-150px
            if h < 12 or h > 150:
                return True
            # 宽度不能太窄（至少父窗口宽度的 30%）
            if w < pw * 0.3:
                return True

            # 计算得分：越靠底部 + 越宽 + 无子窗口 → 越高
            pos_score = rel_top / ph                           # 0~1，越接近底部越高
            width_score = min(w / pw, 1.0)                     # 0~1，越宽越高
            has_children = 0
            try:
                has_children = 1 if win32gui.FindWindowEx(hwnd, 0, None, None) else 0
            except Exception:
                pass
            leaf_bonus = 1.0 if not has_children else 0.3      # 叶子节点加分
            score = pos_score * 0.5 + width_score * 0.3 + leaf_bonus * 0.2

            candidates.append((hwnd, rect, score))
            return True

        win32gui.EnumChildWindows(parent, enum_child, None)

        if candidates:
            candidates.sort(key=lambda x: x[2], reverse=True)
            best = candidates[0]
            return best[0], best[1]

        # 没找到子控件，退回底部15%估算
        return None, None

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