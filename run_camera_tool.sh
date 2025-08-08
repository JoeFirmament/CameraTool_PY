#!/bin/bash

# Basketball Dual Camera Recording Tool Launcher
# This script sets up the environment and launches the camera recording tool

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=== Basketball Dual Camera Recording Tool ===${NC}"
echo ""

# Check if script is in correct directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -f "dual_camera_recorder.py" ]; then
    echo -e "${RED}Error: dual_camera_recorder.py not found in current directory!${NC}"
    echo "Please run this script from the CameraTool_PY directory."
    exit 1
fi

# Check Python version
echo -e "${YELLOW}Checking Python installation...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed!${NC}"
    echo "Please install Python 3: sudo apt install python3"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
echo -e "${GREEN}Python version: $PYTHON_VERSION${NC}"

# Check required packages
echo -e "${YELLOW}Checking required packages...${NC}"

missing_packages=()

# Check OpenCV
if ! python3 -c "import cv2" 2>/dev/null; then
    missing_packages+=("opencv-python")
fi

# Check tkinter
if ! python3 -c "import tkinter" 2>/dev/null; then
    missing_packages+=("python3-tk")
fi

# Install missing packages if any
if [ ${#missing_packages[@]} -ne 0 ]; then
    echo -e "${YELLOW}Installing missing packages...${NC}"
    
    # Install system packages
    if [[ " ${missing_packages[@]} " =~ " python3-tk " ]]; then
        echo -e "${YELLOW}Installing python3-tk...${NC}"
        sudo apt update && sudo apt install -y python3-tk
    fi
    
    # Install pip packages
    if [[ " ${missing_packages[@]} " =~ " opencv-python " ]]; then
        echo -e "${YELLOW}Installing opencv-python...${NC}"
        pip3 install opencv-python
    fi
fi

# Check camera devices
echo -e "${YELLOW}Checking camera devices...${NC}"
camera_count=0
for i in {0..9}; do
    if [ -e "/dev/video$i" ]; then
        echo -e "${GREEN}Found camera: /dev/video$i${NC}"
        camera_count=$((camera_count + 1))
    fi
done

if [ $camera_count -eq 0 ]; then
    echo -e "${RED}Warning: No camera devices found!${NC}"
    echo "Make sure your cameras are connected and detected by the system."
elif [ $camera_count -eq 1 ]; then
    echo -e "${YELLOW}Warning: Only 1 camera detected. This tool requires 2 cameras for dual recording.${NC}"
else
    echo -e "${GREEN}Found $camera_count camera devices.${NC}"
fi

# Check camera permissions
echo -e "${YELLOW}Checking camera permissions...${NC}"
for i in {0..9}; do
    if [ -e "/dev/video$i" ]; then
        if [ -r "/dev/video$i" ] && [ -w "/dev/video$i" ]; then
            echo -e "${GREEN}Camera /dev/video$i: OK${NC}"
        else
            echo -e "${YELLOW}Camera /dev/video$i: Permission issue${NC}"
            echo "You may need to add your user to the video group:"
            echo "sudo usermod -a -G video $USER"
            echo "Then log out and log back in."
        fi
    fi
done

echo ""
echo -e "${GREEN}All checks completed!${NC}"
echo -e "${BLUE}Starting Dual Camera Recording Tool...${NC}"
echo ""

# Set display if not set (for headless systems with X forwarding)
if [ -z "$DISPLAY" ]; then
    export DISPLAY=:0
fi

# Launch the application
python3 dual_camera_recorder.py

echo ""
echo -e "${BLUE}Application closed.${NC}"