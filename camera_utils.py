#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Camera Detection and Management Utilities
Unified module for camera detection, path management, and OpenCV integration
"""

import os
import subprocess
import cv2
import re
from typing import List, Dict, Optional, Tuple, Union


class CameraDevice:
    """Represents a camera device with multiple access methods"""
    
    def __init__(self, index: int, name: str, driver: str, bus_info: str = ""):
        self.index = index
        self.name = name  
        self.driver = driver
        self.bus_info = bus_info
        self.by_id_path: Optional[str] = None
        self.real_path = f"/dev/video{index}"
        self.resolutions: List[str] = []
        self.info: Dict = {}
        
    def add_by_id_path(self, by_id_path: str):
        """Add by-id path for stable device identification"""
        self.by_id_path = by_id_path
        
    def get_primary_path(self) -> str:
        """Get preferred path for accessing camera (by-id if available)"""
        return self.by_id_path if self.by_id_path else self.real_path
        
    def get_fallback_path(self) -> str:
        """Get fallback path for accessing camera"""
        return self.real_path
        
    def get_display_name(self) -> str:
        """Get formatted display name showing both paths if available"""
        if self.by_id_path:
            # Extract the device identifier from by-id path for cleaner display
            by_id_name = os.path.basename(self.by_id_path).replace('-video-index0', '')
            return f"{self.name} - by-id:{by_id_name} -> {self.real_path}"
        else:
            return f"{self.name} - {self.real_path}"
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for backward compatibility"""
        return {
            'index': self.index,
            'path': self.get_primary_path(),
            'fallback_path': self.get_fallback_path(),
            'real_path': self.real_path,
            'name': self.name,
            'display_name': self.get_display_name(),
            'info': self.info,
            'resolutions': self.resolutions,
            'use_by_id': bool(self.by_id_path)
        }


