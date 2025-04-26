import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import cv2
import numpy as np
import glob
from PIL import Image, ImageTk # Requires Pillow: pip install Pillow
import os # For handling file paths
import sys # For handling path separators
import time # For timestamp in filenames
from datetime import datetime,timezone, timedelta
# import threading # Tkinter's after is simpler for GUI updates

# Helper function to convert OpenCV image (NumPy array) to Tkinter PhotoImage
# Also resizes the image to fit within the display area while maintaining aspect ratio
# Returns (tk_photo, error_message)



def cv2_to_tk(cv2_img, display_width, display_height):
    """
    Converts an OpenCV image (BGR numpy array) to a Tkinter PhotoImage,
    resizing it to fit the given dimensions while maintaining aspect ratio.
    Returns (tk_photo, error_message). error_message is None on success.
    """
    if cv2_img is None:
        return (None, "Input OpenCV image is None")

    # Convert BGR to RGB
    try:
        # Ensure image is in a supported format (e.g., 8-bit, 3 channel)
        if len(cv2_img.shape) == 2: # Grayscale
             img_rgb = cv2.cvtColor(cv2_img, cv2.COLOR_GRAY2RGB)
        elif cv2_img.shape[2] == 3: # BGR
             img_rgb = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2RGB)
        elif cv2_img.shape[2] == 4: # BGRA - remove alpha channel
             img_rgb = cv2.cvtColor(cv2_img, cv2.COLOR_BGRA2RGB)
        else:
             return (None, f"Unsupported OpenCV image channel count: {cv2_img.shape[2]}")

        img_pil = Image.fromarray(img_rgb)
    except Exception as e:
        return (None, f"Error converting OpenCV image to PIL: {e}")


    img_width, img_height = img_pil.size

    # Avoid division by zero or incorrect resizing if display_width/height are not valid
    if display_width <= 1 or display_height <= 1:
        # Fallback to original image size or a default size if target is invalid
        # Using original image size will prevent display errors, but won't enforce fixed display size
        # For fixed size preview, the calling code should provide valid display_width/height
        # Returning error if called with invalid dimensions as per design intent of this helper.
         return (None, f"Invalid target display dimensions provided to cv2_to_tk: {display_width}x{display_height}")


    # Calculate scaling factor
    # Avoid division by zero if original image has zero dimension (shouldn't happen but defensive)
    if img_width == 0 or img_height == 0:
        return (None, f"Invalid original image dimensions: {img_width}x{img_height}")

    ratio = min(display_width / img_width, display_height / img_height)
    new_width = int(img_width * ratio)
    new_height = int(img_height * ratio)

    # Ensure dimensions are positive after scaling calculation
    if new_width <= 0 or new_height <= 0:
        # This can happen if display_width/height are much smaller than img_width/height but not <=1 initially
        # and calculation results in 0. Set a minimum size? Or just report?
        # Let's report for now.
        return (None, f"Calculated invalid resize dimensions: {new_width}x{new_height} from {img_width}x{img_height} with ratio {ratio}. Target display {display_width}x{display_height}")

    # Resize image
    try:
        # Use LANCZOS for high-quality downsampling
        img_resized = img_pil.resize((new_width, new_height), Image.Resampling.LANCZOS)
    except Exception as e:
        # print(f"Image resizing failed: {e}") # Debug print
        return (None, f"Image resizing failed: {e}")

    # Convert to PhotoImage
    try:
        tk_photo = ImageTk.PhotoImage(img_resized)
    except Exception as e:
        return (None, f"Error converting PIL image to PhotoImage: {e}")


    # Store a reference to prevent garbage collection
    return (tk_photo, None) # Success


