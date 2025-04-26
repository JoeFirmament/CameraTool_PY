import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox
import tkinter.ttk as ttk
import cv2
import json
import numpy as np
from PIL import Image, ImageTk, ExifTags
import os
from datetime import datetime, timezone, timedelta
import subprocess

class HomographyCalibratorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Homography Calibrator from Label Studio JSON")

        # --- Add Window Icon ---
        icon_path = "icon.png"
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            full_icon_path = os.path.join(script_dir, icon_path)
            if os.path.exists(full_icon_path):
                icon_image_pil = Image.open(full_icon_path)
                icon_photo = ImageTk.PhotoImage(icon_image_pil)
                self.root.iconphoto(True, icon_photo)
                icon_image_pil.close()
            else:
                print(f"Warning: Icon file not found at {full_icon_path}")
        except Exception as e:
            print(f"Warning: Could not load or set window icon: {e}")

        # Calibration Data
        self.image_calib_path = None
        self.image_calib_cv2 = None
        self.image_calib_tk = None
        self.calib_display_width = 0
        self.calib_display_height = 0
        self.points_calib_data = []
        self.active_point_index = -1
        self.homography_matrix = None
        self.verification_tk_ids = []
        self.image_info_path = None
        self.image_info_pil = None

        # --- GUI Elements ---
        main_pane = ttk.Panedwindow(root, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.canvas = tk.Canvas(main_pane, bg="gray")
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        main_pane.add(self.canvas, weight=1)
        self.controls_frame = ttk.Frame(main_pane, padding="10")
        main_pane.add(self.controls_frame, weight=0)
        self.controls_frame.columnconfigure(0, weight=1)
        self.controls_frame.columnconfigure(1, weight=1)

        # --- Calibration Section ---
        calib_label = ttk.Label(self.controls_frame, text="Calibration Section", font=('Arial', 12, 'bold'))
        calib_label.grid(row=0, column=0, columnspan=2, pady=(0, 10), sticky=tk.W)
        self.load_calib_image_button = ttk.Button(self.controls_frame, text="1. Load Calibration Image", command=self.load_calib_image)
        self.load_calib_image_button.grid(row=1, column=0, columnspan=2, pady=2, sticky=tk.W+tk.E)
        self.load_calib_json_button = ttk.Button(self.controls_frame, text="2. Load Calibration JSON", command=self.load_calib_json, state=tk.DISABLED)
        self.load_calib_json_button.grid(row=2, column=0, columnspan=2, pady=2, sticky=tk.W+tk.E)
        self.point_label = ttk.Label(self.controls_frame, text="Load image and JSON first")
        self.point_label.grid(row=3, column=0, columnspan=2, pady=(10, 5), sticky=tk.W)
        self.flat_x_label = ttk.Label(self.controls_frame, text="Real World X:")
        self.flat_x_label.grid(row=4, column=0, padx=2, pady=2, sticky=tk.W)
        self.flat_x_entry = ttk.Entry(self.controls_frame, state=tk.DISABLED)
        self.flat_x_entry.grid(row=4, column=1, padx=2, pady=2, sticky=tk.W+tk.E)
        self.flat_y_label = ttk.Label(self.controls_frame, text="Real World Y:")
        self.flat_y_label.grid(row=5, column=0, padx=2, pady=2, sticky=tk.W)
        self.flat_y_entry = ttk.Entry(self.controls_frame, state=tk.DISABLED)
        self.flat_y_entry.grid(row=5, column=1, padx=2, pady=2, sticky=tk.W+tk.E)
        self.save_button = ttk.Button(self.controls_frame, text="Save", command=self.save_coordinates, state=tk.DISABLED)
        self.save_button.grid(row=6, column=0, padx=2, pady=5, sticky=tk.W+tk.E)
        self.delete_button = ttk.Button(self.controls_frame, text="Delete", command=self.delete_coordinates, state=tk.DISABLED)
        self.delete_button.grid(row=6, column=1, padx=2, pady=5, sticky=tk.W+tk.E)
        self.calculate_button = ttk.Button(self.controls_frame, text="Calculate Homography", command=self.calculate_homography, state=tk.DISABLED)
        self.calculate_button.grid(row=7, column=0, columnspan=2, pady=(10, 5), sticky=tk.W+tk.E)
        self.export_button = ttk.Button(self.controls_frame, text="Export Coordinates (JSON)", command=self.export_coordinates_to_json, state=tk.DISABLED)
        self.export_button.grid(row=8, column=0, columnspan=2, pady=2, sticky=tk.W+tk.E)
        self.verify_button = ttk.Button(self.controls_frame, text="Verify", command=self.verify_untransformed_points, state=tk.DISABLED)
        self.verify_button.grid(row=9, column=0, padx=2, pady=(10, 2), sticky=tk.W+tk.E)
        self.clear_verify_button = ttk.Button(self.controls_frame, text="Clear Verify", command=self.clear_verification_display, state=tk.DISABLED)
        self.clear_verify_button.grid(row=9, column=1, padx=2, pady=(10, 2), sticky=tk.W+tk.E)
        self.homography_label = ttk.Label(self.controls_frame, text="Homography Matrix:", font=('Arial', 10, 'bold'))
        self.homography_label.grid(row=10, column=0, columnspan=2, pady=(10,0), sticky=tk.W)
        self.homography_text = tk.Text(self.controls_frame, height=6, width=30, state=tk.DISABLED, wrap=tk.WORD)
        self.homography_text.grid(row=11, column=0, columnspan=2, pady=5, sticky=tk.W+tk.E)
        self.homography_text.config(state=tk.NORMAL)
        self.homography_text.delete(1.0, tk.END)
        self.homography_text.insert(tk.END, "Load calibration image first.")
        self.homography_text.config(state=tk.DISABLED)
        separator = ttk.Separator(self.controls_frame, orient='horizontal')
        separator.grid(row=12, column=0, columnspan=2, sticky=tk.W+tk.E, pady=10)

        # --- Camera Capture Section ---
        camera_label = ttk.Label(self.controls_frame, text="Camera Capture Section", font=('Arial', 12, 'bold'))
        camera_label.grid(row=13, column=0, columnspan=2, pady=(0, 10), sticky=tk.W)
        self.device_entry = ttk.Entry(self.controls_frame)
        self.device_entry.insert(0, "/dev/video0")
        self.device_entry.grid(row=14, column=0, columnspan=2, pady=2, sticky=tk.W+tk.E)
        self.list_resolutions_button = ttk.Button(self.controls_frame, text="List Resolutions", command=self.list_camera_resolutions)
        self.list_resolutions_button.grid(row=15, column=0, columnspan=2, pady=2, sticky=tk.W+tk.E)
        self.resolution_combobox = ttk.Combobox(self.controls_frame, state="readonly")
        self.resolution_combobox.grid(row=16, column=0, columnspan=2, pady=2, sticky=tk.W+tk.E)
        self.capture_button = ttk.Button(self.controls_frame, text="Capture Photo", command=self.capture_photo, state=tk.DISABLED)
        self.capture_button.grid(row=17, column=0, columnspan=2, pady=2, sticky=tk.W+tk.E)
        separator2 = ttk.Separator(self.controls_frame, orient='horizontal')
        separator2.grid(row=18, column=0, columnspan=2, sticky=tk.W+tk.E, pady=10)

        # --- Image Info Section ---
        info_label = ttk.Label(self.controls_frame, text="Image Info Section", font=('Arial', 12, 'bold'))
        info_label.grid(row=19, column=0, columnspan=2, pady=(0, 5), sticky=tk.W)
        self.load_image_info_button = ttk.Button(self.controls_frame, text="Load Image for Info", command=self.load_image_info)
        self.load_image_info_button.grid(row=20, column=0, columnspan=2, pady=2, sticky=tk.W+tk.E)
        self.image_info_label = ttk.Label(self.controls_frame, text="Image Info:")
        self.image_info_label.grid(row=21, column=0, columnspan=2, pady=(10, 0), sticky=tk.W)
        self.image_info_text = tk.Text(self.controls_frame, height=10, width=30, state=tk.DISABLED, wrap=tk.WORD)
        self.image_info_text.grid(row=22, column=0, columnspan=2, pady=5, sticky=tk.W+tk.E)
        self.image_info_text.config(state=tk.NORMAL)
        self.image_info_text.delete(1.0, tk.END)
        self.image_info_text.insert(tk.END, "Load image for info...")
        self.image_info_text.config(state=tk.DISABLED)
        self.quit_button = ttk.Button(self.controls_frame, text="Quit", command=root.quit)
        self.quit_button.grid(row=23, column=0, columnspan=2, pady=(20, 5), sticky=tk.W+tk.E)
        self.controls_frame.rowconfigure(11, weight=1)
        self.controls_frame.rowconfigure(22, weight=1)

    def list_camera_resolutions(self):
        """Lists all supported resolutions for the specified camera device using v4l2-ctl."""
        device = self.device_entry.get()
        if not device:
            messagebox.showerror("Error", "Please enter a camera device (e.g., /dev/video0).")
            return

        try:
            # Check if v4l2-ctl is available
            subprocess.run(["v4l2-ctl", "--version"], check=True, capture_output=True, text=True)
        except FileNotFoundError:
            messagebox.showerror("Error", "v4l2-ctl not found. Please install v4l-utils (e.g., 'sudo apt install v4l-utils' on Ubuntu).")
            print("Error: v4l2-ctl not found.")
            return
        except subprocess.CalledProcessError:
            messagebox.showerror("Error", "Failed to run v4l2-ctl. Ensure v4l-utils is installed correctly.")
            print("Error: Failed to run v4l2-ctl.")
            return

        try:
            # Run v4l2-ctl to list formats and resolutions
            result = subprocess.run(
                ["v4l2-ctl", "--device", device, "--list-formats-ext"],
                check=True,
                capture_output=True,
                text=True
            )
            output = result.stdout

            # Parse resolutions from v4l2-ctl output
            supported_resolutions = []
            lines = output.splitlines()
            current_format = None
            for line in lines:
                line = line.strip()
                # Look for pixel format lines
                if line.startswith("Pixel Format:"):
                    current_format = line.split("'")[1] if "'" in line else None
                # Look for Size lines under a format (we'll accept common formats like YUYV, MJPG)
                if line.startswith("Size: Discrete") and current_format:
                    # Extract resolution (e.g., "Size: Discrete 1920x1080")
                    res = line.split("Discrete ")[1].split()[0]
                    if 'x' in res:
                        width, height = map(int, res.split('x'))
                        resolution_str = f"{width}x{height}"
                        if resolution_str not in supported_resolutions:
                            supported_resolutions.append(resolution_str)

            if not supported_resolutions:
                messagebox.showerror(
                    "Error",
                    f"No supported resolutions found for device {device}. "
                    "The device may be invalid, not connected, or not properly configured."
                )
                print(f"Error: No resolutions found for device {device}.")
                self.resolution_combobox['values'] = []
                self.capture_button.config(state=tk.DISABLED)
                return

            # Sort resolutions by width for a better user experience
            supported_resolutions.sort(key=lambda x: int(x.split('x')[0]))
            self.resolution_combobox['values'] = supported_resolutions
            self.resolution_combobox.set(supported_resolutions[0])
            self.capture_button.config(state=tk.NORMAL)
            messagebox.showinfo("Resolutions", f"Supported resolutions:\n{', '.join(supported_resolutions)}")
            print(f"Supported resolutions for {device}: {supported_resolutions}")

        except subprocess.CalledProcessError as e:
            messagebox.showerror(
                "Error",
                f"Failed to access device {device}. "
                "The device may be invalid, not connected, or not properly configured."
            )
            print(f"Error accessing device {device}: {e}")
            self.resolution_combobox['values'] = []
            self.capture_button.config(state=tk.DISABLED)
        except Exception as e:
            messagebox.showerror("Error", f"Error listing resolutions: {e}")
            print(f"Error listing resolutions for {device}: {e}")
            self.resolution_combobox['values'] = []
            self.capture_button.config(state=tk.DISABLED)

    def capture_photo(self):
        """Captures a photo using the selected camera and resolution."""
        device = self.device_entry.get()
        resolution = self.resolution_combobox.get()
        if not device or not resolution:
            messagebox.showerror("Error", "Please specify device and select a resolution.")
            return

        try:
            width, height = map(int, resolution.split('x'))
            cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
            if not cap.isOpened():
                messagebox.showerror("Error", f"Could not open camera device {device}.")
                return

            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            ret, frame = cap.read()
            cap.release()

            if not ret:
                messagebox.showerror("Error", "Failed to capture photo.")
                return

            # Generate filename with Beijing timezone (UTC+8) timestamp
            beijing_tz = timezone(timedelta(hours=8))
            timestamp = datetime.now(beijing_tz).strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"{timestamp}_{resolution}.jpg"
            filepath = os.path.join(os.getcwd(), filename)

            # Save the image
            cv2.imwrite(filepath, frame)
            messagebox.showinfo("Success", f"Photo saved as:\n{filepath}")
            print(f"Photo captured and saved to {filepath}")

        except Exception as e:
            messagebox.showerror("Error", f"Error capturing photo: {e}")
            print(f"Error capturing photo: {e}")

    def load_calib_image(self):
        filepath = filedialog.askopenfilename(
            title="Select Calibration Image File",
            filetypes=(("Image files", "*.jpg *.jpeg *.png *.bmp *.tiff"), ("All files", "*.*"))
        )
        if not filepath:
            return
        self.reset_calibration_data_and_display()
        img = cv2.imread(filepath)
        if img is None:
            messagebox.showerror("Error", f"Could not load calibration image from {filepath}")
            print(f"Debug: cv2.imread failed for {filepath}")
            return
        print(f"Debug: cv2.imread successful. Image shape: {img.shape}")
        self.image_calib_path = filepath
        self.image_calib_cv2 = img
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img_pil = Image.fromarray(img_rgb)
        max_width = self.root.winfo_screenwidth() * 0.8
        max_height = self.root.winfo_screenheight() * 0.8
        img_width, img_height = img_pil.size
        if img_width > max_width or img_height > max_height:
            scale = min(max_width / img_width, max_height / img_height)
            new_width = int(img_width * scale)
            new_height = int(img_height * scale)
            img_pil = img_pil.resize((new_width, new_height), Image.Resampling.LANCZOS)
            display_width, display_height = new_width, new_height
        else:
            display_width, display_height = img_width, img_height
        self.calib_display_width = display_width
        self.calib_display_height = display_height
        self.image_calib_tk = ImageTk.PhotoImage(image=img_pil)
        print(f"Debug: PIL image size for display: {img_pil.size}")
        print(f"Debug: ImageTk.PhotoImage created: {self.image_calib_tk}")
        self.canvas.config(width=display_width, height=display_height)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.image_calib_tk)
        print(f"Debug: Canvas configured size (target display size): {display_width}x{display_height}")
        self.canvas.update_idletasks()
        print(f"Debug: Canvas content after create_image: {self.canvas.find_all()}")
        print(f"Calibration image loaded: {self.image_calib_path}")
        self.point_label.config(text="Image loaded. Now load JSON.")
        self.load_calib_json_button.config(state=tk.NORMAL)
        self.homography_text.config(state=tk.NORMAL)
        self.homography_text.delete(1.0, tk.END)
        self.homography_text.insert(tk.END, f"Image loaded: {os.path.basename(self.image_calib_path)}\nLoad JSON next.")
        self.homography_text.config(state=tk.DISABLED)

    def load_calib_json(self):
        if self.image_calib_cv2 is None:
            messagebox.showwarning("Load Image First", "Please load the calibration image before loading the JSON file.")
            return
        filepath = filedialog.askopenfilename(
            title="Select Label Studio JSON File for Calibration",
            filetypes=(("JSON files", "*.json"), ("All files", "*.*"))
        )
        if not filepath:
            return
        try:
            with open(filepath, 'r') as f:
                export_data = json.load(f)
            if not export_data or not isinstance(export_data, list) or not export_data[0] or 'annotations' not in export_data[0] or not export_data[0]['annotations']:
                messagebox.showerror("Error", "Invalid or unexpected Label Studio JSON format.")
                self.reset_calibration_json_data()
                return
            task_data = export_data[0]
            annotations = task_data.get('annotations', [])
            if not annotations:
                messagebox.showerror("Error", "No annotations found in the JSON.")
                self.reset_calibration_json_data()
                return
            results = annotations[0].get('result', [])
            if not results:
                messagebox.showwarning("No Annotation Results", "No annotation results found in the JSON.")
                self.reset_calibration_json_data()
                self.point_label.config(text="JSON loaded, but no points found.")
                return
            original_width_json = None
            original_height_json = None
            for res in results:
                if 'original_width' in res and 'original_height' in res:
                    original_width_json = res['original_width']
                    original_height_json = res['original_height']
                    break
            img_orig_height, img_orig_width = self.image_calib_cv2.shape[:2]
            if original_width_json is None or original_height_json is None:
                messagebox.showwarning("Missing Dimensions in JSON", "Could not find original_width/height in JSON results.\nUsing loaded image dimensions for point scaling.")
                effective_original_width = img_orig_width
                effective_original_height = img_orig_height
            else:
                if int(original_width_json) != img_orig_width or int(original_height_json) != img_orig_height:
                    response = messagebox.askyesno(
                        "Dimension Mismatch",
                        f"JSON dimensions ({original_width_json}x{original_height_json}) "
                        f"do not match the loaded image dimensions ({img_orig_width}x{img_orig_height}).\n"
                        "Point coordinates from JSON might be incorrect for this image.\n"
                        "Do you want to load the points anyway?"
                    )
                    if not response:
                        self.reset_calibration_json_data()
                        return
                    print("Warning: Dimension mismatch acknowledged. Proceeding with point loading based on loaded image dimensions.")
                    effective_original_width = img_orig_width
                    effective_original_height = img_orig_height
                else:
                    effective_original_width = original_width_json
                    effective_original_height = original_height_json
            print(f"Debug: Effective Original Dimensions (used for scaling from JSON %): {effective_original_width}x{effective_original_height}")
            self.points_calib_data = []
            display_width = self.calib_display_width
            display_height = self.calib_display_height
            print(f"Debug: Using Stored Display Dimensions for scaling to display: {display_width}x{display_height}")
            if display_width <= 1 or display_height <= 1:
                messagebox.showwarning("Display Size Error", f"Stored display size is incorrect: {display_width}x{display_height}. Points might be misplaced.")
                print(f"Debug: Stored display size is incorrect: {display_width}x{display_height}. Proceeding with point loading.")
                self.reset_calibration_json_data()
                return
            for res in results:
                if res['type'] == 'keypointlabels' and 'x' in res['value'] and 'y' in res['value']:
                    x_percent = res['value']['x']
                    y_percent = res['value']['y']
                    label = res['value'].get('keypointlabels', [''])[0]
                    pixel_x_orig = (x_percent / 100.0) * effective_original_width
                    pixel_y_orig = (y_percent / 100.0) * effective_original_height
                    if effective_original_width > 0 and effective_original_height > 0:
                        pixel_x_display = pixel_x_orig * (display_width / effective_original_width)
                        pixel_y_display = pixel_y_orig * (display_height / effective_original_height)
                    else:
                        print("Warning: Effective original dimensions are zero during point scaling!")
                        pixel_x_display = (x_percent / 100.0) * display_width
                        pixel_y_display = (y_percent / 100.0) * display_height
                    self.points_calib_data.append({
                        'label': label or f'Point {len(self.points_calib_data) + 1}',
                        'pixel': (pixel_x_display, pixel_y_display),
                        'flat': None,
                        'tk_id': None
                    })
            if not self.points_calib_data:
                messagebox.showwarning("No Keypoints", "No keypoint annotations found in the result.")
                self.reset_calibration_json_data()
                self.point_label.config(text="JSON loaded, but no points found.")
                return
            print(f"Loaded {len(self.points_calib_data)} keypoints from JSON.")
            self.draw_points()
            self.enable_calibration_controls()
            self.point_label.config(text="JSON loaded. Click points to input coordinates.")
            self.homography_text.config(state=tk.NORMAL)
            self.homography_text.delete(1.0, tk.END)
            self.homography_text.insert(tk.END, f"JSON loaded: {os.path.basename(filepath)}\n{len(self.points_calib_data)} points found.\nClick points to enter flat coordinates.")
            self.homography_text.config(state=tk.DISABLED)
        except FileNotFoundError:
            messagebox.showerror("Error", f"JSON file not found at {filepath}")
            self.reset_calibration_json_data()
        except json.JSONDecodeError:
            messagebox.showerror("Error", f"Invalid JSON format in {filepath}")
            self.reset_calibration_json_data()
        except Exception as e:
            messagebox.showerror("An error occurred", str(e))
            import traceback
            traceback.print_exc()
            self.reset_calibration_json_data()

    def reset_calibration_data_and_display(self):
        self.canvas.delete("all")
        self.image_calib_cv2 = None
        self.image_calib_tk = None
        self.image_calib_path = None
        self.calib_display_width = 0
        self.calib_display_height = 0
        self.points_calib_data = []
        self.active_point_index = -1
        self.disable_calibration_controls()
        self.point_label.config(text="Load calibration image first.")
        self.load_calib_json_button.config(state=tk.DISABLED)
        self.homography_text.config(state=tk.NORMAL)
        self.homography_text.delete(1.0, tk.END)
        self.homography_text.insert(tk.END, "Load calibration image first.")
        self.homography_text.config(state=tk.DISABLED)
        self.homography_matrix = None
        self.clear_verification_display()
        self.verify_button.config(state=tk.DISABLED)

    def reset_calibration_json_data(self):
        self.canvas.delete("point_marker")
        self.canvas.delete("point_label_text")
        self.canvas.delete("point_label_outline")
        self.points_calib_data = []
        self.active_point_index = -1
        self.disable_calibration_controls()
        self.point_label.config(text="JSON data cleared.")
        self.homography_text.config(state=tk.NORMAL)
        self.homography_text.delete(1.0, tk.END)
        self.homography_text.insert(tk.END, "JSON data cleared.\nLoad JSON again.")
        self.homography_text.config(state=tk.DISABLED)
        self.homography_matrix = None
        self.clear_verification_display()
        self.verify_button.config(state=tk.DISABLED)

    def draw_points(self):
        if self.image_calib_cv2 is None or not self.points_calib_data:
            return
        self.canvas.delete("point_marker")
        self.canvas.delete("point_label_text")
        self.canvas.delete("point_label_outline")
        for i, point_data in enumerate(self.points_calib_data):
            x_float, y_float = point_data['pixel']
            label = point_data['label']
            color = "red" if point_data['flat'] is None else "blue"
            outline_color = "yellow" if i == self.active_point_index else "black"
            x_int, y_int = int(x_float), int(y_float)
            point_data['tk_id'] = self.canvas.create_oval(
                x_int - 5, y_int - 5, x_int + 5, y_int + 5,
                fill=color, outline=outline_color, width=2, tags="point_marker"
            )
            self.canvas.create_text(
                x_int + 10, y_int - 10, text=label, anchor=tk.NW, font=('Arial', 10, 'bold'),
                fill="black", tags="point_label_outline"
            )
            self.canvas.create_text(
                x_int + 10, y_int - 10, text=label, anchor=tk.NW, font=('Arial', 10, 'bold'),
                fill="white", tags="point_label_text"
            )

    def on_canvas_click(self, event):
        if not self.points_calib_data:
            return
        click_x, click_y = event.x, event.y
        min_dist = float('inf')
        closest_point_index = -1
        tolerance = 15
        for i, point_data in enumerate(self.points_calib_data):
            px_float, py_float = point_data['pixel']
            dist = np.sqrt((click_x - px_float)**2 + (click_y - py_float)**2)
            if dist < tolerance and dist < min_dist:
                min_dist = dist
                closest_point_index = i
        self.set_active_point(closest_point_index)

    def set_active_point(self, index):
        if not self.points_calib_data:
            self.active_point_index = -1
            self.disable_calibration_controls()
            return
        if self.active_point_index == index:
            return
        if self.active_point_index != -1:
            prev_point_data = self.points_calib_data[self.active_point_index]
            if prev_point_data['tk_id'] and self.canvas.find_withtag(prev_point_data['tk_id']):
                self.canvas.itemconfig(prev_point_data['tk_id'], outline="black")
        self.active_point_index = index
        if index != -1:
            point_data = self.points_calib_data[index]
            self.point_label.config(text=f"Editing: {point_data['label']} (Pixel: {point_data['pixel'][0]:.2f}, {point_data['pixel'][1]:.2f})")
            self.flat_x_entry.config(state=tk.NORMAL)
            self.flat_y_entry.config(state=tk.NORMAL)
            self.save_button.config(state=tk.NORMAL)
            self.delete_button.config(state=tk.NORMAL)
            if point_data['flat'] is not None:
                self.flat_x_entry.delete(0, tk.END)
                self.flat_x_entry.insert(0, str(point_data['flat'][0]))
                self.flat_y_entry.delete(0, tk.END)
                self.flat_y_entry.insert(0, str(point_data['flat'][1]))
            else:
                self.flat_x_entry.delete(0, tk.END)
                self.flat_y_entry.delete(0, tk.END)
            if point_data['tk_id'] and self.canvas.find_withtag(point_data['tk_id']):
                self.canvas.itemconfig(point_data['tk_id'], outline="yellow")
        else:
            self.point_label.config(text="Click a point to edit")
            self.flat_x_entry.config(state=tk.DISABLED)
            self.flat_y_entry.config(state=tk.DISABLED)
            self.save_button.config(state=tk.DISABLED)
            self.delete_button.config(state=tk.DISABLED)
        self.check_calculate_button_state()

    def save_coordinates(self):
        if self.active_point_index == -1 or not self.points_calib_data:
            return
        try:
            x_flat = float(self.flat_x_entry.get())
            y_flat = float(self.flat_y_entry.get())
            self.points_calib_data[self.active_point_index]['flat'] = (x_flat, y_flat)
            print(f"Saved flat coordinates ({x_flat}, {y_flat}) for {self.points_calib_data[self.active_point_index]['label']}")
            self.draw_points()
            self.set_active_point(self.active_point_index)
        except ValueError:
            messagebox.showwarning("Invalid Input", "Please enter valid numerical values for X and Y.")
        self.check_calculate_button_state()

    def delete_coordinates(self):
        if self.active_point_index == -1 or not self.points_calib_data:
            return
        point_label = self.points_calib_data[self.active_point_index]['label']
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete coordinates for {point_label}?"):
            self.points_calib_data[self.active_point_index]['flat'] = None
            print(f"Deleted flat coordinates for {point_label}")
            self.flat_x_entry.delete(0, tk.END)
            self.flat_y_entry.delete(0, tk.END)
            self.draw_points()
            self.set_active_point(-1)
        self.check_calculate_button_state()

    def check_calculate_button_state(self):
        valid_points_count = sum(1 for p in self.points_calib_data if p['flat'] is not None)
        if valid_points_count >= 4:
            self.calculate_button.config(state=tk.NORMAL)
            self.homography_text.config(state=tk.NORMAL)
            self.homography_text.delete(1.0, tk.END)
            self.homography_text.insert(tk.END, f"Ready to calculate with {valid_points_count} points.")
            self.homography_text.config(state=tk.DISABLED)
        else:
            self.calculate_button.config(state=tk.DISABLED)
            self.homography_text.config(state=tk.NORMAL)
            self.homography_text.delete(1.0, tk.END)
            self.homography_text.insert(tk.END, f"Need at least 4 points with coordinates ({valid_points_count} currently).")
            self.homography_text.config(state=tk.DISABLED)

    def transform_pixel_to_world(self, pixel_x_display, pixel_y_display):
        if self.homography_matrix is None:
            print("Error: Homography matrix not available for transformation.")
            return None
        if self.image_calib_cv2 is None:
            print("Error: Calibration image not loaded for scaling.")
            return None
        orig_height, orig_width = self.image_calib_cv2.shape[:2]
        if orig_width <= 0 or orig_height <= 0:
            print("Error: Invalid original image dimensions for scaling.")
            return None
        display_width = self.calib_display_width
        display_height = self.calib_display_height
        if display_width <= 0 or display_height <= 0:
            print("Error: Invalid display dimensions stored for scaling.")
            return None
        scaled_pixel_x = pixel_x_display * (orig_width / display_width)
        scaled_pixel_y = pixel_y_display * (orig_height / display_height)
        H = self.homography_matrix
        pixel_coord_homogeneous = np.array([[scaled_pixel_x], [scaled_pixel_y], [1.0]])
        transformed_homogeneous_coord = np.dot(H, pixel_coord_homogeneous)
        sX = transformed_homogeneous_coord[0, 0]
        sY = transformed_homogeneous_coord[1, 0]
        s = transformed_homogeneous_coord[2, 0]
        if abs(s) < 1e-8:
            print(f"Warning: Perspective division by zero or near-zero for pixel ({pixel_x_display:.2f}, {pixel_y_display:.2f}).")
            return None
        world_X = sX / s
        world_Y = sY / s
        return (float(world_X), float(world_Y))

    def calculate_homography(self):
        src_pts = []
        dst_pts = []
        if self.image_calib_cv2 is None:
            messagebox.showwarning("Image Not Loaded", "Calibration image is not loaded.")
            return
        display_width = self.calib_display_width
        display_height = self.calib_display_height
        if display_width <= 0 or display_height <= 0:
            messagebox.showerror("Display Error", "Invalid display dimensions stored.")
            return
        orig_height, orig_width = self.image_calib_cv2.shape[:2]
        if orig_width <= 0 or orig_height <= 0:
            messagebox.showerror("Image Error", "Invalid original image dimensions.")
            return
        for point_data in self.points_calib_data:
            if point_data['flat'] is not None:
                display_pixel_x, display_pixel_y = point_data['pixel']
                scaled_pixel_x = display_pixel_x * (orig_width / display_width)
                scaled_pixel_y = display_pixel_y * (orig_height / display_height)
                src_pts.append((scaled_pixel_x, scaled_pixel_y))
                dst_pts.append(point_data['flat'])
        if len(src_pts) < 4:
            messagebox.showwarning("Not Enough Points", "Need at least 4 corresponding points to calculate homography.")
            return
        src_pts = np.array(src_pts, dtype=np.float32)
        dst_pts = np.array(dst_pts, dtype=np.float32)
        try:
            H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
            self.homography_matrix = H
            self.homography_text.config(state=tk.NORMAL)
            self.homography_text.delete(1.0, tk.END)
            self.homography_text.insert(tk.END, "Calculated Homography Matrix (H):\n")
            self.homography_text.insert(tk.END, str(H))
            self.homography_text.config(state=tk.DISABLED)
            print("\nCalculated Homography Matrix:")
            print(H)
            self.verify_button.config(state=tk.NORMAL)
        except Exception as e:
            messagebox.showerror("Calculation Error", f"Could not compute homography: {e}")
            self.homography_matrix = None
            self.homography_text.config(state=tk.NORMAL)
            self.homography_text.delete(1.0, tk.END)
            self.homography_text.insert(tk.END, f"Error during calculation: {e}")
            self.homography_text.config(state=tk.DISABLED)
            self.verify_button.config(state=tk.DISABLED)

    def export_coordinates_to_json(self):
        if not self.points_calib_data:
            messagebox.showwarning("No Data", "No calibration points loaded.")
            return
        export_list = []
        for point_data in self.points_calib_data:
            if point_data['flat'] is not None:
                export_list.append({
                    "label": point_data['label'],
                    "world_x": point_data['flat'][0],
                    "world_y": point_data['flat'][1]
                })
        if not export_list:
            messagebox.showwarning("No Data", "No world coordinates have been entered yet.")
            return
        filepath = filedialog.asksaveasfilename(
            title="Save World Coordinates JSON",
            defaultextension=".json",
            filetypes=(("JSON files", "*.json"), ("All files", "*.*"))
        )
        if not filepath:
            return
        try:
            with open(filepath, 'w') as f:
                json.dump(export_list, f, indent=4)
            messagebox.showinfo("Export Successful", f"World coordinates exported to:\n{filepath}")
            print(f"World coordinates exported to {filepath}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Error saving file: {e}")
            print(f"Error saving coordinates to {filepath}: {e}")

    def verify_untransformed_points(self):
        if self.homography_matrix is None:
            messagebox.showwarning("No Matrix", "Homography matrix has not been calculated yet.")
            return
        self.clear_verification_display()
        points_to_verify = []
        for point_data in self.points_calib_data:
            if point_data['flat'] is None:
                points_to_verify.append(point_data)
        if not points_to_verify:
            messagebox.showinfo("No Points to Verify", "All points already have entered world coordinates.")
            return
        print("\nVerifying untransformed points...")
        points_verified_count = 0
        for point_data in points_to_verify:
            pixel_x_display, pixel_y_display = point_data['pixel']
            label = point_data['label']
            world_coord = self.transform_pixel_to_world(pixel_x_display, pixel_y_display)
            if world_coord:
                world_x, world_y = world_coord
                print(f"  {label} (Pixel: {pixel_x_display:.2f}, {pixel_y_display:.2f}) -> World: ({world_x:.2f}, {world_y:.2f})")
                x_int, y_int = int(pixel_x_display), int(pixel_y_display)
                point_id = self.canvas.create_oval(
                    x_int - 7, y_int - 7, x_int + 7, y_int + 7,
                    outline="lime green", width=2, tags="verification_marker"
                )
                self.verification_tk_ids.append(point_id)
                text_label = f"({world_x:.2f}, {world_y:.2f})"
                text_id = self.canvas.create_text(
                    x_int + 15, y_int + 5, text=text_label, anchor=tk.NW, font=('Arial', 9, 'bold'),
                    fill="lime green", tags="verification_marker"
                )
                self.verification_tk_ids.append(text_id)
                points_verified_count += 1
        if self.verification_tk_ids:
            self.clear_verify_button.config(state=tk.NORMAL)
            print(f"Displayed calculated coordinates for {points_verified_count} points.")
        else:
            print("No world coordinates could be calculated for untransformed points.")

    def clear_verification_display(self):
        if self.verification_tk_ids:
            print("Clearing verification display.")
            for item_id in self.verification_tk_ids:
                self.canvas.delete(item_id)
            self.verification_tk_ids = []
            self.clear_verify_button.config(state=tk.DISABLED)

    def enable_calibration_controls(self):
        self.check_calculate_button_state()
        self.export_button.config(state=tk.NORMAL)

    def disable_calibration_controls(self):
        self.flat_x_entry.config(state=tk.DISABLED)
        self.flat_y_entry.config(state=tk.DISABLED)
        self.save_button.config(state=tk.DISABLED)
        self.delete_button.config(state=tk.DISABLED)
        self.calculate_button.config(state=tk.DISABLED)
        self.export_button.config(state=tk.DISABLED)
        self.verify_button.config(state=tk.DISABLED)
        self.clear_verify_button.config(state=tk.DISABLED)

    def load_image_info(self):
        filepath = filedialog.askopenfilename(
            title="Select Image File for Info",
            filetypes=(("Image files", "*.jpg *.jpeg *.png *.bmp *.tiff"), ("All files", "*.*"))
        )
        if not filepath:
            return
        try:
            self.image_info_pil = Image.open(filepath)
            self.image_info_path = filepath
            width, height = self.image_info_pil.size
            resolution_info = f"Resolution: {width} x {height} pixels\n\n"
            exif_data = self.image_info_pil._getexif()
            exif_info_string = "EXIF Data:\n"
            if exif_data is not None:
                exif_tags_map = { tag_id: ExifTags.TAGS.get(tag_id, tag_id) for tag_id in exif_data.keys() }
                for tag_id, value in exif_data.items():
                    tag_name = exif_tags_map.get(tag_id, tag_id)
                    if isinstance(value, bytes):
                        try:
                            value_str = value.decode('utf-8', errors='replace')
                        except:
                            value_str = str(value)
                    elif isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], (int,float)) and isinstance(value[1], (int,float)) and value[1] != 0:
                        try:
                            value_str = f"{value[0]}/{value[1]} ({value[0]/value[1]:.2f})"
                        except:
                            value_str = f"{value[0]}/{value[1]}"
                    elif isinstance(value, np.ndarray):
                        value_str = np.array2string(value, threshold=50, edgeitems=2)
                    else:
                        value_str = str(value)
                    if tag_name == 'GPSInfo':
                        exif_info_string += f"  {tag_name}: {value}\n"
                        continue
                    if tag_name != 'GPSInfo':
                        exif_info_string += f"  {tag_name}: {value_str}\n"
                if exif_info_string == "EXIF Data:\n":
                    exif_info_string += "  No common EXIF tags found."
            else:
                exif_info_string += "  No EXIF data found in this image."
            self.image_info_text.config(state=tk.NORMAL)
            self.image_info_text.delete(1.0, tk.END)
            self.image_info_text.insert(tk.END, resolution_info)
            self.image_info_text.insert(tk.END, exif_info_string)
            self.image_info_text.config(state=tk.DISABLED)
            print(f"\nLoaded image info for: {filepath}")
            print(resolution_info.strip())
            print(exif_info_string)
            self.image_info_pil.close()
            self.image_info_pil = None
        except FileNotFoundError:
            messagebox.showerror("Error", f"Image file not found at {filepath}")
            self.image_info_text.config(state=tk.NORMAL)
            self.image_info_text.delete(1.0, tk.END)
            self.image_info_text.insert(tk.END, "Error: File not found.")
            self.image_info_text.config(state=tk.DISABLED)
            self.image_info_pil = None
            self.image_info_path = None
        except Exception as e:
            messagebox.showerror("Error reading image info", str(e))
            import traceback
            traceback.print_exc()
            self.image_info_text.config(state=tk.NORMAL)
            self.image_info_text.delete(1.0, tk.END)
            self.image_info_text.insert(tk.END, f"Error reading info: {e}")
            self.image_info_text.config(state=tk.DISABLED)
            if self.image_info_pil:
                self.image_info_pil.close()
            self.image_info_pil = None
            self.image_info_path = None

if __name__ == "__main__":
    root = tk.Tk()
    app = HomographyCalibratorApp(root)
    root.mainloop()