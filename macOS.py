import ctypes
from ctypes import util
import os

from Quartz import (
    CGEventGetFlags,
    CGEventGetIntegerValueField,
    CGEventMaskBit,
    CGEventTapCreate,
    CGEventTapEnable,
    kCGEventFlagMaskCommand,
    kCGEventFlagMaskControl,
    kCGEventFlagMaskAlternate,
    kCGEventKeyDown,
    kCGHeadInsertEventTap,
    kCGKeyboardEventKeycode,
    kCGSessionEventTap,
    kCGEventTapOptionDefault,
    CGWindowListCopyWindowInfo,
    kCGWindowListOptionOnScreenOnly,
    kCGWindowListExcludeDesktopElements,
    kCGNullWindowID,
)

from AppKit import NSWorkspace
from CoreFoundation import (
    CFMachPortCreateRunLoopSource,
    CFRunLoopAddSource,
    CFRunLoopGetCurrent,
    CFRunLoopRun,
    kCFRunLoopCommonModes,
)

KEY_UP = 126
KEY_DOWN = 125

ALPHA_STEP = 15
ALPHA_MIN = 50
ALPHA_MAX = 255
DEBUG = os.getenv("OPACITY_DEBUG", "0") == "1"


class CGSApi:
    def __init__(self):
        self.lib = self._load_library()
        self.connection = self._get_connection_id()
        self._get_connection_id_for_process = self._bind_get_connection_id_for_process()
        self._set_window_alpha = self._bind_set_window_alpha()

    def _load_library(self):
        skylight = "/System/Library/PrivateFrameworks/SkyLight.framework/SkyLight"
        try:
            return ctypes.cdll.LoadLibrary(skylight)
        except OSError:
            app_services = util.find_library("ApplicationServices")
            if not app_services:
                raise RuntimeError("Failed to locate SkyLight or ApplicationServices")
            return ctypes.cdll.LoadLibrary(app_services)

    def _get_connection_id(self):
        func = getattr(self.lib, "CGSMainConnectionID", None)
        if not func:
            raise RuntimeError("CGSMainConnectionID not available")
        func.restype = ctypes.c_uint32
        return func()

    def _bind_set_window_alpha(self):
        func = getattr(self.lib, "CGSSetWindowAlpha", None)
        if not func:
            raise RuntimeError("CGSSetWindowAlpha not available")
        func.argtypes = [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_float]
        func.restype = ctypes.c_int
        return func

    def _bind_get_connection_id_for_process(self):
        func = getattr(self.lib, "CGSGetConnectionIDForProcess", None)
        if not func:
            return None
        func.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_uint32)]
        func.restype = ctypes.c_int
        return func

    def get_connection_id_for_pid(self, pid):
        if not self._get_connection_id_for_process:
            return self.connection
        conn_id = ctypes.c_uint32(0)
        result = self._get_connection_id_for_process(pid, ctypes.byref(conn_id))
        if result != 0 or conn_id.value == 0:
            if DEBUG:
                print(f"[debug] Failed to resolve connection for pid={pid}, using main connection")
            return self.connection
        return conn_id.value

    def set_window_alpha(self, connection_id, window_id, alpha_float):
        result = self._set_window_alpha(connection_id, window_id, alpha_float)
        return result == 0


class OpacityController:
    def __init__(self, cgs_api):
        self.cgs_api = cgs_api
        self.alpha_by_window = {}

    def adjust_frontmost(self, delta):
        pid = self._frontmost_pid()
        if pid is None:
            if DEBUG:
                print("[debug] No frontmost PID")
            return
        window_id = self._frontmost_window_id(pid)
        if window_id is None:
            if DEBUG:
                print(f"[debug] No frontmost window ID for pid={pid}")
            return
        connection_id = self.cgs_api.get_connection_id_for_pid(pid)
        current = self.alpha_by_window.get(window_id, ALPHA_MAX)
        new_alpha = max(ALPHA_MIN, min(ALPHA_MAX, current + delta))
        if self._set_window_alpha(connection_id, window_id, new_alpha):
            self.alpha_by_window[window_id] = new_alpha
            if DEBUG:
                print(f"[debug] Set window {window_id} alpha={new_alpha}")
        elif DEBUG:
            print(f"[debug] Failed to set alpha for window {window_id}")

    def _set_window_alpha(self, connection_id, window_id, alpha_255):
        alpha_float = float(alpha_255) / 255.0
        return self.cgs_api.set_window_alpha(connection_id, window_id, alpha_float)

    def _frontmost_pid(self):
        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        if not app:
            return None
        return app.processIdentifier()

    def _frontmost_window_id(self, pid):
        options = kCGWindowListOptionOnScreenOnly | kCGWindowListExcludeDesktopElements
        window_list = CGWindowListCopyWindowInfo(options, kCGNullWindowID)
        for info in window_list:
            owner_pid = info.get("kCGWindowOwnerPID")
            layer = info.get("kCGWindowLayer")
            if owner_pid == pid and layer == 0:
                window_id = info.get("kCGWindowNumber")
                if DEBUG:
                    print(f"[debug] Frontmost window id={window_id} pid={pid}")
                return window_id
        return None


_controller = None


def _event_callback(proxy, event_type, event, refcon):
    if event_type != kCGEventKeyDown:
        return event
    flags = CGEventGetFlags(event)
    if not (
        flags & kCGEventFlagMaskCommand
        and flags & kCGEventFlagMaskControl
        and flags & kCGEventFlagMaskAlternate
    ):
        return event
    if DEBUG:
        print("[debug] Hotkey matched")
    keycode = CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)
    if keycode == KEY_UP:
        _controller.adjust_frontmost(ALPHA_STEP)
    elif keycode == KEY_DOWN:
        _controller.adjust_frontmost(-ALPHA_STEP)
    return event


def _create_event_tap():
    mask = CGEventMaskBit(kCGEventKeyDown)
    tap = CGEventTapCreate(
        kCGSessionEventTap,
        kCGHeadInsertEventTap,
        kCGEventTapOptionDefault,
        mask,
        _event_callback,
        None,
    )
    if not tap:
        raise RuntimeError("Failed to create event tap (check Accessibility permissions)")
    if DEBUG:
        print("[debug] Event tap created")
    source = CFMachPortCreateRunLoopSource(None, tap, 0)
    CFRunLoopAddSource(CFRunLoopGetCurrent(), source, kCFRunLoopCommonModes)
    CGEventTapEnable(tap, True)


def main():
    global _controller
    cgs_api = CGSApi()
    _controller = OpacityController(cgs_api)
    _create_event_tap()
    CFRunLoopRun()


if __name__ == "__main__":
    main()
