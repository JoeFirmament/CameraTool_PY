#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dual Camera Recording Tool for Basketball Court
Modern minimalistic design with breathing space
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import cv2
import threading
import time
import os
import sys
import re
from datetime import datetime
import subprocess
import json
from PIL import Image, ImageTk
import numpy as np
import queue
from camera_utils import CameraManager, CameraDevice, open_camera_with_fallback


class ModernDualCameraRecorder:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Basketball Recording Studio")
        self.root.geometry("1200x800")
        self.root.minsize(1000, 700)
        self.root.configure(bg='#f8f9fa')
        
        # Modern color scheme
        self.colors = {
            'bg': '#f8f9fa',
            'card': '#ffffff',
            'primary': '#007bff',
            'success': '#28a745',
            'danger': '#dc3545',
            'warning': '#ffc107',
            'text': '#212529',
            'text_muted': '#6c757d',
            'border': '#dee2e6',
            'shadow': '#00000010'
        }
        
        # Recording state
        self.recording = False
        self.start_time = None
        self.record_duration = 0
        self.recording_timestamp = None  # Store timestamp for consistent file naming
        
        # Camera objects
        self.camera1 = None
        self.camera2 = None
        
        # Preview camera objects (separate from recording)
        self.preview_camera1 = None
        self.preview_camera2 = None
        
        # Video writers
        self.writer1 = None
        self.writer2 = None
        
        # Preview variables
        self.preview_active = False
        self.preview_frame1 = None
        self.preview_frame2 = None
        
        # Frame queues for sharing data between recording and preview
        self.frame_queue1 = queue.Queue(maxsize=2)  # 限制队列大小避免内存积累
        self.frame_queue2 = queue.Queue(maxsize=2)
        
        # Available cameras and resolutions
        self.camera_devices = []
        self.available_resolutions = {}
        
        # Output directory
        self.output_dir = ""
        
        # Camera rotation settings (degrees: 0, 90, 180, 270)
        self.camera1_rotation = 0
        self.camera2_rotation = 0
        
        # Configure styles
        self.configure_styles()
        
        # Initialize GUI
        self.setup_gui()
        
        # Load camera information and auto-assign
        self.load_camera_info()
        self.auto_assign_cameras()
        
        # Start preview
        self.start_preview()
        
    def configure_styles(self):
        """Configure modern ttk styles"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure card style
        style.configure('Card.TFrame', 
                       background=self.colors['card'],
                       relief='flat',
                       borderwidth=1)
        
        # Configure title style - 缩小标题字体
        style.configure('Title.TLabel',
                       background=self.colors['bg'],
                       foreground=self.colors['text'],
                       font=('SF Pro Display', 18, 'bold'))
        
        # Configure subtitle style - 缩小副标题字体
        style.configure('Subtitle.TLabel',
                       background=self.colors['bg'],
                       foreground=self.colors['text_muted'],
                       font=('SF Pro Text', 11))
        
        # Configure section title style - 缩小区域标题字体
        style.configure('SectionTitle.TLabel',
                       background=self.colors['card'],
                       foreground=self.colors['text'],
                       font=('SF Pro Text', 13, 'bold'))
        
        # Configure device info style - 缩小设备信息字体
        style.configure('DeviceInfo.TLabel',
                       background=self.colors['card'],
                       foreground=self.colors['text'],
                       font=('SF Pro Text', 10))
        
        # Configure device name style
        style.configure('DeviceName.TLabel',
                       background=self.colors['card'],
                       foreground=self.colors['text_muted'],
                       font=('SF Pro Text', 10))
        
        # Configure device path style
        style.configure('DevicePath.TLabel',
                       background=self.colors['card'],
                       foreground=self.colors['primary'],
                       font=('SF Pro Text', 11, 'bold'))
        
        # Configure timer style - 缩小计时器字体
        style.configure('Timer.TLabel',
                       background=self.colors['card'],
                       foreground=self.colors['text'],
                       font=('SF Pro Display', 18, 'bold'))
        
        # Configure status style
        style.configure('Status.TLabel',
                       background=self.colors['card'],
                       foreground=self.colors['text_muted'],
                       font=('SF Pro Text', 12))
        
        # Configure modern buttons - 缩小按钮字体和内边距
        style.configure('Start.TButton',
                       font=('SF Pro Text', 10, 'bold'),
                       foreground='white',
                       background=self.colors['success'],
                       borderwidth=0,
                       focuscolor='none',
                       padding=(15, 6))
        
        style.configure('Stop.TButton',
                       font=('SF Pro Text', 10, 'bold'),
                       foreground='white',
                       background=self.colors['danger'],
                       borderwidth=0,
                       focuscolor='none',
                       padding=(15, 6))
        
        style.configure('Primary.TButton',
                       font=('SF Pro Text', 10),
                       foreground='white',
                       background=self.colors['primary'],
                       borderwidth=0,
                       focuscolor='none',
                       padding=(12, 6))
        
        # Configure modern combobox
        style.configure('Modern.TCombobox',
                       fieldbackground=self.colors['card'],
                       borderwidth=1,
                       relief='solid',
                       bordercolor=self.colors['border'],
                       arrowcolor=self.colors['text'],
                       font=('SF Pro Text', 11))
        
        # Configure modern entry
        style.configure('Modern.TEntry',
                       fieldbackground=self.colors['card'],
                       borderwidth=1,
                       relief='solid',
                       bordercolor=self.colors['border'],
                       font=('SF Pro Text', 11))
        
    def setup_gui(self):
        """Setup modern GUI with breathing space"""
        # Main container with reduced padding - 进一步减少边距
        main_container = tk.Frame(self.root, bg=self.colors['bg'])
        main_container.pack(fill='both', expand=True, padx=15, pady=10)
        
        # 删除标题区域 - 释放更多空间给预览画面
        
        # 摄像头区域 - 移除多余标题，减少间距
        camera_card = tk.Frame(main_container, bg=self.colors['card'], 
                       relief='flat', bd=1)
        camera_card.configure(highlightbackground=self.colors['border'], 
                      highlightthickness=1)
        camera_card.pack(fill='both', expand=True, pady=(0, 8))
        
        # 摄像头内容区域
        detection_content = tk.Frame(camera_card, bg=self.colors['card'])
        detection_content.pack(fill='both', expand=True, pady=(6, 6))
        
        # 状态显示
        self.detection_status = ttk.Label(detection_content, text="[...] Auto-detecting cameras...", 
                                        style='DeviceInfo.TLabel')
        self.detection_status.pack(anchor='w', pady=(0, 6))
        
        # Camera cards container - 增加高度以容纳更大的预览画面
        camera_cards = tk.Frame(detection_content, bg=self.colors['card'])
        camera_cards.pack(fill='both', expand=True, pady=(5, 0))
        
        # Camera 1 card
        self.cam1_card = self.create_camera_card(camera_cards, "Camera 1 (Auto)", 0)
        self.cam1_card.pack(side='left', fill='both', expand=True, padx=(0, 15))
        
        # Camera 2 card  
        self.cam2_card = self.create_camera_card(camera_cards, "Camera 2 (Auto)", 1)
        self.cam2_card.pack(side='right', fill='both', expand=True, padx=(15, 0))
        
        # Manual override option
        override_frame = tk.Frame(detection_content, bg=self.colors['card'])
        override_frame.pack(fill='x', pady=(10, 0))
        
        self.manual_mode_var = tk.BooleanVar()
        self.manual_checkbox = tk.Checkbutton(override_frame, text="Manual camera selection", 
                                            variable=self.manual_mode_var,
                                            command=self.toggle_manual_mode,
                                            bg=self.colors['card'],
                                            fg=self.colors['text_muted'],
                                            font=('SF Pro Text', 10))
        self.manual_checkbox.pack(anchor='w')
        
        # 设置区域 - 移除标题，减少间距
        settings_card = tk.Frame(main_container, bg=self.colors['card'], 
                       relief='flat', bd=1)
        settings_card.configure(highlightbackground=self.colors['border'], 
                      highlightthickness=1)
        settings_card.pack(fill='x', pady=(0, 8))
        
        # 设置内容
        settings_content = tk.Frame(settings_card, bg=self.colors['card'])
        settings_content.pack(fill='x', pady=(6, 6))
        
        # Settings in horizontal layout to save space
        settings_row = tk.Frame(settings_content, bg=self.colors['card'])
        settings_row.pack(fill='x', pady=(0, 10))
        
        # Output directory (left side) - 合并标签和输入框到一行
        output_frame = tk.Frame(settings_row, bg=self.colors['card'])
        output_frame.pack(side='left', fill='x', expand=True, padx=(0, 20))
        
        dir_input_frame = tk.Frame(output_frame, bg=self.colors['card'])
        dir_input_frame.pack(fill='x')
        
        ttk.Label(dir_input_frame, text="Output:", 
                 style='DeviceInfo.TLabel').pack(side='left', padx=(0, 10))
        
        self.output_dir_var = tk.StringVar(value=os.path.expanduser("~/Videos"))
        self.output_dir_entry = ttk.Entry(dir_input_frame, textvariable=self.output_dir_var,
                                         style='Modern.TEntry', width=40)
        self.output_dir_entry.pack(side='left', fill='x', expand=True)
        
        ttk.Button(dir_input_frame, text="Browse", 
                  command=self.browse_output_dir, 
                  style='Primary.TButton').pack(side='right', padx=(8, 0))
        
        # FPS setting (right side) - 合并标签和下拉框到一行
        fps_frame = tk.Frame(settings_row, bg=self.colors['card'])
        fps_frame.pack(side='right')
        
        ttk.Label(fps_frame, text="FPS:", 
                 style='DeviceInfo.TLabel').pack(side='left', padx=(0, 10))
        
        self.fps_var = tk.StringVar(value="30")
        fps_combo = ttk.Combobox(fps_frame, textvariable=self.fps_var,
                                values=['15', '24', '30', '48', '60'],
                                style='Modern.TCombobox', width=10, state='readonly')
        fps_combo.pack(side='left')
        
        # 控制区域 - 移除标题，减少间距
        control_card = tk.Frame(main_container, bg=self.colors['card'], 
                       relief='flat', bd=1)
        control_card.configure(highlightbackground=self.colors['border'], 
                      highlightthickness=1)
        control_card.pack(fill='x', pady=(0, 6))
        
        # 控制内容
        control_content = tk.Frame(control_card, bg=self.colors['card'])
        control_content.pack(fill='x', pady=(6, 6))
        
        # Timer display - 减少间距
        timer_frame = tk.Frame(control_content, bg=self.colors['card'])
        timer_frame.pack(fill='x', pady=(0, 8))
        
        self.timer_label = ttk.Label(timer_frame, text="00:00:00", 
                                   style='Timer.TLabel')
        self.timer_label.pack(anchor='center')
        
        # Control buttons - 减少间距
        button_frame = tk.Frame(control_content, bg=self.colors['card'])
        button_frame.pack(fill='x', pady=(0, 8))
        
        self.start_button = ttk.Button(button_frame, text="● Start Recording", 
                                     command=self.start_recording, 
                                     style='Start.TButton')
        self.start_button.pack(side='left', padx=(0, 10))
        
        self.stop_button = ttk.Button(button_frame, text="■ Stop Recording", 
                                    command=self.stop_recording, 
                                    style='Stop.TButton', state='disabled')
        self.stop_button.pack(side='left', padx=(0, 10))
        
        self.extract_button = ttk.Button(button_frame, text="📸 Export Frames", 
                                       command=self.show_extract_dialog, 
                                       style='Primary.TButton')
        self.extract_button.pack(side='left', padx=(0, 10))
        
        # Status display - 减少间距
        self.status_label = ttk.Label(control_content, text="Ready to record", 
                                    style='Status.TLabel')
        self.status_label.pack(anchor='center')
        
        # Progress bar
        self.progress = ttk.Progressbar(control_content, mode='indeterminate',
                                      length=300, style='TProgressbar')
        self.progress.pack(anchor='center', pady=(6, 0))
        
    def create_card_section(self, parent, title):
        """Create a card section with title"""
        section_frame = tk.Frame(parent, bg=self.colors['bg'])
        
        # Section title
        title_label = ttk.Label(section_frame, text=title, 
                              style='SectionTitle.TLabel')
        title_label.pack(anchor='w', pady=(0, 8))
        
        # Card container
        card = tk.Frame(section_frame, bg=self.colors['card'], 
                       relief='flat', bd=1)
        card.configure(highlightbackground=self.colors['border'], 
                      highlightthickness=1)
        card.pack(fill='both', expand=True)
        
        return section_frame  # 返回section_frame
        
    def create_camera_card(self, parent, title, index):
        """Create a camera selection card"""
        card = tk.Frame(parent, bg=self.colors['card'], 
                       relief='flat', bd=1)
        card.configure(highlightbackground=self.colors['border'], 
                      highlightthickness=1)
        
        # Card content with reduced padding
        content = tk.Frame(card, bg=self.colors['card'])
        content.pack(fill='both', expand=True, padx=15, pady=15)
        
        # 摄像头信息 - 合并标题和设备信息到一行
        info_frame = tk.Frame(content, bg=self.colors['card'])
        info_frame.pack(fill='x', pady=(0, 10))
        
        title_label = ttk.Label(info_frame, text=title, 
                              style='DeviceInfo.TLabel')
        title_label.pack(side='left')
        
        # Auto-detected device display
        if index == 0:
            self.camera1_auto_display = ttk.Label(info_frame, text=" - Auto-detecting...", 
                                                style='DeviceName.TLabel')
            self.camera1_auto_display.pack(side='left')
        else:
            self.camera2_auto_display = ttk.Label(info_frame, text=" - Auto-detecting...", 
                                                style='DeviceName.TLabel')
            self.camera2_auto_display.pack(side='left')
        
        # Manual device selection (hidden by default)
        manual_frame = tk.Frame(content, bg=self.colors['card'])
        if index == 0:
            self.camera1_manual_frame = manual_frame
        else:
            self.camera2_manual_frame = manual_frame
        
        # Device selection
        device_label = ttk.Label(manual_frame, text="Device", 
                               style='DeviceName.TLabel')
        device_label.pack(anchor='w', pady=(15, 5))
        
        if index == 0:
            self.camera1_var = tk.StringVar()
            self.camera1_combo = ttk.Combobox(manual_frame, textvariable=self.camera1_var,
                                            style='Modern.TCombobox', 
                                            state='readonly', width=25)
            self.camera1_combo.pack(anchor='w')
            self.camera1_combo.bind('<<ComboboxSelected>>', lambda e: self.update_resolutions(0))
        else:
            self.camera2_var = tk.StringVar()
            self.camera2_combo = ttk.Combobox(manual_frame, textvariable=self.camera2_var,
                                            style='Modern.TCombobox', 
                                            state='readonly', width=25)
            self.camera2_combo.pack(anchor='w')
            self.camera2_combo.bind('<<ComboboxSelected>>', lambda e: self.update_resolutions(1))
        
        # Resolution selection
        res_label = ttk.Label(manual_frame, text="Resolution", 
                            style='DeviceName.TLabel')
        res_label.pack(anchor='w', pady=(15, 5))
        
        if index == 0:
            self.resolution1_var = tk.StringVar(value="1920x1080")
            self.resolution1_combo = ttk.Combobox(manual_frame, textvariable=self.resolution1_var,
                                                style='Modern.TCombobox', 
                                                state='readonly', width=25)
            self.resolution1_combo.pack(anchor='w')
            self.resolution1_combo.bind('<<ComboboxSelected>>', lambda e: self.update_preview_resolution(0))
        else:
            self.resolution2_var = tk.StringVar(value="1920x1080")
            self.resolution2_combo = ttk.Combobox(manual_frame, textvariable=self.resolution2_var,
                                                style='Modern.TCombobox', 
                                                state='readonly', width=25)
            self.resolution2_combo.pack(anchor='w')
            self.resolution2_combo.bind('<<ComboboxSelected>>', lambda e: self.update_preview_resolution(1))
        
        # Rotation selection
        rotation_label = ttk.Label(manual_frame, text="Rotation", 
                                 style='DeviceName.TLabel')
        rotation_label.pack(anchor='w', pady=(15, 5))
        
        if index == 0:
            self.rotation1_var = tk.StringVar(value="0°")
            self.rotation1_combo = ttk.Combobox(manual_frame, textvariable=self.rotation1_var,
                                              values=["0°", "90°", "180°", "270°"],
                                              style='Modern.TCombobox', 
                                              state='readonly', width=25)
            self.rotation1_combo.pack(anchor='w')
            self.rotation1_combo.bind('<<ComboboxSelected>>', lambda e: self.update_rotation(0))
        else:
            self.rotation2_var = tk.StringVar(value="0°")
            self.rotation2_combo = ttk.Combobox(manual_frame, textvariable=self.rotation2_var,
                                              values=["0°", "90°", "180°", "270°"],
                                              style='Modern.TCombobox', 
                                              state='readonly', width=25)
            self.rotation2_combo.pack(anchor='w')
            self.rotation2_combo.bind('<<ComboboxSelected>>', lambda e: self.update_rotation(1))
        
        # Preview display - 使用更大的预览区域
        preview_frame = tk.Frame(content, bg=self.colors['card'])
        preview_frame.pack(fill='both', expand=True, pady=(15, 0))
        
        if index == 0:
            self.preview_label1 = tk.Label(preview_frame, text="Camera 1 Preview\n\n摄像头画面将显示在这里\n帮助调整摄像头位置", 
                                         bg=self.colors['border'], 
                                         fg=self.colors['text_muted'],
                                         font=('SF Pro Text', 10),
                                         relief='solid', bd=1,
                                         justify='center',
                                         width=60, height=17)  # 调整为16:9等比的尺寸
            self.preview_label1.pack(fill='both', expand=True, padx=3, pady=3)
        else:
            self.preview_label2 = tk.Label(preview_frame, text="Camera 2 Preview\n\n摄像头画面将显示在这里\n帮助调整摄像头位置", 
                                         bg=self.colors['border'], 
                                         fg=self.colors['text_muted'],
                                         font=('SF Pro Text', 10),
                                         relief='solid', bd=1,
                                         justify='center',
                                         width=60, height=17)  # 调整为16:9等比的尺寸
            self.preview_label2.pack(fill='both', expand=True, padx=3, pady=3)
        
        # Device info display
        if index == 0:
            self.device1_path = ttk.Label(content, text="", 
                                        style='DevicePath.TLabel')
            self.device1_path.pack(anchor='w', pady=(10, 0))
            
            self.device1_info = ttk.Label(content, text="", 
                                        style='DeviceName.TLabel')
            self.device1_info.pack(anchor='w', pady=(2, 0))
        else:
            self.device2_path = ttk.Label(content, text="", 
                                        style='DevicePath.TLabel')
            self.device2_path.pack(anchor='w', pady=(10, 0))
            
            self.device2_info = ttk.Label(content, text="", 
                                        style='DeviceName.TLabel')
            self.device2_info.pack(anchor='w', pady=(2, 0))
        
        return card
        
            
    def load_camera_info(self):
        """Load camera information using camera_utils module"""
        # Use the new unified camera detection
        detected_cameras = CameraManager.detect_cameras()
        
        # Convert to the format expected by existing code
        self.camera_devices = []
        self.available_resolutions = {}
        
        for camera in detected_cameras:
            device_dict = camera.to_dict()
            self.camera_devices.append(device_dict)
            
            # Convert resolution format for backward compatibility
            # Keep original order (largest first) but also provide display info
            resolution_strings = [res['resolution'] for res in camera.resolutions]
            resolution_with_fps = [res['display'] for res in camera.resolutions]
            
            # Store both formats for flexibility
            self.available_resolutions[device_dict['path']] = resolution_strings
            self.available_resolutions[device_dict['path'] + '_display'] = resolution_with_fps
            
            print(f"Found camera: {camera.name} at {camera.get_primary_path()}")
        
        # Update combo boxes
        device_list = [device['display_name'] for device in self.camera_devices]
        
        self.camera1_combo['values'] = device_list
        self.camera2_combo['values'] = device_list
        
        # Set default values
        if len(device_list) >= 2:
            self.camera1_var.set(device_list[0])
            self.camera2_var.set(device_list[1])
            self.update_resolutions(0)
            self.update_resolutions(1)
            self.update_device_info(0)
            self.update_device_info(1)
        elif len(device_list) == 1:
            self.camera1_var.set(device_list[0])
            self.update_resolutions(0)
            self.update_device_info(0)
            self.update_status("⚠️ Only one camera detected")
        else:
            self.update_status("❌ No cameras detected")
            
    def auto_assign_cameras(self):
        """Automatically assign cameras to Camera 1 and Camera 2"""
        if len(self.camera_devices) >= 2:
            # Auto-assign first two cameras
            cam1_device = self.camera_devices[0]
            cam2_device = self.camera_devices[1]
            
            # Update auto display with device name - 在同一行显示
            self.camera1_auto_display.config(text=f" - [OK] {cam1_device['name']}")
            self.camera2_auto_display.config(text=f" - [OK] {cam2_device['name']}")
            
            # Update device info
            self.device1_path.config(text=f"📹 {cam1_device['path']}")
            self.device2_path.config(text=f"📹 {cam2_device['path']}")
            
            info1 = cam1_device['info']
            info1_text = f"Driver: {info1.get('driver', 'Unknown')}"
            if 'bus' in info1:
                info1_text += f" | Bus: {info1['bus']}"
            self.device1_info.config(text=info1_text)
            
            info2 = cam2_device['info']
            info2_text = f"Driver: {info2.get('driver', 'Unknown')}"
            if 'bus' in info2:
                info2_text += f" | Bus: {info2['bus']}"
            self.device2_info.config(text=info2_text)
            
            # Set resolution variables for auto mode
            self.resolution1_var.set("1920x1080")
            self.resolution2_var.set("1920x1080")
            
            # Update status
            self.detection_status.config(text="[OK] Auto-detected 2 cameras successfully")
            
            # Start preview for both cameras
            self.start_camera_preview()
            
        elif len(self.camera_devices) == 1:
            # Only one camera available
            cam1_device = self.camera_devices[0]
            self.camera1_auto_display.config(text=f" - [OK] {cam1_device['name']}")
            self.camera2_auto_display.config(text=" - [X] No second camera")
            
            self.device1_path.config(text=f"📹 {cam1_device['path']}")
            self.device2_path.config(text="")
            
            info1 = cam1_device['info']
            info1_text = f"Driver: {info1.get('driver', 'Unknown')}"
            if 'bus' in info1:
                info1_text += f" | Bus: {info1['bus']}"
            self.device1_info.config(text=info1_text)
            self.device2_info.config(text="")
            
            # 设置单摄像头模式的分辨率
            self.resolution1_var.set("1920x1080")
            
            self.detection_status.config(text="[!] Only 1 camera detected - need 2 for dual recording")
            
            # Start preview for camera 1 only
            self.start_camera_preview()
        else:
            # No cameras found
            self.camera1_auto_display.config(text=" - [X] No camera detected")
            self.camera2_auto_display.config(text=" - [X] No camera detected")
            self.device1_path.config(text="")
            self.device2_path.config(text="")
            self.device1_info.config(text="")
            self.device2_info.config(text="")
            self.detection_status.config(text="[X] No cameras detected")
            
            # Stop any existing preview
            self.stop_preview()
            
    def toggle_manual_mode(self):
        """Toggle between auto and manual camera selection"""
        if self.manual_mode_var.get():
            # Switch to manual mode
            self.camera1_auto_display.pack_forget()
            self.camera2_auto_display.pack_forget()
            self.camera1_manual_frame.pack(fill='x', pady=(10, 0))
            self.camera2_manual_frame.pack(fill='x', pady=(10, 0))
            self.detection_status.config(text="📋 Manual camera selection mode")
        else:
            # Switch to auto mode
            self.camera1_manual_frame.pack_forget()
            self.camera2_manual_frame.pack_forget()
            self.camera1_auto_display.pack(anchor='w', pady=(15, 0))
            self.camera2_auto_display.pack(anchor='w', pady=(15, 0))
            self.auto_assign_cameras()
            
    def update_resolutions(self, camera_index):
        """Update available resolutions for selected camera"""
        if camera_index == 0:
            device_display = self.camera1_var.get()
            combo = self.resolution1_combo
        else:
            device_display = self.camera2_var.get()
            combo = self.resolution2_combo
        
        if device_display:
            # Find device path
            device_path = None
            for device in self.camera_devices:
                if device['display_name'] == device_display:
                    device_path = device['path']
                    break
            
            if device_path and device_path in self.available_resolutions:
                # Use display format with FPS info if available
                display_key = device_path + '_display'
                if display_key in self.available_resolutions:
                    resolutions_display = self.available_resolutions[display_key]
                    combo['values'] = resolutions_display
                    if resolutions_display:
                        # Set default to 1080p if available, otherwise first resolution
                        default_resolution = None
                        for res in resolutions_display:
                            if "1920x1080" in res:
                                default_resolution = res
                                break
                        if default_resolution:
                            combo.set(default_resolution)
                        else:
                            combo.set(resolutions_display[0])
                else:
                    # Fallback to simple resolution strings
                    resolutions = self.available_resolutions[device_path]
                    combo['values'] = resolutions
                    if resolutions:
                        if "1920x1080" in resolutions:
                            combo.set("1920x1080")
                        else:
                            combo.set(resolutions[0])
                        
    def update_device_info(self, camera_index):
        """Update device information display"""
        if camera_index == 0:
            device_display = self.camera1_var.get()
            path_label = self.device1_path
            info_label = self.device1_info
        else:
            device_display = self.camera2_var.get()
            path_label = self.device2_path
            info_label = self.device2_info
        
        if device_display:
            for device in self.camera_devices:
                if device['display_name'] == device_display:
                    # Display device path prominently
                    path_label.config(text=f"📹 {device['path']}")
                    
                    # Display additional device info
                    info = device['info']
                    info_text = f"Driver: {info.get('driver', 'Unknown')}"
                    if 'bus' in info:
                        info_text += f" | Bus: {info['bus']}"
                    info_label.config(text=info_text)
                    break
                    
    def update_rotation(self, camera_index):
        """Update camera rotation setting"""
        if camera_index == 0:
            rotation_str = self.rotation1_var.get()
            self.camera1_rotation = int(rotation_str.replace('°', ''))
        else:
            rotation_str = self.rotation2_var.get()
            self.camera2_rotation = int(rotation_str.replace('°', ''))
        
        print(f"Camera {camera_index + 1} rotation set to {rotation_str}")
        
    def rotate_frame(self, frame, rotation):
        """Rotate frame by specified degrees"""
        if rotation == 0:
            return frame
        elif rotation == 90:
            return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        elif rotation == 180:
            return cv2.rotate(frame, cv2.ROTATE_180)
        elif rotation == 270:
            return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        else:
            return frame
                    
    def browse_output_dir(self):
        """Browse for output directory"""
        directory = filedialog.askdirectory(initialdir=self.output_dir_var.get())
        if directory:
            self.output_dir_var.set(directory)
            
    def update_status(self, message):
        """Update status label"""
        self.status_label.config(text=message)
        self.root.update_idletasks()
        
    def update_timer(self):
        """Update recording timer"""
        if self.recording and self.start_time:
            elapsed = time.time() - self.start_time
            hours = int(elapsed // 3600)
            minutes = int((elapsed % 3600) // 60)
            seconds = int(elapsed % 60)
            time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            self.timer_label.config(text=time_str)
        
        # Schedule next update
        self.root.after(1000, self.update_timer)
        
    def update_shared_preview(self):
        """更新录制时的共享预览画面"""
        if not self.preview_active or not self.recording:
            return
            
        try:
            # 从队列获取最新帧（非阻塞）
            frame1 = None
            frame2 = None
            
            # 获取队列中最新的帧
            try:
                frame1 = self.frame_queue1.get_nowait()
            except queue.Empty:
                pass
                
            try:
                frame2 = self.frame_queue2.get_nowait()
            except queue.Empty:
                pass
            
            # 更新摄像头1预览
            if frame1 is not None:
                # 转换为tkinter可显示的格式
                frame1_rgb = cv2.cvtColor(frame1, cv2.COLOR_BGR2RGB)
                frame1_pil = Image.fromarray(frame1_rgb)
                # 从1920x1080缩放到预览尺寸
                frame1_pil = frame1_pil.resize((480, 270), Image.LANCZOS)
                frame1_tk = ImageTk.PhotoImage(frame1_pil)
                
                # 更新预览标签
                self.preview_label1.config(image=frame1_tk)
                self.preview_label1.image = frame1_tk
                    
            # 更新摄像头2预览
            if frame2 is not None:
                # 转换为tkinter可显示的格式
                frame2_rgb = cv2.cvtColor(frame2, cv2.COLOR_BGR2RGB)
                frame2_pil = Image.fromarray(frame2_rgb)
                # 从1920x1080缩放到预览尺寸  
                frame2_pil = frame2_pil.resize((480, 270), Image.LANCZOS)
                frame2_tk = ImageTk.PhotoImage(frame2_pil)
                
                # 更新预览标签
                self.preview_label2.config(image=frame2_tk)
                self.preview_label2.image = frame2_tk
                    
        except Exception as e:
            print(f"Shared preview update error: {e}")
            
        # 录制时更快的刷新率（100ms）以获得流畅预览
        if self.preview_active and self.recording:
            self.root.after(100, self.update_shared_preview)
        
    def get_camera_index(self, device_display):
        """Get camera path from display name with fallback support"""
        for device in self.camera_devices:
            if device['display_name'] == device_display:
                # Return a tuple: (primary_path, fallback_path, use_by_id)
                return {
                    'primary': device['path'],
                    'fallback': device.get('fallback_path', device['path']),
                    'use_by_id': device.get('use_by_id', False),
                    'index': device['index']
                }
        return {'primary': 0, 'fallback': 0, 'use_by_id': False, 'index': 0}
    
        
    def parse_resolution(self, resolution_string):
        """Parse resolution string to width, height tuple"""
        try:
            # Handle both formats: "1920x1080" and "1920x1080 @30fps"
            if ' @' in resolution_string:
                # Extract resolution part before FPS info
                resolution_part = resolution_string.split(' @')[0]
            else:
                resolution_part = resolution_string
                
            width, height = map(int, resolution_part.split('x'))
            return width, height
        except:
            return 1920, 1080
            
    def start_recording(self):
        """Start recording from both cameras"""
        if self.manual_mode_var.get():
            # Manual mode - check combo box selections
            if not self.camera1_var.get() or not self.camera2_var.get():
                messagebox.showerror("Error", "Please select both cameras!")
                return
            cam1_info = self.get_camera_index(self.camera1_var.get())
            cam2_info = self.get_camera_index(self.camera2_var.get())
        else:
            # Auto mode - use first two available cameras
            if len(self.camera_devices) < 2:
                messagebox.showerror("Error", "Need at least 2 cameras for dual recording!")
                return
            cam1_info = {
                'primary': self.camera_devices[0]['path'],
                'fallback': self.camera_devices[0].get('fallback_path', self.camera_devices[0]['path']),
                'use_by_id': self.camera_devices[0].get('use_by_id', False),
                'index': self.camera_devices[0]['index']
            }
            cam2_info = {
                'primary': self.camera_devices[1]['path'],
                'fallback': self.camera_devices[1].get('fallback_path', self.camera_devices[1]['path']),
                'use_by_id': self.camera_devices[1].get('use_by_id', False),
                'index': self.camera_devices[1]['index']
            }
            
        if not self.output_dir_var.get():
            messagebox.showerror("Error", "Please select output directory!")
            return
            
        # Create output directory with timestamp
        self.recording_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_dir = os.path.join(self.output_dir_var.get(), f"basketball_recording_{self.recording_timestamp}")
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Camera indices already determined above
        
        # Get resolutions
        width1, height1 = self.parse_resolution(self.resolution1_var.get())
        width2, height2 = self.parse_resolution(self.resolution2_var.get())
        
        # Get FPS
        fps = int(self.fps_var.get())
        
        try:
            # 停止当前预览（释放preview专用的摄像头）
            self.stop_preview()
            
            # Initialize cameras with intelligent path selection (用于录制和共享预览)
            self.camera1 = open_camera_with_fallback(cam1_info)
            self.camera2 = open_camera_with_fallback(cam2_info)
            
            # Set MJPEG format for better performance
            self.camera1.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            self.camera2.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            
            # Set camera properties
            self.camera1.set(cv2.CAP_PROP_FRAME_WIDTH, width1)
            self.camera1.set(cv2.CAP_PROP_FRAME_HEIGHT, height1)
            self.camera1.set(cv2.CAP_PROP_FPS, fps)
            
            self.camera2.set(cv2.CAP_PROP_FRAME_WIDTH, width2)
            self.camera2.set(cv2.CAP_PROP_FRAME_HEIGHT, height2)
            self.camera2.set(cv2.CAP_PROP_FPS, fps)
            
            # Set buffer size to reduce latency
            self.camera1.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self.camera2.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            # Check if cameras opened successfully
            if not self.camera1.isOpened() or not self.camera2.isOpened():
                raise Exception("Failed to open cameras")
            
            # Initialize video writers with timestamp-based names
            fourcc = cv2.VideoWriter_fourcc(*'MJPG')
            video1_path = os.path.join(self.output_dir, f"camera1_{self.recording_timestamp}.avi")
            video2_path = os.path.join(self.output_dir, f"camera2_{self.recording_timestamp}.avi")
            
            self.writer1 = cv2.VideoWriter(video1_path, fourcc, fps, (width1, height1))
            self.writer2 = cv2.VideoWriter(video2_path, fourcc, fps, (width2, height2))
            
            # 清空帧队列
            while not self.frame_queue1.empty():
                try:
                    self.frame_queue1.get_nowait()
                except queue.Empty:
                    break
            while not self.frame_queue2.empty():
                try:
                    self.frame_queue2.get_nowait()
                except queue.Empty:
                    break
            
            # Start recording
            self.recording = True
            self.start_time = time.time()
            
            # 启动共享预览（从录制帧数据中获取）
            self.preview_active = True
            self.update_shared_preview()
            
            # Update UI
            self.start_button.config(state='disabled')
            self.stop_button.config(state='normal')
            self.progress.start()
            self.update_status("🔴 Recording in progress...")
            
            # Start recording thread
            self.recording_thread = threading.Thread(target=self.record_videos)
            self.recording_thread.daemon = True
            self.recording_thread.start()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start recording: {str(e)}")
            self.cleanup_recording()
            # 如果录制失败，重新启动预览
            self.start_preview()
            
    def record_videos(self):
        """Recording loop running in separate thread"""
        frame_count = 0
        
        while self.recording:
            try:
                ret1, frame1 = self.camera1.read()
                ret2, frame2 = self.camera2.read()
                
                if ret1 and ret2:
                    # 应用旋转
                    rotated_frame1 = self.rotate_frame(frame1, self.camera1_rotation)
                    rotated_frame2 = self.rotate_frame(frame2, self.camera2_rotation)
                    
                    # 写入录制文件（使用旋转后的帧）
                    self.writer1.write(rotated_frame1)
                    self.writer2.write(rotated_frame2)
                    frame_count += 1
                    
                    # 将帧数据推送到预览队列（非阻塞）
                    try:
                        # 如果队列满了，丢弃旧帧以保持实时性
                        if self.frame_queue1.full():
                            self.frame_queue1.get_nowait()
                        self.frame_queue1.put_nowait(rotated_frame1.copy())
                        
                        if self.frame_queue2.full():
                            self.frame_queue2.get_nowait()
                        self.frame_queue2.put_nowait(rotated_frame2.copy())
                    except queue.Full:
                        # 队列满时跳过预览帧，优先保证录制
                        pass
                else:
                    print("Failed to read frames from cameras")
                    break
                    
            except Exception as e:
                print(f"Error in recording loop: {str(e)}")
                break
                
        print(f"Recording stopped. Total frames recorded: {frame_count}")
        
    def stop_recording(self):
        """Stop recording"""
        self.recording = False
        self.preview_active = False  # 停止共享预览
        
        # Wait for recording thread to finish
        if hasattr(self, 'recording_thread'):
            self.recording_thread.join(timeout=5)
            
        # Cleanup
        self.cleanup_recording()
        
        # Update UI
        self.start_button.config(state='normal')
        self.stop_button.config(state='disabled')
        self.progress.stop()
        self.update_status("[OK] Recording completed successfully")
        
        # Save recording info
        self.save_recording_info()
        
        # 清空帧队列
        while not self.frame_queue1.empty():
            try:
                self.frame_queue1.get_nowait()
            except queue.Empty:
                break
        while not self.frame_queue2.empty():
            try:
                self.frame_queue2.get_nowait()
            except queue.Empty:
                break
        
        # 重新启动普通预览
        self.start_preview()
        
    def cleanup_recording(self):
        """Clean up recording resources"""
        if self.writer1:
            self.writer1.release()
            self.writer1 = None
            
        if self.writer2:
            self.writer2.release()
            self.writer2 = None
            
        if self.camera1:
            self.camera1.release()
            self.camera1 = None
            
        if self.camera2:
            self.camera2.release()
            self.camera2 = None
            
    def save_recording_info(self):
        """Save recording information to JSON file"""
        if not self.output_dir or not self.start_time or not self.recording_timestamp:
            return
        
        info = {
            "recording_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "duration": time.time() - self.start_time,
            "camera1": {
                "device": self.camera1_var.get(),
                "resolution": self.resolution1_var.get(),
                "video_file": f"camera1_{self.recording_timestamp}.avi"
            },
            "camera2": {
                "device": self.camera2_var.get(),
                "resolution": self.resolution2_var.get(),
                "video_file": f"camera2_{self.recording_timestamp}.avi"
            },
            "fps": int(self.fps_var.get()),
            "output_directory": self.output_dir
        }
        
        info_file = os.path.join(self.output_dir, "recording_info.json")
        with open(info_file, 'w') as f:
            json.dump(info, f, indent=2)
            
    def show_extract_dialog(self):
        """显示静帧导出对话框"""
        # 检查是否有录制的视频文件
        video_files = []
        
        # 搜索当前工作目录和子目录中的视频文件
        search_dir = self.output_dir_var.get() if self.output_dir_var.get() else os.getcwd()
        for root, _, files in os.walk(search_dir):
            for file in files:
                if file.endswith(('.avi', '.mp4', '.mov', '.mkv')):
                    video_files.append(os.path.join(root, file))
        
        if not video_files:
            messagebox.showwarning("Warning", "No video files found! Please record some videos first.")
            return
            
        # 创建对话框
        dialog = tk.Toplevel(self.root)
        dialog.title("Export Video Frames")
        dialog.geometry("600x500")
        dialog.configure(bg=self.colors['bg'])
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 主框架
        main_frame = tk.Frame(dialog, bg=self.colors['bg'])
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # 标题
        title_label = ttk.Label(main_frame, text="Export Video Frames to Images", 
                              style='SectionTitle.TLabel')
        title_label.pack(anchor='w', pady=(0, 15))
        
        # 录制文件夹选择
        folder_frame = tk.Frame(main_frame, bg=self.colors['bg'])
        folder_frame.pack(fill='x', pady=(0, 15))
        
        ttk.Label(folder_frame, text="Select Recording Folder:", 
                 style='DeviceInfo.TLabel').pack(anchor='w', pady=(0, 5))
        
        # 获取录制文件夹列表（包含camera1和camera2视频的文件夹）
        recording_folders = []
        for video_file in video_files:
            folder = os.path.dirname(video_file)
            if folder not in recording_folders:
                # 检查该文件夹是否包含双摄像头录制
                folder_files = os.listdir(folder)
                has_camera1 = any('camera1' in f for f in folder_files if f.endswith(('.avi', '.mp4', '.mov', '.mkv')))
                has_camera2 = any('camera2' in f for f in folder_files if f.endswith(('.avi', '.mp4', '.mov', '.mkv')))
                if has_camera1 and has_camera2:
                    recording_folders.append(folder)
        
        folder_var = tk.StringVar()
        folder_combo = ttk.Combobox(folder_frame, textvariable=folder_var,
                                  values=recording_folders, style='Modern.TCombobox',
                                  state='readonly', width=70)
        folder_combo.pack(fill='x')
        if recording_folders:
            folder_combo.set(recording_folders[0])
        
        # 输出根目录选择
        output_frame = tk.Frame(main_frame, bg=self.colors['bg'])
        output_frame.pack(fill='x', pady=(0, 15))
        
        ttk.Label(output_frame, text="Output Root Directory:", 
                 style='DeviceInfo.TLabel').pack(anchor='w', pady=(0, 5))
        
        output_dir_frame = tk.Frame(output_frame, bg=self.colors['bg'])
        output_dir_frame.pack(fill='x')
        
        output_var = tk.StringVar(value=os.path.join(search_dir, "exported_frames"))
        output_entry = ttk.Entry(output_dir_frame, textvariable=output_var,
                               style='Modern.TEntry')
        output_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))
        
        def browse_output():
            directory = filedialog.askdirectory(initialdir=output_var.get())
            if directory:
                output_var.set(directory)
        
        ttk.Button(output_dir_frame, text="Browse", 
                  command=browse_output, 
                  style='Primary.TButton').pack(side='right')
        
        # 间隔设置
        interval_frame = tk.Frame(main_frame, bg=self.colors['bg'])
        interval_frame.pack(fill='x', pady=(0, 15))
        
        ttk.Label(interval_frame, text="Frame Interval (extract every N frames):", 
                 style='DeviceInfo.TLabel').pack(anchor='w', pady=(0, 5))
        
        interval_var = tk.StringVar(value="30")
        interval_spin = tk.Spinbox(interval_frame, from_=1, to=300, 
                                 textvariable=interval_var, width=10)
        interval_spin.pack(anchor='w')
        
        # 摄像头选择
        camera_frame = tk.Frame(main_frame, bg=self.colors['bg'])
        camera_frame.pack(fill='x', pady=(0, 15))
        
        ttk.Label(camera_frame, text="Export from cameras:", 
                 style='DeviceInfo.TLabel').pack(anchor='w', pady=(0, 5))
        
        camera_options_frame = tk.Frame(camera_frame, bg=self.colors['bg'])
        camera_options_frame.pack(anchor='w')
        
        camera1_var = tk.BooleanVar(value=True)
        camera2_var = tk.BooleanVar(value=True)
        
        tk.Checkbutton(camera_options_frame, text="Camera 1", variable=camera1_var,
                      bg=self.colors['bg'], fg=self.colors['text']).pack(side='left', padx=(0, 20))
        tk.Checkbutton(camera_options_frame, text="Camera 2", variable=camera2_var,
                      bg=self.colors['bg'], fg=self.colors['text']).pack(side='left')
        
        # 进度显示
        progress_frame = tk.Frame(main_frame, bg=self.colors['bg'])
        progress_frame.pack(fill='x', pady=(0, 15))
        
        # Camera 1 进度
        ttk.Label(progress_frame, text="Camera 1 Progress:", 
                 style='DeviceInfo.TLabel').pack(anchor='w')
        progress_bar1 = ttk.Progressbar(progress_frame, mode='determinate', length=500)
        progress_bar1.pack(fill='x', pady=(2, 8))
        
        # Camera 2 进度  
        ttk.Label(progress_frame, text="Camera 2 Progress:", 
                 style='DeviceInfo.TLabel').pack(anchor='w')
        progress_bar2 = ttk.Progressbar(progress_frame, mode='determinate', length=500)
        progress_bar2.pack(fill='x', pady=(2, 8))
        
        progress_label = ttk.Label(progress_frame, text="Ready to extract frames", 
                                 style='DeviceInfo.TLabel')
        progress_label.pack(anchor='w', pady=(5, 0))
        
        # 按钮框架
        button_frame = tk.Frame(main_frame, bg=self.colors['bg'])
        button_frame.pack(fill='x', pady=(10, 0))
        
        def start_extraction():
            recording_folder = folder_var.get()
            output_root = output_var.get()
            interval = int(interval_var.get())
            
            if not recording_folder:
                messagebox.showerror("Error", "Please select a recording folder!")
                return
                
            if not camera1_var.get() and not camera2_var.get():
                messagebox.showerror("Error", "Please select at least one camera!")
                return
                
            # 在新线程中执行抽帧
            extract_thread = threading.Thread(
                target=self.extract_dual_frames_thread,
                args=(recording_folder, output_root, interval, 
                     camera1_var.get(), camera2_var.get(),
                     progress_bar1, progress_bar2, progress_label)
            )
            extract_thread.daemon = True
            extract_thread.start()
        
        ttk.Button(button_frame, text="Start Extraction", 
                  command=start_extraction, 
                  style='Start.TButton').pack(side='left', padx=(0, 10))
        
        ttk.Button(button_frame, text="Close", 
                  command=dialog.destroy, 
                  style='Primary.TButton').pack(side='right')
                  
    def extract_dual_frames_thread(self, recording_folder, output_root, interval, 
                                  extract_cam1, extract_cam2, 
                                  progress_bar1, progress_bar2, progress_label):
        """在单独线程中执行双摄像头帧提取"""
        try:
            # 生成带时间戳的输出文件夹名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            folder_name = os.path.basename(recording_folder)
            export_folder = os.path.join(output_root, f"frames_export_{timestamp}_{folder_name}")
            
            # 查找视频文件
            camera1_video = None
            camera2_video = None
            
            for file in os.listdir(recording_folder):
                if 'camera1' in file and file.endswith(('.avi', '.mp4', '.mov', '.mkv')):
                    camera1_video = os.path.join(recording_folder, file)
                elif 'camera2' in file and file.endswith(('.avi', '.mp4', '.mov', '.mkv')):
                    camera2_video = os.path.join(recording_folder, file)
            
            total_extracted = 0
            
            # 提取Camera 1
            if extract_cam1 and camera1_video:
                self.root.after(0, lambda: progress_label.config(text="Extracting frames from Camera 1..."))
                camera1_output = os.path.join(export_folder, "camera1")
                count = self.extract_frames_from_video(camera1_video, camera1_output, interval, 
                                                     progress_bar1, "Camera 1")
                total_extracted += count
                
            # 提取Camera 2  
            if extract_cam2 and camera2_video:
                self.root.after(0, lambda: progress_label.config(text="Extracting frames from Camera 2..."))
                camera2_output = os.path.join(export_folder, "camera2")
                count = self.extract_frames_from_video(camera2_video, camera2_output, interval, 
                                                     progress_bar2, "Camera 2") 
                total_extracted += count
                
            # 完成提示
            self.root.after(0, lambda: progress_label.config(
                text=f"Completed! Extracted {total_extracted} total frames"))
            self.root.after(0, lambda: messagebox.showinfo(
                "Success", f"Successfully extracted {total_extracted} frames!\n\nOutput: {export_folder}"))
                
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Frame extraction failed: {str(e)}"))
            
    def extract_frames_from_video(self, video_path, output_dir, interval, progress_bar, camera_name):
        """从单个视频提取帧"""
        try:
            # 创建输出目录
            os.makedirs(output_dir, exist_ok=True)
            
            # 打开视频文件
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return 0
            
            # 获取视频信息
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            
            frame_count = 0
            extracted_count = 0
            
            # 更新进度条最大值
            max_extracts = total_frames // interval
            self.root.after(0, lambda: progress_bar.configure(maximum=max_extracts))
            
            # 从视频文件名中提取基础名称（去掉扩展名）
            video_basename = os.path.splitext(os.path.basename(video_path))[0]
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # 每隔指定帧数提取一帧
                if frame_count % interval == 0:
                    timestamp = frame_count / fps
                    # 使用视频文件名作为前缀，再加上帧数信息
                    filename = f"{video_basename}_frame_{frame_count:06d}_t{timestamp:.2f}s.jpg"
                    output_path = os.path.join(output_dir, filename)
                    
                    # 保存帧并检查是否成功
                    success = cv2.imwrite(output_path, frame)
                    if success:
                        extracted_count += 1
                        print(f"Extracted frame {frame_count} to {filename}")
                    else:
                        print(f"Failed to save frame {frame_count} to {filename}")
                    
                    # 更新进度（修复lambda变量捕获）
                    current_count = extracted_count
                    self.root.after(0, lambda c=current_count: progress_bar.configure(value=c))
                
                frame_count += 1
            
            cap.release()
            return extracted_count
            
        except Exception as e:
            print(f"Error extracting from {video_path}: {e}")
            return 0
        
    def start_preview(self):
        """开始预览功能"""
        self.preview_active = True
        self.update_preview()
        
    def stop_preview(self):
        """停止预览功能"""
        self.preview_active = False
        if self.preview_camera1:
            self.preview_camera1.release()
            self.preview_camera1 = None
        if self.preview_camera2:
            self.preview_camera2.release()
            self.preview_camera2 = None
            
    def start_camera_preview(self):
        """根据检测到的摄像头启动预览"""
        if len(self.camera_devices) >= 1:
            # 为第一个摄像头启动预览
            self.init_preview_camera(0)
            
        if len(self.camera_devices) >= 2:
            # 为第二个摄像头启动预览
            self.init_preview_camera(1)
            
    def init_preview_camera(self, camera_index):
        """初始化预览摄像头"""
        try:
            device_index = self.camera_devices[camera_index]['index']
            
            # 获取用户选择的分辨率
            if camera_index == 0:
                resolution_str = self.resolution1_var.get()
            else:
                resolution_str = self.resolution2_var.get()
            
            # 解析分辨率
            width, height = self.parse_resolution(resolution_str) if resolution_str else (1920, 1080)
            
            if camera_index == 0:
                if self.preview_camera1:
                    self.preview_camera1.release()
                self.preview_camera1 = cv2.VideoCapture(device_index)
                if self.preview_camera1.isOpened():
                    # 设置预览分辨率 - 使用用户选择的分辨率
                    self.preview_camera1.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                    self.preview_camera1.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                    self.preview_camera1.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
                    self.preview_camera1.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    print(f"Camera 1 preview set to {width}x{height}")
            else:
                if self.preview_camera2:
                    self.preview_camera2.release()
                self.preview_camera2 = cv2.VideoCapture(device_index)
                if self.preview_camera2.isOpened():
                    # 设置预览分辨率 - 使用用户选择的分辨率
                    self.preview_camera2.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                    self.preview_camera2.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                    self.preview_camera2.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
                    self.preview_camera2.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    print(f"Camera 2 preview set to {width}x{height}")
                    
        except Exception as e:
            print(f"Failed to initialize preview camera {camera_index}: {e}")
            
    def update_preview(self):
        """更新预览画面"""
        if not self.preview_active:
            return
            
        try:
            # 更新摄像头1预览
            if self.preview_camera1 and self.preview_camera1.isOpened():
                ret1, frame1 = self.preview_camera1.read()
                if ret1:
                    # 转换为tkinter可显示的格式
                    frame1_rgb = cv2.cvtColor(frame1, cv2.COLOR_BGR2RGB)
                    frame1_pil = Image.fromarray(frame1_rgb)
                    # 动态调整预览尺寸以适应不同分辨率
                    # 计算合适的预览尺寸（保持宽高比，最大不超过480x270）
                    img_h, img_w = frame1.shape[:2]
                    scale = min(480/img_w, 270/img_h)
                    preview_w = int(img_w * scale)
                    preview_h = int(img_h * scale)
                    frame1_pil = frame1_pil.resize((preview_w, preview_h), Image.LANCZOS)
                    # print(f"Camera 1: {img_w}x{img_h} -> {preview_w}x{preview_h}")  # 调试信息
                    frame1_tk = ImageTk.PhotoImage(frame1_pil)
                    
                    # 更新预览标签
                    self.preview_label1.config(image=frame1_tk)
                    self.preview_label1.image = frame1_tk  # 保持引用
                    
            # 更新摄像头2预览
            if self.preview_camera2 and self.preview_camera2.isOpened():
                ret2, frame2 = self.preview_camera2.read()
                if ret2:
                    # 转换为tkinter可显示的格式
                    frame2_rgb = cv2.cvtColor(frame2, cv2.COLOR_BGR2RGB)
                    frame2_pil = Image.fromarray(frame2_rgb)
                    # 动态调整预览尺寸以适应不同分辨率
                    # 计算合适的预览尺寸（保持宽高比，最大不超过480x270）
                    img_h, img_w = frame2.shape[:2]
                    scale = min(480/img_w, 270/img_h)
                    preview_w = int(img_w * scale)
                    preview_h = int(img_h * scale)
                    frame2_pil = frame2_pil.resize((preview_w, preview_h), Image.LANCZOS)
                    # print(f"Camera 2: {img_w}x{img_h} -> {preview_w}x{preview_h}")  # 调试信息
                    frame2_tk = ImageTk.PhotoImage(frame2_pil)
                    
                    # 更新预览标签
                    self.preview_label2.config(image=frame2_tk)
                    self.preview_label2.image = frame2_tk  # 保持引用
                    
        except Exception as e:
            print(f"Preview update error: {e}")
            
        # 每5秒更新一次预览 - 减少资源消耗，主要用于帮助用户调整摄像头位置
        if self.preview_active:
            self.root.after(5000, self.update_preview)
    
    def update_preview_resolution(self, camera_index):
        """当用户改变分辨率选择时更新预览分辨率"""
        if self.preview_active:
            print(f"Updating preview resolution for camera {camera_index + 1}...")
            # 稍微延迟以避免频繁切换对摄像头造成干扰
            self.root.after(500, lambda: self.init_preview_camera(camera_index))
        
    def run(self):
        """Start the application"""
        self.update_timer()
        self.root.mainloop()
        
    def __del__(self):
        """Cleanup on exit"""
        self.stop_preview()
        self.cleanup_recording()


if __name__ == "__main__":
    try:
        app = ModernDualCameraRecorder()
        app.run()
    except KeyboardInterrupt:
        print("\nApplication interrupted by user")
    except Exception as e:
        print(f"Application error: {str(e)}")