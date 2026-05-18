import ctypes
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
    NSWindow,
    NSWindowStyleMaskTitled,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskResizable,
    NSBackingStoreBuffered,
    NSColor,
    NSRunningApplication,
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
SELF_TEST_MIN_ALPHA = 40
DEBUG = os.getenv("OPACITY_DEBUG", "0") == "1"


class _CGSApi:
    def __init__(self):
        self._lib = None
        self._conn_fn = None
        self._set_alpha_fn = None
        self._load()

    def _try_load(self, path):
        try:
            lib = ctypes.CDLL(path)
        except OSError:
            return None
        return lib

    def _load(self):
        self._lib = self._try_load(
            "/System/Library/PrivateFrameworks/SkyLight.framework/SkyLight"
        )
        if self._lib is None:
            self._lib = self._try_load(
                "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
            )
        if self._lib is None:
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
            return False, None
        conn = self._conn_fn()
        status = self._set_alpha_fn(conn, window_id, float(alpha_float))
        return status == 0, int(status)


class OpacityController:
    def __init__(self):
        self.alpha_by_window = {}
        self.alpha_by_pid = {}
        self.cgs_api = _CGSApi()
        self.override_window_id = None

    def adjust_frontmost(self, delta):
        if self.override_window_id is not None:
            window_id = self.override_window_id
            min_alpha = SELF_TEST_MIN_ALPHA
            current = self.alpha_by_window.get(window_id, min_alpha)
            new_alpha = max(min_alpha, min(ALPHA_MAX, current + delta))
            self.alpha_by_window[window_id] = new_alpha
            ok, status = self._apply_alpha(window_id, new_alpha)
            if DEBUG:
                print(
                    f"[debug] Set alpha window_id={window_id} alpha={new_alpha} ok={ok} status={status}"
                )
            if not ok and DEBUG:
                print("[debug] Failed to set window alpha (API unavailable or blocked)")
            return ok
        pid = self._frontmost_pid()
        if pid is None:
            if DEBUG:
                print("[debug] No frontmost PID")
            return None
        window_ids = self._window_ids_for_pid(pid)
        if not window_ids:
            window_id = self._frontmost_window_id()
            if window_id is None:
                if DEBUG:
                    print("[debug] No focused window id")
                return None
            window_ids = [window_id]
        current = self.alpha_by_pid.get(pid, ALPHA_MIN)
        new_alpha = max(ALPHA_MIN, min(ALPHA_MAX, current + delta))
        self.alpha_by_pid[pid] = new_alpha
        ok_any = False
        for window_id in window_ids:
            ok, status = self._apply_alpha(window_id, new_alpha)
            ok_any = ok_any or bool(ok)
            if DEBUG:
                print(
                    f"[debug] Set alpha window_id={window_id} alpha={new_alpha} ok={ok} status={status}"
                )
        if not ok_any and DEBUG:
            print("[debug] Failed to set window alpha (API unavailable or blocked)")
        return ok_any

    def _apply_alpha(self, window_id, alpha_255):
        if not self.cgs_api.available():
            return False, None
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
            window_id = int(window_id_ref)
            if DEBUG:
                print(f"[debug] Focused window id={window_id}")
            return window_id
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

    def _window_ids_for_pid(self, pid):
        options = kCGWindowListOptionOnScreenOnly | kCGWindowListExcludeDesktopElements
        window_list = CGWindowListCopyWindowInfo(options, kCGNullWindowID)
        window_ids = []
        for info in window_list:
            if info.get("kCGWindowOwnerPID") != pid:
                continue
            if info.get("kCGWindowLayer") != 0:
                continue
            window_id = info.get("kCGWindowNumber")
            if window_id is None:
                continue
            window_id_int = int(window_id)
            if window_id_int not in window_ids:
                window_ids.append(window_id_int)
        return window_ids


_controller = None
_event_tap = None
_self_test_window = None


def _event_callback(proxy, event_type, event, refcon):
    if event_type != kCGEventKeyDown:
        return event
    keycode = CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)
    if DEBUG:
        flags = CGEventGetFlags(event)
        print(f"[debug] KeyDown keycode={keycode} flags=0x{int(flags):x}")
    flags = CGEventGetFlags(event)
    if not (
        flags & kCGEventFlagMaskCommand
        and flags & kCGEventFlagMaskControl
        and flags & kCGEventFlagMaskAlternate
    ):
        return event
    if DEBUG:
        print("[debug] Hotkey matched")
    if keycode == KEY_UP:
        _apply_delta(ALPHA_STEP)
    elif keycode == KEY_DOWN:
        _apply_delta(-ALPHA_STEP)
    return event


def _create_event_tap():
    global _event_tap
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
    if DEBUG:
        print("[debug] Event tap created")
    source = CFMachPortCreateRunLoopSource(None, tap, 0)
    CFRunLoopAddSource(CFRunLoopGetCurrent(), source, kCFRunLoopCommonModes)
    CGEventTapEnable(tap, True)
    _event_tap = tap


def _apply_delta(delta):
    global _controller
    _controller.adjust_frontmost(delta)


def _create_self_test_window():
    rect = ((200, 200), (480, 320))
    style = (
        NSWindowStyleMaskTitled
        | NSWindowStyleMaskClosable
        | NSWindowStyleMaskResizable
    )
    window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        rect,
        style,
        NSBackingStoreBuffered,
        False,
    )
    window.setTitle_("Opacity Self-Test")
    window.setBackgroundColor_(NSColor.windowBackgroundColor())
    window.center()
    window.makeKeyAndOrderFront_(None)
    return window


def main():
    global _controller
    global _self_test_window
    if not AXIsProcessTrusted():
        raise RuntimeError("Accessibility permission is required to read window info")
    NSApplication.sharedApplication()
    NSApp.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    _controller = OpacityController()
    if DEBUG:
        print(f"[debug] CGS API available={_controller.cgs_api.available()}")
    if os.getenv("OPACITY_SELF_TEST", "0") == "1":
        NSRunningApplication.currentApplication().activateWithOptions_(1 << 1)
        _self_test_window = _create_self_test_window()
        try:
            _controller.override_window_id = int(_self_test_window.windowNumber())
        except Exception:
            _controller.override_window_id = None
        if DEBUG:
            print(
                f"[debug] Self-test window id={_controller.override_window_id}"
            )
    _create_event_tap()
    if DEBUG:
        print("[debug] Run loop started")
    CFRunLoopRun()


if __name__ == "__main__":
    main()
