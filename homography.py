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
import re
import threading # Import threading for the camera feed loop
import time # Import time for potential sleep in preview loop

class HomographyCalibratorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Homography Calibrator from Label Studio JSON")

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
        self.calib_display_width = 0
        self.calib_display_height = 0
        self.points_calib_data = []
        self.active_point_index = -1
        self.homography_matrix = None
        self.verification_tk_ids = []
        self.image_info_path = None
        self.image_info_pil = None

        # Camera Capture Data
        self.cap = None # OpenCV VideoCapture object
        self.is_previewing = False # Flag to indicate if preview is running
        self.preview_thread = None # Thread for the camera preview loop
        self.latest_frame = None # Store the latest frame from the camera

        # --- GUI Elements ---
        main_pane = ttk.Panedwindow(root, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Canvas for displaying images/preview
        self.canvas = tk.Canvas(main_pane, bg="gray")
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        main_pane.add(self.canvas, weight=1)

        # Controls Frame
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

        device_label = ttk.Label(self.controls_frame, text="Camera Device:")
        device_label.grid(row=14, column=0, padx=2, pady=2, sticky=tk.W)
        self.device_entry = ttk.Entry(self.controls_frame)
        self.device_entry.insert(0, "/dev/video0") # Default device
        self.device_entry.grid(row=14, column=1, padx=2, pady=2, sticky=tk.W+tk.E)

        self.list_resolutions_button = ttk.Button(self.controls_frame, text="List Resolutions", command=self.list_camera_resolutions)
        self.list_resolutions_button.grid(row=15, column=0, columnspan=2, pady=2, sticky=tk.W+tk.E)

        resolution_label = ttk.Label(self.controls_frame, text="Resolution:")
        resolution_label.grid(row=16, column=0, padx=2, pady=2, sticky=tk.W)
        self.resolution_combobox = ttk.Combobox(self.controls_frame, state="readonly")
        self.resolution_combobox.grid(row=16, column=1, padx=2, pady=2, sticky=tk.W+tk.E)

        # Button to toggle preview/capture
        self.capture_button = ttk.Button(self.controls_frame, text="Start Preview", command=self.toggle_preview, state=tk.DISABLED)
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

        # Configure row weights for expandability
        self.controls_frame.rowconfigure(11, weight=1)
        self.controls_frame.rowconfigure(22, weight=1)

        # Bind the close event to stop the preview if it's running
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)


    def on_closing(self):
        """Handles the window closing event to stop the camera preview."""
        self.stop_preview()
        self.root.destroy()

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
            print(f"Debug: v4l2-ctl output:\n{output}")

            supported_resolutions = set() # Use a set to store unique resolutions

            # Use regex to find all occurrences of "Size: Discrete XXXXxYYYY"
            # The pattern looks for "Size: Discrete " followed by digits, an 'x', and more digits.
            # It captures the digitsXdigits part.
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
                    f"No supported resolutions found for device {device}. "
                    "The device may be invalid, not connected, or not properly configured."
                )
                print(f"Error: No resolutions found for device {device}.")
                self.resolution_combobox['values'] = []
                self.capture_button.config(state=tk.DISABLED)
                return

            # Convert the set to a list and sort by width
            sorted_resolutions = sorted(list(supported_resolutions), key=lambda x: int(x.split('x')[0]))

            self.resolution_combobox['values'] = sorted_resolutions
            if sorted_resolutions:
                self.resolution_combobox.set(sorted_resolutions[0]) # Set the default value
            self.capture_button.config(state=tk.NORMAL)
            messagebox.showinfo("Resolutions", f"Supported resolutions:\n{', '.join(sorted_resolutions)}")
            print(f"Supported resolutions for {device}: {sorted_resolutions}")

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

    def start_preview(self):
        """Starts the camera preview."""
        device = self.device_entry.get()
        resolution_str = self.resolution_combobox.get()
        if not device or not resolution_str:
            messagebox.showwarning("Warning", "Please specify device and select a resolution before starting preview.")
            return

        if self.is_previewing:
            print("Preview is already running.")
            return

        try:
            width, height = map(int, resolution_str.split('x'))
            # Use CAP_V4L2 for Linux, potentially adjust for other OS if needed
            self.cap = cv2.VideoCapture(device, cv2.CAP_V4L2)

            if not self.cap.isOpened():
                messagebox.showerror("Error", f"Could not open camera device {device}. Make sure it is not in use by another application.")
                self.stop_preview() # Ensure cleanup even on failure
                return

            # Try setting the resolution
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

            # Verify if resolution was set correctly (optional but good practice)
            actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            if actual_width != width or actual_height != height:
                 print(f"Warning: Requested resolution {resolution_str} not fully supported. "
                       f"Using {actual_width}x{actual_height}. This might affect the displayed aspect ratio.")
                 # You might want to update the resolution_str variable here if you plan to use it later

            self.is_previewing = True
            self.capture_button.config(text="Capture Frame")
            # Disable controls while previewing
            self.list_resolutions_button.config(state=tk.DISABLED)
            self.device_entry.config(state=tk.DISABLED)
            self.resolution_combobox.config(state=tk.DISABLED)

            # Clear the canvas before displaying the camera feed
            self.canvas.delete("all")
            # Adjust canvas size. You might want to scale this to fit the window better
            self.canvas.config(width=actual_width, height=actual_height)


            # Start the preview update loop in a separate thread
            self.preview_thread = threading.Thread(target=self.update_preview)
            self.preview_thread.daemon = True # Allow thread to exit with the main application
            self.preview_thread.start()

        except ValueError:
             messagebox.showerror("Error", f"Invalid resolution format: {resolution_str}")
             self.stop_preview()
        except Exception as e:
            messagebox.showerror("Error", f"Error starting camera preview: {e}")
            print(f"Error starting camera preview: {e}")
            self.stop_preview() # Ensure cleanup on error

    def update_preview(self):
        """Reads frames from the camera and updates the canvas."""
        try:
            while self.is_previewing:
                ret, frame = self.cap.read()
                if not ret:
                    print("Warning: Could not read frame from camera.")
                    # Add a small delay and continue, might be temporary issue
                    time.sleep(0.05)
                    continue

                # Store the latest frame for capture
                self.latest_frame = frame

                # Convert the OpenCV frame (BGR) to RGB for PIL
                cv2image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # Convert to PIL Image and then to ImageTk format
                img_pil = Image.fromarray(cv2image)

                # --- Optional: Resize image to fit canvas if necessary ---
                # Get current canvas dimensions (they might change if window is resized)
                # canvas_width = self.canvas.winfo_width()
                # canvas_height = self.canvas.winfo_height()

                # Get actual frame dimensions
                # frame_height, frame_width, _ = frame.shape

                # Calculate scaling factor if needed
                # scale_w = canvas_width / frame_width
                # scale_h = canvas_height / frame_height
                # scale = min(scale_w, scale_h)

                # if scale < 1.0: # Only resize if image is larger than canvas
                #     new_width = int(frame_width * scale)
                #     new_height = int(frame_height * scale)
                #     img_pil = img_pil.resize((new_width, new_height), Image.Resampling.LANCZOS)
                # --------------------------------------------------------


                self.image_calib_tk = ImageTk.PhotoImage(image=img_pil) # Reuse the calibration image tk variable for simplicity
                # Update the image on the canvas. Delete previous image to avoid overlap.
                self.canvas.delete("live_preview")
                self.canvas.create_image(0, 0, anchor=tk.NW, image=self.image_calib_tk, tags="live_preview")

                # A short delay to control frame rate and allow GUI updates
                time.sleep(0.01) # Adjust this value to control preview frame rate

        except Exception as e:
            print(f"Error in preview update loop: {e}")
            # Handle error, potentially stop preview gracefully
            self.stop_preview()

    def stop_preview(self):
        """Stops the camera preview and releases the camera."""
        if self.is_previewing:
            self.is_previewing = False # Signal the thread to stop
            # No need to explicitly join daemon thread, it will exit with app

            if self.cap and self.cap.isOpened():
                self.cap.release()
                print("Camera released.")
            self.cap = None
            self.latest_frame = None # Clear the latest frame
            self.canvas.delete("live_preview") # Clear the live preview image from canvas

            # Restore button and control states
            self.capture_button.config(text="Start Preview")
            self.list_resolutions_button.config(state=tk.NORMAL)
            self.device_entry.config(state=tk.NORMAL)
            self.resolution_combobox.config(state="readonly")

            # Optionally clear the canvas or show a static image
            # self.canvas.delete("all") # Clear everything, including potential calibration points if not careful
            # Or show a message:
            # self.canvas.create_text(self.canvas.winfo_width()/2, self.canvas.winfo_height()/2, text="Preview Stopped", fill="black", font=('Arial', 16, 'bold'))


    def toggle_preview(self):
        """Toggles the camera preview on and off, or captures a frame if preview is running."""
        if self.is_previewing:
            self.capture_frame() # If preview is running, capture frame and stop
        else:
            self.start_preview() # If not previewing, start the preview

    def capture_frame(self):
        """Captures a single frame from the current preview (if running) and saves it."""
        if not self.is_previewing or self.latest_frame is None:
            messagebox.showwarning("Warning", "No preview running or frame available to capture.")
            # Ensure preview is stopped if somehow in a bad state
            self.stop_preview()
            return

        # Use the latest frame stored in the update_preview loop
        frame_to_save = self.latest_frame

        # Get the current resolution from the camera object if possible, or rely on the combobox
        # Relying on cap.get is more accurate if resolution wasn't set exactly as requested
        if self.cap and self.cap.isOpened():
             width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
             height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
             resolution = f"{width}x{height}"
        else:
             # Fallback to combobox value, though less reliable after start_preview
             resolution = self.resolution_combobox.get()
             print(f"Warning: Using resolution from combobox ({resolution}) for filename as camera object is not available.")


        # Generate filename with Beijing timezone (UTC+8) timestamp
        # Ensure you have timezone and timedelta imported
        beijing_tz = timezone(timedelta(hours=8))
        timestamp = datetime.now(beijing_tz).strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"capture_{timestamp}_{resolution}.jpg"
        filepath = os.path.join(os.getcwd(), filename)

        try:
            # Save the image
            cv2.imwrite(filepath, frame_to_save)
            messagebox.showinfo("Success", f"Photo captured and saved as:\n{filepath}")
            print(f"Photo captured and saved to {filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"Error saving captured photo: {e}")
            print(f"Error saving captured photo: {e}")
        finally:
             # Always stop the preview after capturing a frame
             self.stop_preview()


    def load_calib_image(self):
        filepath = filedialog.askopenfilename(
            title="Select Calibration Image File",
            filetypes=(("Image files", "*.jpg *.jpeg *.png *.bmp *.tiff"), ("All files", "*.*"))
        )
        if not filepath:
            return
        # Stop any ongoing preview before loading a new image
        self.stop_preview()
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

        # Scale image to fit within a reasonable screen percentage
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
        # print(f"Debug: ImageTk.PhotoImage created: {self.image_calib_tk}") # Too verbose

        self.canvas.config(width=display_width, height=display_height)
        self.canvas.delete("all") # Clear everything, including potential old preview items
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.image_calib_tk)
        print(f"Debug: Canvas configured size (target display size): {display_width}x{display_height}")
        self.canvas.update_idletasks()
        # print(f"Debug: Canvas content after create_image: {self.canvas.find_all()}") # Too verbose
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

            # Basic validation of Label Studio export format
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
                messagebox.showwarning("Missing Dimensions in JSON", "Could not find original_width/height in JSON results.\nUsing loaded image dimensions for point scaling.")
                effective_original_width = img_orig_width
                effective_original_height = img_orig_height
            else:
                # Check for dimension mismatch between JSON and loaded image
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
                print(f"Debug: Stored display size is incorrect: {display_width}x{display_height}. Proceeding with point loading, but accuracy may be affected.")
                # Continue loading points but warn the user.
                # Resetting json data might be too harsh here if the image loaded correctly.
                # self.reset_calibration_json_data()
                # return
                pass # Allow loading but warn

            # Process keypoint annotations
            for res in results:
                if res['type'] == 'keypointlabels' and 'x' in res['value'] and 'y' in res['value']:
                    x_percent = res['value']['x']
                    y_percent = res['value']['y']
                    # Get the label, default to empty string if not present or list is empty
                    label = res['value'].get('keypointlabels', [''])
                    label = label[0] if isinstance(label, list) and label else ''
                    label = label or f'Point {len(self.points_calib_data) + 1}' # Generate default label if empty

                    # Scale points from original JSON dimensions to the original image dimensions
                    # This is necessary if the JSON dimensions don't match the actual image dimensions
                    # which can happen if the image was resized outside of Label Studio after annotation.
                    if effective_original_width > 0 and effective_original_height > 0:
                         pixel_x_orig = (x_percent / 100.0) * effective_original_width
                         pixel_y_orig = (y_percent / 100.0) * effective_original_height
                    else:
                         print("Warning: Effective original dimensions are zero during point scaling from JSON %!")
                         # Fallback to scaling based on display size, but this is less accurate
                         pixel_x_orig = (x_percent / 100.0) * img_orig_width # Use actual image original size
                         pixel_y_orig = (y_percent / 100.0) * img_orig_height


                    # Now scale the original image pixel coordinates to the currently displayed image size
                    if img_orig_width > 0 and img_orig_height > 0 and display_width > 0 and display_height > 0:
                         pixel_x_display = pixel_x_orig * (display_width / img_orig_width)
                         pixel_y_display = pixel_y_orig * (display_height / img_orig_height)
                    else:
                         print("Warning: Original image or display dimensions are zero during point scaling to display!")
                         # Fallback directly from JSON percentage to display size, least accurate
                         pixel_x_display = (x_percent / 100.0) * display_width
                         pixel_y_display = (y_percent / 100.0) * display_height


                    self.points_calib_data.append({
                        'label': label,
                        'pixel': (pixel_x_display, pixel_y_display),
                        'flat': None, # Real-world coordinates
                        'tk_id': None # Tkinter canvas ID for the point marker
                    })

            if not self.points_calib_data:
                messagebox.showwarning("No Keypoints", "No keypoint annotations found in the result.")
                self.reset_calibration_json_data() # Clear JSON data if no points found
                self.point_label.config(text="JSON loaded, but no points found.")
                return

            print(f"Loaded {len(self.points_calib_data)} keypoints from JSON.")
            self.draw_points() # Draw the loaded points on the canvas
            self.enable_calibration_controls() # Enable relevant controls
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
            traceback.print_exc() # Print traceback for debugging
            self.reset_calibration_json_data()


    def reset_calibration_data_and_display(self):
        """Resets all calibration related data and clears the canvas."""
        # Stop preview first if it's running
        self.stop_preview()
        self.canvas.delete("all") # Clear the canvas
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
        """Resets only the JSON loaded calibration data and clears points from canvas."""
        self.canvas.delete("point_marker")
        self.canvas.delete("point_label_text")
        self.canvas.delete("point_label_outline")
        self.points_calib_data = []
        self.active_point_index = -1
        # Keep image loaded state, but disable JSON-dependent controls
        self.disable_calibration_controls() # This might need adjustment if you want to keep some controls enabled after image load
        self.point_label.config(text="JSON data cleared. Load JSON again.")
        self.homography_text.config(state=tk.NORMAL)
        self.homography_text.delete(1.0, tk.END)
        self.homography_text.insert(tk.END, "JSON data cleared.\nLoad JSON again.")
        self.homography_text.config(state=tk.DISABLED)
        self.homography_matrix = None
        self.clear_verification_display()
        self.verify_button.config(state=tk.DISABLED)


    def draw_points(self):
        """Draws or updates point markers and labels on the canvas."""
        if self.image_calib_cv2 is None or not self.points_calib_data:
            # Clear any existing points if image is not loaded or no points
            self.canvas.delete("point_marker")
            self.canvas.delete("point_label_text")
            self.canvas.delete("point_label_outline")
            return

        # Delete existing point representations before redrawing
        self.canvas.delete("point_marker")
        self.canvas.delete("point_label_text")
        self.canvas.delete("point_label_outline")

        for i, point_data in enumerate(self.points_calib_data):
            # Ensure pixel coordinates are numbers before drawing
            if not isinstance(point_data['pixel'], (tuple, list)) or len(point_data['pixel']) != 2:
                 print(f"Warning: Invalid pixel coordinate format for point {point_data.get('label', i)}: {point_data['pixel']}")
                 continue # Skip drawing this point

            x_float, y_float = point_data['pixel']
            label = point_data['label']

            # Determine color based on whether flat coordinates are set
            color = "red" if point_data['flat'] is None else "blue"

            # Determine outline color based on active point
            outline_color = "yellow" if i == self.active_point_index else "black"

            # Ensure coordinates are integers for canvas drawing
            x_int, y_int = int(round(x_float)), int(round(y_float))

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
        # Ignore clicks if calibration image is not loaded or no points exist
        if self.image_calib_cv2 is None or not self.points_calib_data:
            return

        click_x, click_y = event.x, event.y
        min_dist = float('inf')
        closest_point_index = -1
        tolerance = 15 # Pixel tolerance for clicking on a point

        # Find the closest point to the click coordinates within the tolerance
        for i, point_data in enumerate(self.points_calib_data):
             # Ensure pixel coordinates are valid
             if not isinstance(point_data['pixel'], (tuple, list)) or len(point_data['pixel']) != 2:
                  continue # Skip invalid points

             px_float, py_float = point_data['pixel']
             dist = np.sqrt((click_x - px_float)**2 + (click_y - py_float)**2)

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
            self.disable_calibration_controls() # This might disable too much depending on desired state after image load
            # Keep image load/json load enabled
            self.load_calib_image_button.config(state=tk.NORMAL)
            if self.image_calib_cv2 is not None: # Allow loading JSON if image is present
                self.load_calib_json_button.config(state=tk.NORMAL)
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
            self.point_label.config(text=f"Editing: {point_data['label']} (Pixel: {point_data['pixel'][0]:.2f}, {point_data['pixel'][1]:.2f})")

            # Enable flat coordinate entries and save/delete buttons
            self.flat_x_entry.config(state=tk.NORMAL)
            self.flat_y_entry.config(state=tk.NORMAL)
            self.save_button.config(state=tk.NORMAL)
            self.delete_button.config(state=tk.NORMAL)

            # Populate the flat coordinate entries if they exist for this point
            if point_data['flat'] is not None:
                self.flat_x_entry.delete(0, tk.END)
                self.flat_x_entry.insert(0, str(point_data['flat'][0]))
                self.flat_y_entry.delete(0, tk.END)
                self.flat_y_entry.insert(0, str(point_data['flat'][1]))
            else:
                self.flat_x_entry.delete(0, tk.END)
                self.flat_y_entry.delete(0, tk.END)

            # Update the outline color of the newly active point
            if point_data['tk_id'] is not None and self.canvas.find_withtag(point_data['tk_id']):
                self.canvas.itemconfig(point_data['tk_id'], outline="yellow")
        else:
            # If no point is active, reset the label and disable controls
            self.point_label.config(text="Click a point to edit")
            self.flat_x_entry.config(state=tk.DISABLED)
            self.flat_y_entry.config(state=tk.DISABLED)
            self.save_button.config(state=tk.DISABLED)
            self.delete_button.config(state=tk.DISABLED)

        # Check if enough points have flat coordinates to enable the calculate button
        self.check_calculate_button_state()


    def save_coordinates(self):
        """Saves the entered real-world coordinates for the active point."""
        # Ensure there is an active point and calibration data exists
        if self.active_point_index == -1 or not self.points_calib_data:
            return

        try:
            # Get and convert the values from the entry fields
            x_flat = float(self.flat_x_entry.get())
            y_flat = float(self.flat_y_entry.get())

            # Store the flat coordinates in the active point's data
            self.points_calib_data[self.active_point_index]['flat'] = (x_flat, y_flat)
            print(f"Saved flat coordinates ({x_flat}, {y_flat}) for {self.points_calib_data[self.active_point_index]['label']}")

            # Redraw points to update the color of the saved point
            self.draw_points()

            # Keep the same point active after saving
            # self.set_active_point(self.active_point_index)
            # Or you might want to clear the selection: self.set_active_point(-1)
            # For now, keep active to allow quick editing
            pass

        except ValueError:
            messagebox.showwarning("Invalid Input", "Please enter valid numerical values for X and Y.")

        # Check if enough points have flat coordinates to enable the calculate button
        self.check_calculate_button_state()


    def delete_coordinates(self):
        """Deletes the real-world coordinates for the active point."""
        # Ensure there is an active point and calibration data exists
        if self.active_point_index == -1 or not self.points_calib_data:
            return

        point_label = self.points_calib_data[self.active_point_index]['label']

        # Ask for confirmation before deleting
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete coordinates for {point_label}?"):
            # Set the flat coordinates to None
            self.points_calib_data[self.active_point_index]['flat'] = None
            print(f"Deleted flat coordinates for {point_label}")

            # Clear the entry fields
            self.flat_x_entry.delete(0, tk.END)
            self.flat_y_entry.delete(0, tk.END)

            # Redraw points to update the color of the deleted point
            self.draw_points()

            # Clear the active point selection
            self.set_active_point(-1)

        # Check if enough points have flat coordinates to enable the calculate button
        self.check_calculate_button_state()


    def check_calculate_button_state(self):
        """Checks if there are enough points with flat coordinates to enable the calculate button."""
        # Count points that have non-None flat coordinates
        valid_points_count = sum(1 for p in self.points_calib_data if p['flat'] is not None)

        # Enable the calculate button if at least 4 points have flat coordinates
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

        # Also check if the export button should be enabled
        self.export_button.config(state=tk.NORMAL if valid_points_count > 0 else tk.DISABLED)
        self.verify_button.config(state=tk.NORMAL if self.homography_matrix is not None else tk.DISABLED) # Verify needs matrix


    def transform_pixel_to_world(self, pixel_x_display, pixel_y_display):
        """Transforms a pixel coordinate from the *displayed* image to real-world coordinates."""
        if self.homography_matrix is None:
            print("Error: Homography matrix not available for transformation.")
            return None
        if self.image_calib_cv2 is None:
            print("Error: Calibration image not loaded for scaling.")
            return None

        # Get original image dimensions from the loaded calibration image
        orig_height, orig_width = self.image_calib_cv2.shape[:2]
        if orig_width <= 0 or orig_height <= 0:
            print("Error: Invalid original image dimensions for scaling.")
            return None

        # Get the dimensions of the currently displayed image on the canvas
        display_width = self.calib_display_width
        display_height = self.calib_display_height
        if display_width <= 0 or display_height <= 0:
            print("Error: Invalid display dimensions stored for scaling.")
            return None

        # Scale the pixel coordinates from the displayed image size back to the original image size
        # The homography matrix H was calculated using original image coordinates
        scaled_pixel_x = pixel_x_display * (orig_width / display_width)
        scaled_pixel_y = pixel_y_display * (orig_height / display_height)

        # Perform the homography transformation
        H = self.homography_matrix
        pixel_coord_homogeneous = np.array([[scaled_pixel_x], [scaled_pixel_y], [1.0]])
        transformed_homogeneous_coord = np.dot(H, pixel_coord_homogeneous)

        # Perform perspective division
        sX = transformed_homogeneous_coord[0, 0]
        sY = transformed_homogeneous_coord[1, 0]
        s = transformed_homogeneous_coord[2, 0]

        # Handle potential division by zero
        if abs(s) < 1e-8: # Use a small epsilon to check for near-zero
            print(f"Warning: Perspective division by zero or near-zero for pixel ({pixel_x_display:.2f}, {pixel_y_display:.2f}). Result may be at infinity.")
            return None

        world_X = sX / s
        world_Y = sY / s

        return (float(world_X), float(world_Y))


    def calculate_homography(self):
        """Calculates the homography matrix using the selected points."""
        src_pts = [] # Points in the image plane (pixel coordinates - original image size)
        dst_pts = [] # Points in the real-world plane (flat coordinates)

        if self.image_calib_cv2 is None:
            messagebox.showwarning("Image Not Loaded", "Calibration image is not loaded.")
            return

        # Get the dimensions of the currently displayed image on the canvas
        display_width = self.calib_display_width
        display_height = self.calib_display_height
        if display_width <= 0 or display_height <= 0:
            messagebox.showerror("Display Error", "Invalid display dimensions stored. Cannot scale pixel coordinates.")
            return

        # Get original image dimensions from the loaded calibration image
        orig_height, orig_width = self.image_calib_cv2.shape[:2]
        if orig_width <= 0 or orig_height <= 0:
            messagebox.showerror("Image Error", "Invalid original image dimensions.")
            return


        for point_data in self.points_calib_data:
            # Only use points that have both pixel and flat coordinates
            if point_data['flat'] is not None and point_data['pixel'] is not None:
                # Scale pixel coordinates from the displayed image size back to the original image size
                display_pixel_x, display_pixel_y = point_data['pixel']

                if display_width > 0 and display_height > 0 and orig_width > 0 and orig_height > 0:
                     scaled_pixel_x = display_pixel_x * (orig_width / display_width)
                     scaled_pixel_y = display_pixel_y * (orig_height / display_height)
                else:
                     print("Warning: Cannot scale pixel coordinates due to zero dimensions.")
                     continue # Skip this point if dimensions are invalid


                src_pts.append((scaled_pixel_x, scaled_pixel_y))
                dst_pts.append(point_data['flat'])

        # Need at least 4 points to calculate a homography
        if len(src_pts) < 4:
            messagebox.showwarning("Not Enough Points", "Need at least 4 corresponding points with both pixel and real-world coordinates to calculate homography.")
            self.homography_matrix = None
            self.homography_text.config(state=tk.NORMAL)
            self.homography_text.delete(1.0, tk.END)
            self.homography_text.insert(tk.END, "Need at least 4 points with coordinates.")
            self.homography_text.config(state=tk.DISABLED)
            self.verify_button.config(state=tk.DISABLED)
            return

        # Convert lists to NumPy arrays for OpenCV
        src_pts = np.array(src_pts, dtype=np.float32)
        dst_pts = np.array(dst_pts, dtype=np.float32)

        try:
            # Calculate the homography matrix using RANSAC for robustness
            # RANSAC parameters: 5.0 is the maximum allowed reprojection error in pixels
            H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
            # You can optionally check the 'mask' to see which points were considered inliers

            self.homography_matrix = H

            # Display the calculated homography matrix in the text area
            self.homography_text.config(state=tk.NORMAL)
            self.homography_text.delete(1.0, tk.END)
            self.homography_text.insert(tk.END, "Calculated Homography Matrix (H):\n")
            self.homography_text.insert(tk.END, str(H)) # Insert the numpy array string representation
            self.homography_text.config(state=tk.DISABLED)

            print("\nCalculated Homography Matrix:")
            print(H)

            # Enable the verification button after successful calculation
            self.verify_button.config(state=tk.NORMAL)

        except Exception as e:
            # Handle errors during calculation
            messagebox.showerror("Calculation Error", f"Could not compute homography: {e}")
            self.homography_matrix = None
            self.homography_text.config(state=tk.NORMAL)
            self.homography_text.delete(1.0, tk.END)
            self.homography_text.insert(tk.END, f"Error during calculation: {e}")
            self.homography_text.config(state=tk.DISABLED)
            self.verify_button.config(state=tk.DISABLED)


    def export_coordinates_to_json(self):
        """Exports the collected real-world coordinates to a JSON file."""
        # Ensure there are points loaded
        if not self.points_calib_data:
            messagebox.showwarning("No Data", "No calibration points loaded.")
            return

        export_list = []
        # Collect points that have real-world coordinates assigned
        for point_data in self.points_calib_data:
            if point_data['flat'] is not None:
                export_list.append({
                    "label": point_data['label'],
                    "world_x": point_data['flat'][0],
                    "world_y": point_data['flat'][1]
                    # You might want to add original pixel coordinates too
                    # "pixel_x_orig": point_data['pixel_orig'][0],
                    # "pixel_y_orig": point_data['pixel_orig'][1]
                })

        # If no points have world coordinates, warn the user
        if not export_list:
            messagebox.showwarning("No Data", "No real-world coordinates have been entered yet.")
            return

        # Ask the user where to save the JSON file
        filepath = filedialog.asksaveasfilename(
            title="Save World Coordinates JSON",
            defaultextension=".json",
            filetypes=(("JSON files", "*.json"), ("All files", "*.*"))
        )
        if not filepath:
            return # User cancelled the save dialog

        try:
            # Write the data to the JSON file with indentation for readability
            with open(filepath, 'w') as f:
                json.dump(export_list, f, indent=4)

            messagebox.showinfo("Export Successful", f"Real-world coordinates exported to:\n{filepath}")
            print(f"Real-world coordinates exported to {filepath}")

        except Exception as e:
            # Handle errors during file saving
            messagebox.showerror("Export Error", f"Error saving file: {e}")
            print(f"Error saving coordinates to {filepath}: {e}")


    def verify_untransformed_points(self):
        """Transforms pixel coordinates of points without flat coordinates and displays the results."""
        # Ensure homography matrix is available
        if self.homography_matrix is None:
            messagebox.showwarning("No Matrix", "Homography matrix has not been calculated yet.")
            return

        # Clear previous verification markers
        self.clear_verification_display()

        points_to_verify = []
        # Identify points that do *not* have flat coordinates
        for point_data in self.points_calib_data:
            if point_data['flat'] is None and point_data['pixel'] is not None:
                points_to_verify.append(point_data)

        if not points_to_verify:
            messagebox.showinfo("No Points to Verify", "All loaded points already have entered real-world coordinates.")
            return

        print("\nVerifying untransformed points...")
        points_verified_count = 0

        for point_data in points_to_verify:
            pixel_x_display, pixel_y_display = point_data['pixel']
            label = point_data['label']

            # Transform the pixel coordinate to a world coordinate using the homography matrix
            world_coord = self.transform_pixel_to_world(pixel_x_display, pixel_y_display)

            if world_coord:
                world_x, world_y = world_coord
                print(f"  {label} (Pixel: {pixel_x_display:.2f}, {pixel_y_display:.2f}) -> World: ({world_x:.2f}, {world_y:.2f})")

                # Draw a marker and text on the canvas for the transformed point
                # Use the pixel coordinates on the displayed image
                x_int, y_int = int(round(pixel_x_display)), int(round(pixel_y_display))

                # Draw a marker (e.g., a circle)
                point_id = self.canvas.create_oval(
                    x_int - 7, y_int - 7, x_int + 7, y_int + 7,
                    outline="lime green", width=2, tags="verification_marker"
                )
                self.verification_tk_ids.append(point_id) # Store ID to clear later

                # Draw the calculated world coordinates as text
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
            print(f"Displayed calculated coordinates for {points_verified_count} points.")
        else:
            print("No world coordinates could be calculated for untransformed points.")
            messagebox.showinfo("Verification", "Could not calculate world coordinates for any untransformed points.")


    def clear_verification_display(self):
        """Clears the verification markers and text from the canvas."""
        if self.verification_tk_ids:
            print("Clearing verification display.")
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

        # Export button is enabled if any point has flat coordinates (checked in check_calculate_button_state)
        # self.export_button.config(state=tk.NORMAL) # Redundant

        # Verify button is enabled after homography is calculated (checked in check_calculate_button_state)
        # self.verify_button.config(state=tk.NORMAL if self.homography_matrix is not None else tk.DISABLED) # Redundant


    def disable_calibration_controls(self):
        """Disables controls related to calibration data editing and calculation."""
        self.flat_x_entry.config(state=tk.DISABLED)
        self.flat_y_entry.config(state=tk.DISABLED)
        self.save_button.config(state=tk.DISABLED)
        self.delete_button.config(state=tk.DISABLED)
        self.calculate_button.config(state=tk.DISABLED)
        self.export_button.config(state=tk.DISABLED)
        self.verify_button.config(state=tk.DISABLED)
        self.clear_verify_button.config(state=tk.DISABLED)


    def load_image_info(self):
        """Loads an image and displays its basic information and EXIF data."""
        filepath = filedialog.askopenfilename(
            title="Select Image File for Info",
            filetypes=(("Image files", "*.jpg *.jpeg *.png *.bmp *.tiff"), ("All files", "*.*"))
        )
        if not filepath:
            return # User cancelled the dialog

        try:
            # Use PIL to open the image to easily get resolution and EXIF
            self.image_info_pil = Image.open(filepath)
            self.image_info_path = filepath

            width, height = self.image_info_pil.size
            resolution_info = f"Resolution: {width} x {height} pixels\n\n"

            # Get EXIF data
            exif_data = self.image_info_pil._getexif()

            exif_info_string = "EXIF Data:\n"
            if exif_data is not None:
                # Create a dictionary mapping tag IDs to names
                exif_tags_map = { tag_id: ExifTags.TAGS.get(tag_id, tag_id) for tag_id in exif_data.keys() }

                for tag_id, value in exif_data.items():
                    tag_name = exif_tags_map.get(tag_id, tag_id)

                    # Try to decode bytes values
                    if isinstance(value, bytes):
                        try:
                            value_str = value.decode('utf-8', errors='replace')
                        except:
                            value_str = str(value) # Fallback to string representation

                    # Format tuple values, especially for rationals (like aperture, focal length)
                    elif isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], (int,float)) and isinstance(value[1], (int,float)) and value[1] != 0:
                        try:
                            value_str = f"{value[0]}/{value[1]} ({value[0]/value[1]:.2f})"
                        except:
                            value_str = f"{value[0]}/{value[1]}" # Avoid division error

                    # Handle numpy arrays if any (less common in standard EXIF)
                    elif isinstance(value, np.ndarray):
                        value_str = np.array2string(value, threshold=50, edgeitems=2) # Limit size for display

                    else:
                        value_str = str(value) # Default string representation

                    # Skip GPSInfo as it can be large and complex to display directly
                    if tag_name == 'GPSInfo':
                         # You might want to parse GPSInfo separately if needed
                         exif_info_string += f"  {tag_name}: {value}\n"
                         continue # Skip adding individual tags within GPSInfo

                    # Add other EXIF tags to the string
                    if tag_name != 'GPSInfo': # Double check not to add GPSInfo again
                        exif_info_string += f"  {tag_name}: {value_str}\n"

                # If no common EXIF tags were found, add a message
                if exif_info_string == "EXIF Data:\n":
                    exif_info_string += "  No common EXIF tags found."
            else:
                exif_info_string += "  No EXIF data found in this image."


            # Update the image info text area
            self.image_info_text.config(state=tk.NORMAL)
            self.image_info_text.delete(1.0, tk.END)
            self.image_info_text.insert(tk.END, resolution_info)
            self.image_info_text.insert(tk.END, exif_info_string)
            self.image_info_text.config(state=tk.DISABLED)

            print(f"\nLoaded image info for: {filepath}")
            print(resolution_info.strip())
            print(exif_info_string)

            # Close the PIL image to free up resources
            self.image_info_pil.close()
            self.image_info_pil = None # Clear the reference

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
            traceback.print_exc() # Print traceback for debugging
            self.image_info_text.config(state=tk.NORMAL)
            self.image_info_text.delete(1.0, tk.END)
            self.image_info_text.insert(tk.END, f"Error reading info: {e}")
            self.image_info_text.config(state=tk.DISABLED)
            # Ensure PIL image is closed even if an error occurs
            if self.image_info_pil:
                self.image_info_pil.close()
            self.image_info_pil = None
            self.image_info_path = None


if __name__ == "__main__":
    root = tk.Tk()
    app = HomographyCalibratorApp(root)
    root.mainloop()