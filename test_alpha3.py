import ctypes
import Quartz
from AppKit import NSWorkspace
SL = ctypes.cdll.LoadLibrary('/System/Library/PrivateFrameworks/SkyLight.framework/SkyLight')
SL.SLSSetWindowAlpha.argtypes = [ctypes.c_int, ctypes.c_uint32, ctypes.c_float]
conn = SL.SLSMainConnectionID()
for w in Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID):
    if w.get('kCGWindowOwnerPID') == NSWorkspace.sharedWorkspace().frontmostApplication().processIdentifier() and w.get('kCGWindowLayer') == 0:
        wid = w.get('kCGWindowNumber')
        print(SL.SLSSetWindowAlpha(conn, wid, 0.5))
        break
