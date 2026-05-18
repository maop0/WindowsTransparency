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

## macOS (private API)
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
python3 macOS.py
```

### Notes
- Uses private CGS APIs (SkyLight). This may break across macOS releases.
- If the event tap fails, enable Accessibility permissions and restart.
- Opacity range is 50-255 to avoid making windows fully invisible.
- Set `OPACITY_DEBUG=1` to print hotkey and window debug logs.
