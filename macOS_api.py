import ctypes
import os

import objc

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

from ApplicationServices import (
    AXIsProcessTrusted,
    AXUIElementCreateApplication,
    AXUIElementCopyAttributeValue,
    kAXFocusedWindowAttribute,
)

from AppKit import (
    NSWorkspace,
    NSApplication,
    NSApplicationActivationPolicyAccessory,
    NSApp,
)

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
ALPHA_MIN = 0
ALPHA_MAX = 255
DEBUG = os.getenv("OPACITY_DEBUG", "0") == "1"


class _CGSApi:
    def __init__(self):
        self._lib = None
        self._conn_fn = None
        self._set_alpha_fn = None
        self._load()

    def _load(self):
        try:
            self._lib = ctypes.CDLL(
                "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
            )
        except OSError:
            self._lib = None
            return
        try:
            self._conn_fn = self._lib.CGSMainConnectionID
            self._conn_fn.restype = ctypes.c_uint32
        except AttributeError:
            self._conn_fn = None
        try:
            self._set_alpha_fn = self._lib.CGSSetWindowAlpha
            self._set_alpha_fn.argtypes = [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_float]
            self._set_alpha_fn.restype = ctypes.c_int
        except AttributeError:
            self._set_alpha_fn = None

    def available(self):
        return self._conn_fn is not None and self._set_alpha_fn is not None

    def set_window_alpha(self, window_id, alpha_float):
        if not self.available():
            return False
        conn = self._conn_fn()
        status = self._set_alpha_fn(conn, window_id, float(alpha_float))
        return status == 0


class OpacityController:
    def __init__(self):
        self.alpha_by_window = {}
        self.cgs_api = _CGSApi()

    def adjust_frontmost(self, delta):
        window_id = self._frontmost_window_id()
        if window_id is None:
            if DEBUG:
                print("[debug] No focused window id")
            return
        current = self.alpha_by_window.get(window_id, ALPHA_MIN)
        new_alpha = max(ALPHA_MIN, min(ALPHA_MAX, current + delta))
        self.alpha_by_window[window_id] = new_alpha
        if not self._apply_alpha(window_id, new_alpha):
            if DEBUG:
                print("[debug] Failed to set window alpha (API unavailable?)")

    def _apply_alpha(self, window_id, alpha_255):
        if not self.cgs_api.available():
            return False
        alpha_float = float(alpha_255) / 255.0
        return self.cgs_api.set_window_alpha(window_id, alpha_float)

    def _frontmost_pid(self):
        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        if not app:
            return None
        return app.processIdentifier()

    def _frontmost_window_id(self):
        pid = self._frontmost_pid()
        if pid is None:
            return None
        app_elem = AXUIElementCreateApplication(pid)
        if not app_elem:
            return self._fallback_window_id(pid)
        window_ref, err = AXUIElementCopyAttributeValue(
            app_elem, kAXFocusedWindowAttribute, None
        )
        if err != 0 or not window_ref:
            return self._fallback_window_id(pid)
        window_id_ref, win_err = AXUIElementCopyAttributeValue(
            window_ref, "AXWindowNumber", None
        )
        if win_err != 0 or window_id_ref is None:
            return self._fallback_window_id(pid)
        try:
            return int(window_id_ref)
        except (TypeError, ValueError):
            return self._fallback_window_id(pid)

    def _fallback_window_id(self, pid):
        options = kCGWindowListOptionOnScreenOnly | kCGWindowListExcludeDesktopElements
        window_list = CGWindowListCopyWindowInfo(options, kCGNullWindowID)
        for info in window_list:
            if info.get("kCGWindowOwnerPID") != pid:
                continue
            if info.get("kCGWindowLayer") != 0:
                continue
            window_id = info.get("kCGWindowNumber")
            if window_id is not None:
                return int(window_id)
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
        raise RuntimeError("Failed to create event tap (check Input Monitoring)")
    source = CFMachPortCreateRunLoopSource(None, tap, 0)
    CFRunLoopAddSource(CFRunLoopGetCurrent(), source, kCFRunLoopCommonModes)
    CGEventTapEnable(tap, True)


def main():
    global _controller
    if not AXIsProcessTrusted():
        raise RuntimeError("Accessibility permission is required to read window info")
    NSApplication.sharedApplication()
    NSApp.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    _controller = OpacityController()
    if DEBUG and not _controller.cgs_api.available():
        print("[debug] CGS window alpha API not available")
    _create_event_tap()
    CFRunLoopRun()


if __name__ == "__main__":
    main()
