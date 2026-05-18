import ctypes
import Quartz
from AppKit import NSWorkspace
from pynput import keyboard

# Load CoreGraphics private APIs
CoreGraphics = ctypes.cdll.LoadLibrary('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')

CGSSetWindowAlpha = CoreGraphics.CGSSetWindowAlpha
CGSSetWindowAlpha.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_float]

try:
    CGSMainConnectionID = CoreGraphics.CGSMainConnectionID
except AttributeError:
    CGSMainConnectionID = CoreGraphics._CGSDefaultConnection
CGSMainConnectionID.argtypes = []
CGSMainConnectionID.restype = ctypes.c_int

connection = CGSMainConnectionID()
window_alphas = {}

def get_active_window_id():
    workspace = NSWorkspace.sharedWorkspace()
    active_app = workspace.frontmostApplication()
    if not active_app:
        return None

    pid = active_app.processIdentifier()

    options = Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements
    window_list = Quartz.CGWindowListCopyWindowInfo(options, Quartz.kCGNullWindowID)

    for window in window_list:
        window_pid = window.get('kCGWindowOwnerPID', 0)
        layer = window.get('kCGWindowLayer', 0)
        # Assuming the standard application window is on layer 0
        if window_pid == pid and layer == 0:
            return window.get('kCGWindowNumber', 0)

    return None

def change_transparency(delta):
    window_id = get_active_window_id()
    if not window_id:
        return

    current_alpha = window_alphas.get(window_id, 1.0)
    new_alpha = max(0.1, min(1.0, current_alpha + delta))
    window_alphas[window_id] = new_alpha

    # ⚠️ Warning ⚠️
    # In macOS (around 10.14+), WindowServer blocks apps from modifying
    # the window alpha of OTHER applications.
    # Calling this function returns 0 (success) but has no visual effect.
    # To actually change other apps opacity, you need to disable System Integrity Protection (SIP)
    # and use an injected scripting addition (like Yabai's).
    CGSSetWindowAlpha(connection, window_id, new_alpha)
    print(f"Window {window_id} transparency set to {new_alpha:.2f}")

def on_activate_up():
    change_transparency(0.1)

def on_activate_down():
    change_transparency(-0.1)

hotkey_config = {
    '<cmd>+<alt>+<ctrl>+<up>': on_activate_up,
    '<cmd>+<alt>+<ctrl>+<down>': on_activate_down
}

if __name__ == '__main__':
    print("Starting window transparency hotkeys...")
    print("Press Cmd+Option+Ctrl+Up to increase opacity")
    print("Press Cmd+Option+Ctrl+Down to decrease opacity")
    with keyboard.GlobalHotKeys(hotkey_config) as listener:
        listener.join()