class MinimalistCalibratorGUI:
    def __init__(self, master):
        self.master = master
        master.title("Camera Calibration Tool") # Simple title
        # master.minsize(900, 750) # Set minimum window size to accommodate capture preview - Adjusted later

        # --- Try setting application icon ---
        icon_path = "calib.png"
        if os.path.exists(icon_path):
            try:
                # Load the icon image using PIL
                pil_icon = Image.open(icon_path)
                # Convert the PIL image to Tkinter PhotoImage
                tk_icon = ImageTk.PhotoImage(pil_icon)
                # Set the window icon for the root window and all subsequent toplevel windows
                master.iconphoto(True, tk_icon)
            except Exception as e:
                print(f"Warning: Could not load or set application icon from {icon_path}: {e}")
        else:
            print(f"Warning: Application icon file '{icon_path}' not found in the current directory.")

                # Configure ttk style for countdown label

        # --- Configure ttk styles for a white minimalist theme ---
        style = ttk.Style()
        # 'clam' is a relatively simple theme
        style.theme_use('clam')

        # Configure default styles for widget classes, setting background to white
        style.configure('TFrame', background='white')
        style.configure('TLabel', background='white')
        # Configure default style for TLabelframe (background and label text color)
        # Note: This might not make the LabelFrame border white, as the border is part of the theme drawing
        style.configure('TLabelframe', background='white')
        style.configure('TLabelframe.Label', background='white', foreground='black') # Ensure label text is visible

        # Configure Treeview style, setting the content area background to white
        style.configure('Treeview', background='white', fieldbackground='white', foreground='black', rowheight=25) # rowheight can adjust row height
        style.configure('Treeview.Heading', background='white', foreground='black', font=('TkDefaultFont', 10, 'bold'))

        # Define Tag Styles, e.g., excluded rows turn grey
        style.configure('excluded', foreground='gray')
        style.configure('failed', foreground='red')

        # Configure Notebook styles
        style.configure('TNotebook', background='white', borderwidth=0)
        style.configure('TNotebook.Tab', background='lightgray', foreground='black', padding=[5, 2]) # Padding [width, height]
        style.map('TNotebook.Tab', background=[('selected', 'white')]) # Selected tab background is white
        style.configure(
            "CountdownLabel.TLabel",
            background="white",
            foreground="black",
            font=("Helvetica", 60),
            opacity=0.5,  # 设置透明度
        )

        # tk.Text widgets are not ttk, directly set bg parameter


        # Data storage
        self.image_paths = []
        self.objpoints_all = [] # All 3D points for images where corners were found (world coordinate system)
        self.imgpoints_all = [] # All 2D points for images where corners were found (image coordinate system)
        self.successful_image_indices = [] # Original indices of images with successfully found corners (corresponds to objpoints_all/imgpoints_all index)
        self.excluded_indices = set() # Set of original indices of excluded images
        self.camera_matrix = None
        self.dist_coeffs = None
        self.rvecs = None # Rotation vectors for successfully calibrated images (corresponding to objpoints_all/imgpoints_all order)
        self.tvecs = None # Translation vectors for successfully calibrated images (corresponding to objpoints_all/imgpoints_all order)
        self.per_view_errors = [] # Reprojection error for each successfully calibrated image (corresponding to objpoints_all/imgpoints_all order)
        self.image_size = None # Image size (width, height) used for calibration
        self.board_params = {} # Stores chessboard parameters
        self.undistort_image_path = None # Path for the single image to undistort

        # References for validation window images to prevent garbage collection
        self.validation_original_tk = None
        self.validation_undistorted_tk = None

        # Camera Capture variables
        self.camera_cap = None # OpenCV VideoCapture object
        self.is_capturing = False # Flag for timed capture saving
        self.is_capturing_preview = False # Flag for continuous preview loop
        self.capture_count = 0
        self.total_capture_count = 0
        self.capture_interval_ms = 0 # Interval in milliseconds
        self.capture_output_folder = None
        self.capture_after_id = None # To store the ID returned by master.after
        self.preview_after_id = None # To store the ID returned by master.after for preview
        self.last_frame = None # Store the last frame read from camera
        # Fixed preview size
        self.preview_width = 640  # Fixed preview width
        self.preview_height = 480 # Fixed preview height


        # --- GUI Layout ---
        main_frame = ttk.Frame(master, padding="15", style='TFrame')
        main_frame.grid(row=0, column=0, sticky="nsew")
        master.grid_columnconfigure(0, weight=1)
        master.grid_rowconfigure(0, weight=1)
        master.configure(bg='white')

        # --- Use Notebook for main sections ---
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=0, column=0, sticky="nsew")
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(0, weight=1) # Notebook takes up most vertical space


        # --- Tab 1: Camera Calibration ---
        calibration_tab = ttk.Frame(self.notebook, padding="10", style='TFrame')
        self.notebook.add(calibration_tab, text='Camera Calibration')
        calibration_tab.grid_columnconfigure(0, weight=1) # Settings/List column
        calibration_tab.grid_columnconfigure(1, weight=2) # Image View column
        calibration_tab.grid_rowconfigure(0, weight=1) # Calibration setup/images row
        calibration_tab.grid_rowconfigure(1, weight=0) # Results row fixed height

        # --- Section 1: Camera Calibration Setup & Image Management ---
        calibration_setup_frame = ttk.LabelFrame(calibration_tab, text="Setup & Images", padding="10", style='TLabelframe')
        calibration_setup_frame.grid(row=0, column=0, columnspan=2, sticky="nsew", pady=(0, 15)) # Use nsew to fill in tab
        calibration_setup_frame.grid_columnconfigure(0, weight=1) # Left column for settings
        calibration_setup_frame.grid_columnconfigure(1, weight=2) # Right column for image view
        calibration_setup_frame.grid_rowconfigure(1, weight=1) # Row with list/view should expand


        # Settings and List (left side of calibration_setup_frame)
        settings_list_frame = ttk.Frame(calibration_setup_frame, style='TFrame')
        settings_list_frame.grid(row=0, column=0, sticky="nsew") # Spans row 0 in calibration_setup_frame
        # No weight needed on settings_list_frame columns, inner frames handle it

        # Calibration Settings (top left)
        control_frame = ttk.LabelFrame(settings_list_frame, text="Settings", padding="10", style='TLabelframe')
        control_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        control_frame.grid_columnconfigure(0, weight=1)

        control_content_frame = ttk.Frame(control_frame, style='TFrame')
        control_content_frame.grid(row=0, column=0, sticky="nsew", columnspan=2)
        control_frame.grid_rowconfigure(0, weight=1)

        select_file_frame = ttk.Frame(control_content_frame, style='TFrame')
        select_file_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        select_file_frame.grid_columnconfigure(1, weight=1)
        self.select_folder_button = ttk.Button(select_file_frame, text="Select Calibration Image Folder...")
        self.select_folder_button.grid(row=0, column=0, sticky="w", padx=(0, 15))
        self.select_folder_button.config(command=self.select_folder)
        self.folder_path_label = ttk.Label(select_file_frame, text="No folder selected", relief="sunken", anchor="w", style='TLabel')
        self.folder_path_label.grid(row=0, column=1, sticky="ew")

        param_frame = ttk.Frame(control_content_frame, style='TFrame')
        param_frame.grid(row=1, column=0, sticky="w", pady=(5, 0))

        ttk.Label(param_frame, text="Inner Corners(W,H):", style='TLabel').grid(row=0, column=0, padx=(0, 5))
        self.entry_board_w = ttk.Entry(param_frame, width=5)
        self.entry_board_w.grid(row=0, column=1, padx=(0, 2))
        self.entry_board_w.insert(0, "7")
        ttk.Label(param_frame, text=",", style='TLabel').grid(row=0, column=2)
        self.entry_board_h = ttk.Entry(param_frame, width=5)
        self.entry_board_h.grid(row=0, column=3, padx=(0, 15))
        self.entry_board_h.insert(0, "6")

        ttk.Label(param_frame, text="Square Size(m):", style='TLabel').grid(row=0, column=4, padx=(0, 5))
        self.entry_square_size = ttk.Entry(param_frame, width=8)
        self.entry_square_size.grid(row=0, column=5)


        # Image List (bottom left)
        list_frame = ttk.LabelFrame(settings_list_frame, text="Image List (Double-click to preview)", padding="10", style='TLabelframe')
        list_frame.grid(row=1, column=0, sticky="nsew", pady=(10, 0)) # Below settings
        settings_list_frame.grid_rowconfigure(1, weight=1) # Let list frame expand

        list_content_frame = ttk.Frame(list_frame, style='TFrame')
        list_content_frame.grid(row=0, column=0, sticky="nsew", columnspan=2)
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        self.image_list_tree = ttk.Treeview(list_content_frame, columns=("Error", "Status"), show="headings", style='Treeview')
        self.image_list_tree.heading("#0", text="Image Name")
        self.image_list_tree.heading("Error", text="Error")
        self.image_list_tree.heading("Status", text="Status")
        self.image_list_tree.column("#0", width=150, anchor="w", stretch=tk.TRUE)
        self.image_list_tree.column("Error", width=60, anchor="center", stretch=tk.FALSE)
        self.image_list_tree.column("Status", width=80, anchor="center", stretch=tk.FALSE)
        self.image_list_tree.grid(row=0, column=0, sticky="nsew")

        list_vscroll = ttk.Scrollbar(list_content_frame, orient="vertical", command=self.image_list_tree.yview)
        self.image_list_tree.configure(yscrollcommand=list_vscroll.set)
        list_vscroll.grid(row=0, column=1, sticky="ns")

        list_content_frame.grid_columnconfigure(0, weight=1)
        list_content_frame.grid_rowconfigure(0, weight=1)

        self.image_list_tree.bind("<Double-1>", self.on_image_select)
        self.image_list_tree.bind("<<TreeviewSelect>>", self.on_list_select)

        exclude_button = ttk.Button(list_frame, text="Exclude/Include Selected")
        exclude_button.grid(row=1, column=0, columnspan=2, pady=(10, 0))
        exclude_button.config(command=self.toggle_exclude_selected)

        # Image View (right side of calibration_setup_frame)
        image_frame = ttk.LabelFrame(calibration_setup_frame, text="Image View", padding="10", style='TLabelframe')
        image_frame.grid(row=0, column=1, sticky="nsew", rowspan=2) # Spans rows 0 and 1
        calibration_setup_frame.grid_columnconfigure(1, weight=2) # Image area wider
        calibration_setup_frame.grid_rowconfigure(0, weight=1) # Ensure this row containing settings_list_frame and image_frame expands


        image_content_frame = ttk.Frame(image_frame, style='TFrame')
        image_content_frame.grid(row=0, column=0, sticky="nsew")
        image_frame.grid_rowconfigure(0, weight=1)
        image_frame.grid_columnconfigure(0, weight=1)

        self.image_label = ttk.Label(image_content_frame, style='TLabel', anchor='center', text="Image Preview", compound='image')
        self.image_label.grid(row=0, column=0, sticky="nsew")
        image_content_frame.grid_columnconfigure(0, weight=1)
        image_content_frame.grid_rowconfigure(0, weight=1)

        self.current_image_info_label = ttk.Label(image_frame, text="", anchor="center", style='TLabel')
        self.current_image_info_label.grid(row=1, column=0, pady=(10, 0))


        # --- Section 2: Calibration Results & Operations (inside Calibration Tab) ---
        results_operations_frame = ttk.LabelFrame(calibration_tab, text="Calibration Results & Operations", padding="10", style='TLabelframe')
        results_operations_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(15, 0)) # Below calibration_setup_frame
        results_operations_frame.grid_columnconfigure(0, weight=1) # Only one content column

        # Operations buttons and average error (top part of results_operations_frame)
        operation_frame = ttk.Frame(results_operations_frame, style='TFrame')
        operation_frame.grid(row=0, column=0, sticky="w") # Align left

        self.calibrate_button = ttk.Button(operation_frame, text="Start Calibration")
        self.calibrate_button.grid(row=0, column=0, padx=(0, 15))
        self.calibrate_button.config(command=self.run_calibration)

        self.save_button = ttk.Button(operation_frame, text="Save Results...", state=tk.DISABLED)
        self.save_button.grid(row=0, column=1, padx=(0, 15))
        self.save_button.config(command=self.save_results)

        self.validate_button = ttk.Button(operation_frame, text="Validate Calibration", state=tk.DISABLED)
        self.validate_button.grid(row=0, column=2, padx=(0, 20))
        self.validate_button.config(command=self.validate_calibration)

        ttk.Label(operation_frame, text="Avg. Error:", style='TLabel').grid(row=0, column=3, padx=(0, 5))
        self.avg_error_label = ttk.Label(operation_frame, text="N/A", width=10, style='TLabel')
        self.avg_error_label.grid(row=0, column=4, sticky="w")

        # Results display (matrices) (bottom part of results_operations_frame)
        results_display_frame = ttk.Frame(results_operations_frame, style='TFrame')
        results_display_frame.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        results_operations_frame.grid_rowconfigure(1, weight=1) # Let this frame expand

        results_display_frame.grid_columnconfigure(1, weight=1)
        results_display_frame.grid_rowconfigure(0, weight=1)
        results_display_frame.grid_rowconfigure(1, weight=1)

        ttk.Label(results_display_frame, text="Camera Matrix K:", style='TLabel').grid(row=0, column=0, sticky="nw", padx=(0, 5))
        self.matrix_k_text = tk.Text(results_display_frame, height=4, width=40, state=tk.DISABLED, wrap="word", bg='white', fg='black', relief='flat')
        self.matrix_k_text.grid(row=0, column=1, sticky="nsew")

        ttk.Label(results_display_frame, text="Distortion Coeffs D:", style='TLabel').grid(row=1, column=0, sticky="nw", padx=(0, 5), pady=(5, 0))
        self.dist_coeffs_text = tk.Text(results_display_frame, height=2, width=40, state=tk.DISABLED, wrap="word", bg='white', fg='black', relief='flat')
        self.dist_coeffs_text.grid(row=1, column=1, sticky="nsew", pady=(5, 0))


        # --- Tab 2: Single Image Undistortion Tool ---
        undistort_tab = ttk.Frame(self.notebook, padding="10", style='TFrame')
        self.notebook.add(undistort_tab, text='Undistort Single Image')
        undistort_tab.grid_columnconfigure(0, weight=1) # Make the image path label column expandable

        undistort_frame = ttk.LabelFrame(undistort_tab, text="Undistort Single Image Tool", padding="10", style='TLabelframe')
        undistort_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 0)) # Fill the tab
        undistort_frame.grid_columnconfigure(1, weight=1)

        ttk.Label(undistort_frame, text="Input Image:", style='TLabel').grid(row=0, column=0, sticky="w", padx=(0, 5))

        self.select_undistort_image_button = ttk.Button(undistort_frame, text="Select Image File...")
        self.select_undistort_image_button.grid(row=0, column=1, sticky="ew", padx=(0, 5))
        self.select_undistort_image_button.config(command=self.select_undistort_image)

        self.undistort_image_path_label = ttk.Label(undistort_frame, text="No image selected", relief="sunken", anchor="w", style='TLabel')
        self.undistort_image_path_label.grid(row=0, column=2, sticky="ew", padx=(0, 15))

        undistort_frame.grid_columnconfigure(1, weight=0)
        undistort_frame.grid_columnconfigure(2, weight=1)

        self.run_undistort_button = ttk.Button(undistort_frame, text="Undistort and Save...", state=tk.DISABLED)
        self.run_undistort_button.grid(row=1, column=0, columnspan=3, pady=(10, 0))
        self.run_undistort_button.config(command=self.run_undistort_and_save)


        # --- Tab 3: Camera Capture Tool ---
        capture_tab = ttk.Frame(self.notebook, padding="10", style='TFrame')
        self.notebook.add(capture_tab, text='Camera Capture')
        capture_tab.grid_columnconfigure(0, weight=0) # Controls column - fixed width
        capture_tab.grid_columnconfigure(1, weight=1) # Preview column - expands to fill available space
        capture_tab.grid_rowconfigure(0, weight=1) # Capture frame row - expands to fill available space

        capture_frame = ttk.LabelFrame(capture_tab, text="Camera Capture Tool", padding="10", style='TLabelframe')
        capture_frame.grid(row=0, column=0, columnspan=2, sticky="nsew", pady=(0, 0)) # Fill the tab
        # Removed weights from capture_frame columns and rows, rely on capture_tab weights
        capture_frame.grid_columnconfigure(0, weight=0) # Controls column - fixed width
        capture_frame.grid_columnconfigure(1, weight=1) # Preview column - expands

        # Capture Settings and Controls (left side)
        capture_controls_frame = ttk.Frame(capture_frame, style='TFrame')
        # Removed sticky nsew from capture_controls_frame to allow it to take its natural size
        capture_controls_frame.grid(row=0, column=0, padx=(0, 10), rowspan=2, sticky="ns") # Placed in column 0, row 0, sticky ns to fill vertically
        capture_controls_frame.grid_columnconfigure(1, weight=1) # Allow widgets within controls to expand

        ttk.Label(capture_controls_frame, text="Camera Index:", style='TLabel').grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.entry_camera_index = ttk.Entry(capture_controls_frame, width=5)
        self.entry_camera_index.grid(row=0, column=1, sticky="ew", padx=(0, 0))
        self.entry_camera_index.insert(0, "0")

        ttk.Label(capture_controls_frame, text="Interval (s):", style='TLabel').grid(row=1, column=0, sticky="w", padx=(0, 5), pady=(5,0))
        self.entry_capture_interval = ttk.Entry(capture_controls_frame, width=5)
        self.entry_capture_interval.grid(row=1, column=1, sticky="ew", padx=(0, 0), pady=(5,0))

        ttk.Label(capture_controls_frame, text="Total Photos:", style='TLabel').grid(row=2, column=0, sticky="w", padx=(0, 5), pady=(5,0))
        self.entry_total_photos = ttk.Entry(capture_controls_frame, width=5)
        self.entry_total_photos.grid(row=2, column=1, sticky="ew", padx=(0, 0), pady=(5,0))

        ttk.Label(capture_controls_frame, text="Output Folder:", style='TLabel').grid(row=3, column=0, sticky="nw", padx=(0, 5), pady=(10,0))
        self.select_capture_folder_button = ttk.Button(capture_controls_frame, text="Select Folder...")
        self.select_capture_folder_button.grid(row=3, column=1, sticky="ew", padx=(0, 0), pady=(10,0))
        self.select_capture_folder_button.config(command=self.select_capture_folder)

        self.capture_output_folder_label = ttk.Label(capture_controls_frame, text="No folder selected", relief="sunken", anchor="w", style='TLabel', wraplength=200)
        self.capture_output_folder_label.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(5,0))

        self.start_capture_button = ttk.Button(capture_controls_frame, text="Start Capture")
        self.start_capture_button.grid(row=5, column=0, sticky="ew", pady=(10, 5))
        self.start_capture_button.config(command=self.start_capture)

        self.stop_capture_button = ttk.Button(capture_controls_frame, text="Stop Capture", state=tk.DISABLED)
        self.stop_capture_button.grid(row=5, column=1, sticky="ew", pady=(10, 5))
        self.stop_capture_button.config(command=self.stop_capture)

        self.capture_status_label = ttk.Label(capture_controls_frame, text="Idle", anchor="w", style='TLabel', wraplength=250)
        self.capture_status_label.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(5,0))


        # Camera Preview Area (right side)
        capture_preview_frame = ttk.Frame(capture_frame, style='TFrame')
        # Set a fixed size for the preview frame using the predefined preview_width and preview_height
        capture_preview_frame.config(width=self.preview_width, height=self.preview_height)
        # Explicitly prevent this frame from propagating its children's size to its parent
        capture_preview_frame.grid_propagate(False) # This is key to preventing growth

        capture_preview_frame.grid(row=0, column=1, sticky="nsew", rowspan=2) # Still use grid to place frame in capture_frame, sticky allows it to use allocated space

        # Use pack for the preview label inside the fixed-size frame
        self.camera_preview_label = ttk.Label(capture_preview_frame, style='TLabel', anchor='center', text="Camera Preview", compound='image')
        self.camera_preview_label.pack(expand=True, fill="both") # Label expands to fill the fixed frame


        # Bottommost status bar - This stays outside the Notebook
        self.status_bar = ttk.Label(main_frame, text="Ready", relief="sunken", anchor="w", style='TLabel') # Set default status
        self.status_bar.grid(row=1, column=0, sticky="ew") # Below the notebook


        # Configure main_frame row weights
        # Row 0 now contains the notebook, which expands
        # Row 1 contains the status bar, which has fixed height
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_rowconfigure(1, weight=0)


    # --- Core method implementation ---
    # def start_initial_countdown(self, countdown_seconds): # <--- 注释或删除旧名称
    def run_capture_countdown(self, countdown_seconds):
        """Display an initial countdown before starting capture."""
        if countdown_seconds > 0:
            self.camera_preview_label.config(
                text=str(countdown_seconds),
                font=("Helvetica", 90),  # Larger font
                compound="center"
            )
            self.camera_preview_label.configure(style="CountdownLabel.TLabel")  # Apply style
            self.master.after(1000, self.run_capture_countdown, countdown_seconds - 1)
        else:
            # --- Countdown finished ---
            # 显示 "Saving..." 并重置字体和样式
            self.camera_preview_label.config(text="Saving...", font=None, compound="image") # <-- 添加 font=None
            self.camera_preview_label.configure(style="TLabel") # <-- 重置样式
            self.master.update_idletasks() # Update UI to show "Saving..."

            # --- **Call the save function** ---
            save_successful = self._capture_photo_save()

            # --- Decide next step based on save result and count ---
            # 检查 self.is_capturing 以防在保存期间被外部停止
            if self.is_capturing:
                if save_successful and self.capture_count < self.total_capture_count:
                    # 保存成功，且需要继续拍照：安排下一次循环
                    self.status_bar.config(text=f"Photo {self.capture_count} saved. Waiting for interval...")
                    self.schedule_capture_save() # 调用 schedule_capture_save 来等待间隔并开始下一次倒计时
                elif save_successful and self.capture_count >= self.total_capture_count:
                    # 保存成功，且所有照片已拍完：完成并停止
                    self.status_bar.config(text="Camera capture finished.")
                    messagebox.showinfo("Capture Complete", f"Successfully captured {self.capture_count} photos.")
                    self.stop_capture() # 最终停止
                    self.capture_status_label.config(text=f"Capture Complete: {self.capture_count} photos saved.") # 显示最终状态
                elif not save_successful:
                    # 保存失败 (错误已显示，停止函数已在 _capture_photo_save 中调用)
                    self.status_bar.config(text="Capture stopped due to save error.")
                    # 确保停止状态正确反映，以防万一 stop_capture 没被调用
                    if self.is_capturing:
                         self.stop_capture()
                    self.capture_status_label.config(text=f"Capture Error after {self.capture_count-1} photos saved.")
            # else: Capture was stopped externally (e.g., user clicked Stop) - stop_capture handles cleanup 


    def select_folder(self):
        """Open folder selection dialog, load image list"""
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.folder_path_label.config(text=folder_selected)
            # Debug message added here
            self.status_bar.config(text=f"Searching for images in selected folder...") # Added debug message
            self.master.update() # Force GUI update

            # Support common image formats and sort by filename
            image_extensions = ['*.jpg', '*.png', '*.jpeg', '*.bmp', '*.tiff']
            self.image_paths = []
            for ext in image_extensions:
                # Use os.path.join to build cross-platform paths
                self.image_paths.extend(glob.glob(os.path.join(folder_selected, ext)))

            self.image_paths.sort()

            if not self.image_paths:
                # Debug message modified here
                self.status_bar.config(text="No supported image files found (.jpg, .png, etc.)") # Modified debug message
                self.reset_gui_state()
                return

            # Debug message modified here
            self.status_bar.config(text=f"Found {len(self.image_paths)} images.") # Modified debug message
            self.reset_gui_state() # Reset all states and display, but keep image_paths
            self.update_image_list() # Update list display


    def update_image_list(self):
        """Update the Treeview image list, displaying name, error, and status"""
        self.image_list_tree.delete(*self.image_list_tree.get_children()) # Clear the list
        for i, path in enumerate(self.image_paths):
            # Use os.path.basename to get filename, handling cross-platform paths
            filename = os.path.basename(path)

            error_text = ""
            status = ""
            tags = () # Used for setting row color or other styles

            if i in self.excluded_indices:
                 status = "Excluded" # Consistent English status
                 tags = ('excluded',) # Apply excluded style tag

            # Check if the image was successfully used for calibration (implies corners were found)
            # Only show error if calibration was successful AND the image was used
            if self.camera_matrix is not None and i in self.successful_image_indices:
                 try:
                     # Find the index of this image within the list of successfully calibrated images
                     error_index = self.successful_image_indices.index(i)
                     error_text = f"{self.per_view_errors[error_index]:.4f}"
                     if not status: # If not already marked as excluded
                         status = "Success" # Consistent English status
                 except ValueError:
                     # This should ideally not happen if data is consistent
                     status = "Error Finding" # Consistent English status (Shouldn't happen if logic is correct)


            # If not excluded, and the corner finding process has run (successful_image_indices is not empty),
            # and this image was not in the successful list, mark as find failed.
            # Check if objpoints_all is not empty as a sign that find corners process has at least started/ran
            elif not i in self.excluded_indices and (self.successful_image_indices or (self.objpoints_all and i not in self.successful_image_indices)):
                 if not status: # If not already marked as excluded or successful
                     status = "Find Failed" # Consistent English status
                     tags = ('failed',) # Apply find failed style tag
            elif not i in self.excluded_indices and not self.objpoints_all:
                 # If not excluded and corner finding hasn't even run yet
                 status = "" # Or could set to "Pending" or similar if desired, but empty is minimalist


            # Insert item into Treeview
            # iid is used later to retrieve the item based on the original image index
            self.image_list_tree.insert("", "end", iid=str(i), text=filename, values=(error_text, status), tags=tags)


    def on_list_select(self, event):
        """Handle single click on list item, update status bar info"""
        # Get the ID of the currently focused item (which is the original image index as a string)
        selected_item_id = self.image_list_tree.focus()
        if not selected_item_id:
            self.status_bar.config(text="List empty or no item selected")
            return
        try:
            selected_index = int(selected_item_id)
            if 0 <= selected_index < len(self.image_paths):
                filename = os.path.basename(self.image_paths[selected_index])
                item_values = self.image_list_tree.item(selected_item_id, 'values')
                error_text = item_values[0] if len(item_values) > 0 else ""
                status = item_values[1] if len(item_values) > 1 else ""

                info = filename
                if status: info += f" ({status})"
                if error_text: info += f", Error: {error_text}"
                self.status_bar.config(text=f"Selected Image: {info}")
        except (ValueError, IndexError):
            self.status_bar.config(text="Could not get selected image info")


    def on_image_select(self, event):
        """Handle double click on list item, load and display image, draw results if calibrated"""
        # Get the ID of the currently focused item (which is the original image index as a string)
        selected_item_id = self.image_list_tree.focus()
        if not selected_item_id:
            self.status_bar.config(text="No image selected to display.")
            self.image_label.config(image='', text="Image Preview") # Clear image display, show text
            self.image_label.image = None # Remove reference
            self.current_image_info_label.config(text="")
            return

        try:
            selected_index = int(selected_item_id)
            if not (0 <= selected_index < len(self.image_paths)):
                 self.status_bar.config(text="Invalid selected image index.")
                 self.image_label.config(image='', text="Invalid Index") # Clear image display, show text
                 self.image_label.image = None # Remove reference
                 self.current_image_info_label.config(text="Invalid index")
                 return # Index out of bounds

            image_path = self.image_paths[selected_index]
            filename = os.path.basename(image_path)
            self.current_image_info_label.config(text=f"Loading: {filename}")
            self.status_bar.config(text=f"Loading image: {filename}...")
            self.master.update_idletasks() # Force GUI update immediately


            img = cv2.imread(image_path)
            if img is None:
                # Debug message modified here
                self.status_bar.config(text=f"Error: Could not load image file: {filename}") # Modified debug message
                self.image_label.config(image='', text=f"Load Failed:\n{filename}") # Clear image display, show text
                self.image_label.image = None # Remove reference
                self.current_image_info_label.config(text=f"Load Failed: {filename}")
                return

            self.status_bar.config(text=f"Image loaded: {filename}. Preparing for display...")
            self.master.update_idletasks()

            display_img = img.copy() # Make a copy before drawing to avoid modifying original image data

            # --- Visualization: If calibrated and this image was used, draw reprojected points ---
            # Check if calibration is done and the current image is one of the successfully calibrated images
            if self.camera_matrix is not None and selected_index in self.successful_image_indices:
                 self.status_bar.config(text=f"Calibration results found for {filename}. Drawing reprojected corners...")
                 self.master.update_idletasks()
                 try:
                     # Find the index of this image within the list of successfully calibrated images
                     success_idx = self.successful_image_indices.index(selected_index)
                     rvec = self.rvecs[success_idx]
                     tvec = self.tvecs[success_idx]
                     objp = self.objpoints_all[success_idx] # Get the corresponding world points

                     # Reproject 3D points to the image plane
                     imgpoints2, _ = cv2.projectPoints(objp, rvec, tvec, self.camera_matrix, self.dist_coeffs)

                     # Reshape imgpoints2 to the format expected by cv2.drawChessboardCorners
                     imgpoints2_reshaped = np.array(imgpoints2).reshape(-1, 1, 2).astype(np.float32)

                     # If there is also original detected corner info, could draw them here for comparison
                     # E.g.: cv2.drawChessboardCorners(display_img, self.board_params['size'], original_corners_for_this_image, True) # Red or other color

                     # Draw reprojected points (green) and connecting lines, forming the reprojected chessboard pattern
                     # ret=True forces drawing of connecting lines
                     cv2.drawChessboardCorners(display_img, self.board_params['size'], imgpoints2_reshaped, True)


                     self.current_image_info_label.config(text=f"Calibrated: {filename} (Reprojection)")
                     self.status_bar.config(text=f"Displaying calibrated image {filename} with reprojection.")

                 except Exception as e:
                     # If drawing fails, print error but still try to display the original image
                     print(f"Error drawing reprojection for {filename}: {e}") # Debug print
                     self.status_bar.config(text=f"Warning: Error drawing reprojected points: {e}")
                     self.current_image_info_label.config(text=f"Error Drawing: {filename}")
                     # On error, just display the original image as loaded above
                     display_img = img.copy() # Reset display_img to the original image


            # --- Visualization: If not calibrated, but corners were found previously, draw detected corners ---
            # This would require storing the original 'corners2' results for each image during the find corners phase
            # and retrieving them here. For simplicity, this is not implemented in the current version.
            # Only reprojected corners are shown after calibration.
            else:
                 # Default: just display the original image
                 self.current_image_info_label.config(text=f"Preview: {filename}")
                 self.status_bar.config(text=f"Displaying image: {filename}.")


            # Get the current size of the image display area for scaling
            # Need to wait for the widget to be rendered to get correct size
            self.image_label.update_idletasks() # Try to get the latest size
            display_width = self.image_label.winfo_width()
            display_height = self.image_label.winfo_height()

            # print(f"Display area size: {display_width}x{display_height}") # Debug print

            tk_img, error_msg = cv2_to_tk(display_img, display_width, display_height)

            if tk_img:
                self.image_label.config(image=tk_img, text="") # Set image and clear default text
                self.image_label.image = tk_img # Keep a reference to prevent garbage collection
                # Status bar already updated above depending on whether reprojection was drawn
                if "Displaying image:" in self.status_bar.cget("text"):
                    self.status_bar.config(text=f"Image displayed: {filename}")
            else:
                 # print(f"cv2_to_tk failed: {error_msg}") # Debug print
                 self.image_label.config(image='', text=f"Display Error:\n{error_msg}") # Clear image, show error text
                 self.image_label.image = None # Remove reference
                 self.status_bar.config(text=f"Error displaying image {filename}: {error_msg}")
                 self.current_image_info_label.config(text=f"Display Error: {filename}")


        except Exception as e:
            # print(f"Exception in on_image_select: {e}") # Debug print
            error_msg = f"An unexpected error occurred while displaying image: {e}"
            self.status_bar.config(text=error_msg)
            self.image_label.config(image='', text=f"Runtime Error:\n{e}")
            self.image_label.image = None
            self.current_image_info_label.config(text=f"Error: {filename}")


    def toggle_exclude_selected(self):
        """Toggle the exclusion status of selected images"""
        selected_items_ids = self.image_list_tree.selection() # Supports multi-selection
        if not selected_items_ids:
            messagebox.showwarning("Warning", "Please select images to exclude/include from the list first.")
            return

        toggled_count = 0
        for item_id in selected_items_ids:
            try:
                # item_id is the string representation of the image index in self.image_paths
                selected_index = int(item_id)
                if 0 <= selected_index < len(self.image_paths):
                    if selected_index in self.excluded_indices:
                        # If currently excluded, remove from excluded set
                        self.excluded_indices.remove(selected_index)
                        # Update Treeview item status and tags
                        # If the image was previously successful, restore its status and error display
                        if selected_index in self.successful_image_indices:
                            try:
                                error_index = self.successful_image_indices.index(selected_index)
                                error_text = f"{self.per_view_errors[error_index]:.4f}"
                                self.image_list_tree.item(item_id, values=(error_text, 'Success'), tags=()) # Clear tags
                            except ValueError:
                                # Should not happen, but handle defensively
                                self.image_list_tree.item(item_id, values=('', ''), tags=())
                        else:
                             # If it was a 'find failed' image, restore to initial state (no status, no error)
                             self.image_list_tree.item(item_id, values=('', ''), tags=())

                    else:
                        # If not currently excluded, add to excluded set
                        self.excluded_indices.add(selected_index)
                        # Update Treeview item status and tags
                        self.image_list_tree.item(item_id, values=('', 'Excluded'), tags=('excluded',)) # Clear error, mark as excluded, apply tag

                    toggled_count += 1
            except ValueError:
                pass # Ignore invalid item IDs

        if toggled_count > 0:
            self.status_bar.config(text=f"Toggled exclusion status for {toggled_count} images.")
            # Excluding/unexcluding images changes the dataset for calibration, so reset results
            self.reset_calibration_results()
            self.reset_results_display()
            self.save_button.config(state=tk.DISABLED)
            self.validate_button.config(state=tk.DISABLED)
            self.run_undistort_button.config(state=tk.DISABLED)
            # Note: update_image_list is not needed here as individual items are updated above
        else:
             self.status_bar.config(text="No changes made to image exclusion status.")


    def run_calibration(self):
        """Execute the camera calibration process"""
        if not self.image_paths:
            messagebox.showwarning("Warning", "Please select a folder containing calibration images first.")
            self.status_bar.config(text="Calibration failed: No images loaded.") # Added debug message
            return

        # Get and validate parameters
        try:
            board_w = int(self.entry_board_w.get()); board_h = int(self.entry_board_h.get()); square_size = float(self.entry_square_size.get())
            self.board_params['size'] = (board_w, board_h); self.board_params['square_size'] = square_size
            if board_w <= 0 or board_h <= 0 or square_size <= 0: raise ValueError("Parameters must be positive")
        except ValueError:
            messagebox.showerror("Error", "Please check if the entered calibration board parameters are valid positive numbers.");
            self.status_bar.config(text="Calibration failed: Invalid parameters.") # Added debug message
            return

        # Clear previous points and results, keep image_paths and excluded_indices
        self.reset_calibration_results(); self.reset_results_display()
        # Reset error and status markers in the image list (find failed status will be updated below)
        for item_id in self.image_list_tree.get_children():
             current_values = self.image_list_tree.item(item_id, 'values')
             # Keep excluded status if present, clear error and find status
             new_values = ('', current_values[1] if len(current_values) > 1 and current_values[1] == 'Excluded' else '')
             # Keep excluded tag if present, else clear other tags
             current_tags = self.image_list_tree.item(item_id, 'tags')
             new_tags = ('excluded',) if 'excluded' in current_tags else ()

             self.image_list_tree.item(item_id, values=new_values, tags=new_tags)


        # Debug message added here
        self.status_bar.config(text="Starting corner detection process...") # Added debug message
        self.master.update_idletasks() # Force GUI update to show status


        # World points for the calibration board (created once based on parameters)
        objp = np.zeros((self.board_params['size'][0] * self.board_params['size'][1], 3), np.float32)
        objp[:, :2] = np.mgrid[0:self.board_params['size'][0], 0:self.board_params['size'][1]].T.reshape(-1, 2) * self.board_params['square_size']

        temp_objpoints = []; temp_imgpoints = []; temp_successful_indices = [] # Points and indices for the current calculation
        image_size = None
        processed_count = 0
        # Get indices of images NOT excluded
        images_to_process_indices = [i for i in range(len(self.image_paths)) if i not in self.excluded_indices]
        total_images_to_process = len(images_to_process_indices)


        if total_images_to_process <= 0:
             self.status_bar.config(text="No images available for calibration (maybe all excluded?)")
             messagebox.showwarning("Warning", "No images available for calibration.")
             return


        # --- Find Corners Phase ---
        for i in images_to_process_indices: # Iterate only through non-excluded image indices
            path = self.image_paths[i] # Get the original path

            processed_count += 1
            filename = os.path.basename(path)
            # Debug message updated here
            self.status_bar.config(text=f"Finding corners {processed_count}/{total_images_to_process}: {filename}...") # Debug message updated
            self.master.update_idletasks()

            img = cv2.imread(path)
            if img is None:
                # Debug message updated here
                self.status_bar.config(text=f"Warning: Could not load image {filename}. Skipping.") # Debug message updated
                # Update list status for this image
                item_id = str(i); current_values = self.image_list_tree.item(item_id, 'values')
                current_tags = self.image_list_tree.item(item_id, 'tags')
                new_tags = ('excluded',) if 'excluded' in current_tags else ('failed',) # Keep excluded tag if present, else add failed tag
                self.image_list_tree.item(item_id, values=(current_values[0], 'Load Failed'), tags=new_tags); continue # Status set to 'Load Failed'

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            if image_size is None:
                self.image_size = gray.shape[::-1] # Image size (width, height)

            # Find chessboard corners
            # Add flags for robustness if needed (e.g., cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE)
            ret, corners = cv2.findChessboardCorners(gray, self.board_params['size'], cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE)

            if ret == True:
                # If corners are found
                # Debug message added here
                self.status_bar.config(text=f"Corners found in {filename}.") # Added debug message
                temp_objpoints.append(objp) # Add corresponding world points

                # Refine corner locations for sub-pixel accuracy
                criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
                corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
                temp_imgpoints.append(corners2)
                temp_successful_indices.append(i) # Record the original index of the successful image

                # Update list status to 'Corners Found'
                item_id = str(i); current_values = self.image_list_tree.item(item_id, 'values')
                # Keep excluded tag if present, else clear tags
                current_tags = self.image_list_tree.item(item_id, 'tags')
                new_tags = ('excluded',) if 'excluded' in current_tags else ()

                self.image_list_tree.item(item_id, values=(current_values[0], 'Corners Found'), tags=new_tags) # Update status, error will be filled later


            else:
                 # If corners are not found
                 # Debug message added here
                 self.status_bar.config(text=f"Warning: No corners found in {filename}. Skipping.") # Added debug message
                 item_id = str(i); current_values = self.image_list_tree.item(item_id, 'values')
                 # Keep excluded tag if present, else add failed tag
                 current_tags = self.image_list_tree.item(item_id, 'tags')
                 new_tags = ('excluded',) if 'excluded' in current_tags else ('failed',)

                 self.image_list_tree.item(item_id, values=(current_values[0], 'Find Failed'), tags=new_tags) # Status set to 'Find Failed'


        # Update the instance's points and indices with the results of this find phase
        self.objpoints_all = temp_objpoints
        self.imgpoints_all = temp_imgpoints
        self.successful_image_indices = temp_successful_indices


        # --- Perform Calibration Phase ---
        min_images_required = 10 # Empirical value, typically need at least 10-15 successful images
        if len(self.objpoints_all) < min_images_required:
            # Debug message modified here
            msg = f"Calibration failed: Insufficient images with corners found ({len(self.objpoints_all)} images). At least {min_images_required} images are needed." # Modified debug message
            self.status_bar.config(text=msg); messagebox.showwarning("Warning", msg)
            # Even if calibration fails due to insufficient images, update the list to show which ones failed corner finding
            self.update_image_list() # Ensure final list status is accurate (including find failed markers)
            return

        # Debug message modified here
        self.status_bar.config(text=f"Corners found in {len(self.objpoints_all)} images. Performing camera calibration...") # Modified debug message
        self.master.update_idletasks()

        try:
            # Execute cv2.calibrateCamera
            # Add flags as needed to control distortion model (e.g., cv2.CALIB_ZERO_TANGENT_DIST or cv2.CALIB_FIX_K3 etc.)
            # By default, it calculates k1, k2, p1, p2. For many images (>~25), consider adding cv2.CALIB_RATIONAL_MODEL for k4, k5, k6
            ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(
                self.objpoints_all, self.imgpoints_all, self.image_size, None, None
            )

            self.camera_matrix = mtx
            self.dist_coeffs = dist
            self.rvecs = rvecs
            self.tvecs = tvecs

            # --- Evaluate Results: Calculate reprojection error for each image ---
            total_error = 0
            self.per_view_errors.clear()
            for i in range(len(self.objpoints_all)):
                # Reproject world points to image plane
                imgpoints2, _ = cv2.projectPoints(self.objpoints_all[i], self.rvecs[i], self.tvecs[i], self.camera_matrix, self.dist_coeffs)
                # Calculate the average Euclidean distance between detected and reprojected points (error per point)
                # cv2.norm(..., cv2.NORM_L2) calculates the Euclidean norm
                error = cv2.norm(self.imgpoints_all[i], imgpoints2, cv2.NORM_L2) / len(imgpoints2) if len(imgpoints2) > 0 else 0
                self.per_view_errors.append(error)
                total_error += error

            avg_error = total_error / len(self.objpoints_all) if len(self.objpoints_all) > 0 else 0

            # --- Update GUI to Display Results ---
            self.display_results(self.camera_matrix, self.dist_coeffs, avg_error)
            self.update_image_list() # Update list to show error for each successful image and final status

            # Debug message modified here
            self.status_bar.config(text="Camera calibration complete! Average reprojection error: %.4f" % avg_error) # Modified debug message
            self.save_button.config(state=tk.NORMAL) # Enable save button
            self.validate_button.config(state=tk.NORMAL) # Enable validate button
            self.run_undistort_button.config(state=tk.NORMAL) # Enable undistort button


        except Exception as e:
            # Debug message modified here
            self.status_bar.config(text=f"An error occurred during calibration: {e}") # Modified debug message
            messagebox.showerror("Calibration Error", f"An error occurred during camera calibration: {e}")
            self.reset_calibration_results() # Clear potentially partial results
            self.reset_results_display()
            self.update_image_list() # Refresh list status
            self.run_undistort_button.config(state=tk.DISABLED) # Disable undistort button


    def display_results(self, mtx, dist, avg_error):
        """Display calibration results in the GUI Text widgets"""
        # Clear text boxes and set to normal state for editing
        self.matrix_k_text.config(state=tk.NORMAL)
        self.matrix_k_text.delete(1.0, tk.END)
        self.dist_coeffs_text.config(state=tk.NORMAL)
        self.dist_coeffs_text.delete(1.0, tk.END)

        if mtx is not None:
            # Format camera matrix for display
            # max_line_width helps with formatting, wrap="word" in Text widget handles line breaks
            k_str = np.array2string(mtx, precision=4, separator=', ', suppress_small=True, max_line_width=100)
            self.matrix_k_text.insert(tk.END, k_str)

        if dist is not None:
            # Format distortion coefficients for display
            d_str = np.array2string(dist, precision=4, separator=', ', suppress_small=True, max_line_width=100)
            self.dist_coeffs_text.insert(tk.END, d_str)

        # Set text boxes to read-only state
        self.matrix_k_text.config(state=tk.DISABLED)
        self.dist_coeffs_text.config(state=tk.DISABLED)

        self.avg_error_label.config(text=f"{avg_error:.4f}" if avg_error is not None else "N/A")


    def reset_results_display(self):
        """Reset the text and average error label in the results display area"""
        self.matrix_k_text.config(state=tk.NORMAL)
        self.matrix_k_text.delete(1.0, tk.END)
        self.matrix_k_text.config(state=tk.DISABLED)

        self.dist_coeffs_text.config(state=tk.NORMAL)
        self.dist_coeffs_text.delete(1.0, tk.END)
        self.dist_coeffs_text.config(state=tk.DISABLED)

        self.avg_error_label.config(text="N/A")


    def reset_calibration_results(self):
         """Reset all data related to the calibration calculation"""
         self.objpoints_all.clear()
         self.imgpoints_all.clear()
         self.successful_image_indices.clear()
         self.per_view_errors.clear()
         self.camera_matrix = None
         self.dist_coeffs = None
         self.rvecs = None
         self.tvecs = None
         self.undistort_image_path = None # Clear selected undistort image
         self.undistort_image_path_label.config(text="No image selected") # Reset label text
         # self.image_size = None # Image size is usually determined once during the first image load, can keep

         # Clear validation image references
         self.validation_original_tk = None
         self.validation_undistorted_tk = None


    def reset_gui_state(self):
        """Reset GUI to initial state (called after selecting a folder)"""
        # Keep self.image_paths
        self.image_list_tree.delete(*self.image_list_tree.get_children())
        self.image_label.config(image='', text="Image Preview") # Clear image display, show text
        self.image_label.image = None # Remove reference
        self.current_image_info_label.config(text="")

        self.reset_calibration_results() # Reset all calibration calculation related data
        self.reset_results_display() # Reset results display area

        self.excluded_indices.clear() # Clear all exclusion statuses after selecting a new folder

        self.save_button.config(state=tk.DISABLED)
        self.validate_button.config(state=tk.DISABLED)
        self.run_undistort_button.config(state=tk.DISABLED) # Disable undistort button
        # Keep camera capture state if active? No, probably reset.
        self.stop_capture() # Ensure capture is stopped
        self.capture_output_folder = None
        self.capture_output_folder_label.config(text="No folder selected")
        self.capture_status_label.config(text="Idle")
        self.entry_camera_index.delete(0, tk.END) # Clear and reset defaults
        self.entry_camera_index.insert(0, "0")
        self.entry_capture_interval.delete(0, tk.END)
        self.entry_capture_interval.insert(0, "1.0")
        self.entry_total_photos.delete(0, tk.END)
        self.entry_total_photos.insert(0, "20")


    def save_results(self):
        """Save calibration results to a file (.npz format)"""
        if self.camera_matrix is None or self.dist_coeffs is None:
            messagebox.showwarning("Warning", "No calibration results available to save. Please calibrate first.")
            return

        # Default filename and format
        initial_file = "camera_calibration_result.npz"
        # Can try to use the last selected folder as the initial directory
        initialdir = os.path.dirname(self.folder_path_label.cget("text"))
        if not os.path.isdir(initialdir) or initialdir == "No folder selected":
             initialdir = os.getcwd() # If last folder is invalid, use current working directory


        file_path = filedialog.asksaveasfilename(
            initialdir=initialdir,
            initialfile=initial_file,
            defaultextension=".npz",
            filetypes=[("NumPy Files", "*.npz"), ("All Files", "*.*")]
        )

        if file_path:
            try:
                np.savez(file_path, camera_matrix=self.camera_matrix, dist_coeffs=self.dist_coeffs)
                self.status_bar.config(text=f"Calibration results saved to: {os.path.basename(file_path)}")
            except Exception as e:
                self.status_bar.config(text=f"Error saving file: {e}")
                messagebox.showerror("Save Error", f"An error occurred while saving the file: {e}")


    def validate_calibration(self):
        """Provide a method to validate calibration results: display original and undistorted image side-by-side"""
        if self.camera_matrix is None or self.dist_coeffs is None or not self.successful_image_indices:
            messagebox.showwarning("Warning", "No calibration results or successfully calibrated images available for validation.")
            return

        # Pop up a new window to display validation results
        validation_window = tk.Toplevel(self.master)
        validation_window.title("Calibration Validation (Original vs Undistorted)")
        validation_window.transient(self.master) # Make the validation window dependent on the main window
        validation_window.grab_set() # Prevent interaction with the main window
        validation_window.minsize(900, 600) # Set a minimum size for the validation window to accommodate two images

        # Set window background to white
        validation_window.configure(bg='white')

        val_frame = ttk.Frame(validation_window, padding="10", style='TFrame')
        val_frame.grid(row=0, column=0, sticky="nsew")
        validation_window.grid_columnconfigure(0, weight=1)
        validation_window.grid_rowconfigure(0, weight=1) # Let the val_frame expand


        ttk.Label(val_frame, text="Select a successfully calibrated image:", style='TLabel').grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 5))

        # Dropdown list to select image
        successful_image_original_paths = [self.image_paths[i] for i in self.successful_image_indices]

        if not successful_image_original_paths:
             ttk.Label(val_frame, text="No images successfully used for calibration.", style='TLabel').grid(row=1, column=0, columnspan=2)
             return

        self.selected_val_image_path = tk.StringVar()
        self.selected_val_image_path.set(successful_image_original_paths[0])

        val_image_menu = ttk.OptionMenu(val_frame, self.selected_val_image_path, successful_image_original_paths[0], *successful_image_original_paths,
                                        command=self.display_validation_images) # Call display_validation_images
        val_image_menu.grid(row=1, column=0, sticky="ew", padx=(0, 10))
        val_frame.grid_columnconfigure(0, weight=1) # Let the dropdown expand


        # --- Image Display Area (Two Images Side-by-Side) ---
        image_compare_frame = ttk.Frame(val_frame, style='TFrame')
        image_compare_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(10, 0)) # Span across columns below dropdown
        image_compare_frame.grid_columnconfigure(0, weight=1) # Allow left image frame to expand
        image_compare_frame.grid_columnconfigure(1, weight=1) # Allow right image frame to expand
        image_compare_frame.grid_rowconfigure(0, weight=1) # Allow image frames to expand vertically

        # Frame for Original Image
        original_image_frame = ttk.LabelFrame(image_compare_frame, text="Original Image (with distorted grid)", padding=5, style='TLabelframe') # Updated title
        original_image_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5)) # Left side, add right padding
        original_image_frame.grid_columnconfigure(0, weight=1)
        original_image_frame.grid_rowconfigure(0, weight=1)

        self.validation_original_label = ttk.Label(original_image_frame, style='TLabel', anchor='center', text="Loading Original...", compound='image')
        self.validation_original_label.grid(row=0, column=0, sticky="nsew")

        # Frame for Undistorted Image
        undistorted_image_frame = ttk.LabelFrame(image_compare_frame, text="Undistorted Image (with straight grid)", padding=5, style='TLabelframe') # Updated title
        undistorted_image_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0)) # Right side, add left padding
        undistorted_image_frame.grid_columnconfigure(0, weight=1)
        undistorted_image_frame.grid_rowconfigure(0, weight=1)

        self.validation_undistorted_label = ttk.Label(undistorted_image_frame, style='TLabel', anchor='center', text="Loading Undistorted...", compound='image')
        self.validation_undistorted_label.grid(row=0, column=0, sticky="nsew")

        # Let the main validation frame's image display row expand
        val_frame.grid_rowconfigure(2, weight=1)


        # Display the default image pair initially
        self.display_validation_images()


    def display_validation_images(self, *args):
        """
        Load and display the original (with distorted grid) and undistorted (with straight grid)
        versions of the selected image in the validation window.
        Images are resized to fit their respective labels while maintaining aspect ratio.
        *args receives the selected value from the OptionMenu (if called via command).
        """
        selected_image_path = self.selected_val_image_path.get()
        filename = os.path.basename(selected_image_path)

        # Update labels in the validation window immediately
        self.validation_original_label.config(text=f"Loading: {filename}", image='')
        self.validation_original_label.image = None # Clear previous image reference
        self.validation_undistorted_label.config(text=f"Loading: {filename}", image='')
        self.validation_undistorted_label.image = None # Clear previous image reference
        self.validation_original_tk = None # Clear main references
        self.validation_undistorted_tk = None


        self.status_bar.config(text=f"Loading image for validation: {filename}...")
        self.master.update_idletasks()

        try:
            img = cv2.imread(selected_image_path)
            if img is None:
                 error_msg = f"Error: Could not load validation image file: {filename}"
                 self.status_bar.config(text=error_msg)
                 self.validation_original_label.config(text=f"Load Failed:\n{filename}", image='')
                 self.validation_undistorted_label.config(text=f"Load Failed:\n{filename}", image='')
                 return

            # Create copies for drawing
            original_img_with_distorted_grid = img.copy()
            # Undistorted image will be generated below

            self.status_bar.config(text=f"Image loaded: {filename}. Performing undistortion...")
            self.master.update_idletasks()

            # --- Perform Undistortion ---
            undistorted_img = None
            try:
                # Use the image size of the image being undistorted
                h_img, w_img = img.shape[:2]
                # We can use getOptimalNewCameraMatrix here to potentially remove black borders
                # new_camera_matrix, roi = cv2.getOptimalNewCameraMatrix(self.camera_matrix, self.dist_coeffs, (w_img, h_img), 1, (w_img, h_img))
                # undistorted_img = cv2.undistort(img.copy(), self.camera_matrix, self.dist_coeffs, None, new_camera_matrix)
                # # Crop the image
                # x, y, w, h = roi
                # undistorted_img = undistorted_img[y:y+h, x:x+w]

                # Simple undistortion (might have black borders)
                undistorted_img = cv2.undistort(img.copy(), self.camera_matrix, self.dist_coeffs)


            except Exception as e:
                 error_msg = f"Error during undistortion for {filename}: {e}"
                 self.status_bar.config(text=error_msg)
                 self.validation_original_label.config(text=f"Original:\n{filename}", image='') # Still show original if possible
                 self.validation_undistorted_label.config(text=f"Undistort Error:\n{filename}\n{e}", image='')
                 # Continue to display original image, undistorted is None
                 undistorted_img = None


            # --- Draw Grids for Visualization ---
            undistorted_img_with_straight_grid = None
            if undistorted_img is not None:
                self.status_bar.config(text=f"Image undistorted: {filename}. Drawing grids...")
                self.master.update_idletasks()

                undistorted_img_with_straight_grid = undistorted_img.copy() # Draw grid on a copy
                h_u, w_u = undistorted_img_with_straight_grid.shape[:2]

                grid_interval_px = 50 # Pixels between grid lines for the straight grid
                line_color = (255, 255, 255) # White color in BGR
                line_thickness = 1

                # --- Draw Straight Grid on Undistorted Image ---
                try:
                    # Draw vertical lines
                    for x in range(0, w_u, grid_interval_px):
                        cv2.line(undistorted_img_with_straight_grid, (x, 0), (x, h_u), line_color, line_thickness)

                    # Draw horizontal lines
                    for y in range(0, h_u, grid_interval_px):
                        cv2.line(undistorted_img_with_straight_grid, (0, y), (w_u, y), line_color, line_thickness)

                except Exception as e:
                     self.status_bar.config(text=f"Warning: Error drawing straight grid on undistorted image {filename}: {e}")
                     undistorted_img_with_straight_grid = undistorted_img # Use undistorted image without grid


                # --- Draw Distorted Grid on Original Image ---
                # We will project 3D grid points (on a Z=0 plane in camera frame) to the original image using distortion coeffs
                try:
                    h_orig, w_orig = original_img_with_distorted_grid.shape[:2]
                    # Determine 3D grid extent roughly based on original image size and focal length
                    fx = self.camera_matrix[0, 0]
                    fy = self.camera_matrix[1, 1]
                    # Define a 3D grid spacing in "virtual" units, e.g., corresponding to 50 pixels at a unit distance
                    # A grid interval of 50 pixels in the image corresponds roughly to a physical size of 50 / f at unit distance.
                    grid_interval_3d_x = grid_interval_px / fx
                    grid_interval_3d_y = grid_interval_px / fy

                    # Create 3D points for lines. Start from a point that projects near the top-left corner.
                    # Approximate top-left 3D point assuming principal point is image center
                    start_x_3d = -(w_orig / 2.0) / fx * 1.0 # Assuming Z=1.0 for scaling
                    start_y_3d = -(h_orig / 2.0) / fy * 1.0

                    # Create a grid of 3D points (X, Y, 0)
                    points_3d = []
                    # Create points for horizontal lines (varying X, constant Y)
                    for i in range(int(h_orig / grid_interval_px) + 2): # Add buffer
                         y_3d = start_y_3d + i * grid_interval_3d_y
                         for j in range(int(w_orig / grid_interval_px) * 2 + 2): # Wider X range
                             x_3d = start_x_3d + j * grid_interval_3d_x
                             points_3d.append((x_3d, y_3d, 0))

                    # Create points for vertical lines (constant X, varying Y)
                    for j in range(int(w_orig / grid_interval_px) + 2): # Add buffer
                         x_3d = start_x_3d + j * grid_interval_3d_x
                         for i in range(int(h_orig / grid_interval_px) * 2 + 2): # Wider Y range
                             y_3d = start_y_3d + i * grid_interval_3d_y
                             points_3d.append((x_3d, y_3d, 0))

                    points_3d = np.array(points_3d, dtype=np.float32)

                    # Project points to original image plane
                    rvec_ident = np.zeros(3, dtype=np.float32) # Identity rotation (camera looking perpendicular to plane)
                    tvec_zero = np.array([0.0, 0.0, 1.0], dtype=np.float32) # Translation to place the plane at Z=1.0 in front of camera

                    projected_points, _ = cv2.projectPoints(points_3d, rvec_ident, tvec_zero, self.camera_matrix, self.dist_coeffs)

                    # Reshape projected points to extract lines
                    num_horizontal_lines = int(h_orig / grid_interval_px) + 2
                    num_vertical_lines = int(w_orig / grid_interval_px) + 2
                    points_per_hline = int(w_orig / grid_interval_px) * 2 + 2
                    points_per_vline = int(h_orig / grid_interval_px) * 2 + 2

                    projected_h_lines = projected_points[:num_horizontal_lines * points_per_hline].reshape(num_horizontal_lines, points_per_hline, 2)
                    projected_v_lines = projected_points[num_horizontal_lines * points_per_hline:].reshape(num_vertical_lines, points_per_vline, 2)


                    # Draw lines on the original image copy
                    distorted_line_color = (0, 255, 255) # Yellow color in BGR (more visible)
                    distorted_line_thickness = 1

                    # Draw horizontal distorted lines
                    for line_points in projected_h_lines:
                        # Sort points by x-coordinate to draw line segments correctly
                        line_points_sorted = line_points[line_points[:, 0].argsort()]
                        for i in range(len(line_points_sorted) - 1):
                            p1 = tuple(map(int, line_points_sorted[i]))
                            p2 = tuple(map(int, line_points_sorted[i+1]))
                            # Check if points are within image bounds before drawing (optional)
                            # Removed boundary check for simplicity, lines might go outside
                            cv2.line(original_img_with_distorted_grid, p1, p2, distorted_line_color, distorted_line_thickness)


                    # Draw vertical distorted lines
                    for line_points in projected_v_lines:
                         # Sort points by y-coordinate to draw line segments correctly
                         line_points_sorted = line_points[line_points[:, 1].argsort()]
                         for i in range(len(line_points_sorted) - 1):
                             p1 = tuple(map(int, line_points_sorted[i]))
                             p2 = tuple(map(int, line_points_sorted[i+1]))
                             # Check if points are within image bounds before drawing (optional)
                             # Removed boundary check for simplicity, lines might go outside
                             cv2.line(original_img_with_distorted_grid, p1, p2, distorted_line_color, distorted_line_thickness)


                except Exception as e:
                     self.status_bar.config(text=f"Warning: Error drawing distorted grid on original image {filename}: {e}")
                     original_img_with_distorted_grid = img.copy() # Use original image without grid


            else:
                 # If undistortion failed, no grids can be drawn
                 undistorted_img_with_straight_grid = None
                 original_img_with_distorted_grid = img.copy() # Use original image without grid


            # Convert images to Tkinter format and display
            try:
                # Need to update_idletasks on the validation window specifically to get label sizes
                # Get the toplevel window for the labels
                val_window = self.validation_original_label.winfo_toplevel()
                val_window.update_idletasks()

                # Get dimensions of the label widgets
                original_display_width = self.validation_original_label.winfo_width()
                original_display_height = self.validation_original_label.winfo_height()

                undistorted_display_width = self.validation_undistorted_label.winfo_width()
                undistorted_display_height = self.validation_undistorted_label.winfo_height()

                # print(f"Original display area size: {original_display_width}x{original_display_height}") # Debug print
                # print(f"Undistorted display area size: {undistorted_display_width}x{undistorted_display_height}") # Debug print


                # Convert Original Image (with distorted grid)
                tk_original_img, error_msg_orig = cv2_to_tk(original_img_with_distorted_grid, original_display_width, original_display_height)

                if tk_original_img:
                    self.validation_original_label.config(image=tk_original_img, text="") # Set image and clear default text
                    self.validation_original_tk = tk_original_img # Keep a reference
                else:
                    self.validation_original_label.config(image='', text=f"Display Error:\n{error_msg_orig}")
                    self.validation_original_tk = None
                    self.status_bar.config(text=f"Error displaying original image {filename}: {error_msg_orig}")


                # Convert Undistorted Image (with straight grid)
                img_to_convert_undistorted = undistorted_img_with_straight_grid if undistorted_img_with_straight_grid is not None else undistorted_img
                tk_undistorted_img, error_msg_undist = cv2_to_tk(img_to_convert_undistorted, undistorted_display_width, undistorted_display_height)

                if tk_undistorted_img:
                    self.validation_undistorted_label.config(image=tk_undistorted_img, text="") # Set image and clear default text
                    self.validation_undistorted_tk = tk_undistorted_img # Keep a reference
                    if tk_original_img: # Only update main status bar if original also succeeded
                         self.status_bar.config(text=f"Showing original (distorted grid) and undistorted (straight grid) images for {filename}")
                    else: # If original failed, status bar already has original error. Just note undistorted display status.
                         self.status_bar.config(text=f"Original display failed. Showing undistorted image for {filename}.")
                elif undistorted_img is not None: # If undistortion succeeded but TK conversion failed
                    self.validation_undistorted_label.config(image='', text=f"Display Error:\n{error_msg_undist}")
                    self.validation_undistorted_tk = None
                    self.status_bar.config(text=f"Error displaying undistorted image {filename}: {error_msg_undist}")
                # If undistorted_img was None (undistortion failed), label should already show error message from undistortion block
                # If gridded_undistorted_img was None but undistorted_img wasn't (grid failed), and TK conversion failed,
                # the error_msg_undist would contain the cv2_to_tk error for the undistorted_img.

            except Exception as e:
                 # print(f"Exception during TK conversion/display in validation: {e}") # Debug print
                 error_msg = f"An unexpected error occurred during display conversion: {e}"
                 self.status_bar.config(text=error_msg)
                 # Try to show error on labels
                 self.validation_original_label.config(image='', text=f"Runtime Error:\n{e}")
                 self.validation_original_tk = None
                 self.validation_undistorted_label.config(image='', text=f"Runtime Error:\n{e}")
                 self.validation_undistorted_tk = None


        except Exception as e:
             # print(f"Exception in display_validation_images: {e}") # Debug print
             error_msg = f"An unexpected error occurred while displaying validation images: {e}"
             self.status_bar.config(text=error_msg)
             # Try to show error on labels
             self.validation_original_label.config(image='', text=f"Runtime Error:\n{e}")
             self.validation_original_tk = None
             self.validation_undistorted_label.config(image='', text=f"Runtime Error:\n{e}")
             self.validation_undistorted_tk = None


    # --- New Undistort Single Image Feature ---

    def select_undistort_image(self):
        """Open file dialog to select a single image for undistortion."""
        if self.camera_matrix is None or self.dist_coeffs is None:
            messagebox.showwarning("Warning", "Please perform camera calibration first.")
            self.status_bar.config(text="Please calibrate camera before selecting image for undistortion.")
            return

        # Support common image formats
        filetypes = [
            ("Image Files", "*.jpg *.png *.jpeg *.bmp *.tiff"),
            ("All Files", "*.*")
        ]
        image_path = filedialog.askopenfilename(
            title="Select Image to Undistort",
            filetypes=filetypes
        )

        if image_path:
            self.undistort_image_path = image_path
            self.undistort_image_path_label.config(text=os.path.basename(image_path))
            self.status_bar.config(text=f"Selected image for undistortion: {os.path.basename(image_path)}")
        else:
            self.undistort_image_path = None
            self.undistort_image_path_label.config(text="No image selected")
            self.status_bar.config(text="Image selection cancelled.")


    def run_undistort_and_save(self):
        """Undistort the selected single image and save the result."""
        if self.camera_matrix is None or self.dist_coeffs is None:
            messagebox.showwarning("Warning", "Please perform camera calibration first.")
            self.status_bar.config(text="Cannot undistort: Calibration not performed.")
            return

        if self.undistort_image_path is None or not os.path.exists(self.undistort_image_path):
            messagebox.showwarning("Warning", "Please select an image file to undistort.")
            self.status_bar.config(text="Cannot undistort: No valid image file selected.")
            return

        input_filename = os.path.basename(self.undistort_image_path)
        self.status_bar.config(text=f"Loading image for undistortion: {input_filename}...")
        self.master.update_idletasks()

        try:
            img = cv2.imread(self.undistort_image_path)
            if img is None:
                error_msg = f"Error: Could not load image file for undistortion: {input_filename}"
                self.status_bar.config(text=error_msg)
                messagebox.showerror("Error", error_msg)
                return

            self.status_bar.config(text=f"Image loaded: {input_filename}. Performing undistortion...")
            self.master.update_idletasks()

            # Perform Undistortion
            # Use the image size of the image being undistorted
            # h_img, w_img = img.shape[:2]
            # img_size_current = (w_img, h_img)

            # Use getOptimalNewCameraMatrix and undistort to handle cropping/scaling
            # new_camera_matrix, roi = cv2.getOptimalNewCameraMatrix(self.camera_matrix, self.dist_coeffs, img_size_current, 1, img_size_current) # Alpha=1 retains all pixels
            # undistorted_img = cv2.undistort(img, self.camera_matrix, self.dist_coeffs, None, new_camera_matrix)

            # Simple undistortion (might have black borders)
            undistorted_img = cv2.undistort(img, self.camera_matrix, self.dist_coeffs)

        except Exception as e:
            error_msg = f"Error during undistortion process for {input_filename}: {e}"
            self.status_bar.config(text=error_msg)
            messagebox.showerror("Undistortion Error", error_msg)
            return

        # Ask user where to save the undistorted image
        input_name, input_ext = os.path.splitext(input_filename)
        initial_filename = f"{input_name}_undistorted{input_ext}"
        initialdir = os.path.dirname(self.undistort_image_path)

        save_path = filedialog.asksaveasfilename(
            initialdir=initialdir,
            initialfile=initial_filename,
            defaultextension=input_ext if input_ext else ".png", # Suggest original extension or PNG
            filetypes=[
                ("PNG files", "*.png"),
                ("JPEG files", "*.jpg *.jpeg"),
                ("BMP files", "*.bmp"),
                ("TIFF files", "*.tiff"),
                ("All files", "*.*")
            ],
            title="Save Undistorted Image As"
        )

        if save_path:
            try:
                # Save the undistorted image
                # Ensure correct file extension if user didn't provide one and we suggested a default
                # This is handled by defaultextension and filetypes in askSaveasfilename, but can double check
                # e.g., if save_path doesn't have extension, add the default one
                # Root.tk.splitdrives()...
                # if not os.path.splitext(save_path)[1]:
                #     save_path += filedialog.SaveAs.options['defaultextension'] # This is complex, rely on dialog

                cv2.imwrite(save_path, undistorted_img)
                self.status_bar.config(text=f"Undistorted image saved to: {os.path.basename(save_path)}")
                messagebox.showinfo("Success", f"Undistorted image saved to:\n{save_path}")
            except Exception as e:
                error_msg = f"Error saving undistorted image to {os.path.basename(save_path)}: {e}"
                self.status_bar.config(text=error_msg)
                messagebox.showerror("Save Error", error_msg)
        else:
            self.status_bar.config(text="Save operation cancelled.")

    # --- New Camera Capture Feature Methods ---

    def select_capture_folder(self):
        """Open folder selection dialog to save captured images."""
        folder_selected = filedialog.askdirectory(title="Select Folder to Save Photos")
        if folder_selected:
            self.capture_output_folder = folder_selected
            self.capture_output_folder_label.config(text=folder_selected)
            self.status_bar.config(text=f"Selected photo save folder: {folder_selected}")
        else:
            self.capture_output_folder = None
            self.capture_output_folder_label.config(text="No folder selected")
            self.status_bar.config(text="Photo save folder selection cancelled.")



    def start_capture(self):
        """Start timed camera capture."""
        if self.is_capturing_preview: # Check preview status as well
            messagebox.showwarning("Warning", "Camera capture or preview is already in progress.")
            return

        # Validate inputs
        try:
            camera_index = int(self.entry_camera_index.get())
            interval_sec = float(self.entry_capture_interval.get())
            total_photos = int(self.entry_total_photos.get())
            if interval_sec <= 0 or total_photos <= 0:
                raise ValueError("Interval and total photos must be positive.")
            if camera_index < 0:
                raise ValueError("Camera index must be non-negative.")
        except ValueError as e:
            messagebox.showerror("Invalid Input", f"Please check camera settings inputs:\n{e}")
            self.status_bar.config(text="Capture start failed: Invalid settings.")
            return

        if self.capture_output_folder is None or not os.path.isdir(self.capture_output_folder):
            messagebox.showwarning("Warning", "Please select a valid output folder for photos.")
            self.status_bar.config(text="Capture start failed: No output folder selected.")
            return

        # Initialize camera
        self.status_bar.config(text=f"Opening camera {camera_index}...")
        self.master.update_idletasks()
        try:
            self.camera_cap = cv2.VideoCapture(camera_index)
            if not self.camera_cap.isOpened():
                raise IOError(f"Cannot open camera {camera_index}")

            # Optionally set camera resolution (may not work on all cameras/platforms)
            # Attempt to set the camera resolution to match the desired preview size
            # This is not guaranteed to work, but can improve performance if supported.
            # Check if setting resolution is successful
            set_width_success = self.camera_cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.preview_width)
            set_height_success = self.camera_cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.preview_height)

            if not set_width_success or not set_height_success:
                print(f"Warning: Could not set camera resolution to {self.preview_width}x{self.preview_height}. Camera will use default resolution.")
                # You might want to get the actual camera resolution here if setting failed
                # actual_width = self.camera_cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                # actual_height = self.camera_cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                # The cv2_to_tk function will handle scaling whatever resolution is received.


        except Exception as e:
            error_msg = f"Error accessing camera {camera_index}: {e}"
            self.status_bar.config(text="Capture start failed: " + error_msg)
            messagebox.showerror("Camera Error", error_msg)
            self.camera_cap = None # Ensure cap is None on failure
            return

        # Set capture parameters
        self.is_capturing = True # Flag for timed saving
        self.is_capturing_preview = True # Flag for continuous preview
        self.capture_count = 0
        self.total_capture_count = total_photos
        self.capture_interval_ms = int(interval_sec * 1000) # Convert seconds to milliseconds

        # Explicitly set the size of the preview label
        # REMOVE OR COMMENT OUT THIS LINE:
        # self.camera_preview_label.config(width=self.preview_width, height=self.preview_height)
        self.camera_preview_label.update_idletasks()  # Ensure size is applied before first frame


        # Update GUI state
        self.start_capture_button.config(state=tk.DISABLED)
        self.stop_capture_button.config(state=tk.NORMAL)
        self.capture_status_label.config(text=f"Capturing 0/{self.total_capture_count}...") # Updated to English
        self.status_bar.config(text="Camera capture and preview started.") # Updated to English
        self.camera_preview_label.config(text="Previewing...") # Updated to English

        # --- 启动预览更新循环 ---
        self.update_preview()

        # --- 启动第一个倒计时 ---
        first_countdown_seconds = 3 # 设置第一次倒计时的秒数
        self.run_capture_countdown(first_countdown_seconds) # 调用倒计时函数开始循环





    def update_preview(self):
        """Read a frame from the camera and update the preview label.""" # Updated to English
        if self.is_capturing_preview and self.camera_cap is not None:
            ret, frame = self.camera_cap.read()
            if ret:
                self.last_frame = frame  # Store the last frame read from camera # Updated to English

                # Use the fixed preview size for conversion
                tk_img, error_msg = cv2_to_tk(frame, self.preview_width, self.preview_height)

                if tk_img:
                    self.camera_preview_label.config(image=tk_img, text="",font=None) # Update label with new frame
                    self.camera_preview_label.image = tk_img # Keep reference
                else:
                    self.camera_preview_label.config(image='', text=f"Preview Error:\n{error_msg}") # Updated to English
                    self.camera_preview_label.image = None
                    print(f"Preview display error: {error_msg}") # Updated to English


            else:
                error_msg = "Error reading frame from camera." # Updated to English
                self.status_bar.config(text="Capture error: " + error_msg) # Updated to English
                self.capture_status_label.config(text="Preview Failed!") # Updated to English
                self.camera_preview_label.config(image='', text="Camera Error") # Updated to English
                self.camera_preview_label.image = None
                messagebox.showerror("Camera Error", error_msg + "\nStopping capture.") # Updated to English
                self.stop_capture() # Stop capture on frame read error


            # Schedule the next preview update # Updated to English
            if self.is_capturing_preview:
                # Run update_preview again after a short delay (e.g., 30ms for ~30fps)
                self.preview_after_id = self.master.after(30, self.update_preview)


    def schedule_capture_save(self):
        """Schedules the *next* countdown cycle after the interval.""" #<-- 更新文档字符串
        if self.is_capturing and self.capture_count < self.total_capture_count:
            # 设置下一次倒计时的秒数
            next_countdown_seconds = 3 # 或者其他你希望的值

            # 在 self.capture_interval_ms 毫秒后调用 run_capture_countdown
            self.capture_after_id = self.master.after(
                self.capture_interval_ms,       # 等待间隔时间
                self.run_capture_countdown,     # 调用倒计时函数
                next_countdown_seconds          # 传递倒计时的起始秒数
            )
        # 如果条件不满足 (停止或完成)，则不执行任何操作。停止逻辑在 run_capture_countdown 中处理。


    def _capture_photo_save(self):
        """Internal method to save the last captured photo."""
        if not self.is_capturing or self.camera_cap is None:
             # This might happen if stop_capture was called between schedule and execution
             return False

        if self.last_frame is not None:
            self.capture_count += 1
            # --- Generate new filename using Beijing Time (UTC+8) ---
            # 1. Define Beijing timezone (UTC+8)
            beijing_tz = timezone(timedelta(hours=8), name='Asia/Shanghai') # 或 'CST'

            # 2. Get current time in UTC
            utc_now = datetime.now(timezone.utc)

            # 3. Convert UTC time to Beijing time
            beijing_now = utc_now.astimezone(beijing_tz)

            # 4. Format the Beijing time string
            timestamp_str = beijing_now.strftime("%Y%m%d_%H%M%S") # Format: 年月日_时分秒

            # Get resolution from the captured frame itself
            height, width = self.last_frame.shape[:2]
            resolution_str = f"{width}x{height}" # Format: WidthxHeight

            # Construct the filename
            filename = f"LB_{timestamp_str}_{resolution_str}_{self.capture_count}.png"




            filepath = os.path.join(self.capture_output_folder, filename)
            save_success = False
            try:
                cv2.imwrite(filepath, self.last_frame) # Save the last frame read by update_preview
                self.capture_status_label.config(text=f"Captured {self.capture_count}/{self.total_capture_count}: {filename}")
                self.status_bar.config(text=f"Saved photo: {filepath}")
                self.last_frame = None # Clear the frame after saving
                save_success = True
            except Exception as e:
                error_msg = f"Error saving photo {filename}: {e}"
                self.status_bar.config(text="Capture error: " + error_msg)
                print(error_msg) # Print to console for debugging
                messagebox.showerror("Save Error", error_msg + "\nStopping capture.") # 提示错误并停止
                # 遇到保存错误时尝试停止捕获 (如果尚未停止)
                if self.is_capturing:
                    self.stop_capture()
                # save_success 保持 False
                # Decide whether to stop on error or continue. Let's continue for now but log error.

            # Schedule the next save if not done
            #if self.is_capturing and self.capture_count < self.total_capture_count:
            #     self.schedule_capture_save() # Schedule next photo
            #elif self.is_capturing and self.capture_count >= self.total_capture_count:
                 # Capture finished after saving the last photo
            #     self.schedule_capture_save() # Call schedule_capture_save one last time to trigger stop_capture
            return save_success

        else:
             # This means update_preview hasn't successfully read a frame yet
             error_msg = "No frame available to save."
             self.status_bar.config(text="Capture warning: " + error_msg)
             #self.capture_status_label.config(text=f"Waiting for frame ({self.capture_count}/{self.total_capture_count})...")
             # Reschedule saving after a short delay, hoping a frame becomes available
             #if self.is_capturing and self.capture_count < self.total_capture_count:
              #    self.capture_after_id = self.master.after(100, self._capture_photo_save) # Try again in 100ms
             return False

    def stop_capture(self):
        """Stop camera capture."""
        # Cancel both preview and save loops
        if self.preview_after_id:
            self.master.after_cancel(self.preview_after_id)
            self.preview_after_id = None
        if self.capture_after_id:
            self.master.after_cancel(self.capture_after_id)
            self.capture_after_id = None

        self.is_capturing = False
        self.is_capturing_preview = False
        self.last_frame = None # Clear stored frame

        # --- Reset Camera Preview Label ---
        # Reset configuration FIRST, then update status bar/labels
        try:
            # Explicitly reset font, style, text, and image
            self.camera_preview_label.config(
                font=None,              # <-- Reset font explicitly
                text="Camera Preview",  # <-- Set default text
                image='',               # <-- Clear any existing image
                compound='image'        # <-- Ensure compound mode if needed later
            )
            self.camera_preview_label.configure(style="TLabel") # <-- Reset style explicitly
            self.camera_preview_label.image = None # Clear PhotoImage reference

            # Force Tkinter to update widget states and recalculate layout
            # This might help if the container was stretched and didn't shrink back
            self.master.update_idletasks()

        except tk.TclError as e:
             # Handle potential error if the widget was destroyed unexpectedly
             print(f"Warning: Could not reset camera_preview_label: {e}")
        # ---------------------------------     

        if self.camera_cap is not None:
            self.camera_cap.release() # Release camera resource
            self.camera_cap = None
            self.status_bar.config(text="Camera capture stopped.")
            # Update status label based on whether capture finished or was stopped manually
            if self.capture_count >= self.total_capture_count:
                 self.capture_status_label.config(text=f"Capture Complete: {self.capture_count} photos saved.")
            else:
                 self.capture_status_label.config(text=f"Capture Stopped at {self.capture_count} photos.")

            # Reset preview label
            self.camera_preview_label.config(image='', text="Camera Preview",font=None,compound='image')
            self.camera_preview_label.configure(style="TLabel") # <--- 明确重置为默认样式
            self.camera_preview_label.image = None

            self.start_capture_button.config(state=tk.NORMAL)
            self.stop_capture_button.config(state=tk.DISABLED)
        else:
             # This case might happen if camera initialization failed but stop was called
             self.status_bar.config(text="Capture stopping initiated. Camera was not active.")
             self.capture_status_label.config(text="Idle.")
        # --- 同样重置字体和样式，以防万一 ---
             self.camera_preview_label.config(
                 image='',
                 text="Camera Preview",
                 font=None,             # <--- 明确设置字体为 None
                 compound='image'       # <--- 确保 compound 模式正确
             )
             self.camera_preview_label.configure(style="TLabel") # <--- 明确重置为默认样式
             self.camera_preview_label.image = None
             # ----------------------------------
             self.start_capture_button.config(state=tk.NORMAL)
             self.stop_capture_button.config(state=tk.DISABLED)


    def run(self):
        """Start the Tkinter main loop"""
        # Ensure camera resource is released when the window is closed
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.master.mainloop()

    def on_closing(self):
        """Handle window closing event."""
        self.stop_capture() # Stop camera capture before closing
        self.master.destroy() # Close the window


# --- Main program entry point ---
if __name__ == "__main__":
    # Check if necessary libraries are installed
    try:
        import cv2
        import numpy as np
        from PIL import Image, ImageTk
    except ImportError:
        print("Please install necessary libraries: pip install opencv-python numpy Pillow")
        # messagebox.showerror("Dependency Error", "Please install necessary libraries: pip install opencv-python numpy Pillow")
        sys.exit(1)

    root = tk.Tk()
    # Can set minimum window size
    # root.minsize(800, 600) # Set in __init__
    gui = MinimalistCalibratorGUI(root)
    gui.run()