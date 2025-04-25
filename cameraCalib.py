import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import cv2
import numpy as np
import glob
from PIL import Image, ImageTk # Requires Pillow: pip install Pillow
import os # For handling file paths
import sys # For handling path separators


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

    # Avoid division by zero or incorrect resizing if widget size is not ready
    if display_width <= 1 or display_height <= 1:
         # Use default reasonable size if actual widget size is not available yet
         # print(f"Warning: Display area size <= 1. Using default size.") # Debug print
         display_width = 600
         display_height = 400
         # Check if display_width/height are still <= 1 after fallback
         if display_width <= 1 or display_height <= 1:
             return (None, f"Invalid display dimensions after fallback: {display_width}x{display_height}")


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
        master.minsize(900, 600) # Set minimum window size

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


        # --- Configure ttk styles for a white minimalist theme ---
        style = ttk.Style()
        # 'clam' is a relatively simple theme
        style.theme_use('clam')

        # Configure default styles for widget classes, setting background to white
        style.configure('TFrame', background='white')
        style.configure('TLabel', background='white')
        # Configure default style for TLabelFrame (background and label text color)
        # Note: This might not make the LabelFrame border white, as the border is part of the theme drawing
        style.configure('TLabelFrame', background='white')
        style.configure('TLabelFrame.Label', background='white', foreground='black') # Ensure label text is visible

        # Configure Treeview style, setting the content area background to white
        style.configure('Treeview', background='white', fieldbackground='white', foreground='black', rowheight=25) # rowheight can adjust row height
        style.configure('Treeview.Heading', background='white', foreground='black', font=('TkDefaultFont', 10, 'bold'))

        # Define Tag Styles, e.g., excluded rows turn grey
        style.configure('excluded', foreground='gray')
        style.configure('failed', foreground='red')

        # tk.Text widgets are not ttk, set bg parameter directly


        # Data storage
        self.image_paths = []
        self.objpoints_all = [] # 3D points for all images where corners were successfully found (world coordinate system)
        self.imgpoints_all = [] # 2D points for all images where corners were successfully found (image coordinate system)
        self.successful_image_indices = [] # Indices of images with successfully found corners in the original self.image_paths list (corresponding to objpoints_all/imgpoints_all index)
        self.excluded_indices = set() # Set of indices of excluded images in the original self.image_paths list
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


        # --- GUI Layout ---
        # Main frame, apply default TFrame style (already configured with white background), add padding
        main_frame = ttk.Frame(master, padding="15", style='TFrame') # Add outer padding
        main_frame.grid(row=0, column=0, sticky="nsew")
        master.grid_columnconfigure(0, weight=1)
        master.grid_rowconfigure(0, weight=1)
        master.configure(bg='white') # Set root window background to white


        # Top control/parameter area - Use LabelFrame for grouping, **do not specify style**, rely on default style (configured with white background), add padding
        control_frame = ttk.LabelFrame(main_frame, text="Settings", padding="10") # Simpler title, add inner padding
        control_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 15)) # Add bottom pady
        control_frame.grid_columnconfigure(0, weight=1) # Allow internal frame to expand


        # Create a white Frame inside control_frame to hold content
        control_content_frame = ttk.Frame(control_frame, style='TFrame')
        control_content_frame.grid(row=0, column=0, sticky="nsew", columnspan=2) # Fill the content area of the LabelFrame
        control_frame.grid_rowconfigure(0, weight=1) # Let internal frame expand


        # File selection row - Use Frame for organization, apply default TFrame style, add padding
        select_file_frame = ttk.Frame(control_content_frame, style='TFrame') # Placed inside control_content_frame
        select_file_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10)) # Add bottom pady
        select_file_frame.grid_columnconfigure(1, weight=1) # Path label takes up remaining space
        self.select_folder_button = ttk.Button(select_file_frame, text="Select Image Folder...")
        self.select_folder_button.grid(row=0, column=0, sticky="w", padx=(0, 15)) # Add right padx
        self.select_folder_button.config(command=self.select_folder) # Bind command
        # Label applies default TLabel style
        self.folder_path_label = ttk.Label(select_file_frame, text="No folder selected", relief="sunken", anchor="w", style='TLabel') # sunken adds a subtle border
        self.folder_path_label.grid(row=0, column=1, sticky="ew")


        # Parameter input row - Use internal frame for organization, apply default TFrame style, add padding
        param_frame = ttk.Frame(control_content_frame, style='TFrame') # Placed inside control_content_frame
        param_frame.grid(row=1, column=0, sticky="w", pady=(5, 0)) # Add top pady

        ttk.Label(param_frame, text="Inner Corners(W,H):", style='TLabel').grid(row=0, column=0, padx=(0, 5)) # Add right padx
        self.entry_board_w = ttk.Entry(param_frame, width=5)
        self.entry_board_w.grid(row=0, column=1, padx=(0, 2))
        self.entry_board_w.insert(0, "7") # Default value
        ttk.Label(param_frame, text=",", style='TLabel').grid(row=0, column=2)
        self.entry_board_h = ttk.Entry(param_frame, width=5)
        self.entry_board_h.grid(row=0, column=3, padx=(0, 15)) # Add right padx
        self.entry_board_h.insert(0, "6") # Default value

        ttk.Label(param_frame, text="Square Size(m):", style='TLabel').grid(row=0, column=4, padx=(0, 5)) # Add right padx
        self.entry_square_size = ttk.Entry(param_frame, width=8)
        self.entry_square_size.grid(row=0, column=5)


        # Middle content area - Split horizontally, left list right image, apply default TFrame style
        content_frame = ttk.Frame(main_frame, style='TFrame')
        content_frame.grid(row=1, column=0, columnspan=2, sticky="nsew")
        main_frame.grid_columnconfigure(0, weight=1) # Left list column
        main_frame.grid_columnconfigure(1, weight=2) # Right image column, takes twice the space
        main_frame.grid_rowconfigure(1, weight=1) # Content area fills remaining height


        # Left image list area - Use LabelFrame for grouping, **do not specify style**, rely on default style (configured with white background), add padding
        list_frame = ttk.LabelFrame(content_frame, text="Image List (Double-click to preview)", padding="10") # Simpler title, add inner padding
        list_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 15)) # Add right padx
        content_frame.grid_columnconfigure(0, weight=1) # Allow internal frame to expand
        content_frame.grid_rowconfigure(0, weight=1) # Allow internal frame to expand

        # In list_frame, create a white Frame to hold content
        list_content_frame = ttk.Frame(list_frame, style='TFrame')
        list_content_frame.grid(row=0, column=0, sticky="nsew", columnspan=2) # Fill the content area of the LabelFrame
        list_frame.grid_rowconfigure(0, weight=1) # Let internal frame expand
        list_frame.grid_columnconfigure(0, weight=1) # Let internal frame expand


        # Use Treeview to display list (filename, error, status), using configured Treeview style
        self.image_list_tree = ttk.Treeview(list_content_frame, columns=("Error", "Status"), show="headings", style='Treeview') # Placed inside list_content_frame
        self.image_list_tree.heading("#0", text="Image Name") # #0 is the default text column
        self.image_list_tree.heading("Error", text="Error")
        self.image_list_tree.heading("Status", text="Status")
        # column stretch=tk.TRUE makes the filename column self-adjust width, other columns fixed
        self.image_list_tree.column("#0", width=150, anchor="w", stretch=tk.TRUE)
        self.image_list_tree.column("Error", width=60, anchor="center", stretch=tk.FALSE)
        self.image_list_tree.column("Status", width=80, anchor="center", stretch=tk.FALSE)
        self.image_list_tree.grid(row=0, column=0, sticky="nsew")

        list_vscroll = ttk.Scrollbar(list_content_frame, orient="vertical", command=self.image_list_tree.yview) # Placed inside list_content_frame
        self.image_list_tree.configure(yscrollcommand=list_vscroll.set)
        list_vscroll.grid(row=0, column=1, sticky="ns")

        list_content_frame.grid_columnconfigure(0, weight=1) # Treeview fills internal Frame width
        list_content_frame.grid_rowconfigure(0, weight=1) # Treeview fills internal Frame height

        # Bind double click event
        self.image_list_tree.bind("<Double-1>", self.on_image_select)
        self.image_list_tree.bind("<<TreeviewSelect>>", self.on_list_select) # Bind single click for status bar


        # Image exclusion button
        exclude_button = ttk.Button(list_frame, text="Exclude/Include Selected") # This button is placed at the bottom of the LabelFrame, not inside the inner Frame
        exclude_button.grid(row=1, column=0, columnspan=2, pady=(10, 0)) # Add top pady
        exclude_button.config(command=self.toggle_exclude_selected) # Bind command


        # Right image display area - Use LabelFrame for grouping, **do not specify style**, rely on default style (configured with white background), add padding
        image_frame = ttk.LabelFrame(content_frame, text="Image View", padding="10") # Simpler title, add inner padding
        image_frame.grid(row=0, column=1, sticky="nsew")
        content_frame.grid_columnconfigure(1, weight=2) # Image area is wider
        image_frame.grid_columnconfigure(0, weight=1) # Allow internal frame to expand
        image_frame.grid_rowconfigure(0, weight=1) # Allow internal frame to expand

        # In image_frame, create a white Frame to hold content
        image_content_frame = ttk.Frame(image_frame, style='TFrame')
        image_content_frame.grid(row=0, column=0, sticky="nsew", columnspan=1) # Fill the content area of the LabelFrame
        image_frame.grid_rowconfigure(0, weight=1)
        image_frame.grid_columnconfigure(0, weight=1)


        self.image_label = ttk.Label(image_content_frame, style='TLabel', anchor='center', text="Image Preview", compound='image') # Add default text
        self.image_label.grid(row=0, column=0, sticky="nsew") # Use nsew to make the label fill the frame
        image_content_frame.grid_columnconfigure(0, weight=1) # Label fills internal Frame width
        image_content_frame.grid_rowconfigure(0, weight=1) # Label fills internal Frame height


        self.current_image_info_label = ttk.Label(image_frame, text="", anchor="center", style='TLabel') # Placed at the bottom of the LabelFrame
        self.current_image_info_label.grid(row=1, column=0, pady=(10, 0)) # Add top pady


        # Bottom operation/results area - Use LabelFrame for grouping, **do not specify style**, rely on default style (configured with white background), add padding
        bottom_frame = ttk.LabelFrame(main_frame, text="Results and Operations", padding="10") # Simpler title, add inner padding
        bottom_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(15, 0)) # Add top pady


        # --- Bottom Layout: Operations buttons and results display arranged vertically ---
        # operation_frame placed in bottom_frame's row 0, column 0
        # results_display_frame placed in bottom_frame's row 1, column 0
        bottom_frame.grid_columnconfigure(0, weight=1) # Bottom area has only one column that needs to stretch
        bottom_frame.grid_rowconfigure(0, weight=0) # Operation row does not need to stretch with window (or very small weight)
        bottom_frame.grid_rowconfigure(1, weight=1) # Results display row needs to stretch with window


        # Operation buttons and average error - Placed in bottom_frame's top row (row 0)
        operation_frame = ttk.Frame(bottom_frame, style='TFrame') # Placed inside bottom_frame
        # Placed in bottom_frame's row 0, column 0
        operation_frame.grid(row=0, column=0, sticky="w") # Align left


        self.calibrate_button = ttk.Button(operation_frame, text="Start Calibration")
        self.calibrate_button.grid(row=0, column=0, padx=(0, 15)) # Add right padx
        self.calibrate_button.config(command=self.run_calibration) # Bind command

        self.save_button = ttk.Button(operation_frame, text="Save Results...", state=tk.DISABLED) # Initially disabled
        self.save_button.grid(row=0, column=1, padx=(0, 15)) # Add right padx
        self.save_button.config(command=self.save_results) # Bind command

        self.validate_button = ttk.Button(operation_frame, text="Validate Calibration", state=tk.DISABLED) # Initially disabled
        self.validate_button.grid(row=0, column=2, padx=(0, 20)) # Add right padx
        self.validate_button.config(command=self.validate_calibration) # Bind command

        # Label applies default TLabel style
        ttk.Label(operation_frame, text="Avg. Error:", style='TLabel').grid(row=0, column=3, padx=(0, 5)) # Simpler label, add right padx
        self.avg_error_label = ttk.Label(operation_frame, text="N/A", width=10, style='TLabel') # Fixed width to prevent jumping, applies default TLabel style
        self.avg_error_label.grid(row=0, column=4, sticky="w")


        # Results display (using Text widget to display multi-line matrices) - Placed in bottom_frame's bottom row (row 1)
        results_display_frame = ttk.Frame(bottom_frame, style='TFrame') # Use Frame to organize results display, applies default TFrame style
        # Placed in bottom_frame's row 1, column 0
        results_display_frame.grid(row=1, column=0, sticky="nsew", pady=(10, 0)) # Fill entire width, add top pady

        # Ensure controls inside results_display_frame can also stretch
        results_display_frame.grid_columnconfigure(1, weight=1) # Make the second column where the text boxes are expand
        results_display_frame.grid_rowconfigure(0, weight=1) # Make the first row (K matrix) expand
        results_display_frame.grid_rowconfigure(1, weight=1) # Make the second row (D coefficients) expand


        # Label applies default TLabel style
        ttk.Label(results_display_frame, text="Camera Matrix K:", style='TLabel').grid(row=0, column=0, sticky="nw", padx=(0, 5)) # Top left alignment
        # Use tk.Text and set background color directly, remove border
        self.matrix_k_text = tk.Text(results_display_frame, height=4, width=40, state=tk.DISABLED, wrap="word", bg='white', fg='black', relief='flat') # Increase width
        self.matrix_k_text.grid(row=0, column=1, sticky="nsew") # Fill right space

        # Label applies default TLabel style
        ttk.Label(results_display_frame, text="Distortion Coeffs D:", style='TLabel').grid(row=1, column=0, sticky="nw", padx=(0, 5), pady=(5, 0)) # Top left alignment
        # Use tk.Text and set background color directly, remove border
        self.dist_coeffs_text = tk.Text(results_display_frame, height=2, width=40, state=tk.DISABLED, wrap="word", bg='white', fg='black', relief='flat') # Increase width
        self.dist_coeffs_text.grid(row=1, column=1, sticky="nsew", pady=(5, 0)) # Fill right space


        # --- New: Single Image Undistortion Frame ---
        undistort_frame = ttk.LabelFrame(main_frame, text="Undistort Single Image", padding="10")
        undistort_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(15, 0)) # Below bottom_frame
        undistort_frame.grid_columnconfigure(1, weight=1) # Path label takes space

        ttk.Label(undistort_frame, text="Input Image:", style='TLabel').grid(row=0, column=0, sticky="w", padx=(0, 5))

        self.select_undistort_image_button = ttk.Button(undistort_frame, text="Select Image File...")
        self.select_undistort_image_button.grid(row=0, column=1, sticky="ew", padx=(0, 5))
        self.select_undistort_image_button.config(command=self.select_undistort_image) # Bind command

        self.undistort_image_path_label = ttk.Label(undistort_frame, text="No image selected", relief="sunken", anchor="w", style='TLabel')
        self.undistort_image_path_label.grid(row=0, column=2, sticky="ew", padx=(0, 15)) # Moved to column 2

        # Make column 1 (button) and column 2 (label) share the space better
        undistort_frame.grid_columnconfigure(1, weight=0) # Button size is fixed
        undistort_frame.grid_columnconfigure(2, weight=1) # Label takes remaining space


        self.run_undistort_button = ttk.Button(undistort_frame, text="Undistort and Save...", state=tk.DISABLED) # Initially disabled
        self.run_undistort_button.grid(row=1, column=0, columnspan=3, pady=(10, 0)) # Span across all columns
        self.run_undistort_button.config(command=self.run_undistort_and_save) # Bind command


        # Bottommost status bar - sunken style adds a sense of depth, applies default TLabel style
        self.status_bar = ttk.Label(master, text="Please select image folder...", relief="sunken", anchor="w", style='TLabel')
        # Placed in row 4 below the new undistort frame
        self.status_bar.grid(row=4, column=0, columnspan=2, sticky="ew")


        # Ensure some areas resize when window size changes (re-confirming these configurations)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(1, weight=1) # content_frame changes with height
        content_frame.grid_columnconfigure(0, weight=1) # list_frame changes with width
        content_frame.grid_columnconfigure(1, weight=2) # image_frame changes with width faster
        content_frame.grid_rowconfigure(0, weight=1) # list_frame and image_frame change with height
        # Ensure the inner content frames within LabelFrames expand correctly
        image_frame.grid_columnconfigure(0, weight=1)
        image_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)
        list_frame.grid_rowconfigure(0, weight=1)
        control_frame.grid_columnconfigure(0, weight=1)
        control_frame.grid_rowconfigure(0, weight=1)
        bottom_frame.grid_columnconfigure(0, weight=1)
        bottom_frame.grid_rowconfigure(0, weight=0)
        bottom_frame.grid_rowconfigure(1, weight=1)
        undistort_frame.grid_columnconfigure(2, weight=1) # Ensure undistort path label expands

        # Make sure the status bar row also expands horizontally
        master.grid_columnconfigure(0, weight=1) # This was already set, just reconfirming


    # --- Core method implementation ---

    def select_folder(self):
        """Open folder selection dialog, load image list"""
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.folder_path_label.config(text=folder_selected)
            self.status_bar.config(text=f"Looking for images...")
            self.master.update() # Force GUI update

            # Support common image formats and sort by filename
            image_extensions = ['*.jpg', '*.png', '*.jpeg', '*.bmp', '*.tiff']
            self.image_paths = []
            for ext in image_extensions:
                # Use os.path.join to build cross-platform paths
                self.image_paths.extend(glob.glob(os.path.join(folder_selected, ext)))

            self.image_paths.sort()

            if not self.image_paths:
                self.status_bar.config(text="No supported image files found (.jpg, .png, etc.)")
                self.reset_gui_state()
                return

            self.status_bar.config(text=f"Found {len(self.image_paths)} images.")
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
                 status = "Excluded"
                 tags = ('excluded',) # Apply excluded style tag

            # Check if the image was successfully used for calibration (implies corners were found)
            # Only show error if calibration was successful AND the image was used
            if self.camera_matrix is not None and i in self.successful_image_indices:
                 try:
                     # Find the index of this image within the list of successfully calibrated images
                     error_index = self.successful_image_indices.index(i)
                     error_text = f"{self.per_view_errors[error_index]:.4f}"
                     if not status: # If not already marked as excluded
                         status = "Success" # Mark as successful
                 except ValueError:
                     # This should ideally not happen if data is consistent
                     status = "Error Finding" # Error looking up error


            # If not excluded, and the corner finding process has run (successful_image_indices is not empty),
            # and this image was not in the successful list, mark as find failed.
            elif not i in self.excluded_indices and self.successful_image_indices:
                 if not status: # If not already marked as excluded or successful
                     status = "Find Failed"
                     tags = ('failed',) # Apply find failed style tag


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
                self.status_bar.config(text=f"Error: Could not load image file: {filename}")
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
                                self.image_list_tree.item(item_id, values=('', ''), tags=()) # If error not found, clear
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
            return

        # Get and validate parameters
        try:
            board_w = int(self.entry_board_w.get()); board_h = int(self.entry_board_h.get()); square_size = float(self.entry_square_size.get())
            self.board_params['size'] = (board_w, board_h); self.board_params['square_size'] = square_size
            if board_w <= 0 or board_h <= 0 or square_size <= 0: raise ValueError("Parameters must be positive")
        except ValueError:
            messagebox.showerror("Error", "Please check if the entered calibration board parameters are valid positive numbers."); return

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


        self.status_bar.config(text="Searching for chessboard corners...")
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
            self.status_bar.config(text=f"Finding corners {processed_count}/{total_images_to_process}: {filename}...")
            self.master.update_idletasks()

            img = cv2.imread(path)
            if img is None:
                self.status_bar.config(text=f"Warning: Could not load image {filename}")
                # Update list status for this image
                item_id = str(i); current_values = self.image_list_tree.item(item_id, 'values')
                current_tags = self.image_list_tree.item(item_id, 'tags')
                new_tags = ('excluded',) if 'excluded' in current_tags else ('failed',) # Keep excluded tag if present, else add failed tag
                self.image_list_tree.item(item_id, values=(current_values[0], 'Load Failed'), tags=new_tags); continue

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            if image_size is None:
                self.image_size = gray.shape[::-1] # Image size (width, height)

            # Find chessboard corners
            # Add flags for robustness if needed (e.g., cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE)
            ret, corners = cv2.findChessboardCorners(gray, self.board_params['size'], cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE)

            if ret == True:
                # If corners are found
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
                 item_id = str(i); current_values = self.image_list_tree.item(item_id, 'values')
                 # Keep excluded tag if present, else add failed tag
                 current_tags = self.image_list_tree.item(item_id, 'tags')
                 new_tags = ('excluded',) if 'excluded' in current_tags else ('failed',)

                 self.image_list_tree.item(item_id, values=(current_values[0], 'Find Failed'), tags=new_tags)


        # Update the instance's points and indices with the results of this find phase
        self.objpoints_all = temp_objpoints
        self.imgpoints_all = temp_imgpoints
        self.successful_image_indices = temp_successful_indices


        # --- Perform Calibration Phase ---
        min_images_required = 10 # Empirical value, typically need at least 10-15 successful images
        if len(self.objpoints_all) < min_images_required:
            msg = f"Insufficient images with corners found ({len(self.objpoints_all)} images). Typically at least {min_images_required} images are needed for reliable calibration results."
            self.status_bar.config(text=msg); messagebox.showwarning("Warning", msg)
            # Even if calibration fails due to insufficient images, update the list to show which ones failed corner finding
            self.update_image_list() # Ensure final list status is accurate (including find failed markers)
            return

        self.status_bar.config(text=f"Corners found in {len(self.objpoints_all)} images, performing camera calibration...")
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

            self.status_bar.config(text="Camera calibration complete! Average reprojection error: %.4f" % avg_error)
            self.save_button.config(state=tk.NORMAL) # Enable save button
            self.validate_button.config(state=tk.NORMAL) # Enable validate button
            self.run_undistort_button.config(state=tk.NORMAL) # Enable undistort button


        except Exception as e:
            self.status_bar.config(text=f"An error occurred during calibration: {e}")
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
        original_image_frame = ttk.LabelFrame(image_compare_frame, text="Original Image (with distorted grid)", padding=5) # Updated title
        original_image_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5)) # Left side, add right padding
        original_image_frame.grid_columnconfigure(0, weight=1)
        original_image_frame.grid_rowconfigure(0, weight=1)

        self.validation_original_label = ttk.Label(original_image_frame, style='TLabel', anchor='center', text="Loading Original...", compound='image')
        self.validation_original_label.grid(row=0, column=0, sticky="nsew")

        # Frame for Undistorted Image
        undistorted_image_frame = ttk.LabelFrame(image_compare_frame, text="Undistorted Image (with straight grid)", padding=5) # Updated title
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
                img_size_current = (w_img, h_img)

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
                # We will define a 3D grid plane and project its points to the original image
                # This shows how straight lines in the world project with distortion.
                # Assuming a Z=0 plane relative to the camera origin.
                # The size of the 3D grid impacts what part of the distortion is visible.
                # Let's create a grid that spans a reasonable range, e.g., based on image size / focal length.
                # Approximate FOV mapping at Z=1: X_range ~= W_px / fx, Y_range ~= H_px / fy
                # We need points at Z=0, so use a distance factor.
                # Let's create a grid in a 3D plane that roughly covers the image area.
                # The density of points should be high enough to show curvature.
                grid_density_3d = 20 # Points per dimension for a square region in 3D
                # Estimate the range of X and Y in 3D (at Z=0) to cover the image FOV
                # Using average focal length and assuming image center projects to origin
                try:
                    fx = self.camera_matrix[0, 0]
                    fy = self.camera_matrix[1, 1]
                    cx = self.camera_matrix[0, 2]
                    cy = self.camera_matrix[1, 2]
                    h_img, w_img = img.shape[:2]

                    # Estimate the 3D coordinates (X,Y) that project to the image corners/edges
                    # This is tricky without knowing the Z distance. Let's assume a virtual plane distance D=1.0 for scaling the 3D grid.
                    # X = (u - cx) * Z / fx, Y = (v - cy) * Z / fy. At Z=D.
                    # Let's make the 3D grid span a range based on pixel dimensions scaled by inverse focal length.
                    # A grid covering +/- W_px / (2*fx) and +/- H_px / (2*fy) at Z=1 might be too small or large.
                    # Let's use a fixed range based on typical board dimensions, scaled by square size.
                    # Assuming the grid plane is somewhere in front of the camera.
                    # Create points for lines parallel to X axis and Y axis in 3D.
                    # Define lines in the XZ plane and YZ plane (or XY plane at Z=const). Let's use XY at Z=0.

                    # Points for horizontal lines (constant Y, varying X)
                    points_3d_horizontal = []
                    y_values_3d = np.linspace(-h_img / (2*fy), h_img / (2*fy), grid_density_3d) # Y values in a projected plane at Z=1
                    x_values_3d = np.linspace(-w_img / (2*fx), w_img / (2*fx), grid_density_3d * 2) # Wider X range

                    for y in y_values_3d:
                        for x in x_values_3d:
                            points_3d_horizontal.append((x, y, 0)) # Assume Z=0 plane

                    # Points for vertical lines (constant X, varying Y)
                    points_3d_vertical = []
                    x_values_3d_vert = np.linspace(-w_img / (2*fx), w_img / (2*fx), grid_density_3d) # X values
                    y_values_3d_vert = np.linspace(-h_img / (2*fy), h_img / (2*fy), grid_density_3d * 2) # Wider Y range

                    for x in x_values_3d_vert:
                         for y in y_values_3d_vert:
                             points_3d_vertical.append((x, y, 0)) # Assume Z=0 plane


                    points_3d_horizontal = np.array(points_3d_horizontal, dtype=np.float32)
                    points_3d_vertical = np.array(points_3d_vertical, dtype=np.float32)

                    # Project points to original image plane using camera matrix and distortion coefficients
                    # Assuming identity rotation and zero translation for projection from camera frame Z=0 plane
                    rvec_ident = np.zeros(3, dtype=np.float32) # Corresponds to identity rotation
                    tvec_zero = np.zeros(3, dtype=np.float32) # Corresponds to zero translation

                    projected_points_horizontal, _ = cv2.projectPoints(points_3d_horizontal, rvec_ident, tvec_zero, self.camera_matrix, self.dist_coeffs)
                    projected_points_vertical, _ = cv2.projectPoints(points_3d_vertical, rvec_ident, tvec_zero, self.camera_matrix, self.dist_coeffs)

                    # Reshape projected points
                    projected_points_horizontal = projected_points_horizontal.reshape(-1, len(x_values_3d), 2)
                    projected_points_vertical = projected_points_vertical.reshape(-1, len(y_values_3d_vert), 2)

                    # Draw lines on the original image copy
                    # Color for distorted grid (e.g., Red)
                    distorted_line_color = (0, 0, 255) # Red in BGR
                    distorted_line_thickness = 1

                    # Draw horizontal distorted lines
                    for line_points in projected_points_horizontal:
                        for i in range(len(line_points) - 1):
                            p1 = tuple(map(int, line_points[i]))
                            p2 = tuple(map(int, line_points[i+1]))
                            # Check if points are within image bounds before drawing (optional)
                            if 0 <= p1[0] < w_img and 0 <= p1[1] < h_img and \
                               0 <= p2[0] < w_img and 0 <= p2[1] < h_img:
                                cv2.line(original_img_with_distorted_grid, p1, p2, distorted_line_color, distorted_line_thickness)

                    # Draw vertical distorted lines
                    for line_points in projected_points_vertical:
                        for i in range(len(line_points) - 1):
                            p1 = tuple(map(int, line_points[i]))
                            p2 = tuple(map(int, line_points[i+1]))
                             # Check if points are within image bounds before drawing (optional)
                            if 0 <= p1[0] < w_img and 0 <= p1[1] < h_img and \
                               0 <= p2[0] < w_img and 0 <= p2[1] < h_img:
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
            h_img, w_img = img.shape[:2]
            img_size_current = (w_img, h_img)

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


    def run(self):
        """Start the Tkinter main loop"""
        self.master.mainloop()


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
