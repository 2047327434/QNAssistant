"""模拟键盘操作模块"""
import ctypes
import time

# 虚拟键码
VK_CONTROL = 0x11
VK_SHIFT = 0x10
VK_MENU = 0x12  # Alt
VK_TAB = 0x09
VK_RETURN = 0x0D
VK_A = 0x41
VK_C = 0x43
VK_V = 0x56
VK_X = 0x58
VK_ESCAPE = 0x1B

user32 = ctypes.windll.user32


def key_down(vk_code):
    """按下按键"""
    user32.keybd_event(vk_code, 0, 0, 0)


def key_up(vk_code):
    """释放按键"""
    user32.keybd_event(vk_code, 0, 2, 0)  # KEYEVENTF_KEYUP = 2


def press_key(vk_code, delay=0.03):
    """按下并释放按键"""
    key_down(vk_code)
    time.sleep(delay)
    key_up(vk_code)


def send_key_combo(*keys, delay=0.03, post_delay=0.05):
    """发送组合键 (如 Ctrl+A, Ctrl+C, Ctrl+V)"""
    # 按下所有修饰键
    for key in keys[:-1]:
        key_down(key)
    time.sleep(delay)

    # 按下并释放最后一个键
    press_key(keys[-1], delay)

    # 释放所有修饰键（逆序）
    for key in reversed(keys[:-1]):
        key_up(key)

    time.sleep(post_delay)


def ctrl_a(delay=0.05):
    """Ctrl+A 全选"""
    send_key_combo(VK_CONTROL, VK_A, post_delay=delay)


def ctrl_c(delay=0.05):
    """Ctrl+C 复制"""
    send_key_combo(VK_CONTROL, VK_C, post_delay=delay)


def ctrl_v(delay=0.05):
    """Ctrl+V 粘贴"""
    send_key_combo(VK_CONTROL, VK_V, post_delay=delay)


def ctrl_x(delay=0.05):
    """Ctrl+X 剪切"""
    send_key_combo(VK_CONTROL, VK_X, post_delay=delay)


def press_tab(delay=0.05):
    """按 Tab 键"""
    press_key(VK_TAB)
    time.sleep(delay)


def press_enter(delay=0.05):
    """按 Enter 键"""
    press_key(VK_RETURN)
    time.sleep(delay)


def press_escape(delay=0.05):
    """按 Escape 键"""
    press_key(VK_ESCAPE)
    time.sleep(delay)


def type_text(text, interval=0.01):
    """逐字符输入文本（备用方案，速度较慢）"""
    for char in text:
        # 使用 SendInput 发送 Unicode 字符
        INPUT_KEYBOARD = 1
        KEYEVENTF_UNICODE = 0x0004

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [
                ("wVk", ctypes.c_ushort),
                ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
            ]

        class INPUT(ctypes.Structure):
            class _INPUT(ctypes.Union):
                _fields_ = [("ki", KEYBDINPUT)]

            _anonymous_ = ("_input",)
            _fields_ = [("type", ctypes.c_ulong), ("_input", _INPUT)]

        # Key down
        inp = INPUT()
        inp.type = INPUT_KEYBOARD
        inp.wScan = ord(char)
        inp.dwFlags = KEYEVENTF_UNICODE
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

        # Key up
        inp.dwFlags = KEYEVENTF_UNICODE | 2  # KEYEVENTF_KEYUP
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

        time.sleep(interval)
