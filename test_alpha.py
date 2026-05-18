import ctypes
import Quartz
from AppKit import NSWorkspace
CoreGraphics = ctypes.cdll.LoadLibrary('/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics')
CGSGetWindowAlpha = CoreGraphics.CGSGetWindowAlpha
# alpha value is return by reference
CGSGetWindowAlpha.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_float)]
connection = CoreGraphics.CGSMainConnectionID()
# Find window 5848 or just any
print("Testing")
