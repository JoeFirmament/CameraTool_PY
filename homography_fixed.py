#!/usr/bin/env python3
"""
修复版本的Homography标定工具
解决X11字体转发问题的完整解决方案
"""

import os
import sys

# 设置环境变量以避免字体问题
os.environ['TK_SILENCE_DEPRECATION'] = '1'
if 'DISPLAY' in os.environ:
    # 强制使用本地字体而不是X11转发的字体
    os.environ['FONTCONFIG_FILE'] = '/dev/null'

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
        print("初始化Homography标定工具...")
        
        # 创建主窗口时使用最安全的配置
        self.root = tk.Tk()
        
        # 设置窗口属性
        self.root.title("Homography Calibrator")
        self.root.geometry("1200x800")
        
        # 禁用一些可能导致问题的特性
        try:
            self.root.option_add('*tearOff', False)
            # 不设置字体选项，让系统自动选择
        except:
            pass
        
        print("主窗口创建成功")
        
        # 初始化数据
        self.init_data()
        
        # 创建界面
        self.create_interface()
        
        # 绑定事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        print("程序初始化完成")
    
    def init_data(self):
        """初始化数据成员"""
        # 摄像头相关
        self.cap = None
        self.is_previewing = False
        self.preview_thread = None
        self.current_frame = None
        
        # 标定相关
        self.calibration_points = []
        self.homography_matrix = None
        self.is_calibration_mode = False
        self.is_verification_mode = False
        
        # 显示相关
        self.canvas_scale = 1.0
        self.canvas_offset_x = 0
        self.canvas_offset_y = 0
        self.selected_point_id = None
    
    def create_interface(self):
        """创建用户界面"""
        print("创建用户界面...")
        
        # 主容器
        main_container = tk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 左侧：预览区域
        self.create_preview_area(main_container)
        
        # 右侧：控制区域
        self.create_control_area(main_container)
        
        print("界面创建完成")
    
    def create_preview_area(self, parent):
        """创建预览区域"""
        preview_frame = tk.Frame(parent, bg='lightgray')
        preview_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 画布
        self.canvas = tk.Canvas(preview_frame, bg='gray', width=800, height=600)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.canvas.bind('<Button-1>', self.on_canvas_click)
        
        # 状态标签
        self.canvas_status = tk.Label(preview_frame, text="点击'开始预览'启动摄像头", 
                                     bg='lightgray')
        self.canvas_status.pack(pady=2)
    
    def create_control_area(self, parent):
        """创建控制区域"""
        control_frame = tk.Frame(parent, width=350, bg='white')
        control_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        control_frame.pack_propagate(False)
        
        # 标题 - 不指定字体
        title_label = tk.Label(control_frame, text="Homography标定工具", bg='white')
        title_label.pack(pady=10)
        
        # 各个控制区域
        self.create_camera_section(control_frame)
        self.create_calibration_section(control_frame)
        self.create_points_section(control_frame)
        self.create_calculation_section(control_frame)
        self.create_status_section(control_frame)
    
    def create_camera_section(self, parent):
        """创建摄像头控制区域"""
        section = tk.LabelFrame(parent, text="摄像头控制", bg='white')
        section.pack(fill=tk.X, padx=10, pady=5)
        
        # 设备路径
        tk.Label(section, text="设备:", bg='white').pack(anchor=tk.W, padx=5)
        self.device_var = tk.StringVar(value="/dev/video0")
        device_entry = tk.Entry(section, textvariable=self.device_var)
        device_entry.pack(fill=tk.X, padx=5, pady=2)
        
        # 检测分辨率按钮
        detect_btn = tk.Button(section, text="检测分辨率", 
                              command=self.detect_resolutions)
        detect_btn.pack(fill=tk.X, padx=5, pady=2)
        
        # 分辨率选择
        tk.Label(section, text="分辨率:", bg='white').pack(anchor=tk.W, padx=5)
        self.resolution_var = tk.StringVar()
        self.resolution_combo = ttk.Combobox(section, textvariable=self.resolution_var,
                                           state='readonly')
        self.resolution_combo.pack(fill=tk.X, padx=5, pady=2)
        
        # 预览控制
        self.preview_btn = tk.Button(section, text="开始预览", 
                                   command=self.toggle_preview,
                                   state=tk.DISABLED)
        self.preview_btn.pack(fill=tk.X, padx=5, pady=5)
    
    def create_calibration_section(self, parent):
        """创建标定控制区域"""
        section = tk.LabelFrame(parent, text="标定控制", bg='white')
        section.pack(fill=tk.X, padx=10, pady=5)
        
        # 标定模式
        self.calib_mode_var = tk.BooleanVar()
        calib_check = tk.Checkbutton(section, text="标定模式 (点击添加点)",
                                   variable=self.calib_mode_var,
                                   command=self.toggle_calibration_mode,
                                   bg='white')
        calib_check.pack(anchor=tk.W, padx=5, pady=2)
        
        # 验证模式
        self.verify_mode_var = tk.BooleanVar()
        self.verify_check = tk.Checkbutton(section, text="验证模式 (点击查看坐标)",
                                         variable=self.verify_mode_var,
                                         command=self.toggle_verification_mode,
                                         bg='white', state=tk.DISABLED)
        self.verify_check.pack(anchor=tk.W, padx=5, pady=2)
        
        # 显示Y轴5-10米验证点（两侧分布）
        self.grid_var = tk.BooleanVar()
        self.grid_check = tk.Checkbutton(section, text="显示Y轴5-10米验证点(两侧)",
                                       variable=self.grid_var,
                                       command=self.toggle_grid,
                                       bg='white', state=tk.DISABLED)
        self.grid_check.pack(anchor=tk.W, padx=5, pady=2)
    
    def create_points_section(self, parent):
        """创建点管理区域"""
        section = tk.LabelFrame(parent, text="标定点管理", bg='white')
        section.pack(fill=tk.X, padx=10, pady=5)
        
        # 点列表
        list_frame = tk.Frame(section, bg='white')
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        self.points_listbox = tk.Listbox(list_frame, height=6, width=30)
        self.points_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        self.points_listbox.bind('<<ListboxSelect>>', self.on_point_select)
        
        scrollbar = tk.Scrollbar(list_frame, orient=tk.VERTICAL)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.points_listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.points_listbox.yview)
        
        # 操作按钮
        btn_frame = tk.Frame(section, bg='white')
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.edit_btn = tk.Button(btn_frame, text="编辑", 
                                command=self.edit_point, state=tk.DISABLED)
        self.edit_btn.pack(side=tk.LEFT, padx=2)
        
        self.delete_btn = tk.Button(btn_frame, text="删除", 
                                  command=self.delete_point, state=tk.DISABLED)
        self.delete_btn.pack(side=tk.LEFT, padx=2)
        
        clear_btn = tk.Button(btn_frame, text="清空", command=self.clear_points)
        clear_btn.pack(side=tk.RIGHT, padx=2)
    
    def create_calculation_section(self, parent):
        """创建计算区域"""
        section = tk.LabelFrame(parent, text="矩阵计算", bg='white')
        section.pack(fill=tk.X, padx=10, pady=5)
        
        # 计算按钮
        self.calc_btn = tk.Button(section, text="计算Homography矩阵",
                                command=self.calculate_homography,
                                state=tk.DISABLED)
        self.calc_btn.pack(fill=tk.X, padx=5, pady=5)
        
        # 保存加载按钮
        file_frame = tk.Frame(section, bg='white')
        file_frame.pack(fill=tk.X, padx=5, pady=2)
        
        self.save_btn = tk.Button(file_frame, text="保存",
                                command=self.save_calibration,
                                state=tk.DISABLED)
        self.save_btn.pack(side=tk.LEFT, padx=2)
        
        load_btn = tk.Button(file_frame, text="加载",
                           command=self.load_calibration)
        load_btn.pack(side=tk.RIGHT, padx=2)
    
    def create_status_section(self, parent):
        """创建状态显示区域"""
        section = tk.LabelFrame(parent, text="状态信息", bg='white')
        section.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.status_text = tk.Text(section, height=8, wrap=tk.WORD, 
                                 state=tk.DISABLED, bg='white')
        self.status_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.log_message("程序已启动，请先检测摄像头分辨率")
    
    def log_message(self, message):
        """添加日志消息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        full_message = f"[{timestamp}] {message}\n"
        
        self.status_text.config(state=tk.NORMAL)
        self.status_text.insert(tk.END, full_message)
        self.status_text.see(tk.END)
        self.status_text.config(state=tk.DISABLED)
        
        print(f"LOG: {message}")
    
    def detect_resolutions(self):
        """检测摄像头分辨率"""
        device = self.device_var.get()
        if not device:
            messagebox.showerror("错误", "请输入设备路径")
            return
        
        try:
            self.log_message(f"检测设备 {device} 的分辨率...")
            
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
                
                # 设置默认分辨率
                if "1920x1080" in res_list:
                    self.resolution_var.set("1920x1080")
                elif "1280x720" in res_list:
                    self.resolution_var.set("1280x720")
                else:
                    self.resolution_var.set(res_list[0])
                
                self.preview_btn.config(state=tk.NORMAL)
                self.log_message(f"检测到 {len(res_list)} 种分辨率: {', '.join(res_list)}")
            else:
                messagebox.showerror("错误", "未检测到支持的分辨率")
                self.log_message("未检测到支持的分辨率")
                
        except subprocess.TimeoutExpired:
            messagebox.showerror("错误", "检测超时")
            self.log_message("分辨率检测超时")
        except subprocess.CalledProcessError as e:
            messagebox.showerror("错误", f"无法访问设备: {e}")
            self.log_message(f"设备访问失败: {e}")
        except Exception as e:
            messagebox.showerror("错误", f"检测失败: {e}")
            self.log_message(f"检测失败: {e}")
    
    def toggle_preview(self):
        """切换预览状态"""
        if self.is_previewing:
            self.stop_preview()
        else:
            self.start_preview()
    
    def start_preview(self):
        """开始预览"""
        device = self.device_var.get()
        resolution = self.resolution_var.get()
        
        if not device or not resolution:
            messagebox.showwarning("警告", "请设置设备和分辨率")
            return
        
        try:
            width, height = map(int, resolution.split('x'))
            
            self.cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
            if not self.cap.isOpened():
                raise Exception("无法打开摄像头")
            
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            
            self.is_previewing = True
            self.preview_btn.config(text="停止预览")
            
            # 启动预览线程
            self.preview_thread = threading.Thread(target=self.preview_loop, daemon=True)
            self.preview_thread.start()
            
            self.log_message(f"预览已启动: {resolution}")
            self.canvas_status.config(text=f"预览中: {resolution}")
            
        except Exception as e:
            messagebox.showerror("错误", f"启动预览失败: {e}")
            self.log_message(f"预览启动失败: {e}")
            self.stop_preview()
    
    def stop_preview(self):
        """停止预览"""
        self.is_previewing = False
        
        if self.cap:
            self.cap.release()
            self.cap = None
        
        self.current_frame = None
        self.preview_btn.config(text="开始预览")
        self.canvas.delete("all")
        
        self.log_message("预览已停止")
        self.canvas_status.config(text="预览已停止")
    
    def preview_loop(self):
        """预览循环"""
        while self.is_previewing and self.cap:
            ret, frame = self.cap.read()
            if ret:
                self.current_frame = frame.copy()
                self.root.after(0, self.update_display)
            time.sleep(0.03)
    
    def update_display(self):
        """更新画布显示"""
        if self.current_frame is None:
            return
        
        try:
            # 在帧上绘制覆盖层
            display_frame = self.current_frame.copy()
            self.draw_overlay(display_frame)
            
            # 计算缩放参数
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
            
            # 转换并显示
            img_rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
            img_pil = Image.fromarray(img_rgb)
            img_pil = img_pil.resize((new_w, new_h), Image.Resampling.LANCZOS)
            
            self.photo = ImageTk.PhotoImage(img_pil)
            
            self.canvas.delete("image")
            self.canvas.create_image(self.canvas_offset_x, self.canvas_offset_y,
                                   anchor=tk.NW, image=self.photo, tags="image")
            
        except Exception as e:
            print(f"显示更新失败: {e}")
    
    def draw_overlay(self, frame):
        """绘制覆盖层"""
        # 绘制标定点
        for i, point in enumerate(self.calibration_points):
            px, py = map(int, point['pixel'])
            
            # 点的颜色
            color = (0, 255, 0) if point.get('world') else (0, 0, 255)
            
            # 绘制点
            cv2.circle(frame, (px, py), 8, color, -1)
            cv2.circle(frame, (px, py), 10, (255, 255, 255), 2)
            
            # 绘制编号
            cv2.putText(frame, str(i+1), (px-10, py-15),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
            # 显示世界坐标
            if point.get('world'):
                wx, wy = point['world']
                text = f"({wx:.1f},{wy:.1f})"
                cv2.putText(frame, text, (px+15, py+5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # 绘制Y轴5-10米验证点
        if self.homography_matrix is not None and self.grid_var.get():
            self.draw_random_points(frame)
    
    def draw_random_points(self, frame):
        """绘制Y轴5-10米距离范围内的验证点（两侧分布）"""
        try:
            print("开始绘制指定验证点...")
            H_inv = np.linalg.inv(self.homography_matrix)
            img_h, img_w = frame.shape[:2]
            
            # 定义Y轴5-10米距离范围内的5个验证点，分布在Y轴两侧 (单位:毫米)
            y_distances = [5000, 6250, 7500, 8750, 10000]  # 5个等间距的Y轴距离
            verification_points = []
            
            for y_dist in y_distances:
                # 每个Y距离在左右两侧各放一个点
                verification_points.append((-500, y_dist))  # 左侧0.5米
                verification_points.append((500, y_dist))   # 右侧0.5米
            
            points_drawn = 0
            
            for i, (world_x, world_y) in enumerate(verification_points):
                
                # 将世界坐标转换为像素坐标
                world_pt = np.array([[world_x], [world_y], [1.0]], dtype=np.float32)
                pixel_pt = np.dot(H_inv, world_pt)
                
                if abs(pixel_pt[2, 0]) > 1e-8:
                    px = pixel_pt[0, 0] / pixel_pt[2, 0]
                    py = pixel_pt[1, 0] / pixel_pt[2, 0]
                    
                    # 检查点是否在图像范围内
                    if 0 <= px <= img_w and 0 <= py <= img_h:
                        px_int = int(px)
                        py_int = int(py)
                        
                        # 所有验证点都使用小点，根据左右位置选择颜色
                        if world_x < 0:  # 左侧点用蓝色
                            point_color = (255, 0, 0)      # 蓝色
                        else:  # 右侧点用绿色
                            point_color = (0, 255, 0)      # 绿色
                        
                        point_radius = 4                    # 统一小点
                        border_color = (255, 255, 255)     # 白色边框
                        border_radius = 6
                        
                        # 绘制点
                        cv2.circle(frame, (px_int, py_int), point_radius, point_color, -1)  # 填充圆
                        cv2.circle(frame, (px_int, py_int), border_radius, border_color, 2)  # 边框
                        
                        # 显示世界坐标 (转换为米)
                        world_x_m = world_x / 1000.0
                        world_y_m = world_y / 1000.0
                        coord_text = f"({world_x_m:.2f}m, {world_y_m:.2f}m)"
                        
                        # 计算文本位置，避免超出画面边界
                        text_x = px_int + 15
                        text_y = py_int - 10
                        
                        # 检查文本是否会超出右边界
                        text_size = cv2.getTextSize(coord_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
                        if text_x + text_size[0] > img_w:
                            text_x = px_int - text_size[0] - 15
                        
                        # 检查文本是否会超出上边界
                        if text_y < 20:
                            text_y = py_int + 25
                        
                        # 绘制文本背景（黑色半透明）
                        text_bg_x1 = max(0, text_x - 5)
                        text_bg_y1 = max(0, text_y - 15)
                        text_bg_x2 = min(img_w, text_x + text_size[0] + 5)
                        text_bg_y2 = min(img_h, text_y + 5)
                        
                        overlay = frame.copy()
                        cv2.rectangle(overlay, (text_bg_x1, text_bg_y1), (text_bg_x2, text_bg_y2), (0, 0, 0), -1)
                        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
                        
                        # 绘制坐标文本
                        cv2.putText(frame, coord_text, (text_x, text_y),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                        
                        # 绘制点编号
                        point_num = str(i + 1)
                        cv2.putText(frame, point_num, (px_int - 5, py_int + 5),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 2)  # 黑色背景
                        cv2.putText(frame, point_num, (px_int - 5, py_int + 5),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)  # 白色前景
                        
                        points_drawn += 1
                        side = "左" if world_x < 0 else "右"
                        print(f"验证点 #{i+1}: 世界坐标({world_x_m:.1f}m, {world_y_m:.1f}m) [{side}侧] -> 像素坐标({px_int}, {py_int})")
            
            print(f"Y轴5-10米验证点绘制完成，共绘制 {points_drawn} 个点 (总共 {len(verification_points)} 个点)")
            if points_drawn == 0:
                print("警告: 没有在视野范围内找到5-10米距离的验证点，请检查标定结果或调整摄像头位置")
            elif points_drawn < len(verification_points):
                print(f"提示: 有 {len(verification_points) - points_drawn} 个验证点在视野范围外")
                
        except Exception as e:
            print(f"验证点绘制失败: {e}")
            import traceback
            traceback.print_exc()
    
    def on_canvas_click(self, event):
        """处理画布点击"""
        if not self.is_previewing or self.current_frame is None:
            return
        
        # 转换坐标
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
        """添加标定点"""
        # 检查是否点击了现有点
        for i, point in enumerate(self.calibration_points):
            px, py = point['pixel']
            if abs(px - pixel_x) < 20 and abs(py - pixel_y) < 20:
                self.edit_existing_point(i)
                return
        
        # 输入世界坐标
        try:
            x_str = simpledialog.askstring("输入坐标", "请输入X坐标 (毫米):")
            if x_str is None:
                return
            
            y_str = simpledialog.askstring("输入坐标", "请输入Y坐标 (毫米):")
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
            
            self.log_message(f"添加点 #{len(self.calibration_points)}: "
                           f"像素({pixel_x:.1f},{pixel_y:.1f}) -> 世界({world_x},{world_y})")
            
        except (ValueError, TypeError):
            messagebox.showerror("错误", "请输入有效数字")
    
    def verify_point(self, pixel_x, pixel_y):
        """验证点坐标"""
        if self.homography_matrix is None:
            messagebox.showwarning("警告", "请先计算Homography矩阵")
            return
        
        try:
            pixel_pt = np.array([[pixel_x], [pixel_y], [1.0]], dtype=np.float32)
            world_pt = np.dot(self.homography_matrix, pixel_pt)
            
            if abs(world_pt[2, 0]) > 1e-8:
                world_x = world_pt[0, 0] / world_pt[2, 0]
                world_y = world_pt[1, 0] / world_pt[2, 0]
                
                messagebox.showinfo("验证结果",
                                  f"像素坐标: ({pixel_x:.1f}, {pixel_y:.1f})\n"
                                  f"世界坐标: ({world_x:.2f}, {world_y:.2f}) mm")
                
                self.log_message(f"验证: 像素({pixel_x:.1f},{pixel_y:.1f}) -> "
                               f"世界({world_x:.2f},{world_y:.2f})")
            else:
                messagebox.showerror("错误", "坐标变换失败")
                
        except Exception as e:
            messagebox.showerror("错误", f"验证失败: {e}")
    
    def toggle_calibration_mode(self):
        """切换标定模式"""
        self.is_calibration_mode = self.calib_mode_var.get()
        if self.is_calibration_mode and self.is_verification_mode:
            self.verify_mode_var.set(False)
            self.is_verification_mode = False
        
        status = "启用" if self.is_calibration_mode else "关闭"
        self.log_message(f"标定模式已{status}")
    
    def toggle_verification_mode(self):
        """切换验证模式"""
        self.is_verification_mode = self.verify_mode_var.get()
        if self.is_verification_mode and self.is_calibration_mode:
            self.calib_mode_var.set(False)
            self.is_calibration_mode = False
        
        status = "启用" if self.is_verification_mode else "关闭"
        self.log_message(f"验证模式已{status}")
    
    def toggle_grid(self):
        """切换Y轴5-10米验证点显示（两侧分布）"""
        status = "启用" if self.grid_var.get() else "关闭"
        self.log_message(f"Y轴5-10米验证点(两侧)显示已{status}")
    
    def update_points_list(self):
        """更新点列表"""
        self.points_listbox.delete(0, tk.END)
        
        for i, point in enumerate(self.calibration_points):
            px, py = point['pixel']
            if point.get('world'):
                wx, wy = point['world']
                text = f"点{i+1}: ({px:.1f},{py:.1f}) -> ({wx},{wy})"
            else:
                text = f"点{i+1}: ({px:.1f},{py:.1f}) -> 未设置"
            
            self.points_listbox.insert(tk.END, text)
    
    def on_point_select(self, event):
        """处理点选择"""
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
        """编辑选中点"""
        if self.selected_point_id is not None:
            self.edit_existing_point(self.selected_point_id)
    
    def edit_existing_point(self, point_index):
        """编辑已存在的点"""
        if point_index >= len(self.calibration_points):
            return
        
        point = self.calibration_points[point_index]
        current_world = point.get('world', (0, 0))
        
        try:
            x_str = simpledialog.askstring("编辑坐标", 
                                         f"X坐标 (当前: {current_world[0]}):")
            if x_str is None:
                return
            
            y_str = simpledialog.askstring("编辑坐标",
                                         f"Y坐标 (当前: {current_world[1]}):")
            if y_str is None:
                return
            
            world_x = float(x_str)
            world_y = float(y_str)
            
            self.calibration_points[point_index]['world'] = (world_x, world_y)
            self.update_points_list()
            self.update_button_states()
            
            px, py = point['pixel']
            self.log_message(f"更新点 #{point_index+1}: "
                           f"像素({px:.1f},{py:.1f}) -> 世界({world_x},{world_y})")
            
        except (ValueError, TypeError):
            messagebox.showerror("错误", "请输入有效数字")
    
    def delete_point(self):
        """删除选中点"""
        if self.selected_point_id is not None:
            if messagebox.askyesno("确认", "确定删除此点?"):
                self.calibration_points.pop(self.selected_point_id)
                self.update_points_list()
                self.update_button_states()
                self.homography_matrix = None
                
                self.log_message(f"删除点 #{self.selected_point_id+1}")
                self.selected_point_id = None
                self.edit_btn.config(state=tk.DISABLED)
                self.delete_btn.config(state=tk.DISABLED)
    
    def clear_points(self):
        """清空所有点"""
        if self.calibration_points:
            if messagebox.askyesno("确认", "确定清空所有点?"):
                self.calibration_points.clear()
                self.update_points_list()
                self.update_button_states()
                self.homography_matrix = None
                self.log_message("已清空所有标定点")
    
    def update_button_states(self):
        """更新按钮状态"""
        valid_points = sum(1 for p in self.calibration_points if p.get('world'))
        
        # 计算按钮
        if valid_points >= 4:
            self.calc_btn.config(state=tk.NORMAL)
        else:
            self.calc_btn.config(state=tk.DISABLED)
        
        # 其他按钮
        if self.homography_matrix is not None:
            self.save_btn.config(state=tk.NORMAL)
            self.verify_check.config(state=tk.NORMAL)
            self.grid_check.config(state=tk.NORMAL)
        else:
            self.save_btn.config(state=tk.DISABLED)
            self.verify_check.config(state=tk.DISABLED)
            self.grid_check.config(state=tk.DISABLED)
    
    def calculate_homography(self):
        """计算Homography矩阵"""
        src_points = []
        dst_points = []
        
        for point in self.calibration_points:
            if point.get('world'):
                src_points.append(point['pixel'])
                dst_points.append(point['world'])
        
        if len(src_points) < 4:
            messagebox.showwarning("警告", "至少需要4个有效点")
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
                self.log_message(f"Homography矩阵计算成功:\n{matrix_str}")
                
                messagebox.showinfo("成功", "矩阵计算完成!\n可以启用验证模式测试")
            else:
                messagebox.showerror("错误", "矩阵计算失败")
                
        except Exception as e:
            messagebox.showerror("错误", f"计算失败: {e}")
    
    def save_calibration(self):
        """保存标定数据"""
        if not self.calibration_points or self.homography_matrix is None:
            messagebox.showwarning("警告", "没有数据可保存")
            return
        
        try:
            from tkinter import filedialog
            
            filename = filedialog.asksaveasfilename(
                title="保存标定",
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
                
                messagebox.showinfo("成功", f"数据已保存:\n{filename}")
                self.log_message(f"标定数据已保存: {filename}")
                
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {e}")
    
    def load_calibration(self):
        """加载标定数据"""
        try:
            from tkinter import filedialog
            
            filename = filedialog.askopenfilename(
                title="加载标定",
                filetypes=[("JSON files", "*.json")]
            )
            
            if filename:
                with open(filename, 'r') as f:
                    data = json.load(f)
                
                self.calibration_points = data['points']
                self.homography_matrix = np.array(data['matrix'])
                
                self.update_points_list()
                self.update_button_states()
                
                messagebox.showinfo("成功", f"数据已加载:\n{filename}")
                self.log_message(f"标定数据已加载: {filename}")
                
        except Exception as e:
            messagebox.showerror("错误", f"加载失败: {e}")
    
    def on_closing(self):
        """关闭程序"""
        self.stop_preview()
        self.root.destroy()
    
    def run(self):
        """运行程序"""
        print("启动主循环...")
        self.root.mainloop()


def main():
    """主函数"""
    print("启动Homography标定工具...")
    
    try:
        app = HomographyCalibrator()
        app.run()
    except Exception as e:
        print(f"程序启动失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main()) 