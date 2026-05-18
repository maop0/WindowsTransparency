import ctypes
import Quartz
from AppKit import NSWorkspace
# try SkyLight
SL = ctypes.cdll.LoadLibrary('/System/Library/PrivateFrameworks/SkyLight.framework/SkyLight')
CGSMainConnectionID = SL.SLSMainConnectionID
CGSMainConnectionID.restype = ctypes.c_int
conn = CGSMainConnectionID()
SLSSetWindowAlpha = SL.SLSSetWindowAlpha
SLSSetWindowAlpha.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_float]
workspace = NSWorkspace.sharedWorkspace()
active_app = workspace.frontmostApplication()
pid = active_app.processIdentifier()
print("PID:", pid)
options = Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements
window_list = Quartz.CGWindowListCopyWindowInfo(options, Quartz.kCGNullWindowID)
win_id = None
for window in window_list:
    window_pid = window.get('kCGWindowOwnerPID', 0)
    layer = window.get('kCGWindowLayer', 0)
    if window_pid == pid and layer == 0:
        win_id = window.get('kCGWindowNumber', 0)
        break
print("Win ID:", win_id)
if win_iimport ctypes
import Quartz
= import QuartAlfrom AppKit n_# try SkyLight
SL = ctypes.cdprSL = ctypes.ca CGSMainConnectionID = SL.SLSMainConnectioncat << 'EOF' > test_alpha2.py
import ctypes
import Quartz
from AppKit import NSWorkspace
SL = ctypes.cdll.LoadLibrary('/System/Library/PrivateFrameworks/SkyLight.framework/SkyLight')
conn = SL.SLSMainConnectionID()
SLSSetWindowAlpha = SL.SLSSetWindowAlpha
SLSSetWindowAlpha.argtypes = [ctypes.c_int, ctypes.c_uint32, ctypes.c_float]
workspace = NSWorkspace.sharedWorkspace()
pid = workspace.frontmostApplication().processIdentifier()
options = Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements
window_list = Quartz.CGWindowListCopyWindowInfo(options, Quartz.kCGNullWindowID)
for window in window_list:
    if window.get('kCGWindowOwnerPID') == pid and window.get('kCGWindowLayer') == 0:
        win_id = window.get('kCGWindowNumber')
        print(f"Setting {win_id} to 0.5")
        res = SLSSetWindowAlpha(conn, win_id, 0.5)
        print("Result:", res)
        break
