# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Core Architecture

Q_CameraTools is a Python-based basketball training analysis toolkit focused on dual-camera recording and court calibration. The main components are:

### Primary Applications
- `dual_camera_recorder.py`: Main GUI application for synchronized dual-camera recording with real-time preview
- `homography.py`: Court calibration tool for establishing coordinate transformations
- `camera_calibration.py`: Camera distortion correction utility using checkerboard patterns
- `test_camera_detection.py`: Camera device detection and compatibility testing

### Key Technical Patterns
- **Tkinter GUI Framework**: All applications use tkinter for cross-platform GUI
- **Unified Camera Management**: Uses `camera_utils.py` module for consistent camera detection and device path management
- **By-ID Device Paths**: Prefers `/dev/v4l/by-id/` paths for stable camera identification with `/dev/videoX` fallback
- **Threading Architecture**: Recording and preview run in separate threads with queue-based frame sharing
- **JSON Configuration**: Camera parameters and recording metadata stored in JSON format

## Development Commands

### Installation & Setup
```bash
# Install system dependencies (Ubuntu/Debian)
sudo apt install python3-tk v4l-utils

# Install Python dependencies
pip install opencv-python numpy Pillow

# Quick dependency check and launch
./run_camera_tool.sh

# Test camera detection with unified module
python3 -c "from camera_utils import CameraManager; CameraManager.test_camera_detection()"
```

### Running Applications
```bash
# Main dual-camera recorder (most common)
python3 dual_camera_recorder.py

# Camera detection and troubleshooting
python3 test_camera_detection.py

# Court calibration
python3 homography.py

# Camera distortion correction
python3 camera_calibration.py
```

### Testing & Debugging
```bash
# Check available camera devices
ls -la /dev/video*

# Test camera access permissions
v4l2-ctl --list-devices

# Quick camera compatibility test
python3 test_camera_detection.py
```

## File Structure Conventions

### Output Organization
- `video/`: Contains timestamped recording folders (e.g., `basketball_recording_20250721_121910/`)
- `video/exported_frames/`: Frame exports organized by timestamp and camera
- JSON files in root: Camera calibration and configuration data

### Naming Patterns
- Recording folders: `basketball_recording_YYYYMMDD_HHMMSS/`
- Video files: `camera1_YYYYMMDD_HHMMSS.avi`, `camera2_YYYYMMDD_HHMMSS.avi`
- Frame exports: `camera_N_frame_XXXXXX_tYY.YYs.jpg`

## Unified Camera Utilities (`camera_utils.py`)

### Core Classes
- **CameraDevice**: Represents a camera with multiple access paths and metadata
- **CameraManager**: Static methods for camera detection, opening, and management

### Key Features
- **Stable Device Identification**: Uses `/dev/v4l/by-id/` paths when available
- **Intelligent Fallback**: Tries by-id → /dev/videoX → device index in order
- **Resolution Detection**: Automatically detects and parses supported resolutions with FPS
- **Cross-Application API**: Consistent interface used by all tools

### Usage Pattern
```python
from camera_utils import CameraManager, open_camera_with_fallback

# Detect all cameras
cameras = CameraManager.detect_cameras()

# Open camera with fallback support
cap = open_camera_with_fallback(cameras[0])
```

## Camera System Design

### Device Detection Logic (Updated with camera_utils module)
The unified camera detection system provides consistent device management:
1. **Primary Detection**: Uses `camera_utils.CameraManager.detect_cameras()` to scan all available devices
2. **Path Mapping**: Maps `/dev/v4l/by-id/` stable paths to `/dev/videoX` devices for hardware consistency
3. **Intelligent Fallback**: Opens cameras using by-id paths first, falls back to traditional paths if needed
4. **Resolution Detection**: Automatically detects supported resolutions with FPS information using v4l2-ctl
5. **Device Info**: Retrieves comprehensive device information (driver, bus info, capabilities)
6. **Cross-Application Consistency**: All applications (dual_camera_recorder, homography, test_camera_detection) use the same detection logic

### Threading Model
- **Main Thread**: GUI and user interaction
- **Recording Thread**: Handles video writing for both cameras
- **Preview Thread**: Manages real-time camera display (separate from recording)
- **Shared Preview**: During recording, preview uses frames from recording queue
- **Frame Queues**: Limited-size queues prevent memory accumulation
- **Camera Path Management**: Intelligent device opening with by-id preference

## Common Issues & Solutions

### Camera Access Problems
- Add user to video group: `sudo usermod -a -G video $USER`
- Check device permissions in `/dev/video*`
- Ensure cameras aren't used by other applications

### GUI Font Issues (X11 forwarding)
- `homography.py` includes X11 font forwarding fixes
- Set `TK_SILENCE_DEPRECATION=1` environment variable

### Performance Optimization
- Frame queues use `maxsize=2` to limit memory usage
- Recording and preview use separate camera instances
- Preview resolution can be different from recording resolution

## Integration Points

When adding new features:
1. **Use Unified Camera API**: Always import and use `camera_utils` module for camera operations
2. **Follow GUI Patterns**: Use existing Tkinter GUI patterns from `dual_camera_recorder.py`
3. **Device Opening**: Use `open_camera_with_fallback()` instead of direct `cv2.VideoCapture()`
4. **Camera Detection**: Use `CameraManager.detect_cameras()` for consistent device discovery
5. **Threading Safety**: Consider threading implications for camera access
6. **Configuration**: Maintain JSON-based configuration for persistence
7. **File Naming**: Follow timestamp-based file naming conventions

### Code Update Pattern
When updating existing camera code:
```python
# OLD: Direct OpenCV usage
cap = cv2.VideoCapture(device_index)

# NEW: Using camera_utils
from camera_utils import open_camera_with_fallback
cap = open_camera_with_fallback(camera_device)
```

## Dependencies Management

Complete dependency list (extend requirements.txt):
```
opencv-python>=4.5.0
numpy>=1.19.0
Pillow>=8.0.0
```

System packages needed: `python3-tk`, `v4l-utils`