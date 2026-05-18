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
    CGPoint,
    CGSize,
)

from ApplicationServices import (
    AXIsProcessTrusted,
    AXUIElementCreateApplication,
    AXUIElementCopyAttributeValue,
    AXValueGetType,
    AXValueGetValue,
    kAXFocusedWindowAttribute,
    kAXPositionAttribute,
    kAXSizeAttribute,
    kAXValueCGPointType,
    kAXValueCGSizeType,
)

from AppKit import (
    NSWorkspace,
    NSApplication,
    NSApplicationActivationPolicyAccessory,
    NSApp,
    NSWindow,
    NSWindowStyleMaskBorderless,
    NSBackingStoreBuffered,
    NSStatusWindowLevel,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorFullScreenAuxiliary,
    NSColor,
    NSScreen,
    NSTimer,
    NSObject,
    NSView,
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
REFRESH_INTERVAL = 1.0 / 120.0
CORNER_RADIUS = 12.0
SHADOW_PADDING = 36.0
SHADOW_PADDING_TOP = 18.0
SHADOW_PADDING_BOTTOM = 52.0
DEBUG = os.getenv("OPACITY_DEBUG", "0") == "1"


class OpacityController:
    def __init__(self):
        self.alpha_by_pid = {}
        self.overlay_window = None
        self.overlay_view = None

    def adjust_frontmost(self, delta):
        pid = self._frontmost_pid()
        if pid is None:
            if DEBUG:
                print("[debug] No frontmost PID")
            return
        frame = self._frontmost_window_frame(pid)
        if not frame:
            if DEBUG:
                print(f"[debug] No frontmost window frame for pid={pid}")
            return
        current = self.alpha_by_pid.get(pid, ALPHA_MIN)
        new_alpha = max(ALPHA_MIN, min(ALPHA_MAX, current + delta))
        self.alpha_by_pid[pid] = new_alpha
        self.refresh_overlay()
        if DEBUG:
            x, y, w, h = frame
            print(
                f"[debug] Overlay frame=({x:.1f},{y:.1f},{w:.1f},{h:.1f}) alpha={new_alpha}"
            )

    def refresh_overlay(self):
        pid = self._frontmost_pid()
        if pid is None:
            self._hide_overlay()
            return
        alpha = self.alpha_by_pid.get(pid, ALPHA_MIN)
        if alpha <= 0:
            self._hide_overlay()
            return
        frame = self._frontmost_window_frame(pid)
        if not frame:
            self._hide_overlay()
            return
        expanded = self._expand_frame(
            frame,
            SHADOW_PADDING,
            SHADOW_PADDING_TOP,
            SHADOW_PADDING_BOTTOM,
        )
        self._ensure_overlay(expanded, alpha)

    def _ensure_overlay(self, frame, alpha_255):
        x, y, w, h = frame
        if not self.overlay_window:
            rect = ((x, y), (w, h))
            window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
                rect,
                NSWindowStyleMaskBorderless,
                NSBackingStoreBuffered,
                False,
            )
            window.setOpaque_(False)
            window.setHasShadow_(False)
            window.setIgnoresMouseEvents_(True)
            window.setLevel_(NSStatusWindowLevel)
            window.setBackgroundColor_(NSColor.clearColor())
            behavior = (
                NSWindowCollectionBehaviorCanJoinAllSpaces
                | NSWindowCollectionBehaviorFullScreenAuxiliary
            )
            window.setCollectionBehavior_(behavior)
            view = NSView.alloc().initWithFrame_(rect)
            view.setWantsLayer_(True)
            view.layer().setCornerRadius_(CORNER_RADIUS)
            view.layer().setMasksToBounds_(True)
            window.setContentView_(view)
            self.overlay_window = window
            self.overlay_view = view
        self.overlay_window.setFrame_display_(((x, y), (w, h)), True)
        alpha_float = float(alpha_255) / 255.0
        color = NSColor.whiteColor().colorWithAlphaComponent_(alpha_float)
        if self.overlay_view:
            self.overlay_view.layer().setBackgroundColor_(color.CGColor())
        self.overlay_window.orderFrontRegardless()

    def _hide_overlay(self):
        if self.overlay_window:
            self.overlay_window.orderOut_(None)

    def _expand_frame(self, frame, padding, padding_top, padding_bottom):
        x, y, w, h = frame
        return (
            x - padding,
            y - padding_bottom,
            w + padding * 2,
            h + padding_top + padding_bottom,
        )

    def _frontmost_pid(self):
        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        if not app:
            return None
        return app.processIdentifier()

    def _frontmost_window_frame(self, pid):
        app_elem = AXUIElementCreateApplication(pid)
        if not app_elem:
            return None
        window_ref, err = AXUIElementCopyAttributeValue(app_elem, kAXFocusedWindowAttribute, None)
        if err != 0 or not window_ref:
            return self._fallback_window_frame(pid)
        pos_ref, pos_err = AXUIElementCopyAttributeValue(window_ref, kAXPositionAttribute, None)
        size_ref, size_err = AXUIElementCopyAttributeValue(window_ref, kAXSizeAttribute, None)
        if pos_err != 0 or size_err != 0:
            return self._fallback_window_frame(pid)
        if AXValueGetType(pos_ref) != kAXValueCGPointType:
            return self._fallback_window_frame(pid)
        if AXValueGetType(size_ref) != kAXValueCGSizeType:
            return self._fallback_window_frame(pid)
        pos = CGPoint()
        size = CGSize()
        AXValueGetValue(pos_ref, kAXValueCGPointType, pos)
        AXValueGetValue(size_ref, kAXValueCGSizeType, size)
        return (pos.x, pos.y, size.width, size.height)

    def _fallback_window_frame(self, pid):
        options = kCGWindowListOptionOnScreenOnly | kCGWindowListExcludeDesktopElements
        window_list = CGWindowListCopyWindowInfo(options, kCGNullWindowID)
        for info in window_list:
            if info.get("kCGWindowOwnerPID") != pid:
                continue
            if info.get("kCGWindowLayer") != 0:
                continue
            bounds = info.get("kCGWindowBounds")
            if not bounds:
                continue
            x = bounds.get("X", 0.0)
            y = bounds.get("Y", 0.0)
            w = bounds.get("Width", 0.0)
            h = bounds.get("Height", 0.0)
            screen = NSScreen.mainScreen()
            if screen:
                screen_height = screen.frame().size.height
                y = screen_height - y - h
            return (x, y, w, h)
        return None


class _OverlayRefresher(NSObject):
    def initWithController_(self, controller):
        self = objc.super(_OverlayRefresher, self).init()
        if self is None:
            return None
        self.controller = controller
        return self

    def tick_(self, _timer):
        self.controller.refresh_overlay()


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
    if not AXIsProcessTrusted():
        raise RuntimeError("Accessibility permission is required to read window info")
    NSApplication.sharedApplication()
    NSApp.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    _controller = OpacityController()
    refresher = _OverlayRefresher.alloc().initWithController_(_controller)
    NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
        REFRESH_INTERVAL,
        refresher,
        "tick:",
        None,
        True,
    )
    _create_event_tap()
    CFRunLoopRun()


if __name__ == "__main__":
    main()

