import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox
import tkinter.ttk as ttk # Import ttk for themed widgets
import cv2
import json
import numpy as np
from PIL import Image, ImageTk, ExifTags
import os

class HomographyCalibratorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Homography Calibrator from Label Studio JSON")

        # --- Add Window Icon ---
        icon_path = "icon.png" # Assume icon.png is in the same directory as the script
        try:
            # Get the directory of the script
            script_dir = os.path.dirname(os.path.abspath(__file__))
            full_icon_path = os.path.join(script_dir, icon_path)

            if os.path.exists(full_icon_path):
                # Load the icon image using PIL
                icon_image_pil = Image.open(full_icon_path)
                # Create a PhotoImage object
                icon_photo = ImageTk.PhotoImage(icon_image_pil)
                # Set the window icon
                self.root.iconphoto(True, icon_photo) # True means use for window and dialogs
                icon_image_pil.close() # Close the PIL image file
            else:
                print(f"Warning: Icon file not found at {full_icon_path}")
        except Exception as e:
            print(f"Warning: Could not load or set window icon: {e}")
        # --- End Add Window Icon ---


        # Calibration Data
        self.image_calib_path = None  # Path for the calibration image file
        self.image_calib_cv2 = None   # OpenCV image for calibration (may be resized)
        self.image_calib_tk = None    # Tkinter image for calibration display
        self.calib_display_width = 0  # Store the calculated width for canvas display
        self.calib_display_height = 0 # Store the calculated height for canvas display

        self.points_calib_data = [] # [{'label': 'p1', 'pixel': (float_x, float_y), 'flat': (fx, fy) or None, 'tk_id': None}]
        self.active_point_index = -1  # Index of the currently selected calibration point

        self.homography_matrix = None # Store the calculated homography matrix
        self.verification_tk_ids = [] # Store IDs of elements drawn for verification


        # Image Info Data (independent)
        self.image_info_path = None   # Path for the image loaded for info
        self.image_info_pil = None    # PIL image for info (original size)


        # --- GUI Elements ---
        # Use a main pane or frame to hold the left canvas and right controls frame
        main_pane = ttk.Panedwindow(root, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=5, pady=5) # Add a little padding around the main pane

        # Left side: Canvas
        # Keep as tk.Canvas as ttk doesn't have one
        self.canvas = tk.Canvas(main_pane, bg="gray") # Set a background for clarity if no image
        self.canvas.bind("<Button-1>", self.on_canvas_click) # Bind mouse click event
        main_pane.add(self.canvas, weight=1) # Allow canvas to expand

        # Right side: Controls Frame
        # Use ttk.Frame for themed appearance
        self.controls_frame = ttk.Frame(main_pane, padding="10") # Add padding inside the frame
        main_pane.add(self.controls_frame, weight=0) # Control frame does not expand horizontally

        # Use grid for layout inside the controls_frame
        self.controls_frame.columnconfigure(0, weight=1) # Allow column 0 to expand a bit
        self.controls_frame.columnconfigure(1, weight=1) # Allow column 1 to expand a bit


        # --- Calibration Section ---
        # Use ttk.Label
        calib_label = ttk.Label(self.controls_frame, text="Calibration Section", font=('Arial', 12, 'bold'))
        calib_label.grid(row=0, column=0, columnspan=2, pady=(0, 10), sticky=tk.W) # Span across 2 columns


        # Use ttk.Button
        self.load_calib_image_button = ttk.Button(self.controls_frame, text="1. Load Calibration Image", command=self.load_calib_image)
        self.load_calib_image_button.grid(row=1, column=0, columnspan=2, pady=2, sticky=tk.W+tk.E) # Span across 2 columns


        # Use ttk.Button
        self.load_calib_json_button = ttk.Button(self.controls_frame, text="2. Load Calibration JSON", command=self.load_calib_json, state=tk.DISABLED)
        self.load_calib_json_button.grid(row=2, column=0, columnspan=2, pady=2, sticky=tk.W+tk.E) # Span across 2 columns


        # Use ttk.Label
        self.point_label = ttk.Label(self.controls_frame, text="Load image and JSON first")
        self.point_label.grid(row=3, column=0, columnspan=2, pady=(10, 5), sticky=tk.W) # Span across 2 columns

        # Real World Coordinates Input (Labels and Entries)
        self.flat_x_label = ttk.Label(self.controls_frame, text="Real World X:")
        self.flat_x_label.grid(row=4, column=0, padx=2, pady=2, sticky=tk.W)
        self.flat_x_entry = ttk.Entry(self.controls_frame, state=tk.DISABLED)
        self.flat_x_entry.grid(row=4, column=1, padx=2, pady=2, sticky=tk.W+tk.E) # Entry expands horizontally

        self.flat_y_label = ttk.Label(self.controls_frame, text="Real World Y:")
        self.flat_y_label.grid(row=5, column=0, padx=2, pady=2, sticky=tk.W)
        self.flat_y_entry = ttk.Entry(self.controls_frame, state=tk.DISABLED)
        self.flat_y_entry.grid(row=5, column=1, padx=2, pady=2, sticky=tk.W+tk.E) # Entry expands horizontally


        # --- Point Action Buttons (Side-by-Side) ---
        # Use ttk.Button
        self.save_button = ttk.Button(self.controls_frame, text="Save", command=self.save_coordinates, state=tk.DISABLED)
        self.save_button.grid(row=6, column=0, padx=2, pady=5, sticky=tk.W+tk.E) # Button expands in its column


        # Use ttk.Button
        self.delete_button = ttk.Button(self.controls_frame, text="Delete", command=self.delete_coordinates, state=tk.DISABLED)
        self.delete_button.grid(row=6, column=1, padx=2, pady=5, sticky=tk.W+tk.E) # Button expands in its column
        # --- End Point Action Buttons ---


        # Use ttk.Button
        self.calculate_button = ttk.Button(self.controls_frame, text="Calculate Homography", command=self.calculate_homography, state=tk.DISABLED)
        self.calculate_button.grid(row=7, column=0, columnspan=2, pady=(10, 5), sticky=tk.W+tk.E) # Span across 2 columns


        # --- New: Export Button ---
        # Use ttk.Button
        self.export_button = ttk.Button(self.controls_frame, text="Export Coordinates (JSON)", command=self.export_coordinates_to_json, state=tk.DISABLED)
        self.export_button.grid(row=8, column=0, columnspan=2, pady=2, sticky=tk.W+tk.E) # Span across 2 columns
        # --- End New ---


        # --- New: Verification Buttons (Side-by-Side) ---
        # Use ttk.Button
        self.verify_button = ttk.Button(self.controls_frame, text="Verify", command=self.verify_untransformed_points, state=tk.DISABLED)
        self.verify_button.grid(row=9, column=0, padx=2, pady=(10, 2), sticky=tk.W+tk.E) # Button expands in its column

        # Use ttk.Button
        self.clear_verify_button = ttk.Button(self.controls_frame, text="Clear Verify", command=self.clear_verification_display, state=tk.DISABLED)
        self.clear_verify_button.grid(row=9, column=1, padx=2, pady=(10, 2), sticky=tk.W+tk.E) # Button expands in its column
        # --- End New ---


        # Use ttk.Label
        self.homography_label = ttk.Label(self.controls_frame, text="Homography Matrix:", font=('Arial', 10, 'bold'))
        self.homography_label.grid(row=10, column=0, columnspan=2, pady=(10,0), sticky=tk.W) # Span across 2 columns

        # Use ttk.Text (no ttk equivalent, keep tk.Text but can style)
        # Tkinter Text doesn't have built-in ttk styling, but we can configure some options
        self.homography_text = tk.Text(self.controls_frame, height=6, width=30, state=tk.DISABLED, wrap=tk.WORD) # Wrap text
        self.homography_text.grid(row=11, column=0, columnspan=2, pady=5, sticky=tk.W+tk.E) # Span and expand horizontally
        self.homography_text.config(state=tk.NORMAL) # Enable temporarily to set initial text
        self.homography_text.delete(1.0, tk.END)
        self.homography_text.insert(tk.END, "Load calibration image first.")
        self.homography_text.config(state=tk.DISABLED)


        # Separator (Use ttk.Separator)
        separator = ttk.Separator(self.controls_frame, orient='horizontal')
        separator.grid(row=12, column=0, columnspan=2, sticky=tk.W+tk.E, pady=10) # Span and expand horizontally


        # --- Image Info Section ---
        # Use ttk.Label
        info_label = ttk.Label(self.controls_frame, text="Image Info Section", font=('Arial', 12, 'bold'))
        info_label.grid(row=13, column=0, columnspan=2, pady=(0, 5), sticky=tk.W) # Span across 2 columns


        # Use ttk.Button
        self.load_image_info_button = ttk.Button(self.controls_frame, text="Load Image for Info", command=self.load_image_info)
        self.load_image_info_button.grid(row=14, column=0, columnspan=2, pady=2, sticky=tk.W+tk.E) # Span across 2 columns


        # Use ttk.Label
        self.image_info_label = ttk.Label(self.controls_frame, text="Image Info:")
        self.image_info_label.grid(row=15, column=0, columnspan=2, pady=(10, 0), sticky=tk.W) # Span across 2 columns

        # Use ttk.Text (keep tk.Text)
        self.image_info_text = tk.Text(self.controls_frame, height=10, width=30, state=tk.DISABLED, wrap=tk.WORD) # Wrap text
        self.image_info_text.grid(row=16, column=0, columnspan=2, pady=5, sticky=tk.W+tk.E) # Span and expand horizontally
        self.image_info_text.config(state=tk.NORMAL) # Enable temporarily to set initial text
        self.image_info_text.delete(1.0, tk.END)
        self.image_info_text.insert(tk.END, "Load image for info...")
        self.image_info_text.config(state=tk.DISABLED)


        # --- General Controls ---
        # Use ttk.Button
        self.quit_button = ttk.Button(self.controls_frame, text="Quit", command=root.quit)
        self.quit_button.grid(row=17, column=0, columnspan=2, pady=(20, 5), sticky=tk.W+tk.E) # Span across 2 columns


        # --- Configure row weights to make some rows expand ---
        # This is good practice but might make the layout less 'minimal' depending on content.
        # Let's make the Text areas expand vertically.
        self.controls_frame.rowconfigure(11, weight=1) # Row for homography_text
        self.controls_frame.rowconfigure(16, weight=1) # Row for image_info_text


    # --- Rest of the class methods are the same ---

    def load_calib_image(self):
        """
        Loads the calibration image file and displays it on the canvas.
        """
        filepath = filedialog.askopenfilename(
             title="Select Calibration Image File",
             filetypes=(("Image files", "*.jpg *.jpeg *.png *.bmp *.tiff"), ("All files", "*.*"))
        )
        if not filepath:
            return

        # Reset calibration state
        self.reset_calibration_data_and_display()

        # Load the image using OpenCV
        img = cv2.imread(filepath)

        if img is None:
            messagebox.showerror("Error", f"Could not load calibration image from {filepath}")
            print(f"Debug: cv2.imread failed for {filepath}") # Debug line
            return

        print(f"Debug: cv2.imread successful. Image shape: {img.shape}") # Debug line

        self.image_calib_path = filepath
        self.image_calib_cv2 = img # Store original loaded image

        # --- Prepare image for display ---
        # Convert image to RGB for PIL/Tkinter
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img_pil = Image.fromarray(img_rgb)

        # Adjust image size for display if it's too large
        max_width = self.root.winfo_screenwidth() * 0.8
        max_height = self.root.winfo_screenheight() * 0.8
        img_width, img_height = img_pil.size

        if img_width > max_width or img_height > max_height:
             scale = min(max_width / img_width, max_height / img_height)
             new_width = int(img_width * scale)
             new_height = int(img_height * scale)
             img_pil = img_pil.resize((new_width, new_height), Image.Resampling.LANCZOS)
             # Note: self.image_calib_cv2 remains original size.
             # Point coordinates from JSON will be scaled relative to this potentially resized display size.
             display_width, display_height = new_width, new_height
        else:
             display_width, display_height = img_width, img_height

        # --- Store calculated display dimensions ---
        self.calib_display_width = display_width
        self.calib_display_height = display_height
        # --- End Store ---

        self.image_calib_tk = ImageTk.PhotoImage(image=img_pil)

        print(f"Debug: PIL image size for display: {img_pil.size}") # Debug line
        print(f"Debug: ImageTk.PhotoImage created: {self.image_calib_tk}") # Debug line


        # Configure canvas size and display image
        self.canvas.config(width=display_width, height=display_height)
        self.canvas.delete("all") # Clear previous content
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.image_calib_tk)

        print(f"Debug: Canvas configured size (target display size): {display_width}x{display_height}") # Debug line
        # Note: canvas.winfo_width/height *might* be different after layout, but we use our calculated size for points.

        # 尝试添加这行强制 Canvas 更新，可能有助于在 macOS 上及时显示图片
        self.canvas.update_idletasks()
        # 或者尝试更新 root 窗口
        # self.root.update_idletasks()

        print(f"Debug: Canvas content after create_image: {self.canvas.find_all()}") # Debug line
        # print(f"Debug: Canvas actual size via winfo: {self.canvas.winfo_width()}x{self.canvas.winfo_height()}") # Optional: compare


        # Update status labels and button states
        print(f"Calibration image loaded: {self.image_calib_path}")
        self.point_label.config(text="Image loaded. Now load JSON.")
        self.load_calib_json_button.config(state=tk.NORMAL) # Enable JSON load button
        self.homography_text.config(state=tk.NORMAL)
        self.homography_text.delete(1.0, tk.END)
        self.homography_text.insert(tk.END, f"Image loaded: {os.path.basename(self.image_calib_path)}\nLoad JSON next.")
        self.homography_text.config(state=tk.DISABLED)

    def load_calib_json(self):
        """
        Loads the calibration JSON file, validates against the loaded image,
        extracts points, and draws them on the canvas.
        """
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

            # Assuming the first task and first annotation result
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

            # --- Validate JSON dimensions against the loaded image ---
            # Get original dimensions from JSON results - usually consistent for all results
            # Need to find the first result that has these dimensions
            original_width_json = None
            original_height_json = None
            for res in results:
                if 'original_width' in res and 'original_height' in res:
                    original_width_json = res['original_width']
                    original_height_json = res['original_height']
                    break # Found dimensions in at least one result

            img_orig_height, img_orig_width = self.image_calib_cv2.shape[:2]

            if original_width_json is None or original_height_json is None:
                 # If dimensions are missing in all results
                 messagebox.showwarning("Missing Dimensions in JSON", "Could not find original_width/height in JSON results.\nUsing loaded image dimensions for point scaling.")
                 # Fallback to loaded image dimensions
                 effective_original_width = img_orig_width
                 effective_original_height = img_orig_height
            else:
                 # Dimensions found in JSON, now compare to loaded image
                 if int(original_width_json) != img_orig_width or int(original_height_json) != img_orig_height:
                    response = messagebox.askyesno(
                        "Dimension Mismatch",
                        f"JSON dimensions ({original_width_json}x{original_height_json}) "
                        f"do not match the loaded image dimensions ({img_orig_width}x{img_orig_height}).\n"
                        "Point coordinates from JSON might be incorrect for this image.\n"
                        "Do you want to load the points anyway? (Not recommended, but possible if image was resized *after* labeling)"
                    )
                    if not response:
                        self.reset_calibration_json_data()
                        return
                    # If user continues despite mismatch, scale based on loaded image dimensions
                    print("Warning: Dimension mismatch acknowledged. Proceeding with point loading based on loaded image dimensions.")
                    effective_original_width = img_orig_width
                    effective_original_height = img_orig_height
                 else:
                    # Dimensions match, use JSON dimensions for conversion (should be same as image)
                    effective_original_width = original_width_json
                    effective_original_height = original_height_json

            # --- Debug Print for Effective Original Dimensions ---
            print(f"Debug: Effective Original Dimensions (used for scaling from JSON %): {effective_original_width}x{effective_original_height}") # Debug line
            # --- End Debug Print ---


            # Extract and store points data
            self.points_calib_data = []
            # --- Use stored display dimensions for point scaling ---
            display_width = self.calib_display_width
            display_height = self.calib_display_height
            # --- End Use Stored ---

            # --- Debug Print for Canvas/Display Dimensions (now using stored) ---
            print(f"Debug: Using Stored Display Dimensions for scaling to display: {display_width}x{display_height}") # Modified Debug line
            # print(f"Debug: Actual Canvas dimensions via winfo: {self.canvas.winfo_width()}x{self.canvas.winfo_height()}") # Optional: compare


            if display_width <= 1 or display_height <= 1:
                 # This indicates an issue during image loading or display setup
                 messagebox.showwarning("Display Size Error", f"Stored display size is incorrect: {display_width}x{display_height}. Points might be misplaced.")
                 print(f"Debug: Stored display size is incorrect: {display_width}x{display_height}. Proceeding with point loading.")
                 self.reset_calibration_json_data()
                 return # Stop loading points if display size is bad


            for res in results:
                if res['type'] == 'keypointlabels' and 'x' in res['value'] and 'y' in res['value']:
                    x_percent = res['value']['x']
                    y_percent = res['value']['y']
                    label = res['value'].get('keypointlabels', [''])[0]

                    # Convert percentage based on effective_original_width/height
                    # Then scale to the current display width/height
                    # Calculate original pixel coordinates based on JSON percentage and effective original dimensions
                    pixel_x_orig = (x_percent / 100.0) * effective_original_width
                    pixel_y_orig = (y_percent / 100.0) * effective_original_height

                    # Scale original pixel coordinates to the current display dimensions (using stored size)
                    if effective_original_width > 0 and effective_original_height > 0:
                         # Store as float, not int!
                         pixel_x_display = pixel_x_orig * (display_width / effective_original_width)
                         pixel_y_display = pixel_y_orig * (display_height / effective_original_height)
                    else:
                         # Fallback should ideally not be reached if image was loaded
                         print("Warning: Effective original dimensions are zero during point scaling!")
                         # Still store as float in fallback
                         pixel_x_display = (x_percent / 100.0) * display_width # Fallback - might be inaccurate
                         pixel_y_display = (y_percent / 100.0) * display_height


                    self.points_calib_data.append({
                        'label': label or f'Point {len(self.points_calib_data) + 1}',
                        # --- Store as float tuple ---
                        'pixel': (pixel_x_display, pixel_y_display), # Store as float tuple
                        # --- End Store as float tuple ---
                        'flat': None, # Initialize flat coordinate to None
                        'tk_id': None # To store the ID of the point drawn on canvas
                    })

            if not self.points_calib_data:
                messagebox.showwarning("No Keypoints", "No keypoint annotations found in the result.")
                self.reset_calibration_json_data()
                self.point_label.config(text="JSON loaded, but no points found.")
                return

            print(f"Loaded {len(self.points_calib_data)} keypoints from JSON.")
            self.draw_points() # Draw points after loading JSON
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
         """Resets all calibration-related data and clears display."""
         self.canvas.delete("all")
         self.image_calib_cv2 = None
         self.image_calib_tk = None
         self.image_calib_path = None
         self.calib_display_width = 0  # Reset stored dimensions
         self.calib_display_height = 0 # Reset stored dimensions

         self.points_calib_data = []
         self.active_point_index = -1
         self.disable_calibration_controls()
         self.point_label.config(text="Load calibration image first.")
         self.load_calib_json_button.config(state=tk.DISABLED) # Disable JSON load button
         self.homography_text.config(state=tk.NORMAL)
         self.homography_text.delete(1.0, tk.END)
         self.homography_text.insert(tk.END, "Load calibration image first.")
         self.homography_text.config(state=tk.DISABLED)

         # Also clear matrix and verification data
         self.homography_matrix = None
         self.clear_verification_display() # Clear any displayed verification points
         self.verify_button.config(state=tk.DISABLED) # Disable verify button


    def reset_calibration_json_data(self):
         """Resets calibration data loaded from JSON."""
         # Keep the image displayed if loaded, but remove points and input capabilities
         self.canvas.delete("point_marker")
         self.canvas.delete("point_label_text")
         self.canvas.delete("point_label_outline")
         self.points_calib_data = []
         self.active_point_index = -1
         self.disable_calibration_controls() # Disable controls that rely on points
         self.point_label.config(text="JSON data cleared.")
         self.homography_text.config(state=tk.NORMAL)
         self.homography_text.delete(1.0, tk.END)
         self.homography_text.insert(tk.END, "JSON data cleared.\nLoad JSON again.")
         self.homography_text.config(state=tk.DISABLED)

         # Also clear matrix and verification data
         self.homography_matrix = None
         self.clear_verification_display() # Clear any displayed verification points
         self.verify_button.config(state=tk.DISABLED) # Disable verify button



    def draw_points(self):
        """Draws all calibration points on the canvas with their labels."""
        # Ensure calibration image is loaded (not None) AND points data exists.
        if self.image_calib_cv2 is None or not self.points_calib_data:
            return

        # Redraw all points - clear existing ones first
        self.canvas.delete("point_marker")
        self.canvas.delete("point_label_text")
        self.canvas.delete("point_label_outline")
        # Do NOT clear verification markers here, they are handled separately


        for i, point_data in enumerate(self.points_calib_data):
            # Use the pixel coordinates stored (now floats)
            x_float, y_float = point_data['pixel']
            label = point_data['label']
            color = "red" if point_data['flat'] is None else "blue"
            outline_color = "yellow" if i == self.active_point_index else "black"

            # --- Cast to int ONLY FOR DRAWING ---
            x_int, y_int = int(x_float), int(y_float)
            # --- End Cast ---

            # Draw circle using integer coordinates
            point_data['tk_id'] = self.canvas.create_oval(
                x_int - 5, y_int - 5, x_int + 5, y_int + 5,
                fill=color, outline=outline_color, width=2, tags="point_marker"
            )

            # Draw label text using integer coordinates
            # Draw outline text slightly shifted
            self.canvas.create_text(
                x_int + 10, y_int - 10, text=label, anchor=tk.NW, font=('Arial', 10, 'bold'),
                fill="black", tags="point_label_outline"
            )
            self.canvas.create_text(
                x_int + 10, y_int - 10, text=label, anchor=tk.NW, font=('Arial', 10, 'bold'),
                fill="white", tags="point_label_text"
            )


    def on_canvas_click(self, event):
        """Handles mouse clicks on the canvas to select points for calibration."""
        # This callback only applies if calibration points are loaded
        if not self.points_calib_data:
            return

        click_x, click_y = event.x, event.y # Click coordinates are integers

        # Find the closest point to the click
        min_dist = float('inf')
        closest_point_index = -1
        tolerance = 15 # Pixels tolerance for clicking on a point

        for i, point_data in enumerate(self.points_calib_data):
            # Use the pixel coordinates stored (now floats)
            px_float, py_float = point_data['pixel']
            # Distance calculation works correctly with float point and integer click
            dist = np.sqrt((click_x - px_float)**2 + (click_y - py_float)**2)
            if dist < tolerance and dist < min_dist:
                min_dist = dist
                closest_point_index = i

        self.set_active_point(closest_point_index)


    def set_active_point(self, index):
        """Sets the currently active calibration point for data entry."""
        # Only proceed if points data is loaded
        if not self.points_calib_data:
             self.active_point_index = -1
             self.disable_calibration_controls()
             return # Cannot select a point if none are loaded


        if self.active_point_index == index:
            return # No change

        # Update previous active point drawing (remove highlight)
        if self.active_point_index != -1:
            prev_point_data = self.points_calib_data[self.active_point_index]
            # Check if the point object still exists on canvas before changing config
            if prev_point_data['tk_id'] and self.canvas.find_withtag(prev_point_data['tk_id']):
                 self.canvas.itemconfig(prev_point_data['tk_id'], outline="black")


        self.active_point_index = index

        if index != -1:
            point_data = self.points_calib_data[index]
            # Display the pixel coordinates from stored float tuple
            self.point_label.config(text=f"Editing: {point_data['label']} (Pixel: {point_data['pixel'][0]:.2f}, {point_data['pixel'][1]:.2f})") # Display with precision


            # Enable entry fields and buttons
            self.flat_x_entry.config(state=tk.NORMAL)
            self.flat_y_entry.config(state=tk.NORMAL)
            self.save_button.config(state=tk.NORMAL)
            self.delete_button.config(state=tk.NORMAL)


            # Populate entry fields with existing flat coordinates if any
            if point_data['flat'] is not None:
                self.flat_x_entry.delete(0, tk.END)
                self.flat_x_entry.insert(0, str(point_data['flat'][0]))
                self.flat_y_entry.delete(0, tk.END)
                self.flat_y_entry.insert(0, str(point_data['flat'][1]))
            else:
                self.flat_x_entry.delete(0, tk.END)
                self.flat_y_entry.delete(0, tk.END)


            # Update current active point drawing (add highlight)
            # Check if the point object still exists on canvas before changing config
            if point_data['tk_id'] and self.canvas.find_withtag(point_data['tk_id']):
                 self.canvas.itemconfig(point_data['tk_id'], outline="yellow")


        else: # No point selected
            self.point_label.config(text="Click a point to edit")
            self.flat_x_entry.config(state=tk.DISABLED)
            self.flat_y_entry.config(state=tk.DISABLED)
            self.save_button.config(state=tk.DISABLED)
            self.delete_button.config(state=tk.DISABLED)

        self.check_calculate_button_state()


    def save_coordinates(self):
        """Saves the entered real-world coordinates for the active calibration point."""
        if self.active_point_index == -1 or not self.points_calib_data:
            return

        try:
            x_flat = float(self.flat_x_entry.get())
            y_flat = float(self.flat_y_entry.get())

            self.points_calib_data[self.active_point_index]['flat'] = (x_flat, y_flat)
            print(f"Saved flat coordinates ({x_flat}, {y_flat}) for {self.points_calib_data[self.active_point_index]['label']}")

            # Redraw points to update color
            self.draw_points()
            self.set_active_point(self.active_point_index) # Refresh highlight and input fields state

        except ValueError:
            messagebox.showwarning("Invalid Input", "Please enter valid numerical values for X and Y.")

        self.check_calculate_button_state()


    def delete_coordinates(self):
        """Deletes the real-world coordinates for the active calibration point."""
        if self.active_point_index == -1 or not self.points_calib_data:
            return

        point_label = self.points_calib_data[self.active_point_index]['label']
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete coordinates for {point_label}?"):
            self.points_calib_data[self.active_point_index]['flat'] = None
            print(f"Deleted flat coordinates for {point_label}")
            self.flat_x_entry.delete(0, tk.END)
            self.flat_y_entry.delete(0, tk.END)

            # Redraw points to update color
            self.draw_points()
            self.set_active_point(-1) # Deselect the point after deleting its data

        self.check_calculate_button_state()

    def check_calculate_button_state(self):
        """Enables/disables the calculate button based on available points with flat data."""
        valid_points_count = sum(1 for p in self.points_calib_data if p['flat'] is not None)
        if valid_points_count >= 4:
            self.calculate_button.config(state=tk.NORMAL)
            # Update homography text area state and content
            self.homography_text.config(state=tk.NORMAL)
            self.homography_text.delete(1.0, tk.END)
            self.homography_text.insert(tk.END, f"Ready to calculate with {valid_points_count} points.")
            self.homography_text.config(state=tk.DISABLED)

        else:
            self.calculate_button.config(state=tk.DISABLED)
            # Update homography text area state and content
            self.homography_text.config(state=tk.NORMAL)
            self.homography_text.delete(1.0, tk.END)
            self.homography_text.insert(tk.END, f"Need at least 4 points with coordinates ({valid_points_count} currently).")
            self.homography_text.config(state=tk.DISABLED)

    def transform_pixel_to_world(self, pixel_x_display, pixel_y_display):
        """
        Transforms a pixel coordinate (from display size) to world coordinate using the stored matrix.
        Returns (world_x, world_y) or None if matrix is not available or calculation fails.
        """
        if self.homography_matrix is None:
            print("Error: Homography matrix not available for transformation.")
            return None

        # Get the original dimensions of the loaded OpenCV image
        if self.image_calib_cv2 is None:
            print("Error: Calibration image not loaded for scaling.")
            return None
        orig_height, orig_width = self.image_calib_cv2.shape[:2]
        if orig_width <= 0 or orig_height <= 0:
             print("Error: Invalid original image dimensions for scaling.")
             return None

        # Get the dimensions used for displaying the image on the canvas (stored size)
        display_width = self.calib_display_width
        display_height = self.calib_display_height
        if display_width <= 0 or display_height <= 0:
             print("Error: Invalid display dimensions stored for scaling.")
             return None

        # Scale pixel points from display size back to original image size
        scaled_pixel_x = pixel_x_display * (orig_width / display_width)
        scaled_pixel_y = pixel_y_display * (orig_height / display_height)

        # Use the stored homography matrix
        H = self.homography_matrix

        # Represent pixel coordinate in homogeneous coordinates
        pixel_coord_homogeneous = np.array([[scaled_pixel_x],
                                            [scaled_pixel_y],
                                            [1.0]])

        # Perform matrix multiplication
        transformed_homogeneous_coord = np.dot(H, pixel_coord_homogeneous)

        # Perform perspective division
        sX = transformed_homogeneous_coord[0, 0]
        sY = transformed_homogeneous_coord[1, 0]
        s = transformed_homogeneous_coord[2, 0]

        if abs(s) < 1e-8: # Check if s is close to zero
            print(f"Warning: Perspective division by zero or near-zero for pixel ({pixel_x_display:.2f}, {pixel_y_display:.2f}). Result may be at infinity or invalid.")
            return None # Cannot divide by zero

        world_X = sX / s
        world_Y = sY / s

        return (float(world_X), float(world_Y)) # Return as standard Python floats


    def calculate_homography(self):
        """Calculates the homography matrix using the collected point pairs."""
        src_pts = [] # Pixel points (scaled back to original image size, retaining float precision)
        dst_pts = [] # Flat/Real-world points

        # Get the original dimensions of the loaded calibration image
        if self.image_calib_cv2 is None:
             messagebox.showwarning("Image Not Loaded", "Calibration image is not loaded.")
             return

        # Get the dimensions used for displaying the image on the canvas (stored size)
        display_width = self.calib_display_width
        display_height = self.calib_display_height

        # Note: Check for zero/negative dimensions here is also good practice
        if display_width <= 0 or display_height <= 0:
            messagebox.showerror("Display Error", "Invalid display dimensions stored.")
            return


        # Get the original dimensions of the loaded OpenCV image
        orig_height, orig_width = self.image_calib_cv2.shape[:2]

        # Note: Check for zero/negative original dimensions here is also good practice
        if orig_width <= 0 or orig_height <= 0:
             messagebox.showerror("Image Error", "Invalid original image dimensions.")
             return


        for point_data in self.points_calib_data:
            if point_data['flat'] is not None:
                # --- Get the stored float pixel coordinates (display size) ---
                display_pixel_x, display_pixel_y = point_data['pixel']
                # --- End Get ---

                # Scale pixel points from display size back to original image size
                scaled_pixel_x = display_pixel_x * (orig_width / display_width)
                scaled_pixel_y = display_pixel_y * (orig_height / display_height)

                src_pts.append((scaled_pixel_x, scaled_pixel_y)) # Append float tuple
                dst_pts.append(point_data['flat'])


        if len(src_pts) < 4:
            messagebox.showwarning("Not Enough Points", "Need at least 4 corresponding points to calculate homography.")
            return

        # Convert list of float tuples to numpy array (dtype float32 is standard for OpenCV functions)
        src_pts = np.array(src_pts, dtype=np.float32)
        dst_pts = np.array(dst_pts, dtype=np.float32)

        try:
            # Use RANSAC for robustness
            # 5.0 is max reprojection error in pixels. Adjust if needed.
            H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
            self.homography_matrix = H # Store the calculated matrix

            self.homography_text.config(state=tk.NORMAL)
            self.homography_text.delete(1.0, tk.END)
            self.homography_text.insert(tk.END, "Calculated Homography Matrix (H):\n")
            self.homography_text.insert(tk.END, str(H))
            self.homography_text.config(state=tk.DISABLED)

            print("\nCalculated Homography Matrix:")
            print(H)

            # Enable verification button after matrix is calculated
            self.verify_button.config(state=tk.NORMAL)


        except Exception as e:
            messagebox.showerror("Calculation Error", f"Could not compute homography: {e}")
            self.homography_matrix = None # Clear matrix on error
            self.homography_text.config(state=tk.NORMAL)
            self.homography_text.delete(1.0, tk.END)
            self.homography_text.insert(tk.END, f"Error during calculation: {e}")
            self.homography_text.config(state=tk.DISABLED)
            self.verify_button.config(state=tk.DISABLED) # Disable verify on error


    def export_coordinates_to_json(self):
        """
        Exports the collected world coordinates to a JSON file.
        """
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
        """
        Calculates and displays world coordinates for points without entered data
        using the calculated homography matrix.
        """
        if self.homography_matrix is None:
            messagebox.showwarning("No Matrix", "Homography matrix has not been calculated yet.")
            return

        # Clear previous verification display
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

                # Draw calculated point on the canvas
                # Use integer coordinates for drawing
                x_int, y_int = int(pixel_x_display), int(pixel_y_display)
                # Draw a different marker (e.g., green outline, no fill)
                point_id = self.canvas.create_oval(
                    x_int - 7, y_int - 7, x_int + 7, y_int + 7, # Slightly larger circle
                    outline="lime green", width=2, tags="verification_marker"
                )
                self.verification_tk_ids.append(point_id)

                # Draw the calculated world coordinate text next to the point
                text_label = f"({world_x:.2f}, {world_y:.2f})"
                text_id = self.canvas.create_text(
                    x_int + 15, y_int + 5, text=text_label, anchor=tk.NW, font=('Arial', 9, 'bold'),
                    fill="lime green", tags="verification_marker" # Use the same tag to clear
                )
                self.verification_tk_ids.append(text_id)
                points_verified_count += 1

        if self.verification_tk_ids:
            self.clear_verify_button.config(state=tk.NORMAL) # Enable clear button if points were drawn
            print(f"Displayed calculated coordinates for {points_verified_count} points.")
        else:
             print("No world coordinates could be calculated for untransformed points.")


    def clear_verification_display(self):
        """
        Clears the points and text drawn by the verification function.
        """
        if self.verification_tk_ids:
            print("Clearing verification display.")
            for item_id in self.verification_tk_ids:
                self.canvas.delete(item_id)
            self.verification_tk_ids = [] # Clear the list of IDs
            self.clear_verify_button.config(state=tk.DISABLED) # Disable clear button


    def enable_calibration_controls(self):
        """Enables calibration controls after loading JSON data."""
        # Entry fields and Save/Delete buttons are enabled when a point is selected by set_active_point
        self.check_calculate_button_state() # Enable calculate if enough points have data
        self.export_button.config(state=tk.NORMAL) # Enable export button after JSON is loaded
        # Verify button is enabled after matrix is calculated


    def disable_calibration_controls(self):
        """Disables calibration controls (except load buttons) when no calibration data is ready."""
        self.flat_x_entry.config(state=tk.DISABLED)
        self.flat_y_entry.config(state=tk.DISABLED)
        self.save_button.config(state=tk.DISABLED)
        self.delete_button.config(state=tk.DISABLED)
        self.calculate_button.config(state=tk.DISABLED)
        self.export_button.config(state=tk.DISABLED) # Disable export button
        self.verify_button.config(state=tk.DISABLED) # Disable verify button
        self.clear_verify_button.config(state=tk.DISABLED) # Disable clear verify button


    # --- Image Info Section (Same as before, minor updates to GPSInfo formatting) ---

    def load_image_info(self):
        """
        Loads an image file and displays its resolution and EXIF information.
        """
        filepath = filedialog.askopenfilename(
             title="Select Image File for Info",
             filetypes=(("Image files", "*.jpg *.jpeg *.png *.bmp *.tiff"), ("All files", "*.*"))
        )
        if not filepath:
            return

        try:
            # Use PIL to open the image and get EXIF data
            self.image_info_pil = Image.open(filepath)
            self.image_info_path = filepath

            # --- Get Resolution ---
            width, height = self.image_info_pil.size
            resolution_info = f"Resolution: {width} x {height} pixels\n\n"

            # --- Get EXIF Info ---
            exif_data = self.image_info_pil._getexif()
            exif_info_string = "EXIF Data:\n"

            if exif_data is not None:
                # Map EXIF tags to names
                exif_tags_map = { tag_id: ExifTags.TAGS.get(tag_id, tag_id) for tag_id in exif_data.keys() }

                for tag_id, value in exif_data.items():
                    tag_name = exif_tags_map.get(tag_id, tag_id)
                    # Simple formatting for common data types
                    if isinstance(value, bytes):
                         try:
                              value_str = value.decode('utf-8', errors='replace')
                         except:
                              value_str = str(value) # Fallback
                    elif isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], (int,float)) and isinstance(value[1], (int,float)) and value[1] != 0:
                         # Handle rational numbers (e.g., aperture, exposure). Check for float too.
                         try: # Avoid division by zero or other math errors
                              value_str = f"{value[0]}/{value[1]} ({value[0]/value[1]:.2f})"
                         except:
                             value_str = f"{value[0]}/{value[1]}"
                    elif isinstance(value, np.ndarray): # Sometimes arrays sneak in
                         value_str = np.array2string(value, threshold=50, edgeitems=2) # Limit output size
                    else:
                         value_str = str(value)

                    # Basic handling for specific complex tags like GPSInfo
                    if tag_name == 'GPSInfo':
                         # GPSInfo is often a dictionary itself, but can be stored in different ways.
                         # A simple string representation is safer than deep parsing here.
                         exif_info_string += f"  {tag_name}: {value}\n"
                         continue # Skip adding the main tag_name line below


                    # Add the tag info line (unless it was GPSInfo handled above)
                    if tag_name != 'GPSInfo':
                         exif_info_string += f"  {tag_name}: {value_str}\n"


                if exif_info_string == "EXIF Data:\n": # Check if any tags were actually processed
                    exif_info_string += "  No common EXIF tags found."

            else:
                exif_info_string += "  No EXIF data found in this image."


            # --- Display Info ---
            self.image_info_text.config(state=tk.NORMAL)
            self.image_info_text.delete(1.0, tk.END) # Clear previous info
            self.image_info_text.insert(tk.END, resolution_info)
            self.image_info_text.insert(tk.END, exif_info_string)
            self.image_info_text.config(state=tk.DISABLED)

            print(f"\nLoaded image info for: {filepath}")
            print(resolution_info.strip())
            print(exif_info_string)

            # Close the PIL image to free up resources
            self.image_info_pil.close()
            self.image_info_pil = None # Clear reference


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
            self.homography_text.config(state=tk.DISABLED)
            if self.image_info_pil:
                 self.image_info_pil.close()
            self.image_info_pil = None
            self.image_info_path = None



# --- Run the application ---
if __name__ == "__main__":
    root = tk.Tk()
    app = HomographyCalibratorApp(root)
    root.mainloop()
