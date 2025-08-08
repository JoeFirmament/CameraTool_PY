#!/usr/bin/env python3
"""
Test camera detection to verify device names are correctly displayed
"""

import subprocess
import os
import re


def get_camera_info_v4l2(device_path):
    """Get camera information using v4l2-ctl"""
    try:
        cmd = ['v4l2-ctl', '-d', device_path, '--info']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        
        if result.returncode == 0:
            info = {}
            for line in result.stdout.split('\n'):
                if 'Card type' in line:
                    info['name'] = line.split(':', 1)[1].strip()
                elif 'Driver name' in line:
                    info['driver'] = line.split(':', 1)[1].strip()
                elif 'Bus info' in line:
                    info['bus'] = line.split(':', 1)[1].strip()
            
            return info
        else:
            return None
            
    except Exception as e:
        print(f"Error getting info for {device_path}: {e}")
        return None


def get_supported_resolutions_v4l2(device_path):
    """Get supported resolutions using v4l2-ctl"""
    try:
        cmd = ['v4l2-ctl', '-d', device_path, '--list-formats-ext']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            resolutions = set()
            for line in result.stdout.split('\n'):
                if 'Size:' in line:
                    match = re.search(r'Size: Discrete (\d+)x(\d+)', line)
                    if match:
                        width, height = match.groups()
                        resolutions.add(f"{width}x{height}")
            
            return sorted(list(resolutions), key=lambda x: int(x.split('x')[0]))
        else:
            return []
            
    except Exception as e:
        print(f"Error getting resolutions for {device_path}: {e}")
        return []


def test_camera_detection():
    """Test camera detection logic"""
    print("Testing camera detection...")
    print("=" * 50)
    
    camera_devices = []
    
    # Check for video devices
    for i in range(10):
        device_path = f"/dev/video{i}"
        if os.path.exists(device_path):
            print(f"\nTesting {device_path}...")
            
            # Get device info
            info = get_camera_info_v4l2(device_path)
            if info:
                device_name = info.get('name', f'Camera {i}')
                print(f"  Device name: {device_name}")
                print(f"  Driver: {info.get('driver', 'Unknown')}")
                print(f"  Bus: {info.get('bus', 'Unknown')}")
                
                # Get supported resolutions
                resolutions = get_supported_resolutions_v4l2(device_path)
                print(f"  Resolutions: {len(resolutions)} available")
                
                if len(resolutions) > 0:
                    print(f"  Sample resolutions: {resolutions[:3]}")
                    
                    # Only add devices that can actually capture video
                    camera_devices.append({
                        'index': i,
                        'path': device_path,
                        'name': device_name,
                        'info': info,
                        'resolutions': resolutions
                    })
                    print(f"  ✅ Added to camera list")
                else:
                    print(f"  ❌ No resolutions - probably metadata device")
            else:
                print(f"  ❌ No device info available")
    
    print("\n" + "=" * 50)
    print("FINAL CAMERA LIST:")
    print("=" * 50)
    
    for i, device in enumerate(camera_devices):
        print(f"{i+1}. {device['name']} - {device['path']}")
        print(f"   Driver: {device['info']['driver']}")
        print(f"   Resolutions: {len(device['resolutions'])}")
        print()
    
    print(f"Total cameras found: {len(camera_devices)}")
    
    if len(camera_devices) >= 2:
        print("\n✅ Sufficient cameras for dual recording!")
        print(f"Camera 1 (Auto): {camera_devices[0]['name']}")
        print(f"Camera 2 (Auto): {camera_devices[1]['name']}")
    else:
        print("\n⚠️  Not enough cameras for dual recording")


if __name__ == "__main__":
    test_camera_detection()