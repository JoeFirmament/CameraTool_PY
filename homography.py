import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox
import tkinter.ttk as ttk
import cv2
import json
import numpy as np
from PIL import Image, ImageTk # Keep Image and ImageTk for image display, ExifTags is not needed
import os
from datetime import datetime, timezone, timedelta
import subprocess
import re
import threading
import time

class HomographyCalibratorApp:
    def __init__(self, root):
        self.root = root
        # Initial title, will be updated with image resolution
        self.root.title("Homography Calibrator from Label Studio JSON")

        # Set initial window size and position (WidthxHeight+X+Y)
        # Opens at a reasonable default size, can be resized by user
        self.root.geometry("1000x700") # Adjusted default size

        # --- Add Window Icon ---
        icon_path = "icon.png" # Make sure you have an icon.png file in the same directory
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
        # We will store pixel coordinates relative to the ORIGINAL image size
        # and calculate display coordinates on the fly.
        self.points_calib_data = [] # Each item will have 'label', 'pixel_orig', 'flat', 'tk_id', 'pixel_display'
        self.active_point_index = -1
        self.homography_matrix = None
        self.verification_tk_ids = []
        # Removed image_info_path and image_info_pil

        # Camera Capture Data
        self.cap = None # OpenCV VideoCapture object
        self.is_previewing = False # Flag to indicate if preview is running
        self.preview_thread = None # Thread for the camera preview loop
        self.latest_frame = None # Store the latest frame from the camera
        self.current_photo_tk = None # Store the captured photo ImageTK object

        # --- GUI Elements ---
        main_pane = ttk.Panedwindow(root, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Canvas for displaying images/preview
        self.canvas = tk.Canvas(main_pane, bg="gray", width=800, height=600) # Adjusted initial size
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        main_pane.add(self.canvas, weight=1) # Allow the left pane (containing the canvas) to expand


        # Controls Frame (Right Pane)
        self.controls_frame = ttk.Frame(main_pane, padding="5") # Reduced padding
        main_pane.add(self.controls_frame, weight=0) # Right pane has fixed width initially
        self.controls_frame.columnconfigure(0, weight=1)
        self.controls_frame.columnconfigure(1, weight=1)

        # --- Calibration Section ---
        calib_label = ttk.Label(self.controls_frame, text="Calibration Section", font=('Arial', 12, 'bold'))
        calib_label.grid(row=0, column=0, columnspan=2, pady=(0, 5), sticky=tk.W) # Reduced pady

        self.load_calib_image_button = ttk.Button(self.controls_frame, text="1. Load Calibration Image", command=self.load_calib_image)
        self.load_calib_image_button.grid(row=1, column=0, columnspan=2, pady=1, sticky=tk.W+tk.E) # Reduced pady

        self.load_calib_json_button = ttk.Button(self.controls_frame, text="2. Load Calibration JSON", command=self.load_calib_json, state=tk.DISABLED)
        self.load_calib_json_button.grid(row=2, column=0, columnspan=2, pady=1, sticky=tk.W+tk.E) # Reduced pady

        # 新增的加载世界坐标按钮
        self.load_world_coords_button = ttk.Button(self.controls_frame, text="3. Load World Coords (JSON)", command=self.load_world_coordinates_from_json, state=tk.DISABLED)
        self.load_world_coords_button.grid(row=3, column=0, columnspan=2, pady=1, sticky=tk.W+tk.E) # Adjusted row


        self.point_label = ttk.Label(self.controls_frame, text="Load image and JSON first")
        self.point_label.grid(row=4, column=0, columnspan=2, pady=(5, 2), sticky=tk.W) # Adjusted row

        self.flat_x_label = ttk.Label(self.controls_frame, text="Real World X:")
        self.flat_x_label.grid(row=5, column=0, padx=2, pady=1, sticky=tk.W) # Adjusted row
        self.flat_x_entry = ttk.Entry(self.controls_frame, state=tk.DISABLED)
        self.flat_x_entry.grid(row=5, column=1, padx=2, pady=1, sticky=tk.W+tk.E) # Adjusted row

        self.flat_y_label = ttk.Label(self.controls_frame, text="Real World Y:")
        self.flat_y_label.grid(row=6, column=0, padx=2, pady=1, sticky=tk.W) # Adjusted row
        self.flat_y_entry = ttk.Entry(self.controls_frame, state=tk.DISABLED)
        self.flat_y_entry.grid(row=6, column=1, padx=2, pady=1, sticky=tk.W+tk.E) # Adjusted row

        self.save_button = ttk.Button(self.controls_frame, text="Save", command=self.save_coordinates, state=tk.DISABLED)
        self.save_button.grid(row=7, column=0, padx=2, pady=2, sticky=tk.W+tk.E) # Adjusted row

        self.delete_button = ttk.Button(self.controls_frame, text="Delete", command=self.delete_coordinates, state=tk.DISABLED)
        self.delete_button.grid(row=7, column=1, padx=2, pady=2, sticky=tk.W+tk.E) # Adjusted row

        self.calculate_button = ttk.Button(self.controls_frame, text="Calculate Homography", command=self.calculate_homography, state=tk.DISABLED)
        self.calculate_button.grid(row=8, column=0, columnspan=2, pady=(5, 2), sticky=tk.W+tk.E) # Adjusted row

        # Original Export Points from JSON button
        self.export_button = ttk.Button(self.controls_frame, text="Export Original Points (JSON)", command=self.export_coordinates_to_json, state=tk.DISABLED)
        self.export_button.grid(row=9, column=0, columnspan=2, pady=1, sticky=tk.W+tk.E) # Adjusted row

        # Export World Coordinates button
        self.export_world_coords_button = ttk.Button(self.controls_frame, text="Export World Coords (JSON)", command=self.export_world_coordinates_to_json, state=tk.DISABLED)
        self.export_world_coords_button.grid(row=10, column=0, columnspan=2, pady=1, sticky=tk.W+tk.E) # Adjusted row

        self.verify_button = ttk.Button(self.controls_frame, text="Verify", command=self.verify_untransformed_points, state=tk.DISABLED)
        self.verify_button.grid(row=11, column=0, padx=2, pady=(5, 1), sticky=tk.W+tk.E) # Adjusted row

        self.clear_verify_button = ttk.Button(self.controls_frame, text="Clear Verify", command=self.clear_verification_display, state=tk.DISABLED)
        self.clear_verify_button.grid(row=11, column=1, padx=2, pady=(5, 1), sticky=tk.W+tk.E) # Adjusted row

        self.homography_label = ttk.Label(self.controls_frame, text="Homography Matrix:", font=('Arial', 10, 'bold'))
        self.homography_label.grid(row=12, column=0, columnspan=2, pady=(5,0), sticky=tk.W) # Adjusted row

        # Increased height for Homography Matrix text box
        self.homography_text = tk.Text(self.controls_frame, height=10, width=40, state=tk.DISABLED, wrap=tk.WORD)
        self.homography_text.grid(row=13, column=0, columnspan=2, pady=2, sticky=tk.W+tk.E) # Adjusted row and reduced pady
        self.homography_text.config(state=tk.NORMAL)
        self.homography_text.delete(1.0, tk.END)
        self.homography_text.insert(tk.END, "Load calibration image first.")
        self.homography_text.config(state=tk.DISABLED)

        separator = ttk.Separator(self.controls_frame, orient='horizontal')
        separator.grid(row=14, column=0, columnspan=2, sticky=tk.W+tk.E, pady=5) # Adjusted row and reduced pady

        # --- Camera Capture Section --- (Retained as requested)
        camera_label = ttk.Label(self.controls_frame, text="Camera Capture Section", font=('Arial', 12, 'bold'))
        camera_label.grid(row=15, column=0, columnspan=2, pady=(0, 5), sticky=tk.W) # Adjusted row

        device_label = ttk.Label(self.controls_frame, text="Camera Device:")
        device_label.grid(row=16, column=0, padx=2, pady=1, sticky=tk.W) # Adjusted row
        self.device_entry = ttk.Entry(self.controls_frame)
        self.device_entry.insert(0, "/dev/video0") # Default device
        self.device_entry.grid(row=16, column=1, padx=2, pady=1, sticky=tk.W+tk.E) # Adjusted row

        self.list_resolutions_button = ttk.Button(self.controls_frame, text="List Resolutions", command=self.list_camera_resolutions)
        self.list_resolutions_button.grid(row=17, column=0, columnspan=2, pady=1, sticky=tk.W+tk.E) # Adjusted row

        resolution_label = ttk.Label(self.controls_frame, text="Resolution:")
        resolution_label.grid(row=18, column=0, padx=2, pady=1, sticky=tk.W) # Adjusted row
        self.resolution_combobox = ttk.Combobox(self.controls_frame, state="readonly")
        self.resolution_combobox.grid(row=18, column=1, padx=2, pady=1, sticky=tk.W+tk.E) # Adjusted row

        # Button to toggle preview/capture
        self.capture_button = ttk.Button(self.controls_frame, text="Start Preview", command=self.toggle_preview, state=tk.DISABLED)
        self.capture_button.grid(row=19, column=0, columnspan=2, pady=2, sticky=tk.W+tk.E) # Adjusted row

        # Removed Image Info Section GUI elements

        self.quit_button = ttk.Button(self.controls_frame, text="Quit", command=root.quit)
        # Adjusted row for the quit button after adding the new export button and shifting others
        self.quit_button.grid(row=21, column=0, columnspan=2, pady=(10, 2), sticky=tk.W+tk.E) # Adjusted row and reduced pady

        # Configure row weights for expandability
        # Keep homography text area expandable
        self.controls_frame.rowconfigure(13, weight=1) # Adjusted row index

        # Bind the close event to stop the preview if it's running
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Bind the canvas configure event to redraw when canvas size changes
        self.canvas.bind("<Configure>", self.on_canvas_configure)


    # --- New method to load world coordinates from JSON ---
    def load_world_coordinates_from_json(self):
        if not self.points_calib_data:
            messagebox.showwarning("加载错误", "请先加载标定点 JSON 文件。")
            return

        filepath = filedialog.askopenfilename(
            title="选择世界坐标 JSON 文件",
            filetypes=(("JSON files", "*.json"), ("All files", "*.*"))
        )
        if not filepath:
            return

        try:
            with open(filepath, 'r') as f:
                world_coords_data = json.load(f)

            if not isinstance(world_coords_data, list):
                 messagebox.showerror("格式错误", "导入的 JSON 文件格式不正确，应为列表结构。")
                 return

            updated_count = 0
            missing_points = [] # To track points in JSON that don't match loaded points

            # Create a dictionary for quick lookup of points by label
            points_dict = {point['label']: point for point in self.points_calib_data}

            for item in world_coords_data:
                label = item.get('label')
                world_x = item.get('world_x')
                world_y = item.get('world_y')

                if label is not None and world_x is not None and world_y is not None:
                    if label in points_dict:
                        # Update the 'flat' coordinate for the matching point
                        points_dict[label]['flat'] = (float(world_x), float(world_y))
                        updated_count += 1
                        print(f"已通过导入更新点 '{label}' 的世界坐标为: ({world_x}, {world_y})")
                        # Optional: Update the color of the point marker on the canvas immediately
                        # This would require finding the tk_id and updating the itemconfig
                        # For now, draw_points() will handle this on redraw
                    else:
                        missing_points.append(label)
                        print(f"警告: 导入文件中点 '{label}' 在当前加载的标定点中不存在。")
                else:
                    print(f"警告: 导入文件中存在格式不正确的条目: {item}")


            if updated_count > 0:
                messagebox.showinfo("导入成功", f"成功导入并更新了 {updated_count} 个点的世界坐标。")
                self.draw_points() # Redraw points to update colors
                self.check_calculate_button_state() # Update button states
            elif not missing_points:
                 messagebox.showwarning("导入完成", "导入文件中没有找到与当前加载的标定点相匹配的点。")
            else:
                 messagebox.showwarning("导入完成", "导入文件中没有找到与当前加载的标定点相匹配的有效点。")

            if missing_points:
                 print(f"\n导入文件中未匹配的点标签: {', '.join(missing_points)}")


        except FileNotFoundError:
            messagebox.showerror("错误", f"文件未找到: {filepath}")
        except json.JSONDecodeError:
            messagebox.showerror("格式错误", "无效的 JSON 文件格式。请检查文件内容。")
        except Exception as e:
            messagebox.showerror("发生错误", f"导入世界坐标时发生错误: {str(e)}")
            import traceback
            traceback.print_exc() # Print traceback for debugging


    def on_closing(self):
        """Handles the window closing event to stop the camera preview."""
        self.stop_preview()
        self.root.destroy()

    def on_canvas_configure(self, event):
        """Handles canvas resizing to redraw the current image/preview."""
        # print(f"Debug: Canvas configured to size: {event.width}x{event.height}") # Uncomment for debug
        # When the canvas is resized, redraw the current content
        # Note: Redrawing calibration points also happens here indirectly
        if self.is_previewing:
             # If preview is running, the update_preview loop will handle redrawing based on new canvas size.
             # No explicit action needed here unless the preview loop is paused or optimized.
             pass
        elif self.image_calib_cv2 is not None: # Check if calibration image is loaded (original cv2 image)
            # If a calibration image is loaded, redraw it scaled to the new canvas size
            self.display_image_on_canvas(self.image_calib_cv2) # Redraw the original cv2 image
            self.draw_points() # Redraw points based on new canvas size
            self.verify_untransformed_points() # Redraw verification markers if any

        # If a captured photo were being displayed (not implemented fully yet), handle it here:
        # elif self.captured_photo_cv2 is not None:
        #      self.display_image_on_canvas(self.captured_photo_cv2)


    def get_display_scale_and_offset(self):
        """Calculates the scale factor and offset for displaying the original image on the current canvas."""
        if self.image_calib_cv2 is None:
            return 1.0, 0, 0 # Default scale and offset if no image loaded

        orig_height, orig_width = self.image_calib_cv2.shape[:2]
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        if orig_width <= 1 or orig_height <= 1 or canvas_width <= 1 or canvas_height <= 1:
             return 1.0, 0, 0 # Cannot calculate with invalid dimensions

        scale_w = canvas_width / orig_width
        scale_h = canvas_height / orig_height
        display_scale = min(scale_w, scale_h)

        scaled_img_width = int(orig_width * display_scale)
        scaled_img_height = int(orig_height * display_scale)

        offset_x = (canvas_width - scaled_img_width) // 2
        offset_y = (canvas_height - scaled_img_height) // 2

        return display_scale, offset_x, offset_y


    def display_image_on_canvas(self, cv2_image):
        """Displays a cv2 image on the canvas, scaled to fit and centered."""
        if cv2_image is None:
            self.canvas.delete("all")
            self.image_calib_tk = None
            self.current_photo_tk = None
            return

        # Get current canvas dimensions
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        if canvas_width <= 1 or canvas_height <= 1:
             print("Warning: Canvas has invalid size for displaying image.")
             return # Cannot display on invalid canvas size


        # Get image dimensions
        img_height, img_width = cv2_image.shape[:2]

        if img_width <= 1 or img_height <= 1:
             print("Warning: Image has invalid size for displaying.")
             self.canvas.delete("all")
             self.image_calib_tk = None
             self.current_photo_tk = None
             return # Cannot display invalid image


        # Calculate scaling factor and new dimensions to fit within canvas while maintaining aspect ratio
        display_scale, offset_x, offset_y = self.get_display_scale_and_offset()

        new_width = int(img_width * display_scale)
        new_height = int(img_height * display_scale)


        # Resize image using PIL
        img_rgb = cv2.cvtColor(cv2_image, cv2.COLOR_BGR2RGB)
        img_pil = Image.fromarray(img_rgb)
        # Use LANCZOS for high-quality downsampling
        img_pil_resized = img_pil.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Convert to PhotoImage
        img_tk = ImageTk.PhotoImage(image=img_pil_resized)

        # Update the canvas
        # Delete only specific tags if managing multiple layers (e.g., live_preview vs calib_image)
        # For now, assume this is for the calibration image or a static photo
        self.canvas.delete("calibration_image") # Clear previous calibration image
        self.canvas.create_image(offset_x, offset_y, anchor=tk.NW, image=img_tk, tags="calibration_image")


        # Store the PhotoImage to prevent garbage collection
        # If it's a calibration image, store in self.image_calib_tk
        # If it's a captured photo, store in self.current_photo_tk
        # Need a way to differentiate or manage which one is currently displayed
        # Let's store the currently displayed PhotoImage in self.image_calib_tk for static images.
        self.image_calib_tk = img_tk # Overwrite for current displayed static image


    def list_camera_resolutions(self):
        """Lists all supported resolutions for the specified camera device using v4l2-ctl."""
        device = self.device_entry.get()
        if not device:
            messagebox.showerror("Error", "请填写摄像头设备路径 (例如: /dev/video0)。")
            return

        try:
            # Check if v4l2-ctl is available
            subprocess.run(["v4l2-ctl", "--version"], check=True, capture_output=True, text=True)
        except FileNotFoundError:
            messagebox.showerror("Error", "未找到 v4l2-ctl 命令。请安装 v4l-utils (例如，在 Ubuntu 上运行 'sudo apt install v4l-utils')。")
            print("Error: v4l2-ctl not found.")
            return
        except subprocess.CalledProcessError:
            messagebox.showerror("Error", "运行 v4l2-ctl 失败。请确保已正确安装 v4l-utils。")
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
            # print(f"Debug: v4l2-ctl output:\n{output}") # Uncomment for debug

            supported_resolutions = set() # Use a set to store unique resolutions

            # Use regex to find all occurrences of "Size: Discrete XXXXxYYYY"
            resolution_pattern = re.compile(r'Size: Discrete (\d+x\d+)')

            for line in output.splitlines():
                line = line.strip()
                match = resolution_pattern.search(line)
                if match:
                    resolution = match.group(1)
                    supported_resolutions.add(resolution) # Add to the set

            if not supported_resolutions:
                messagebox.showerror(
                    "Error",
                    f"未找到设备 {device} 支持的分辨率。设备可能无效、未连接或配置不正确。"
                )
                print(f"Error: No resolutions found for device {device}.")
                self.resolution_combobox['values'] = []
                self.capture_button.config(state=tk.DISABLED)
                return

            # Convert the set to a list and sort by width
            sorted_resolutions = sorted(list(supported_resolutions), key=lambda x: int(x.split('x')[0]))

            self.resolution_combobox['values'] = sorted_resolutions
            if sorted_resolutions:
                # Select a common high-definition resolution if available, otherwise the first one
                if "1920x1080" in sorted_resolutions:
                     self.resolution_combobox.set("1920x1080")
                elif "1280x720" in sorted_resolutions:
                     self.resolution_combobox.set("1280x720")
                else:
                     self.resolution_combobox.set(sorted_resolutions[0])

            self.capture_button.config(state=tk.NORMAL)
            # messagebox.showinfo("分辨率", f"支持的分辨率:\n{', '.join(sorted_resolutions)}") # Can be annoying, uncomment if needed
            print(f"Supported resolutions for {device}: {sorted_resolutions}")

        except subprocess.CalledProcessError as e:
            messagebox.showerror(
                "Error",
                f"访问设备 {device} 失败。设备可能无效、未连接或配置不正确。"
            )
            print(f"Error accessing device {device}: {e}")
            self.resolution_combobox['values'] = []
            self.capture_button.config(state=tk.DISABLED)
        except Exception as e:
            messagebox.showerror("Error", f"列出分辨率时发生错误: {e}")
            print(f"Error listing resolutions for {device}: {e}")
            self.resolution_combobox['values'] = []
            self.capture_button.config(state=tk.DISABLED)

    def start_preview(self):
        """Starts the camera preview."""
        device = self.device_entry.get()
        resolution_str = self.resolution_combobox.get()
        if not device or not resolution_str:
            messagebox.showwarning("警告", "请在开始预览前指定设备并选择分辨率。")
            return

        if self.is_previewing:
            print("预览已在运行中。")
            return

        # Clear any currently displayed static image or points
        self.canvas.delete("all")
        self.image_calib_tk = None
        self.current_photo_tk = None
        self.image_calib_cv2 = None # Clear calibration image data


        try:
            width, height = map(int, resolution_str.split('x'))
            # Use CAP_V4L2 for Linux, potentially adjust for other OS if needed
            self.cap = cv2.VideoCapture(device, cv2.CAP_V4L2)

            if not self.cap.isOpened():
                messagebox.showerror("错误", f"无法打开摄像头设备 {device}。请确保它未被其他应用程序占用。")
                self.stop_preview() # Ensure cleanup even on failure
                return

            # Try setting the resolution
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

            # Verify if resolution was set correctly (optional but good practice)
            actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            if actual_width != width or actual_height != height:
                 print(f"警告: 请求的分辨率 {resolution_str} 未被摄像头完全支持。正在使用 {actual_width}x{actual_height}。预览将被缩放以适应画布。")

            self.is_previewing = True
            self.capture_button.config(text="捕获帧")
            # Disable controls while previewing
            self.list_resolutions_button.config(state=tk.DISABLED)
            self.device_entry.config(state=tk.DISABLED)
            self.resolution_combobox.config(state=tk.DISABLED)

            # Start the preview update loop in a separate thread
            self.preview_thread = threading.Thread(target=self.update_preview)
            self.preview_thread.daemon = True # Allow thread to exit with the main application
            self.preview_thread.start()

        except ValueError:
             messagebox.showerror("错误", f"无效的分辨率格式: {resolution_str}")
             self.stop_preview()
        except Exception as e:
            messagebox.showerror("错误", f"启动摄像头预览时发生错误: {e}")
            print(f"Error starting camera preview: {e}")
            self.stop_preview() # Ensure cleanup on error

    def update_preview(self):
        """Reads frames from the camera and updates the canvas, scaling to fit."""
        try:
            while self.is_previewing and self.cap and self.cap.isOpened():
                ret, frame = self.cap.read()
                if not ret:
                    print("警告: 无法从摄像头读取帧。")
                    # Add a small delay and continue, might be temporary issue
                    time.sleep(0.05)
                    continue

                # Store the latest frame for capture
                self.latest_frame = frame

                # Get current canvas dimensions to scale the frame
                canvas_width = self.canvas.winfo_width()
                canvas_height = self.canvas.winfo_height()

                if canvas_width <= 1 or canvas_height <= 1:
                     # Canvas not ready or too small, skip displaying
                     time.sleep(0.01)
                     continue

                # Get frame dimensions
                frame_height, frame_width, _ = frame.shape

                if frame_width <= 1 or frame_height <= 1:
                     print("警告: 收到无效的帧大小以进行显示。")
                     time.sleep(0.01)
                     continue

                # Calculate scaling factor to fit within canvas while maintaining aspect ratio
                # Since we don't store the cv2 image for preview in self.image_calib_cv2,
                # we need to calculate scale and offset based on current frame size
                scale_w = canvas_width / frame_width
                scale_h = canvas_height / frame_height
                display_scale = min(scale_w, scale_h)

                new_width = int(frame_width * display_scale)
                new_height = int(frame_height * display_scale)

                offset_x = (canvas_width - new_width) // 2
                offset_y = (canvas_height - new_height) // 2


                # Resize frame using PIL
                cv2image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img_pil = Image.fromarray(cv2image)
                # Use LANCZOS for high-quality downsampling
                img_pil_resized = img_pil.resize((new_width, new_height), Image.Resampling.LANCZOS)

                # Convert to PhotoImage
                self.image_calib_tk = ImageTk.PhotoImage(image=img_pil_resized) # Reuse for preview

                # Update the image on the canvas. Delete previous preview image.
                self.canvas.delete("live_preview")
                # Calculate position to center the scaled image on the canvas
                self.canvas.create_image(offset_x, offset_y, anchor=tk.NW, image=self.image_calib_tk, tags="live_preview")

                # Process GUI events to keep it responsive
                self.root.update_idletasks()

                # Short delay to control frame rate (optional, update_idletasks might be sufficient)
                # time.sleep(0.005) # Adjust as needed

            print("预览更新循环已停止。")
        except Exception as e:
            print(f"预览更新循环中发生错误: {e}")
            # Stop preview gracefully if an error occurs in the loop
            self.root.after(0, self.stop_preview) # Use after to call stop_preview on the main thread


    def stop_preview(self):
        """Stops the camera preview and releases the camera."""
        if self.is_previewing:
            self.is_previewing = False # Signal the thread to stop
            # It's good practice to wait for the thread to finish if it's not a daemon thread,
            # but since it's a daemon thread, it will exit when the main app exits.
            # If you weren't using daemon threads, you'd do:
            # if self.preview_thread and self.preview_thread.is_alive():
            #     self.preview_thread.join()

            if self.cap and self.cap.isOpened():
                self.cap.release()
                print("摄像头已释放。")
            self.cap = None
            self.latest_frame = None # Clear the latest frame

            # Clear the live preview image from canvas and any potential old calibration markers/text
            self.canvas.delete("live_preview")
            # Optionally reset canvas to default background or message
            # self.canvas.delete("all") # Only clear if you want everything gone
            # Center text on the canvas
            canvas_center_x = self.canvas.winfo_width() / 2
            canvas_center_y = self.canvas.winfo_height() / 2
            if canvas_center_x > 0 and canvas_center_y > 0: # Ensure canvas has valid dimensions
                 self.canvas.create_text(canvas_center_x, canvas_center_y, text="预览已停止", fill="black", font=('Arial', 16, 'bold'))


            # Restore button and control states
            self.capture_button.config(text="开始预览")
            self.list_resolutions_button.config(state=tk.NORMAL)
            self.device_entry.config(state=tk.NORMAL)
            self.resolution_combobox.config(state="readonly")

            # If calibration image was loaded before preview, redraw it
            if self.image_calib_cv2 is not None:
                 self.display_image_on_canvas(self.image_calib_cv2)
                 self.draw_points() # Redraw calibration points
                 self.verify_untransformed_points() # Redraw verification points


    def toggle_preview(self):
        """Toggles the camera preview on and off, or captures a frame if preview is running."""
        if self.is_previewing:
            self.capture_frame() # If preview is running, capture frame and stop
        else:
            self.start_preview() # If not previewing, start the preview

    def capture_frame(self):
        """Captures a single frame from the current preview (if running) and saves it."""
        if not self.is_previewing or self.latest_frame is None:
            messagebox.showwarning("警告", "没有正在运行的预览或帧可捕获。")
            # Ensure preview is stopped if somehow in a bad state
            self.stop_preview()
            return

        # Use the latest frame stored in the update_preview loop
        frame_to_save = self.latest_frame

        # Get the current resolution from the camera object if possible, or rely on the combobox
        if self.cap and self.cap.isOpened():
             width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
             height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
             resolution = f"{width}x{height}"
        else:
             # Fallback to combobox value, though less reliable after start_preview
             resolution = self.resolution_combobox.get()
             print(f"警告: 相机对象不可用，使用组合框中的分辨率 ({resolution}) 作为文件名。")


        # Generate filename with Beijing timezone (UTC+8) timestamp
        # Ensure you have timezone and timedelta imported
        beijing_tz = timezone(timedelta(hours=8))
        timestamp = datetime.now(beijing_tz).strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"capture_{timestamp}_{resolution}.jpg"
        filepath = os.path.join(os.getcwd(), filename)

        try:
            # Save the image
            cv2.imwrite(filepath, frame_to_save)
            messagebox.showinfo("成功", f"照片已捕获并保存为:\n{filepath}")
            print(f"照片已捕获并保存到 {filepath}")

            # Optionally display the captured photo on the canvas after stopping preview
            # Store the captured frame in a different variable if you want to distinguish it from calib image
            # self.captured_photo_cv2 = frame_to_save
            # self.display_image_on_canvas(self.captured_photo_cv2) # Call display function if you want to show the photo

        except Exception as e:
            messagebox.showerror("错误", f"保存捕获照片时发生错误: {e}")
            print(f"Error saving captured photo: {e}")
        finally:
             # Always stop the preview after capturing a frame
             self.stop_preview()


    def load_calib_image(self):
        filepath = filedialog.askopenfilename(
            title="选择标定图像文件",
            filetypes=(("Image files", "*.jpg *.jpeg *.png *.bmp *.tiff"), ("All files", "*.*"))
        )
        if not filepath:
            return
        # Stop any ongoing preview before loading a new image
        self.stop_preview() # This also clears the canvas

        img = cv2.imread(filepath)
        if img is None:
            messagebox.showerror("错误", f"无法从 {filepath} 加载标定图像")
            print(f"Debug: cv2.imread failed for {filepath}")
            return
        print(f"Debug: cv2.imread successful. Image shape: {img.shape}")
        self.image_calib_path = filepath
        self.image_calib_cv2 = img # Store the original cv2 image

        # Display the image on the canvas, scaled to fit and centered
        self.display_image_on_canvas(self.image_calib_cv2)

        # Get image resolution and update the window title
        if self.image_calib_cv2 is not None:
            height, width = self.image_calib_cv2.shape[:2]
            self.root.title(f"Homography Calibrator - {os.path.basename(filepath)} ({width}x{height})")
        else:
            self.root.title("Homography Calibrator from Label Studio JSON") # Reset title if image loading failed


        print(f"标定图像已加载: {self.image_calib_path}")
        self.point_label.config(text="图像已加载。现在加载 JSON。")
        self.load_calib_json_button.config(state=tk.NORMAL)
        # self.load_world_coords_button.config(state=tk.DISABLED) # Ensure this is disabled until JSON is loaded


        self.homography_text.config(state=tk.NORMAL)
        self.homography_text.delete(1.0, tk.END)
        self.homography_text.insert(tk.END, f"图像已加载: {os.path.basename(self.image_calib_path)}\n下一步加载 JSON。")
        self.homography_text.config(state=tk.DISABLED)


    def load_calib_json(self):
        if self.image_calib_cv2 is None:
            messagebox.showwarning("请先加载图像", "请先加载标定图像文件，然后加载 JSON 文件。")
            return
        filepath = filedialog.askopenfilename(
            title="选择 Label Studio 标定 JSON 文件",
            filetypes=(("JSON files", "*.json"), ("All files", "*.*"))
        )
        if not filepath:
            return
        try:
            with open(filepath, 'r') as f:
                export_data = json.load(f)

            # Basic validation of Label Studio export format
            if not export_data or not isinstance(export_data, list) or not export_data[0] or 'annotations' not in export_data[0] or not export_data[0]['annotations']:
                messagebox.showerror("错误", "无效或意外的 Label Studio JSON 格式。")
                self.reset_calibration_json_data()
                return

            task_data = export_data[0]
            annotations = task_data.get('annotations', [])
            if not annotations:
                messagebox.showerror("错误", "JSON 中未找到标注。")
                self.reset_calibration_json_data()
                return

            results = annotations[0].get('result', [])
            if not results:
                messagebox.showwarning("未找到标注结果", "JSON 中未找到标注结果。")
                self.reset_calibration_json_data()
                self.point_label.config(text="JSON 已加载，但未找到点。")
                return

            # Find original image dimensions from JSON for scaling calculation
            original_width_json = None
            original_height_json = None
            for res in results:
                if 'original_width' in res and 'original_height' in res:
                    original_width_json = res['original_width']
                    original_height_json = res['original_height']
                    break

            img_orig_height, img_orig_width = self.image_calib_cv2.shape[:2]

            # Handle cases where original_width/height might be missing in JSON
            if original_width_json is None or original_height_json is None:
                messagebox.showwarning("JSON 中缺少尺寸信息", "在 JSON 结果中找不到 original_width/height。\n将使用加载的图像尺寸进行点缩放。")
                effective_original_width = img_orig_width
                effective_original_height = img_orig_height
            else:
                # Check for dimension mismatch between JSON and loaded image
                if int(original_width_json) != img_orig_width or int(original_height_json) != img_orig_height:
                    response = messagebox.askyesno(
                        "尺寸不匹配",
                        f"JSON 尺寸 ({original_width_json}x{original_height_json}) "
                        f"与加载的图像尺寸 ({img_orig_width}x{img_orig_height}) 不匹配。\n"
                        "来自 JSON 的点坐标可能对该图像不正确。\n"
                        "您确定要加载这些点吗？"
                    )
                    if not response:
                        self.reset_calibration_json_data()
                        return
                    print("警告: 尺寸不匹配已确认。将基于加载的图像尺寸继续加载点。")
                    effective_original_width = img_orig_width
                    effective_original_height = img_orig_height
                else:
                    effective_original_width = original_width_json
                    effective_original_height = original_height_json

            # print(f"Debug: Effective Original Dimensions (used for scaling from JSON %): {effective_original_width}x{effective_original_height}") # Uncomment for debug


            self.points_calib_data = []

            # Process keypoint annotations
            for res in results:
                if res['type'] == 'keypointlabels' and 'x' in res['value'] and 'y' in res['value']:
                    x_percent = res['value']['x']
                    y_percent = res['value']['y']
                    # Get the label, default to empty string if not present or list is empty
                    label = res['value'].get('keypointlabels', [''])
                    label = label[0] if isinstance(label, list) and label else ''
                    # Generate a default label if it's still empty or None
                    if not label:
                        label = f'Point {len(self.points_calib_data) + 1}'


                    # Calculate pixel coordinates relative to the *original* image size
                    if effective_original_width > 0 and effective_original_height > 0:
                         pixel_x_orig = (x_percent / 100.0) * effective_original_width
                         pixel_y_orig = (y_percent / 100.0) * effective_original_height
                    else:
                         print("警告: 从 JSON 的 % 缩放点时，有效的原始尺寸为零！")
                         # Fallback to scaling based on actual image original size (less accurate if JSON dimensions were different)
                         pixel_x_orig = (x_percent / 100.0) * img_orig_width
                         pixel_y_orig = (y_percent / 100.0) * img_orig_height


                    self.points_calib_data.append({
                        'label': label,
                        'pixel_orig': (pixel_x_orig, pixel_y_orig), # Store original pixel coordinates
                        'flat': None, # Real-world coordinates (initially None)
                        'tk_id': None, # Tkinter canvas ID for the point marker
                        'pixel_display': None # Will be calculated when drawing
                    })

            if not self.points_calib_data:
                messagebox.showwarning("未找到关键点", "在结果中未找到关键点标注。")
                self.reset_calibration_json_data() # Clear JSON data if no points found
                self.point_label.config(text="JSON 已加载，但未找到点。")
                return

            print(f"已从 JSON 加载 {len(self.points_calib_data)} 个关键点。")
            # Draw the loaded points on the canvas. This will now use the pixel_orig and calculate display coords.
            self.draw_points()
            self.enable_calibration_controls() # Enable relevant controls
            self.point_label.config(text="JSON 已加载。点击点以输入坐标。")

            self.homography_text.config(state=tk.NORMAL)
            self.homography_text.delete(1.0, tk.END)
            self.homography_text.insert(tk.END, f"JSON 已加载: {os.path.basename(filepath)}\n找到 {len(self.points_calib_data)} 个点。\n点击点以输入平面坐标或导入世界坐标。")
            self.homography_text.config(state=tk.DISABLED)

            # Enable the Load World Coords button after points are loaded
            self.load_world_coords_button.config(state=tk.NORMAL)


        except FileNotFoundError:
            messagebox.showerror("错误", f"未找到 JSON 文件: {filepath}")
            self.reset_calibration_json_data()
        except json.JSONDecodeError:
            messagebox.showerror("格式错误", f"JSON 文件格式无效: {filepath}")
            self.reset_calibration_json_data()
        except Exception as e:
            messagebox.showerror("发生错误", str(e))
            import traceback
            traceback.print_exc() # Print traceback for debugging
            self.reset_calibration_json_data()


    def reset_calibration_data_and_display(self):
        """Resets all calibration related data and clears the canvas."""
        # Stop preview first if it's running
        self.stop_preview() # This also clears the canvas and points

        # Clear calibration specific data
        self.image_calib_cv2 = None
        self.image_calib_tk = None
        self.image_calib_path = None
        self.points_calib_data = [] # Reset the point data
        self.active_point_index = -1
        self.disable_calibration_controls()
        self.point_label.config(text="加载标定图像文件。")
        self.load_calib_json_button.config(state=tk.DISABLED)
        self.load_world_coords_button.config(state=tk.DISABLED) # Disable Load World Coords button
        self.homography_text.config(state=tk.NORMAL)
        self.homography_text.delete(1.0, tk.END)
        self.homography_text.insert(tk.END, "加载标定图像文件。")
        self.homography_text.config(state=tk.DISABLED)
        self.homography_matrix = None
        self.clear_verification_display()
        self.verify_button.config(state=tk.DISABLED)

        # Reset window title
        self.root.title("Homography Calibrator from Label Studio JSON")


    def reset_calibration_json_data(self):
        """Resets only the JSON loaded calibration data and clears points from canvas."""
        self.canvas.delete("point_marker")
        self.canvas.delete("point_label_text")
        self.canvas.delete("point_label_outline")
        self.points_calib_data = [] # Reset the point data
        self.active_point_index = -1
        # Keep image loaded state, but disable JSON-dependent controls
        self.disable_calibration_controls() # This might need adjustment if you want to keep some controls enabled after image load
        self.point_label.config(text="JSON 数据已清除。请再次加载 JSON。")
        self.load_world_coords_button.config(state=tk.DISABLED) # Disable Load World Coords button
        self.homography_text.config(state=tk.NORMAL)
        self.homography_text.delete(1.0, tk.END)
        self.homography_text.insert(tk.END, "JSON 数据已清除。\n请再次加载 JSON。")
        self.homography_text.config(state=tk.DISABLED)
        self.homography_matrix = None
        self.clear_verification_display()
        self.verify_button.config(state=tk.DISABLED)


    def draw_points(self):
        """Draws or updates point markers and labels on the canvas."""
        # Ensure calibration image is loaded and there are points to draw, and not in preview mode
        if self.image_calib_cv2 is None or not self.points_calib_data or self.is_previewing:
            # Clear any existing points if conditions are not met
            self.canvas.delete("point_marker")
            self.canvas.delete("point_label_text")
            self.canvas.delete("point_label_outline")
            return

        # Delete existing point representations before redrawing
        self.canvas.delete("point_marker")
        self.canvas.delete("point_label_text")
        self.canvas.delete("point_label_outline")

        # Get the scaling and offset needed to map original image coordinates to canvas display coordinates
        display_scale, offset_x, offset_y = self.get_display_scale_and_offset()

        if display_scale <= 1e-8: # Avoid division by near zero or invalid scale
             print("警告: 显示比例为零或无效，无法正确绘制点。")
             return


        for i, point_data in enumerate(self.points_calib_data):
            # Use the original pixel coordinates for calculation
            if 'pixel_orig' not in point_data or not isinstance(point_data['pixel_orig'], (tuple, list)) or len(point_data['pixel_orig']) != 2:
                 print(f"警告: 点 {point_data.get('label', i)} 的原始像素坐标格式无效。")
                 continue # Skip drawing this point

            x_orig, y_orig = point_data['pixel_orig']
            label = point_data['label']

            # Calculate the display coordinates on the canvas
            x_display = x_orig * display_scale + offset_x
            y_display = y_orig * display_scale + offset_y

            # Store the calculated display coordinates
            point_data['pixel_display'] = (x_display, y_display)

            # Determine color based on whether flat coordinates are set
            color = "red" if point_data.get('flat') is None else "blue" # Use .get for safety

            # Determine outline color based on active point
            outline_color = "yellow" if i == self.active_point_index else "black"

            # Ensure coordinates are integers for canvas drawing
            x_int, y_int = int(round(x_display)), int(round(y_display))

            # Draw the point marker (oval)
            point_data['tk_id'] = self.canvas.create_oval(
                x_int - 5, y_int - 5, x_int + 5, y_int + 5,
                fill=color, outline=outline_color, width=2, tags="point_marker"
            )

            # Draw the label text (outline and then main text for better visibility)
            # Adjust text position relative to the point
            text_x = x_int + 10
            text_y = y_int - 10

            # Draw outline text (black)
            self.canvas.create_text(
                text_x, text_y, text=label, anchor=tk.NW, font=('Arial', 10, 'bold'),
                fill="black", tags="point_label_outline"
            )

            # Draw main text (white)
            self.canvas.create_text(
                text_x, text_y, text=label, anchor=tk.NW, font=('Arial', 10, 'bold'),
                fill="white", tags="point_label_text"
            )


    def on_canvas_click(self, event):
        """Handles click events on the canvas to select a point."""
        # Ignore clicks if calibration image is not loaded or no points exist, or in preview mode
        if self.image_calib_cv2 is None or not self.points_calib_data or self.is_previewing:
            return

        click_x, click_y = event.x, event.y
        min_dist = float('inf')
        closest_point_index = -1
        tolerance = 15 # Pixel tolerance for clicking on a point

        # Find the closest point to the click coordinates within the tolerance
        for i, point_data in enumerate(self.points_calib_data):
             # Use the calculated display coordinates for click detection
             if 'pixel_display' not in point_data or not isinstance(point_data['pixel_display'], (tuple, list)) or len(point_data['pixel_display']) != 2:
                  continue # Skip invalid points

             px_display, py_display = point_data['pixel_display']

             # Calculate distance from the click point to the point marker's center on the canvas
             dist = np.sqrt((click_x - px_display)**2 + (click_y - py_display)**2)

             if dist < tolerance and dist < min_dist:
                min_dist = dist
                closest_point_index = i

        # Set the closest point as the active point
        self.set_active_point(closest_point_index)


    def set_active_point(self, index):
        """Sets the currently active point for coordinate input."""
        # If no points loaded, ensure no point is active and controls are disabled
        if not self.points_calib_data:
            self.active_point_index = -1
            self.disable_calibration_controls()
            # Re-enable load buttons which might be disabled by disable_calibration_controls
            self.load_calib_image_button.config(state=tk.NORMAL)
            # Check if image is loaded to enable load json button
            if self.image_calib_cv2 is not None:
                 self.load_calib_json_button.config(state=tk.NORMAL)
            # Ensure Load World Coords button is also handled if JSON points are cleared
            self.load_world_coords_button.config(state=tk.DISABLED)
            return

        # If the clicked index is the same as the current active index, do nothing
        if self.active_point_index == index:
            return

        # If there was a previously active point, reset its outline color
        if self.active_point_index != -1:
            prev_point_data = self.points_calib_data[self.active_point_index]
            # Check if the canvas item exists before trying to configure it
            if prev_point_data['tk_id'] is not None and self.canvas.find_withtag(prev_point_data['tk_id']):
                self.canvas.itemconfig(prev_point_data['tk_id'], outline="black")

        # Set the new active point index
        self.active_point_index = index

        # Update the controls and label based on the new active point
        if index != -1:
            point_data = self.points_calib_data[index]

            # Display pixel and world coordinates in the point label
            pixel_orig_str = f"原始像素: ({point_data['pixel_orig'][0]:.2f}, {point_data['pixel_orig'][1]:.2f})" if 'pixel_orig' in point_data and point_data['pixel_orig'] is not None else "原始像素: N/A"
            # Check if 'flat' exists and is not None before formatting
            if point_data.get('flat') is not None:
                 world_coord_str = f"世界坐标: ({point_data['flat'][0]:.2f}, {point_data['flat'][1]:.2f})"
                 # Populate the flat coordinate entries
                 self.flat_x_entry.delete(0, tk.END)
                 self.flat_x_entry.insert(0, str(point_data['flat'][0]))
                 self.flat_y_entry.delete(0, tk.END)
                 self.flat_y_entry.insert(0, str(point_data['flat'][1]))
            else:
                 world_coord_str = "世界坐标: 未设置"
                 # Clear the entry fields
                 self.flat_x_entry.delete(0, tk.END)
                 self.flat_y_entry.delete(0, tk.END)


            self.point_label.config(text=f"编辑点: {point_data['label']} | {pixel_orig_str} | {world_coord_str}")


            # Enable flat coordinate entries and save/delete buttons
            self.flat_x_entry.config(state=tk.NORMAL)
            self.flat_y_entry.config(state=tk.NORMAL)
            self.save_button.config(state=tk.NORMAL)
            self.delete_button.config(state=tk.NORMAL)


            # Update the outline color of the newly active point
            if point_data['tk_id'] is not None and self.canvas.find_withtag(point_data['tk_id']):
                self.canvas.itemconfig(point_data['tk_id'], outline="yellow")
        else:
            # If no point is active, reset the label and disable controls
            self.point_label.config(text="点击点进行编辑")
            self.flat_x_entry.config(state=tk.DISABLED)
            self.flat_y_entry.config(state=tk.DISABLED)
            self.save_button.config(state=tk.DISABLED)
            self.delete_button.config(state=tk.DISABLED)
            self.flat_x_entry.delete(0, tk.END) # Clear entries when no point is selected
            self.flat_y_entry.delete(0, tk.END) # Clear entries when no point is selected


        # Check if enough points have flat coordinates to enable the calculate button
        self.check_calculate_button_state()


    def save_coordinates(self):
        """Saves the entered real-world coordinates for the active point."""
        # Ensure there is an active point and calibration data exists
        if self.active_point_index == -1 or not self.points_calib_data or self.active_point_index >= len(self.points_calib_data):
            print("错误: 没有有效的活动点尝试保存。")
            return

        try:
            # Get and convert the values from the entry fields
            x_flat = float(self.flat_x_entry.get())
            y_flat = float(self.flat_y_entry.get())

            # Store the flat coordinates in the active point's data
            self.points_calib_data[self.active_point_index]['flat'] = (x_flat, y_flat)
            point_label = self.points_calib_data[self.active_point_index]['label']
            print(f"已为点 '{point_label}' 手动保存世界坐标: ({x_flat}, {y_flat})")

            # Redraw points to update the color of the saved point
            self.draw_points()

            # Update the point label to show the saved coordinates
            self.set_active_point(self.active_point_index)


        except ValueError:
            messagebox.showwarning("无效输入", "请输入有效的数字作为 X 和 Y 值。")
        except IndexError:
             print(f"错误: 活动点索引 {self.active_point_index} 超出了 points_calib_data 的范围。")
             self.set_active_point(-1) # Reset active point

        # Check if enough points have flat coordinates to enable the calculate button
        self.check_calculate_button_state()


    def delete_coordinates(self):
        """Deletes the real-world coordinates for the active point."""
        # Ensure there is an active point and calibration data exists
        if self.active_point_index == -1 or not self.points_calib_data or self.active_point_index >= len(self.points_calib_data):
            print("错误: 没有有效的活动点尝试删除。")
            return

        try:
            point_label = self.points_calib_data[self.active_point_index]['label']

            # Ask for confirmation before deleting
            if messagebox.askyesno("确认删除", f"确定要删除点 '{point_label}' 的坐标吗？"):
                # Set the flat coordinates to None
                self.points_calib_data[self.active_point_index]['flat'] = None
                print(f"已删除点 '{point_label}' 的世界坐标。")

                # Clear the entry fields
                self.flat_x_entry.delete(0, tk.END)
                self.flat_y_entry.delete(0, tk.END)

                # Redraw points to update the color of the deleted point
                self.draw_points()

                # Clear the active point selection
                self.set_active_point(-1)

        except IndexError:
             print(f"错误: 删除期间活动点索引 {self.active_point_index} 超出了范围。")
             self.set_active_point(-1) # Reset active point


        # Check if enough points have flat coordinates to enable the calculate button
        self.check_calculate_button_state()


    def check_calculate_button_state(self):
        """Checks if there are enough points with flat coordinates to enable the calculate button."""
        # Count points that have non-None flat coordinates
        valid_points_count = sum(1 for p in self.points_calib_data if p.get('flat') is not None) # Use .get for safety


        # Enable the calculate button if at least 4 points have flat coordinates
        if valid_points_count >= 4:
            self.calculate_button.config(state=tk.NORMAL)
            self.homography_text.config(state=tk.NORMAL)
            self.homography_text.delete(1.0, tk.END)
            self.homography_text.insert(tk.END, f"准备使用 {valid_points_count} 个点计算 Homography 矩阵。")
            self.homography_text.config(state=tk.DISABLED)
        else:
            self.calculate_button.config(state=tk.DISABLED)
            self.homography_text.config(state=tk.NORMAL)
            self.homography_text.delete(1.0, tk.END)
            self.homography_text.insert(tk.END, f"需要至少 4 个点具有坐标 (当前 {valid_points_count} 个点)。")
            self.homography_text.config(state=tk.DISABLED)

        # Also check if the export buttons should be enabled
        export_enabled = valid_points_count > 0
        # Original export is enabled if *any* points are loaded from JSON, regardless of flat coords
        self.export_button.config(state=tk.NORMAL if self.points_calib_data else tk.DISABLED)
        # New export is enabled if at least one point has flat coordinates
        self.export_world_coords_button.config(state=tk.NORMAL if export_enabled else tk.DISABLED) # Enable new export button

        self.verify_button.config(state=tk.NORMAL if self.homography_matrix is not None else tk.DISABLED) # Verify needs matrix


    def transform_pixel_to_world(self, pixel_x_orig, pixel_y_orig):
        """Transforms a pixel coordinate from the *original* image to real-world coordinates."""
        if self.homography_matrix is None:
            print("错误: Homography 矩阵不可用，无法进行转换。")
            return None

        # The homography matrix H was calculated using original image coordinates,
        # so we use the original pixel coordinates directly here.

        H = self.homography_matrix
        pixel_coord_homogeneous = np.array([[pixel_x_orig], [pixel_y_orig], [1.0]])
        transformed_homogeneous_coord = np.dot(H, pixel_coord_homogeneous)

        # Perform perspective division
        sX = transformed_homogeneous_coord[0, 0]
        sY = transformed_homogeneous_coord[1, 0]
        s = transformed_homogeneous_coord[2, 0]

        # Handle potential division by zero
        if abs(s) < 1e-8: # Use a small epsilon to check for near-zero
            print(f"警告: 原始像素 ({pixel_x_orig:.2f}, {pixel_y_orig:.2f}) 的透视除以零或接近零。结果可能在无穷远处。")
            return None

        world_X = sX / s
        world_Y = sY / s

        return (float(world_X), float(world_Y))


    def calculate_homography(self):
        """Calculates the homography matrix using the selected points."""
        src_pts = [] # Points in the image plane (pixel coordinates - original image size)
        dst_pts = [] # Points in the real-world plane (flat coordinates)
        calculation_points_info = [] # To store info for printing

        if self.image_calib_cv2 is None:
            messagebox.showwarning("未加载图像", "未加载标定图像。")
            return

        # Homography is calculated from original image coordinates to world coordinates
        for point_data in self.points_calib_data:
            # Only use points that have both original pixel and flat coordinates
            if point_data.get('flat') is not None and point_data.get('pixel_orig') is not None:
                 x_orig, y_orig = point_data['pixel_orig']
                 flat_x, flat_y = point_data['flat']
                 src_pts.append((x_orig, y_orig))
                 dst_pts.append(point_data['flat'])
                 calculation_points_info.append({
                     'label': point_data['label'],
                     'pixel_orig': (x_orig, y_orig),
                     'flat': (flat_x, flat_y)
                 })


        # Need at least 4 points to calculate a homography
        if len(src_pts) < 4:
            messagebox.showwarning("点不足", "需要至少 4 对具有像素和世界坐标的对应点才能计算 Homography 矩阵。")
            self.homography_matrix = None
            self.homography_text.config(state=tk.NORMAL)
            self.homography_text.delete(1.0, tk.END)
            self.homography_text.insert(tk.END, "需要至少 4 个点具有坐标。")
            self.homography_text.config(state=tk.DISABLED)
            self.verify_button.config(state=tk.DISABLED)
            return

        # Print the points used for calculation
        print("\n用于计算 Homography 矩阵的点:")
        for p_info in calculation_points_info:
             print(f"  标签: {p_info['label']}, 原始像素: ({p_info['pixel_orig'][0]:.2f}, {p_info['pixel_orig'][1]:.2f}), 世界坐标: ({p_info['flat'][0]:.2f}, {p_info['flat'][1]:.2f})")


        # Convert lists to NumPy arrays for OpenCV
        src_pts = np.array(src_pts, dtype=np.float32)
        dst_pts = np.array(dst_pts, dtype=np.float32)

        try:
            # Calculate the homography matrix using RANSAC for robustness
            # RANSAC parameters: 5.0 is the maximum allowed reprojection error in pixels (in the original image scale)
            H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
            # You can optionally check the 'mask' to see which points were considered inliers

            self.homography_matrix = H

            # Display the calculated homography matrix in the text area
            self.homography_text.config(state=tk.NORMAL)
            self.homography_text.delete(1.0, tk.END)
            self.homography_text.insert(tk.END, "计算出的 Homography 矩阵 (H):\n")
            # Format the matrix display for better readability
            matrix_str = np.array2string(H, precision=4, suppress_small=True, separator=', ')
            self.homography_text.insert(tk.END, matrix_str)
            self.homography_text.config(state=tk.DISABLED)

            print("\n计算出的 Homography 矩阵:")
            print(H)

            # Enable the verification button after successful calculation
            self.verify_button.config(state=tk.NORMAL)

            # Redraw points and verification if they exist
            self.draw_points()
            self.verify_untransformed_points()


        except Exception as e:
            # Handle errors during calculation
            messagebox.showerror("计算错误", f"无法计算 Homography 矩阵: {e}")
            self.homography_matrix = None
            self.homography_text.config(state=tk.NORMAL)
            self.homography_text.delete(1.0, tk.END)
            self.homography_text.insert(tk.END, f"计算过程中发生错误: {e}")
            self.homography_text.config(state=tk.DISABLED)
            self.verify_button.config(state=tk.DISABLED)


    def export_coordinates_to_json(self):
        """Exports the loaded original pixel coordinates to a JSON file (Label Studio format)."""
        # Ensure there are points loaded
        if not self.points_calib_data:
            messagebox.showwarning("无数据", "未从 JSON 加载标定点。")
            return

        # Create a basic structure similar to Label Studio export, but simplified
        # Note: This exports the original pixel points loaded from the input JSON,
        # NOT the manually entered world coordinates.
        export_data = []
        task_result = []

        # Get original dimensions from the loaded calibration image if available
        original_width = self.image_calib_cv2.shape[1] if self.image_calib_cv2 is not None else None
        original_height = self.image_calib_cv2.shape[0] if self.image_calib_cv2 is not None else None


        for point_data in self.points_calib_data:
             # Calculate percentage based on original dimensions if available
             # Ensure division by zero is handled
             x_percent = (point_data['pixel_orig'][0] / original_width) * 100 if original_width and original_width > 0 else 0
             y_percent = (point_data['pixel_orig'][1] / original_height) * 100 if original_height and original_height > 0 else 0


             result_item = {
                "type": "keypointlabels",
                "value": {
                    "x": x_percent,
                    "y": y_percent,
                    "keypointlabels": [point_data.get('label', 'Unnamed Point')]
                },
                # Add original dimensions if known
                "original_width": original_width,
                "original_height": original_height,
                # You might add 'from_name', 'to_name', 'source', etc. if needed for full LS format
            }
             task_result.append(result_item)

        # Wrap the results in a task structure (simplified)
        task = {
            "annotations": [{"result": task_result}],
            # Add other task-level info if needed (e.g., 'data', 'id')
            # For this simple export, we just focus on the results
        }
        export_data.append(task)


        # Ask the user where to save the JSON file
        filepath = filedialog.asksaveasfilename(
            title="保存原始点 JSON (Label Studio 样式)",
            defaultextension=".json",
            filetypes=(("JSON files", "*.json"), ("All files", "*.*"))
        )
        if not filepath:
            return # User cancelled the save dialog

        try:
            # Write the data to the JSON file with indentation for readability
            with open(filepath, 'w', encoding='utf-8') as f: # Added encoding for broader compatibility
                json.dump(export_data, f, indent=4, ensure_ascii=False) # ensure_ascii=False for non-ASCII chars in labels

            messagebox.showinfo("导出成功", f"原始点已导出到:\n{filepath}")
            print(f"原始点已导出到 {filepath}")

        except Exception as e:
            # Handle errors during file saving
            messagebox.showerror("导出错误", f"保存文件时发生错误: {e}")
            print(f"Error saving original points to {filepath}: {e}")


    def export_world_coordinates_to_json(self):
        """Exports the manually entered real-world coordinates to a JSON file."""
        # Ensure there are points loaded
        if not self.points_calib_data:
            messagebox.showwarning("无数据", "未加载标定点。")
            return

        export_list = []
        # Collect points that have real-world coordinates assigned
        for point_data in self.points_calib_data:
            if point_data.get('flat') is not None: # Use .get for safety
                export_item = {
                    "label": point_data.get('label', 'Unnamed Point'), # Use .get with default
                    "world_x": point_data['flat'][0],
                    "world_y": point_data['flat'][1]
                }
                # Optionally add original pixel coordinates if stored
                if point_data.get('pixel_orig') is not None:
                     export_item["pixel_x_orig"] = point_data['pixel_orig'][0]
                     export_item["pixel_y_orig"] = point_data['pixel_orig'][1]

                export_list.append(export_item)


        # If no points have world coordinates, warn the user
        if not export_list:
            messagebox.showwarning("无数据", "尚未为任何点输入世界坐标。")
            return

        # Ask the user where to save the JSON file
        filepath = filedialog.asksaveasfilename(
            title="保存世界坐标 JSON",
            defaultextension=".json",
            filetypes=(("JSON files", "*.json"), ("All files", "*.*"))
        )
        if not filepath:
            return # User cancelled the save dialog

        try:
            # Write the data to the JSON file with indentation for readability
            with open(filepath, 'w', encoding='utf-8') as f: # Added encoding for broader compatibility
                json.dump(export_list, f, indent=4, ensure_ascii=False) # ensure_ascii=False for non-ASCII chars in labels

            messagebox.showinfo("导出成功", f"世界坐标已导出到:\n{filepath}")
            print(f"世界坐标已导出到 {filepath}")

        except Exception as e:
            # Handle errors during file saving
            messagebox.showerror("导出错误", f"保存文件时发生错误: {e}")
            print(f"Error saving coordinates to {filepath}: {e}")


    def verify_untransformed_points(self):
        """Transforms pixel coordinates of points without flat coordinates and displays the results."""
        # Ensure homography matrix is available and calibration image is loaded
        if self.homography_matrix is None:
            # messagebox.showwarning("无矩阵", "尚未计算 Homography 矩阵。") # Avoid excessive popups
            self.clear_verification_display() # Clear any old markers
            self.verify_button.config(state=tk.DISABLED)
            return

        if self.image_calib_cv2 is None:
             print("警告: 未加载标定图像，无法显示验证标记。")
             self.clear_verification_display()
             return


        # Clear previous verification markers
        self.clear_verification_display()

        points_to_verify = []
        # Identify points that do *not* have flat coordinates but have original pixel coordinates
        for point_data in self.points_calib_data:
            if point_data.get('flat') is None and point_data.get('pixel_orig') is not None:
                points_to_verify.append(point_data)

        if not points_to_verify:
            # messagebox.showinfo("无点可验证", "所有加载的点都已输入世界坐标或无效的像素数据。") # Avoid excessive popups
            self.clear_verification_display() # Ensure cleared if no points
            return

        print("\n正在验证未转换的点...")
        points_verified_count = 0

        # Get the scaling and offset for the current canvas display
        display_scale, offset_x, offset_y = self.get_display_scale_and_offset()

        if display_scale <= 1e-8:
             print("警告: 显示比例为零或无效，无法显示验证标记。")
             return


        for point_data in points_to_verify:
            # Use the original pixel coordinates for transformation
            x_orig, y_orig = point_data['pixel_orig']
            label = point_data['label']

            # Transform the original pixel coordinate to a world coordinate
            world_coord = self.transform_pixel_to_world(x_orig, y_orig)

            if world_coord:
                world_x, world_y = world_coord
                print(f"  '{label}' (原始像素: {x_orig:.2f}, {y_orig:.2f}) -> 世界坐标 (计算值): ({world_x:.2f}, {world_y:.2f})")

                # Calculate the display coordinates on the canvas for drawing the verification marker
                x_display = x_orig * display_scale + offset_x
                y_display = y_orig * display_scale + offset_y


                # Draw a marker (e.g., a circle) at the *displayed* pixel location
                x_int, y_int = int(round(x_display)), int(round(y_display))

                point_id = self.canvas.create_oval(
                    x_int - 7, y_int - 7, x_int + 7, y_int + 7,
                    outline="lime green", width=2, tags="verification_marker"
                )
                self.verification_tk_ids.append(point_id) # Store ID to clear later

                # Draw the calculated world coordinates as text next to the marker
                text_label = f"({world_x:.2f}, {world_y:.2f})"
                text_id = self.canvas.create_text(
                    x_int + 15, y_int + 5, text=text_label, anchor=tk.NW, font=('Arial', 9, 'bold'),
                    fill="lime green", tags="verification_marker"
                )
                self.verification_tk_ids.append(text_id) # Store ID to clear later

                points_verified_count += 1

        if self.verification_tk_ids:
            # Enable the clear verify button if any markers were drawn
            self.clear_verify_button.config(state=tk.NORMAL)
            print(f"已为 {points_verified_count} 个点显示计算出的世界坐标。")
        else:
            print("无法为任何未转换的点计算世界坐标。")
            # messagebox.showinfo("验证", "无法为任何未转换的点计算世界坐标。") # Avoid excessive popups


    def clear_verification_display(self):
        """Clears the verification markers and text from the canvas."""
        if self.verification_tk_ids:
            print("正在清除验证显示。")
            for item_id in self.verification_tk_ids:
                # Check if the item still exists on the canvas before deleting
                if self.canvas.find_withtag(item_id):
                     self.canvas.delete(item_id)
            self.verification_tk_ids = [] # Clear the list of IDs
            self.clear_verify_button.config(state=tk.DISABLED)


    def enable_calibration_controls(self):
        """Enables controls related to calibration data editing and calculation."""
        # Individual point editing controls (save, delete) are enabled when a point is clicked.
        # Calculate button is enabled based on number of points with flat coordinates.
        self.check_calculate_button_state() # This handles calculate and export buttons

        # The Load World Coords button should be enabled once points are loaded from the initial JSON
        if self.points_calib_data:
             self.load_world_coords_button.config(state=tk.NORMAL)
        else:
             self.load_world_coords_button.config(state=tk.DISABLED)

        # Verify button is enabled after homography is calculated (checked in check_calculate_button_state)


    def disable_calibration_controls(self):
        """Disables controls related to calibration data editing and calculation."""
        self.flat_x_entry.config(state=tk.DISABLED)
        self.flat_y_entry.config(state=tk.DISABLED)
        self.save_button.config(state=tk.DISABLED)
        self.delete_button.config(state=tk.DISABLED)
        self.calculate_button.config(state=tk.DISABLED)
        self.export_button.config(state=tk.DISABLED)
        self.export_world_coords_button.config(state=tk.DISABLED) # Disable new export button
        self.verify_button.config(state=tk.DISABLED)
        self.clear_verify_button.config(state=tk.DISABLED)
        self.load_calib_json_button.config(state=tk.DISABLED) # Also disable load JSON button when resetting


    # Removed the load_image_info method entirely


if __name__ == "__main__":
    root = tk.Tk()
    app = HomographyCalibratorApp(root)
    root.mainloop()