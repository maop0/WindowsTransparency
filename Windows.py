import ctypes
from ctypes import wintypes

USER32 = ctypes.WinDLL("user32", use_last_error=True)

WM_HOTKEY = 0x0312

HOTKEY_ID_UP = 1
HOTKEY_ID_DOWN = 2

MOD_CONTROL = 0x0002
VK_UP = 0x26
VK_DOWN = 0x28

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
LWA_ALPHA = 0x00000002

ALPHA_STEP = 15
ALPHA_MIN = 50
ALPHA_MAX = 255

GetForegroundWindow = USER32.GetForegroundWindow
GetWindowLongW = USER32.GetWindowLongW
SetWindowLongW = USER32.SetWindowLongW
SetLayeredWindowAttributes = USER32.SetLayeredWindowAttributes
RegisterHotKey = USER32.RegisterHotKey
UnregisterHotKey = USER32.UnregisterHotKey
GetMessageW = USER32.GetMessageW
TranslateMessage = USER32.TranslateMessage
DispatchMessageW = USER32.DispatchMessageW

GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
GetWindowLongW.restype = ctypes.c_long
SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
SetWindowLongW.restype = ctypes.c_long
SetLayeredWindowAttributes.argtypes = [wintypes.HWND, wintypes.COLORREF, wintypes.BYTE, wintypes.DWORD]
SetLayeredWindowAttributes.restype = wintypes.BOOL
RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
RegisterHotKey.restype = wintypes.BOOL
UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
UnregisterHotKey.restype = wintypes.BOOL


class OpacityController:
    def __init__(self):
        self.alpha_by_hwnd = {}

    def _ensure_layered(self, hwnd):
        ex_style = GetWindowLongW(hwnd, GWL_EXSTYLE)
        if not (ex_style & WS_EX_LAYERED):
            SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style | WS_EX_LAYERED)

    def _get_alpha(self, hwnd):
        return self.alpha_by_hwnd.get(hwnd, ALPHA_MAX)

    def _set_alpha(self, hwnd, alpha):
        self._ensure_layered(hwnd)
        alpha = max(ALPHA_MIN, min(ALPHA_MAX, alpha))
        ok = SetLayeredWindowAttributes(hwnd, 0, alpha, LWA_ALPHA)
        if ok:
            self.alpha_by_hwnd[hwnd] = alpha

    def adjust_active(self, delta):
        hwnd = GetForegroundWindow()
        if not hwnd:
            return
        current = self._get_alpha(hwnd)
        self._set_alpha(hwnd, current + delta)


class Msg(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
    ]


def register_hotkeys():
    if not RegisterHotKey(None, HOTKEY_ID_UP, MOD_CONTROL, VK_UP):
        raise RuntimeError("Failed to register Ctrl+Up hotkey")
    if not RegisterHotKey(None, HOTKEY_ID_DOWN, MOD_CONTROL, VK_DOWN):
        UnregisterHotKey(None, HOTKEY_ID_UP)
        raise RuntimeError("Failed to register Ctrl+Down hotkey")


def unregister_hotkeys():
    UnregisterHotKey(None, HOTKEY_ID_UP)
    UnregisterHotKey(None, HOTKEY_ID_DOWN)


def message_loop(controller):
    msg = Msg()
    while GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
        if msg.message == WM_HOTKEY:
            if msg.wParam == HOTKEY_ID_UP:
                controller.adjust_active(ALPHA_STEP)
            elif msg.wParam == HOTKEY_ID_DOWN:
                controller.adjust_active(-ALPHA_STEP)
        TranslateMessage(ctypes.byref(msg))
        DispatchMessageW(ctypes.byref(msg))


def main():
    controller = OpacityController()
    register_hotkeys()
    try:
        message_loop(controller)
    finally:
        unregister_hotkeys()


if __name__ == "__main__":
    main()

