#!/usr/bin/env python3
"""
Fixed version of Homography calibration tool
Complete solution to X11 font forwarding issues
"""

import os
import sys

# Set environment variables to avoid font issues
os.environ['TK_SILENCE_DEPRECATION'] = '1'
#if 'DISPLAY' in os.environ:
#    # Force using local fonts instead of X11 forwarded fonts
#    os.environ['FONTCONFIG_FILE'] = '/dev/null'

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import cv2
import numpy as np
from PIL import Image, ImageTk
import threading
import time
import subprocess
import re
import json
from datetime import datetime

class HomographyCalibrator:
    def __init__(self):
        print("Initializing Homography calibration tool...")
        
        # Create main window with safest configuration
        self.root = tk.Tk()
        
        # Set window properties
        self.root.title("Homography Calibrator")
        self.root.geometry("1200x800")
        
        # Disable some features that might cause issues
        try:
            self.root.option_add('*tearOff', False)
            # Don't set font options, let system choose automatically
        except:
            pass
        
        print("Main window created successfully")
        
        # Initialize data
        self.init_data()
        
        # Create interface
        self.create_interface()
        
        # Bind events
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        print("Program initialization completed")
    
    def init_data(self):
        """Initialize data members"""
        # Camera related
        self.cap = None
        self.is_previewing = False
        self.preview_thread = None
        self.current_frame = None
        
        # Calibration related
        self.calibration_points = []
        self.homography_matrix = None
        self.is_calibration_mode = False
        self.is_verification_mode = False
        
        # Display related
        self.canvas_scale = 1.0
        self.canvas_offset_x = 0
        self.canvas_offset_y = 0
        self.selected_point_id = None
    
    def create_interface(self):
        """Create user interface"""
        print("Creating user interface...")
        
        # Main container
        main_container = tk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Left: preview area
        self.create_preview_area(main_container)
        
        # Right: control area
        self.create_control_area(main_container)
        
        print("Interface creation completed")
    
    def create_preview_area(self, parent):
        """Create preview area"""
        preview_frame = tk.Frame(parent, bg='lightgray')
        preview_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Canvas
        self.canvas = tk.Canvas(preview_frame, bg='gray', width=800, height=600)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.canvas.bind('<Button-1>', self.on_canvas_click)
        
        # Status label
        self.canvas_status = tk.Label(preview_frame, text="Click 'Start Preview' to start camera", 
                                     bg='lightgray')
        self.canvas_status.pack(pady=2)
    
    def create_control_area(self, parent):
        """Create control area"""
        control_frame = tk.Frame(parent, width=350, bg='white')
        control_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        control_frame.pack_propagate(False)
        
        # Title - no font specification
        title_label = tk.Label(control_frame, text="Homography Calibration Tool", bg='white')
        title_label.pack(pady=10)
        
        # Various control areas
        self.create_camera_section(control_frame)
        self.create_calibration_section(control_frame)
        self.create_points_section(control_frame)
        self.create_calculation_section(control_frame)
        self.create_status_section(control_frame)
    
    def create_camera_section(self, parent):
        """Create camera control area"""
        section = tk.LabelFrame(parent, text="Camera Control", bg='white')
        section.pack(fill=tk.X, padx=10, pady=5)
        
        # Device path
        tk.Label(section, text="Device:", bg='white').pack(anchor=tk.W, padx=5)
        self.device_var = tk.StringVar(value="/dev/video0")
        device_entry = tk.Entry(section, textvariable=self.device_var)
        device_entry.pack(fill=tk.X, padx=5, pady=2)
        
        # Detect resolution button
        detect_btn = tk.Button(section, text="Detect Resolution", 
                              command=self.detect_resolutions)
        detect_btn.pack(fill=tk.X, padx=5, pady=2)
        
        # Resolution selection
        tk.Label(section, text="Resolution:", bg='white').pack(anchor=tk.W, padx=5)
        self.resolution_var = tk.StringVar()
        self.resolution_combo = ttk.Combobox(section, textvariable=self.resolution_var,
                                           state='readonly')
        self.resolution_combo.pack(fill=tk.X, padx=5, pady=2)
        
        # Preview control
        self.preview_btn = tk.Button(section, text="Start Preview", 
                                   command=self.toggle_preview,
                                   state=tk.DISABLED)
        self.preview_btn.pack(fill=tk.X, padx=5, pady=5)
    
    def create_calibration_section(self, parent):
        """Create calibration control area"""
        section = tk.LabelFrame(parent, text="Calibration Control", bg='white')
        section.pack(fill=tk.X, padx=10, pady=5)
        
        # Calibration mode
        self.calib_mode_var = tk.BooleanVar()
        calib_check = tk.Checkbutton(section, text="Calibration Mode (click to add points)",
                                   variable=self.calib_mode_var,
                                   command=self.toggle_calibration_mode,
                                   bg='white')
        calib_check.pack(anchor=tk.W, padx=5, pady=2)
        
        # Verification mode
        self.verify_mode_var = tk.BooleanVar()
        self.verify_check = tk.Checkbutton(section, text="Verification Mode (click to view coordinates)",
                                         variable=self.verify_mode_var,
                                         command=self.toggle_verification_mode,
                                         bg='white', state=tk.DISABLED)
        self.verify_check.pack(anchor=tk.W, padx=5, pady=2)
        
        # Show Y-axis 5-10m verification points (both sides)
        self.grid_var = tk.BooleanVar()
        self.grid_check = tk.Checkbutton(section, text="Show Y-axis 5-10m verification points (both sides)",
                                       variable=self.grid_var,
                                       command=self.toggle_grid,
                                       bg='white', state=tk.DISABLED)
        self.grid_check.pack(anchor=tk.W, padx=5, pady=2)
    
    def create_points_section(self, parent):
        """Create points management area"""
        section = tk.LabelFrame(parent, text="Calibration Points Management", bg='white')
        section.pack(fill=tk.X, padx=10, pady=5)
        
        # Points list
        list_frame = tk.Frame(section, bg='white')
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        self.points_listbox = tk.Listbox(list_frame, height=6, width=30)
        self.points_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        self.points_listbox.bind('<<ListboxSelect>>', self.on_point_select)
        
        scrollbar = tk.Scrollbar(list_frame, orient=tk.VERTICAL)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.points_listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.points_listbox.yview)
        
        # Operation buttons
        btn_frame = tk.Frame(section, bg='white')
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.edit_btn = tk.Button(btn_frame, text="Edit", 
                                command=self.edit_point, state=tk.DISABLED)
        self.edit_btn.pack(side=tk.LEFT, padx=2)
        
        self.delete_btn = tk.Button(btn_frame, text="Delete", 
                                  command=self.delete_point, state=tk.DISABLED)
        self.delete_btn.pack(side=tk.LEFT, padx=2)
        
        clear_btn = tk.Button(btn_frame, text="Clear", command=self.clear_points)
        clear_btn.pack(side=tk.RIGHT, padx=2)
    
    def create_calculation_section(self, parent):
        """Create calculation area"""
        section = tk.LabelFrame(parent, text="Matrix Calculation", bg='white')
        section.pack(fill=tk.X, padx=10, pady=5)
        
        # Calculate button
        self.calc_btn = tk.Button(section, text="Calculate Homography Matrix",
                                command=self.calculate_homography,
                                state=tk.DISABLED)
        self.calc_btn.pack(fill=tk.X, padx=5, pady=5)
        
        # Save and load buttons
        file_frame = tk.Frame(section, bg='white')
        file_frame.pack(fill=tk.X, padx=5, pady=2)
        
        self.save_btn = tk.Button(file_frame, text="Save",
                                command=self.save_calibration,
                                state=tk.DISABLED)
        self.save_btn.pack(side=tk.LEFT, padx=2)
        
        load_btn = tk.Button(file_frame, text="Load",
                           command=self.load_calibration)
        load_btn.pack(side=tk.RIGHT, padx=2)
    
    def create_status_section(self, parent):
        """Create status display area"""
        section = tk.LabelFrame(parent, text="Status Information", bg='white')
        section.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.status_text = tk.Text(section, height=8, wrap=tk.WORD, 
                                 state=tk.DISABLED, bg='white')
        self.status_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.log_message("Program started, please detect camera resolution first")
    
    def log_message(self, message):
        """Add log message"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        full_message = f"[{timestamp}] {message}\n"
        
        self.status_text.config(state=tk.NORMAL)
        self.status_text.insert(tk.END, full_message)
        self.status_text.see(tk.END)
        self.status_text.config(state=tk.DISABLED)
        
        print(f"LOG: {message}")
    
    def detect_resolutions(self):
        """Detect camera resolutions"""
        device = self.device_var.get()
        if not device:
            messagebox.showerror("Error", "Please enter device path")
            return
        
        try:
            self.log_message(f"Detecting resolutions for device {device}...")
            
            result = subprocess.run(
                ["v4l2-ctl", "--device", device, "--list-formats-ext"],
                capture_output=True, text=True, check=True, timeout=10
            )
            
            resolutions = set()
            for line in result.stdout.splitlines():
                if "Size: Discrete" in line:
                    match = re.search(r'(\d+x\d+)', line)
                    if match:
                        resolutions.add(match.group(1))
            
            if resolutions:
                res_list = sorted(list(resolutions), key=lambda x: int(x.split('x')[0]))
                self.resolution_combo['values'] = res_list
                
                # Set default resolution
                if "1920x1080" in res_list:
                    self.resolution_var.set("1920x1080")
                elif "1280x720" in res_list:
                    self.resolution_var.set("1280x720")
                else:
                    self.resolution_var.set(res_list[0])
                
                self.preview_btn.config(state=tk.NORMAL)
                self.log_message(f"Detected {len(res_list)} resolutions: {', '.join(res_list)}")
            else:
                messagebox.showerror("Error", "No supported resolutions detected")
                self.log_message("No supported resolutions detected")
                
        except subprocess.TimeoutExpired:
            messagebox.showerror("Error", "Detection timeout")
            self.log_message("Resolution detection timeout")
        except subprocess.CalledProcessError as e:
            messagebox.showerror("Error", f"Cannot access device: {e}")
            self.log_message(f"Device access failed: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Detection failed: {e}")
            self.log_message(f"Detection failed: {e}")
    
    def toggle_preview(self):
        """Toggle preview status"""
        if self.is_previewing:
            self.stop_preview()
        else:
            self.start_preview()
    
    def start_preview(self):
        """Start preview"""
        device = self.device_var.get()
        resolution = self.resolution_var.get()
        
        if not device or not resolution:
            messagebox.showwarning("Warning", "Please set device and resolution")
            return
        
        try:
            width, height = map(int, resolution.split('x'))
            
            self.cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
            if not self.cap.isOpened():
                raise Exception("Cannot open camera")
            
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            
            self.is_previewing = True
            self.preview_btn.config(text="Stop Preview")
            
            # Start preview thread
            self.preview_thread = threading.Thread(target=self.preview_loop, daemon=True)
            self.preview_thread.start()
            
            self.log_message(f"Preview started: {resolution}")
            self.canvas_status.config(text=f"Previewing: {resolution}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start preview: {e}")
            self.log_message(f"Preview startup failed: {e}")
            self.stop_preview()
    
    def stop_preview(self):
        """Stop preview"""
        self.is_previewing = False
        
        if self.cap:
            self.cap.release()
            self.cap = None
        
        self.current_frame = None
        self.preview_btn.config(text="Start Preview")
        self.canvas.delete("all")
        
        self.log_message("Preview stopped")
        self.canvas_status.config(text="Preview stopped")
    
    def preview_loop(self):
        """Preview loop"""
        while self.is_previewing and self.cap:
            ret, frame = self.cap.read()
            if ret:
                self.current_frame = frame.copy()
                self.root.after(0, self.update_display)
            time.sleep(0.03)
    
    def update_display(self):
        """Update canvas display"""
        if self.current_frame is None:
            return
        
        try:
            # Draw overlay on frame
            display_frame = self.current_frame.copy()
            self.draw_overlay(display_frame)
            
            # Calculate scaling parameters
            canvas_w = self.canvas.winfo_width()
            canvas_h = self.canvas.winfo_height()
            
            if canvas_w <= 1 or canvas_h <= 1:
                return
            
            img_h, img_w = display_frame.shape[:2]
            self.canvas_scale = min(canvas_w / img_w, canvas_h / img_h)
            
            new_w = int(img_w * self.canvas_scale)
            new_h = int(img_h * self.canvas_scale)
            
            self.canvas_offset_x = (canvas_w - new_w) // 2
            self.canvas_offset_y = (canvas_h - new_h) // 2
            
            # Convert and display
            img_rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
            img_pil = Image.fromarray(img_rgb)
            img_pil = img_pil.resize((new_w, new_h), Image.Resampling.LANCZOS)
            
            self.photo = ImageTk.PhotoImage(img_pil)
            
            self.canvas.delete("image")
            self.canvas.create_image(self.canvas_offset_x, self.canvas_offset_y,
                                   anchor=tk.NW, image=self.photo, tags="image")
            
        except Exception as e:
            print(f"Display update failed: {e}")
    
    def draw_overlay(self, frame):
        """Draw overlay"""
        # Draw calibration points
        for i, point in enumerate(self.calibration_points):
            px, py = map(int, point['pixel'])
            
            # Point color
            color = (0, 255, 0) if point.get('world') else (0, 0, 255)
            
            # Draw point
            cv2.circle(frame, (px, py), 8, color, -1)
            cv2.circle(frame, (px, py), 10, (255, 255, 255), 2)
            
            # Draw number
            cv2.putText(frame, str(i+1), (px-10, py-15),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
            # Display world coordinates
            if point.get('world'):
                wx, wy = point['world']
                text = f"({wx:.1f},{wy:.1f})"
                cv2.putText(frame, text, (px+15, py+5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # Draw Y-axis 5-10m verification points
        if self.homography_matrix is not None and self.grid_var.get():
            self.draw_random_points(frame)
    
    def draw_random_points(self, frame):
        """Draw verification points in Y-axis 5-10m range (both sides distribution)"""
        try:
            print("Starting to draw specified verification points...")
            H_inv = np.linalg.inv(self.homography_matrix)
            img_h, img_w = frame.shape[:2]
            
            # Define 5 verification points in Y-axis 5-10m range, distributed on both sides of Y-axis (unit: mm)
            y_distances = [5000, 6250, 7500, 8750, 10000]  # 5 equally spaced Y-axis distances
            verification_points = []
            
            for y_dist in y_distances:
                # Place one point on each side for each Y distance
                verification_points.append((-500, y_dist))  # Left side 0.5m
                verification_points.append((500, y_dist))   # Right side 0.5m
            
            points_drawn = 0
            
            for i, (world_x, world_y) in enumerate(verification_points):
                
                # Convert world coordinates to pixel coordinates
                world_pt = np.array([[world_x], [world_y], [1.0]], dtype=np.float32)
                pixel_pt = np.dot(H_inv, world_pt)
                
                if abs(pixel_pt[2, 0]) > 1e-8:
                    px = pixel_pt[0, 0] / pixel_pt[2, 0]
                    py = pixel_pt[1, 0] / pixel_pt[2, 0]
                    
                    # Check if point is within image bounds
                    if 0 <= px <= img_w and 0 <= py <= img_h:
                        px_int = int(px)
                        py_int = int(py)
                        
                        # All verification points use small dots, color based on left/right position
                        if world_x < 0:  # Left side points use blue
                            point_color = (255, 0, 0)      # Blue
                        else:  # Right side points use green
                            point_color = (0, 255, 0)      # Green
                        
                        point_radius = 4                    # Uniform small dots
                        border_color = (255, 255, 255)     # White border
                        border_radius = 6
                        
                        # Draw point
                        cv2.circle(frame, (px_int, py_int), point_radius, point_color, -1)  # Fill circle
                        cv2.circle(frame, (px_int, py_int), border_radius, border_color, 2)  # Border
                        
                        # Display world coordinates (convert to meters)
                        world_x_m = world_x / 1000.0
                        world_y_m = world_y / 1000.0
                        coord_text = f"({world_x_m:.2f}m, {world_y_m:.2f}m)"
                        
                        # Calculate text position, avoid going out of screen bounds
                        text_x = px_int + 15
                        text_y = py_int - 10
                        
                        # Check if text would exceed right boundary
                        text_size = cv2.getTextSize(coord_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
                        if text_x + text_size[0] > img_w:
                            text_x = px_int - text_size[0] - 15
                        
                        # Check if text would exceed top boundary
                        if text_y < 20:
                            text_y = py_int + 25
                        
                        # Draw text background (black semi-transparent)
                        text_bg_x1 = max(0, text_x - 5)
                        text_bg_y1 = max(0, text_y - 15)
                        text_bg_x2 = min(img_w, text_x + text_size[0] + 5)
                        text_bg_y2 = min(img_h, text_y + 5)
                        
                        overlay = frame.copy()
                        cv2.rectangle(overlay, (text_bg_x1, text_bg_y1), (text_bg_x2, text_bg_y2), (0, 0, 0), -1)
                        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
                        
                        # Draw coordinate text
                        cv2.putText(frame, coord_text, (text_x, text_y),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                        
                        # Draw point number
                        point_num = str(i + 1)
                        cv2.putText(frame, point_num, (px_int - 5, py_int + 5),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 2)  # Black background
                        cv2.putText(frame, point_num, (px_int - 5, py_int + 5),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)  # White foreground
                        
                        points_drawn += 1
                        side = "Left" if world_x < 0 else "Right"
                        print(f"Verification point #{i+1}: World coordinates({world_x_m:.1f}m, {world_y_m:.1f}m) [{side} side] -> Pixel coordinates({px_int}, {py_int})")
            
            print(f"Y-axis 5-10m verification points drawing completed, drew {points_drawn} points (total {len(verification_points)} points)")
            if points_drawn == 0:
                print("Warning: No verification points found in 5-10m range within field of view, please check calibration results or adjust camera position")
            elif points_drawn < len(verification_points):
                print(f"Note: {len(verification_points) - points_drawn} verification points are outside field of view")
                
        except Exception as e:
            print(f"Verification points drawing failed: {e}")
            import traceback
            traceback.print_exc()
    
    def on_canvas_click(self, event):
        """Handle canvas click"""
        if not self.is_previewing or self.current_frame is None:
            return
        
        # Convert coordinates
        canvas_x = event.x - self.canvas_offset_x
        canvas_y = event.y - self.canvas_offset_y
        
        if canvas_x < 0 or canvas_y < 0:
            return
        
        pixel_x = canvas_x / self.canvas_scale
        pixel_y = canvas_y / self.canvas_scale
        
        img_h, img_w = self.current_frame.shape[:2]
        if pixel_x >= img_w or pixel_y >= img_h:
            return
        
        if self.is_calibration_mode:
            self.add_calibration_point(pixel_x, pixel_y)
        elif self.is_verification_mode:
            self.verify_point(pixel_x, pixel_y)
    
    def add_calibration_point(self, pixel_x, pixel_y):
        """Add calibration point"""
        # Check if clicked on existing point
        for i, point in enumerate(self.calibration_points):
            px, py = point['pixel']
            if abs(px - pixel_x) < 20 and abs(py - pixel_y) < 20:
                self.edit_existing_point(i)
                return
        
        # Input world coordinates
        try:
            x_str = simpledialog.askstring("Input Coordinates", "Please enter X coordinate (mm):")
            if x_str is None:
                return
            
            y_str = simpledialog.askstring("Input Coordinates", "Please enter Y coordinate (mm):")
            if y_str is None:
                return
            
            world_x = float(x_str)
            world_y = float(y_str)
            
            point_data = {
                'pixel': (pixel_x, pixel_y),
                'world': (world_x, world_y),
                'id': len(self.calibration_points)
            }
            
            self.calibration_points.append(point_data)
            self.update_points_list()
            self.update_button_states()
            
            self.log_message(f"Added point #{len(self.calibration_points)}: "
                           f"Pixel({pixel_x:.1f},{pixel_y:.1f}) -> World({world_x},{world_y})")
            
        except (ValueError, TypeError):
            messagebox.showerror("Error", "Please enter valid numbers")
    
    def verify_point(self, pixel_x, pixel_y):
        """Verify point coordinates"""
        if self.homography_matrix is None:
            messagebox.showwarning("Warning", "Please calculate Homography matrix first")
            return
        
        try:
            pixel_pt = np.array([[pixel_x], [pixel_y], [1.0]], dtype=np.float32)
            world_pt = np.dot(self.homography_matrix, pixel_pt)
            
            if abs(world_pt[2, 0]) > 1e-8:
                world_x = world_pt[0, 0] / world_pt[2, 0]
                world_y = world_pt[1, 0] / world_pt[2, 0]
                
                messagebox.showinfo("Verification Result",
                                  f"Pixel coordinates: ({pixel_x:.1f}, {pixel_y:.1f})\n"
                                  f"World coordinates: ({world_x:.2f}, {world_y:.2f}) mm")
                
                self.log_message(f"Verification: Pixel({pixel_x:.1f},{pixel_y:.1f}) -> "
                               f"World({world_x:.2f},{world_y:.2f})")
            else:
                messagebox.showerror("Error", "Coordinate transformation failed")
                
        except Exception as e:
            messagebox.showerror("Error", f"Verification failed: {e}")
    
    def toggle_calibration_mode(self):
        """Toggle calibration mode"""
        self.is_calibration_mode = self.calib_mode_var.get()
        if self.is_calibration_mode and self.is_verification_mode:
            self.verify_mode_var.set(False)
            self.is_verification_mode = False
        
        status = "Enabled" if self.is_calibration_mode else "Disabled"
        self.log_message(f"Calibration mode {status}")
    
    def toggle_verification_mode(self):
        """Toggle verification mode"""
        self.is_verification_mode = self.verify_mode_var.get()
        if self.is_verification_mode and self.is_calibration_mode:
            self.calib_mode_var.set(False)
            self.is_calibration_mode = False
        
        status = "Enabled" if self.is_verification_mode else "Disabled"
        self.log_message(f"Verification mode {status}")
    
    def toggle_grid(self):
        """Toggle Y-axis 5-10m verification points display (both sides distribution)"""
        status = "Enabled" if self.grid_var.get() else "Disabled"
        self.log_message(f"Y-axis 5-10m verification points (both sides) display {status}")
    
    def update_points_list(self):
        """Update points list"""
        self.points_listbox.delete(0, tk.END)
        
        for i, point in enumerate(self.calibration_points):
            px, py = point['pixel']
            if point.get('world'):
                wx, wy = point['world']
                text = f"Point{i+1}: ({px:.1f},{py:.1f}) -> ({wx},{wy})"
            else:
                text = f"Point{i+1}: ({px:.1f},{py:.1f}) -> Not set"
            
            self.points_listbox.insert(tk.END, text)
    
    def on_point_select(self, event):
        """Handle point selection"""
        selection = self.points_listbox.curselection()
        if selection:
            self.selected_point_id = selection[0]
            self.edit_btn.config(state=tk.NORMAL)
            self.delete_btn.config(state=tk.NORMAL)
        else:
            self.selected_point_id = None
            self.edit_btn.config(state=tk.DISABLED)
            self.delete_btn.config(state=tk.DISABLED)
    
    def edit_point(self):
        """Edit selected point"""
        if self.selected_point_id is not None:
            self.edit_existing_point(self.selected_point_id)
    
    def edit_existing_point(self, point_index):
        """Edit existing point"""
        if point_index >= len(self.calibration_points):
            return
        
        point = self.calibration_points[point_index]
        current_world = point.get('world', (0, 0))
        
        try:
            x_str = simpledialog.askstring("Edit Coordinates", 
                                         f"X coordinate (current: {current_world[0]}):")
            if x_str is None:
                return
            
            y_str = simpledialog.askstring("Edit Coordinates",
                                         f"Y coordinate (current: {current_world[1]}):")
            if y_str is None:
                return
            
            world_x = float(x_str)
            world_y = float(y_str)
            
            self.calibration_points[point_index]['world'] = (world_x, world_y)
            self.update_points_list()
            self.update_button_states()
            
            px, py = point['pixel']
            self.log_message(f"Updated point #{point_index+1}: "
                           f"Pixel({px:.1f},{py:.1f}) -> World({world_x},{world_y})")
            
        except (ValueError, TypeError):
            messagebox.showerror("Error", "Please enter valid numbers")
    
    def delete_point(self):
        """Delete selected point"""
        if self.selected_point_id is not None:
            if messagebox.askyesno("Confirm", "Are you sure to delete this point?"):
                self.calibration_points.pop(self.selected_point_id)
                self.update_points_list()
                self.update_button_states()
                self.homography_matrix = None
                
                self.log_message(f"Deleted point #{self.selected_point_id+1}")
                self.selected_point_id = None
                self.edit_btn.config(state=tk.DISABLED)
                self.delete_btn.config(state=tk.DISABLED)
    
    def clear_points(self):
        """Clear all points"""
        if self.calibration_points:
            if messagebox.askyesno("Confirm", "Are you sure to clear all points?"):
                self.calibration_points.clear()
                self.update_points_list()
                self.update_button_states()
                self.homography_matrix = None
                self.log_message("Cleared all calibration points")
    
    def update_button_states(self):
        """Update button states"""
        valid_points = sum(1 for p in self.calibration_points if p.get('world'))
        
        # Calculate button
        if valid_points >= 4:
            self.calc_btn.config(state=tk.NORMAL)
        else:
            self.calc_btn.config(state=tk.DISABLED)
        
        # Other buttons
        if self.homography_matrix is not None:
            self.save_btn.config(state=tk.NORMAL)
            self.verify_check.config(state=tk.NORMAL)
            self.grid_check.config(state=tk.NORMAL)
        else:
            self.save_btn.config(state=tk.DISABLED)
            self.verify_check.config(state=tk.DISABLED)
            self.grid_check.config(state=tk.DISABLED)
    
    def calculate_homography(self):
        """Calculate Homography matrix"""
        src_points = []
        dst_points = []
        
        for point in self.calibration_points:
            if point.get('world'):
                src_points.append(point['pixel'])
                dst_points.append(point['world'])
        
        if len(src_points) < 4:
            messagebox.showwarning("Warning", "At least 4 valid points required")
            return
        
        try:
            src_points = np.array(src_points, dtype=np.float32)
            dst_points = np.array(dst_points, dtype=np.float32)
            
            self.homography_matrix, mask = cv2.findHomography(
                src_points, dst_points, cv2.RANSAC, 5.0
            )
            
            if self.homography_matrix is not None:
                self.update_button_states()
                
                matrix_str = np.array2string(self.homography_matrix,
                                           precision=6, suppress_small=True)
                self.log_message(f"Homography matrix calculation successful:\n{matrix_str}")
                
                messagebox.showinfo("Success", "Matrix calculation completed!\nYou can enable verification mode to test")
            else:
                messagebox.showerror("Error", "Matrix calculation failed")
                
        except Exception as e:
            messagebox.showerror("Error", f"Calculation failed: {e}")
    
    def save_calibration(self):
        """Save calibration data"""
        if not self.calibration_points or self.homography_matrix is None:
            messagebox.showwarning("Warning", "No data to save")
            return
        
        try:
            from tkinter import filedialog
            
            filename = filedialog.asksaveasfilename(
                title="Save Calibration",
                defaultextension=".json",
                filetypes=[("JSON files", "*.json")]
            )
            
            if filename:
                data = {
                    'timestamp': datetime.now().isoformat(),
                    'points': self.calibration_points,
                    'matrix': self.homography_matrix.tolist(),
                    'point_count': len(self.calibration_points)
                }
                
                with open(filename, 'w') as f:
                    json.dump(data, f, indent=4)
                
                messagebox.showinfo("Success", f"Data saved to:\n{filename}")
                self.log_message(f"Calibration data saved: {filename}")
                
        except Exception as e:
            messagebox.showerror("Error", f"Save failed: {e}")
    
    def load_calibration(self):
        """Load calibration data"""
        try:
            from tkinter import filedialog
            
            filename = filedialog.askopenfilename(
                title="Load Calibration",
                filetypes=[("JSON files", "*.json")]
            )
            
            if filename:
                with open(filename, 'r') as f:
                    data = json.load(f)
                
                self.calibration_points = data['points']
                self.homography_matrix = np.array(data['matrix'])
                
                self.update_points_list()
                self.update_button_states()
                
                messagebox.showinfo("Success", f"Data loaded from:\n{filename}")
                self.log_message(f"Calibration data loaded: {filename}")
                
        except Exception as e:
            messagebox.showerror("Error", f"Load failed: {e}")
    
    def on_closing(self):
        """Close program"""
        self.stop_preview()
        self.root.destroy()
    
    def run(self):
        """Run program"""
        print("Starting main loop...")
        self.root.mainloop()


def main():
    """Main function"""
    print("Starting Homography calibration tool...")
    
    try:
        app = HomographyCalibrator()
        app.run()
    except Exception as e:
        print(f"Program startup failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main()) 