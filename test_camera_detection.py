#!/usr/bin/env python3
"""
Modern Camera Detection Studio - Interactive GUI for testing camera compatibility
Using the unified camera_utils module with beautiful modern interface
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from camera_utils import CameraManager
import threading
from datetime import datetime

class ModernCameraDetectionGUI:
    def __init__(self):
        # Create main window with modern styling
        self.root = tk.Tk()
        self.root.title("🔍 Camera Detection Studio")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)
        self.root.configure(bg='#f8f9fa')
        
        # Modern color scheme (same as dual_camera_recorder)
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
        
        # Configure modern styles
        self.configure_styles()
        
        # Initialize data
        self.cameras = []
        self.is_detecting = False
        
        # Create interface
        self.create_interface()
        
        print("🔍 Modern Camera Detection Studio initialized")
    
    def configure_styles(self):
        """Configure modern ttk styles"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure title style
        style.configure('Title.TLabel',
                       background=self.colors['bg'],
                       foreground=self.colors['text'],
                       font=('SF Pro Display', 18, 'bold'))
        
        # Configure subtitle style
        style.configure('Subtitle.TLabel',
                       background=self.colors['bg'],
                       foreground=self.colors['text_muted'],
                       font=('SF Pro Text', 11))
        
        # Configure section title style
        style.configure('SectionTitle.TLabel',
                       background=self.colors['card'],
                       foreground=self.colors['text'],
                       font=('SF Pro Text', 13, 'bold'))
        
        # Configure device info style
        style.configure('DeviceInfo.TLabel',
                       background=self.colors['card'],
                       foreground=self.colors['text'],
                       font=('SF Pro Text', 10))
        
        # Configure modern buttons
        style.configure('Primary.TButton',
                       font=('SF Pro Text', 10),
                       foreground='white',
                       background=self.colors['primary'],
                       borderwidth=0,
                       focuscolor='none',
                       padding=(12, 8))
        
        style.configure('Success.TButton',
                       font=('SF Pro Text', 10, 'bold'),
                       foreground='white',
                       background=self.colors['success'],
                       borderwidth=0,
                       focuscolor='none',
                       padding=(15, 8))
    
    def create_interface(self):
        """Create the modern interface"""
        # Main container
        main_container = tk.Frame(self.root, bg=self.colors['bg'])
        main_container.pack(fill='both', expand=True, padx=15, pady=10)
        
        # Title section
        title_frame = tk.Frame(main_container, bg=self.colors['bg'])
        title_frame.pack(fill='x', pady=(0, 20))
        
        title_label = ttk.Label(title_frame, text="🔍 Camera Detection Studio", 
                              style='Title.TLabel')
        title_label.pack(anchor='center')
        
        subtitle_label = ttk.Label(title_frame, text="Comprehensive camera compatibility testing and device analysis", 
                                 style='Subtitle.TLabel')
        subtitle_label.pack(anchor='center', pady=(5, 0))
        
        # Control section
        control_card = tk.Frame(main_container, bg=self.colors['card'], 
                               relief='flat', bd=1)
        control_card.configure(highlightbackground=self.colors['border'], 
                              highlightthickness=1)
        control_card.pack(fill='x', pady=(0, 15))
        
        control_content = tk.Frame(control_card, bg=self.colors['card'])
        control_content.pack(fill='x', padx=15, pady=15)
        
        # Section title
        section_title = ttk.Label(control_content, text="Detection Controls", 
                                style='SectionTitle.TLabel')
        section_title.pack(anchor='w', pady=(0, 10))
        
        # Buttons
        button_frame = tk.Frame(control_content, bg=self.colors['card'])
        button_frame.pack(fill='x')
        
        self.detect_btn = ttk.Button(button_frame, text="🔍 Start Detection", 
                                   command=self.start_detection,
                                   style='Success.TButton')
        self.detect_btn.pack(side='left', padx=(0, 10))
        
        self.clear_btn = ttk.Button(button_frame, text="🧹 Clear Results", 
                                  command=self.clear_results,
                                  style='Primary.TButton')
        self.clear_btn.pack(side='left')
        
        # Status label
        self.status_label = ttk.Label(control_content, text="Ready to detect cameras", 
                                    style='DeviceInfo.TLabel')
        self.status_label.pack(anchor='w', pady=(10, 0))
        
        # Results section
        results_card = tk.Frame(main_container, bg=self.colors['card'], 
                               relief='flat', bd=1)
        results_card.configure(highlightbackground=self.colors['border'], 
                              highlightthickness=1)
        results_card.pack(fill='both', expand=True)
        
        results_content = tk.Frame(results_card, bg=self.colors['card'])
        results_content.pack(fill='both', expand=True, padx=15, pady=15)
        
        # Section title
        results_title = ttk.Label(results_content, text="Detection Results", 
                                style='SectionTitle.TLabel')
        results_title.pack(anchor='w', pady=(0, 10))
        
        # Results text area
        self.results_text = scrolledtext.ScrolledText(
            results_content, 
            wrap='word', 
            height=25,
            bg=self.colors['card'],
            fg=self.colors['text'],
            font=('SF Pro Text', 10),
            relief='flat',
            borderwidth=1,
            highlightbackground=self.colors['border']
        )
        self.results_text.pack(fill='both', expand=True)
        
        # Add initial welcome message
        self.add_log("🚀 Camera Detection Studio Ready")
        self.add_log("Click 'Start Detection' to scan for available cameras")
        self.add_log("=" * 50)
    
    def add_log(self, message):
        """Add a log message with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        full_message = f"[{timestamp}] {message}\n"
        
        self.results_text.config(state='normal')
        self.results_text.insert('end', full_message)
        self.results_text.see('end')
        self.results_text.config(state='disabled')
        
        # Also print to console for debugging
        print(f"LOG: {message}")
    
    def clear_results(self):
        """Clear the results text area"""
        self.results_text.config(state='normal')
        self.results_text.delete('1.0', 'end')
        self.results_text.config(state='disabled')
        
        # Re-add welcome message
        self.add_log("🧹 Results cleared")
        self.add_log("Ready for new detection")
        self.add_log("=" * 50)
    
    def start_detection(self):
        """Start camera detection in a separate thread"""
        if self.is_detecting:
            return
        
        self.is_detecting = True
        self.detect_btn.config(state='disabled', text="🔄 Detecting...")
        self.status_label.config(text="Scanning for cameras...")
        
        # Run detection in background thread to avoid blocking GUI
        detection_thread = threading.Thread(target=self.detect_cameras_thread)
        detection_thread.daemon = True
        detection_thread.start()
    
    def detect_cameras_thread(self):
        """Camera detection in background thread"""
        try:
            self.root.after(0, lambda: self.add_log("🔍 Starting comprehensive camera detection..."))
            self.root.after(0, lambda: self.add_log("=" * 50))
            
            # Capture the output by redirecting CameraManager's print statements
            import io
            import sys
            from contextlib import redirect_stdout
            
            # Create string buffer to capture output
            output_buffer = io.StringIO()
            
            # Capture CameraManager output
            with redirect_stdout(output_buffer):
                cameras = CameraManager.detect_cameras()
            
            # Get the captured output
            detection_output = output_buffer.getvalue()
            
            # Process the output line by line
            for line in detection_output.split('\n'):
                if line.strip():
                    self.root.after(0, lambda msg=line: self.add_log(msg))
            
            # Add summary
            self.root.after(0, lambda: self.add_log("=" * 50))
            self.root.after(0, lambda: self.add_log(f"📊 Detection Summary:"))
            self.root.after(0, lambda: self.add_log(f"Total cameras found: {len(cameras)}"))
            
            if len(cameras) >= 2:
                self.root.after(0, lambda: self.add_log("✅ Sufficient cameras for dual recording!"))
            elif len(cameras) == 1:
                self.root.after(0, lambda: self.add_log("⚠️ Only 1 camera detected - need 2 for dual recording"))
            else:
                self.root.after(0, lambda: self.add_log("❌ No cameras detected - check connections"))
            
            # Update status
            status_text = f"Detection complete - {len(cameras)} cameras found"
            self.root.after(0, lambda: self.status_label.config(text=status_text))
            
        except Exception as e:
            error_msg = f"❌ Detection failed: {str(e)}"
            self.root.after(0, lambda: self.add_log(error_msg))
            self.root.after(0, lambda: self.status_label.config(text="Detection failed"))
        
        finally:
            # Re-enable button
            self.root.after(0, lambda: self.detect_btn.config(state='normal', text="🔍 Start Detection"))
            self.is_detecting = False
    
    def run(self):
        """Start the application"""
        self.root.mainloop()

def main():
    """Main function - now with modern GUI"""
    try:
        app = ModernCameraDetectionGUI()
        app.run()
    except KeyboardInterrupt:
        print("\nApplication interrupted by user")
    except Exception as e:
        print(f"Application error: {str(e)}")
        return 1
    return 0

# Legacy function for backward compatibility
def test_camera_detection():
    """Legacy function - now launches modern GUI"""
    print("Launching modern Camera Detection Studio...")
    main()

if __name__ == "__main__":
    exit(main())