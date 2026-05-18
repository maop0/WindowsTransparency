# WindowsTransparency
Small hotkey tools to adjust the active window's opacity.

## Windows
### Features
- Ctrl+Up increases opacity
- Ctrl+Down decreases opacity
- Works on the currently focused window

### Requirements
- Windows 10/11
- Python 3.8+

### Run
```bash
python Windows.py
```

### Notes
- Opacity range is 50-255 to avoid making windows fully invisible.
- Some system or protected windows may not allow opacity changes.

## macOS (overlay)
### Features
- Command+Option+Control+Up increases opacity
- Command+Option+Control+Down decreases opacity
- Works on the currently focused window

### Requirements
- macOS 12+
- Python 3.8+
- `pyobjc` installed
- Accessibility + Input Monitoring permissions enabled for Terminal/IDE

### Run
```bash
python3 macOS_overlay.py
```

### Notes
- Uses an overlay window to simulate brightening the active window (does not change the app's real opacity).
- Requires Accessibility permissions to read the focused window bounds.
- Opacity range is 0-255 (0 hides the overlay).
- Set `OPACITY_DEBUG=1` to print hotkey and overlay debug logs.

## macOS (native API attempt)
### Features
- Command+Option+Control+Up increases opacity
- Command+Option+Control+Down decreases opacity
- Works on the currently focused window

### Requirements
- macOS 12+
- Python 3.8+
- `pyobjc` installed
- Accessibility + Input Monitoring permissions enabled for Terminal/IDE

### Run
```bash
python3 macOS_api.py
```

### Notes
- Uses a private CGS API to try changing the real window alpha; it may fail on newer macOS versions.
- Requires Accessibility permissions to read the focused window id.
- Opacity range is 0-255 (0 is fully transparent if the API allows it).
- Set `OPACITY_DEBUG=1` to print debug logs.

