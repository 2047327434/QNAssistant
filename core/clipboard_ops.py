"""剪贴板操作模块 - 写入/读取/还原"""
import ctypes
import time


class ClipboardOps:
    """安全的剪贴板操作，支持保存和还原"""

    def __init__(self):
        self._saved_content = None

    def save(self):
        """保存当前剪贴板内容"""
        self._saved_content = self.read()

    def restore(self):
        """还原之前保存的剪贴板内容"""
        if self._saved_content is not None:
            self.write(self._saved_content)
            self._saved_content = None

    def read(self):
        """读取剪贴板文本内容"""
        try:
            import win32clipboard
            import win32con

            win32clipboard.OpenClipboard()
            try:
                if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                    data = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                    return data
                return ""
            finally:
                win32clipboard.CloseClipboard()
        except Exception as e:
            # 备用方案：使用 ctypes
            return self._read_with_ctypes()

    def write(self, text):
        """将文本写入剪贴板"""
        try:
            import win32clipboard
            import win32con

            win32clipboard.OpenClipboard()
            try:
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
            finally:
                win32clipboard.CloseClipboard()
            return True
        except Exception as e:
            return self._write_with_ctypes(text)

    def _read_with_ctypes(self):
        """使用 ctypes 读取剪贴板（备用方案）"""
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        if not user32.OpenClipboard(0):
            return ""

        try:
            if user32.IsClipboardFormatAvailable(13):  # CF_UNICODETEXT = 13
                handle = user32.GetClipboardData(13)
                if handle:
                    ptr = kernel32.GlobalLock(handle)
                    if ptr:
                        size = kernel32.GlobalSize(handle)
                        if size:
                            data = ctypes.wstring_at(ptr, size // 2)
                            kernel32.GlobalUnlock(handle)
                            return data.rstrip("\0")
            return ""
        finally:
            user32.CloseClipboard()

    def _write_with_ctypes(self, text):
        """使用 ctypes 写入剪贴板（备用方案）"""
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        if not user32.OpenClipboard(0):
            return False

        try:
            user32.EmptyClipboard()
            # 分配全局内存
            text_bytes = text.encode("utf-16-le") + b"\0\0"
            size = len(text_bytes)
            handle = kernel32.GlobalAlloc(0x0002, size)  # GMEM_MOVEABLE
            if handle:
                ptr = kernel32.GlobalLock(handle)
                if ptr:
                    ctypes.memmove(ptr, text_bytes, size)
                    kernel32.GlobalUnlock(handle)
                    user32.SetClipboardData(13, handle)  # CF_UNICODETEXT
                    return True
            return False
        finally:
            user32.CloseClipboard()