class CameraManager:
    """Unified camera detection and management"""
    
    @staticmethod
    def get_camera_info_v4l2(device_path: str) -> Optional[Dict[str, str]]:
        """Get camera information using v4l2-ctl"""
        try:
            cmd = ['v4l2-ctl', '-d', device_path, '--info']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                info = {}
                for line in result.stdout.split('\n'):
                    if 'Card type' in line:
                        info['name'] = line.split(':')[1].strip()
                    elif 'Driver name' in line:
                        info['driver'] = line.split(':')[1].strip()
                    elif 'Bus info' in line:
                        info['bus'] = line.split(':')[1].strip()
                return info
                
        except Exception as e:
            print(f"Error getting info for {device_path}: {e}")
            return None
    
    @staticmethod
    def get_supported_resolutions_v4l2(device_path: str) -> List[Dict]:
        """Get supported resolutions with framerates using v4l2-ctl"""
        try:
            cmd = ['v4l2-ctl', '-d', device_path, '--list-formats-ext']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                resolution_data = {}  # resolution -> {fps: [list], format: str}
                current_format = None
                current_resolution = None
                
                for line in result.stdout.split('\n'):
                    # Detect format
                    if line.strip().startswith('[') and ']:' in line:
                        # Extract format like "MJPG" from "[0]: 'MJPG' (Motion-JPEG, compressed)"
                        format_match = re.search(r"'([A-Z0-9]+)'", line)
                        if format_match:
                            current_format = format_match.group(1)
                    
                    # Detect resolution
                    elif 'Size: Discrete' in line:
                        match = re.search(r'(\d+)x(\d+)', line)
                        if match:
                            current_resolution = f"{match.group(1)}x{match.group(2)}"
                            if current_resolution not in resolution_data:
                                resolution_data[current_resolution] = {
                                    'fps': [], 
                                    'format': current_format or 'UNKNOWN'
                                }
                    
                    # Detect framerate  
                    elif 'Interval:' in line and current_resolution:
                        # Extract FPS from lines like "Interval: Discrete 0.033s (30.000 fps)"
                        fps_match = re.search(r'\(([0-9.]+)\s+fps\)', line)
                        if fps_match:
                            fps = float(fps_match.group(1))
                            if fps not in resolution_data[current_resolution]['fps']:
                                resolution_data[current_resolution]['fps'].append(fps)
                
                # Convert to list format with FPS info
                resolutions = []
                for res, data in resolution_data.items():
                    if data['fps']:
                        # Sort FPS in descending order
                        fps_list = sorted(data['fps'], reverse=True)
                        max_fps = max(fps_list)
                        fps_str = f"{max_fps:.0f}fps" if len(fps_list) == 1 else f"{max_fps:.0f}fps({len(fps_list)} rates)"
                        resolutions.append({
                            'resolution': res,
                            'fps_info': fps_str,
                            'max_fps': max_fps,
                            'all_fps': fps_list,
                            'format': data['format'],
                            'display': f"{res} @{fps_str}"
                        })
                
                # Sort by resolution (width * height) in descending order
                resolutions.sort(key=lambda x: int(x['resolution'].split('x')[0]) * int(x['resolution'].split('x')[1]), reverse=True)
                return resolutions
                
        except Exception as e:
            print(f"Error getting resolutions for {device_path}: {e}")
            return []
    
    @staticmethod
    def scan_by_id_devices() -> Dict[str, str]:
        """Scan /dev/v4l/by-id/ for stable device paths"""
        by_id_mapping = {}  # by_id_path -> real_path
        by_id_path = "/dev/v4l/by-id/"
        
        if os.path.exists(by_id_path):
            try:
                for device_file in os.listdir(by_id_path):
                    if device_file.endswith('-video-index0'):  # Only get main video devices
                        by_id_full_path = os.path.join(by_id_path, device_file)
                        real_path = os.path.realpath(by_id_full_path)
                        by_id_mapping[by_id_full_path] = real_path
            except Exception as e:
                print(f"Warning: Could not read by-id devices: {e}")
        
        return by_id_mapping
    
    @classmethod
    def detect_cameras(cls) -> List[CameraDevice]:
        """Detect all available cameras with comprehensive information"""
        cameras = []
        by_id_mapping = cls.scan_by_id_devices()
        
        # Create reverse mapping for easy lookup
        real_to_by_id = {v: k for k, v in by_id_mapping.items()}
        
        # Scan traditional video devices
        for i in range(10):
            device_path = f"/dev/video{i}"
            if os.path.exists(device_path):
                # Get device info
                info = cls.get_camera_info_v4l2(device_path)
                if info:
                    device_name = info.get('name', f'Camera {i}')
                    driver = info.get('driver', 'unknown')
                    bus_info = info.get('bus', '')
                    
                    # Clean up device name (remove redundant parts)
                    if ':' in device_name:
                        parts = device_name.split(':')
                        if len(parts) == 2 and parts[0].strip() == parts[1].strip():
                            device_name = parts[0].strip()
                    
                    # Get supported resolutions
                    resolutions = cls.get_supported_resolutions_v4l2(device_path)
                    
                    # Only add devices that can actually capture video (have resolutions)
                    if resolutions and len(resolutions) > 0:
                        camera = CameraDevice(i, device_name, driver, bus_info)
                        camera.resolutions = resolutions
                        camera.info = info
                        
                        # Add by-id path if available
                        if device_path in real_to_by_id:
                            camera.add_by_id_path(real_to_by_id[device_path])
                        
                        cameras.append(camera)
                        print(f"Found camera: {device_name} at {camera.get_primary_path()}")
        
        return cameras
    
    @staticmethod
    def open_camera_with_fallback(camera: Union[CameraDevice, Dict]) -> Optional[cv2.VideoCapture]:
        """Open camera with intelligent path selection and fallback"""
        if isinstance(camera, dict):
            primary_path = camera.get('primary', camera.get('path'))
            fallback_path = camera.get('fallback', camera.get('fallback_path', primary_path))
            index = camera.get('index', 0)
        else:
            primary_path = camera.get_primary_path()
            fallback_path = camera.get_fallback_path()
            index = camera.index
        
        # Try primary path first (by-id if available)
        cap = CameraManager._try_open_camera(primary_path)
        if cap:
            return cap
        
        # Try fallback path if different
        if primary_path != fallback_path:
            cap = CameraManager._try_open_camera(fallback_path)
            if cap:
                return cap
        
        # Try traditional index as last resort
        if isinstance(index, int):
            cap = CameraManager._try_open_camera(index)
            if cap:
                return cap
        
        print(f"❌ All camera open attempts failed for camera")
        return None
    
    @staticmethod
    def _try_open_camera(path_or_index) -> Optional[cv2.VideoCapture]:
        """Try to open a single camera path/index"""
        try:
            print(f"Trying camera path: {path_or_index}")
            cap = cv2.VideoCapture(path_or_index)
            if cap.isOpened():
                # Test if we can actually read from the camera
                ret, frame = cap.read()
                if ret and frame is not None:
                    print(f"✅ Successfully opened camera: {path_or_index}")
                    # Reset for actual use
                    cap.release()
                    return cv2.VideoCapture(path_or_index)
                else:
                    print(f"⚠️  Camera opened but can't read frames: {path_or_index}")
                    cap.release()
            else:
                print(f"❌ Failed to open camera: {path_or_index}")
        except Exception as e:
            print(f"❌ Exception opening camera {path_or_index}: {e}")
        
        return None
    
    @staticmethod
    def test_camera_detection():
        """Test camera detection and print detailed information"""
        print("Testing camera detection...")
        print("=" * 50)
        
        cameras = CameraManager.detect_cameras()
        
        print(f"\nFINAL CAMERA LIST:")
        print("=" * 50)
        
        for i, camera in enumerate(cameras, 1):
            print(f"{i}. {camera.get_display_name()}")
            print(f"   Driver: {camera.driver}")
            print(f"   Primary path (for code): {camera.get_primary_path()}")
            if camera.by_id_path:
                print(f"   Fallback path: {camera.get_fallback_path()}")
            print(f"   Resolutions: {len(camera.resolutions)}")
            if camera.resolutions:
                # Show top 3 resolutions (largest first) with FPS info
                sample = camera.resolutions[:3] if len(camera.resolutions) >= 3 else camera.resolutions
                sample_display = [res['display'] for res in sample]
                print(f"   Top resolutions: {sample_display}")
                if len(camera.resolutions) > 3:
                    print(f"   ... and {len(camera.resolutions) - 3} more")
            print()
        
        print(f"Total cameras found: {len(cameras)}")
        
        if len(cameras) >= 2:
            print("✅ Sufficient cameras for dual recording!")
            if len(cameras) >= 2:
                print(f"Camera 1 (Auto): {cameras[0].name}")
                print(f"Camera 2 (Auto): {cameras[1].name}")
        else:
            print("❌ Insufficient cameras for dual recording.")
        
        return cameras


# Convenience functions for backward compatibility
def get_camera_info_v4l2(device_path: str) -> Optional[Dict[str, str]]:
    """Backward compatibility wrapper"""
    return CameraManager.get_camera_info_v4l2(device_path)


def get_supported_resolutions_v4l2(device_path: str) -> List[str]:
    """Backward compatibility wrapper - returns simple resolution strings"""  
    full_data = CameraManager.get_supported_resolutions_v4l2(device_path)
    return [res['resolution'] for res in full_data]


def detect_cameras() -> List[CameraDevice]:
    """Detect all available cameras"""
    return CameraManager.detect_cameras()


def open_camera_with_fallback(camera: Union[CameraDevice, Dict]) -> Optional[cv2.VideoCapture]:
    """Open camera with fallback support"""
    return CameraManager.open_camera_with_fallback(camera)


# Main execution for testing
if __name__ == "__main__":
    CameraManager.test_camera_detection()