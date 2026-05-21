"""聊天内容抓取模块 - 从千牛CEF窗口抓取客户聊天记录"""
import time
import win32gui
import win32con
import ctypes

from .clipboard_ops import ClipboardOps
from .keyboard_ops import ctrl_a, ctrl_c, ctrl_v, press_escape
from .window_tracker import WindowTracker


class ChatCapture:
    """从千牛聊天窗口抓取客户文字内容"""

    def __init__(self, tracker: WindowTracker):
        self.tracker = tracker
        self.clipboard = ClipboardOps()

    def capture_chat_text(self):
        """
        抓取当前千牛聊天窗口中的聊天记录文本
        
        流程:
        1. 定位千牛聊天窗口
        2. 置千牛前台
        3. 点击聊天记录区域使其获得焦点
        4. Ctrl+A 全选 → Ctrl+C 复制
        5. 读取剪贴板内容
        6. Esc 取消选择
        7. 还原剪贴板
        
        Returns:
            dict: {
                "success": bool,
                "raw_text": str,      # 原始抓取文本
                "customer_msg": str,  # 提取的客户最新发言
                "error": str          # 错误信息（失败时）
            }
        """
        result = {"success": False, "raw_text": "", "customer_msg": "", "error": ""}

        # 1. 定位聊天窗口
        chat_hwnd = self.tracker.find_chat_window()
        if not chat_hwnd:
            result["error"] = "未找到千牛聊天窗口"
            return result

        # 2. 置千牛前台
        self.tracker.bring_to_front(chat_hwnd)
        time.sleep(0.1)

        # 3. 保存剪贴板内容
        self.clipboard.save()

        # 4. 点击聊天记录区域使其获得焦点
        chat_area = self.tracker.get_chat_display_area()
        if not chat_area:
            result["error"] = "无法定位聊天显示区域"
            self.clipboard.restore()
            return result

        # 模拟鼠标左键点击聊天记录区域中心
        self._click_position(chat_area[0], chat_area[1])
        time.sleep(0.1)

        # 5. Ctrl+A 全选聊天内容
        ctrl_a(delay=0.08)
        time.sleep(0.05)

        # 6. Ctrl+C 复制
        ctrl_c(delay=0.08)
        time.sleep(0.1)

        # 7. 读取剪贴板
        raw_text = self.clipboard.read()

        # 8. Esc 取消选择
        press_escape(delay=0.05)

        # 9. 还原剪贴板
        self.clipboard.restore()

        # 10. 解析聊天内容
        if raw_text and len(raw_text) > 5:
            result["success"] = True
            result["raw_text"] = raw_text
            result["customer_msg"] = self._extract_customer_message(raw_text)
        else:
            result["error"] = "抓取到的内容过短或为空"

        return result

    def _click_position(self, x, y):
        """模拟鼠标左键点击指定坐标"""
        # 将坐标转换为绝对坐标（0-65535范围）
        abs_x = int(x * 65535 / ctypes.windll.user32.GetSystemMetrics(0))
        abs_y = int(y * 65535 / ctypes.windll.user32.GetSystemMetrics(1))

        # MOUSEEVENTF_ABSOLUTE = 0x8000, MOUSEEVENTF_LEFTDOWN = 0x0002, MOUSEEVENTF_LEFTUP = 0x0004
        user32 = ctypes.windll.user32
        user32.SetCursorPos(x, y)
        time.sleep(0.02)
        user32.mouse_event(0x8000 | 0x0002, abs_x, abs_y, 0, 0)  # 左键按下
        time.sleep(0.01)
        user32.mouse_event(0x8000 | 0x0004, abs_x, abs_y, 0, 0)  # 左键释放

    def _extract_customer_message(self, raw_text):
        """从原始聊天文本中提取客户最新发言
        
        千牛聊天记录通常格式：
        - 客户消息在右侧或带"客户"标记
        - 客服消息在左侧或带"我"标记
        - 消息按时间顺序排列
        
        简化策略：提取最后几行非客服发言
        """
        lines = raw_text.strip().split("\n")
        messages = []

        for line in lines:
            line = line.strip()
            if not line:
                continue
            # 排除明显的客服标记（带"我:"、"客服:"等）
            # 千牛中客服发言通常格式: "我: xxx" 或 "客服昵称: xxx"
            # 客户发言通常没有"我"标记
            if line.startswith("我:") or line.startswith("我："):
                continue
            if "客服" in line[:10]:
                continue
            messages.append(line)

        # 取最后 3 条非客服消息作为客户最近发言
        recent = messages[-3:] if len(messages) >= 3 else messages
        return "\n".join(recent)

    def capture_selected_text(self):
        """仅抓取当前选中区域的文本（如果用户已手动选中）"""
        self.clipboard.save()
        ctrl_c(delay=0.08)
        time.sleep(0.05)
        text = self.clipboard.read()
        self.clipboard.restore()
        return text