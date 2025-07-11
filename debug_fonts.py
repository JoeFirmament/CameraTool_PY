#!/usr/bin/env python3
"""
tkinter字体问题调试脚本
逐步测试各种tkinter组件，找出导致X11字体错误的具体原因
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sys
import traceback

def test_step(step_name, test_func):
    """执行测试步骤"""
    print(f"\n测试步骤: {step_name}")
    try:
        test_func()
        print(f"✓ {step_name} - 成功")
        return True
    except Exception as e:
        print(f"✗ {step_name} - 失败: {e}")
        traceback.print_exc()
        return False

def test_basic_window():
    """测试基本窗口"""
    root = tk.Tk()
    root.title("Basic Test")
    root.geometry("300x200")
    root.withdraw()  # 隐藏窗口
    root.destroy()

def test_basic_widgets():
    """测试基本控件"""
    root = tk.Tk()
    root.withdraw()
    
    # 基本控件
    label = tk.Label(root, text="Test Label")
    button = tk.Button(root, text="Test Button")
    entry = tk.Entry(root)
    
    label.destroy()
    button.destroy()
    entry.destroy()
    root.destroy()

def test_ttk_widgets():
    """测试ttk控件"""
    root = tk.Tk()
    root.withdraw()
    
    # ttk控件
    ttk_label = ttk.Label(root, text="TTK Label")
    ttk_button = ttk.Button(root, text="TTK Button")
    ttk_entry = ttk.Entry(root)
    
    ttk_label.destroy()
    ttk_button.destroy()
    ttk_entry.destroy()
    root.destroy()

def test_complex_layout():
    """测试复杂布局"""
    root = tk.Tk()
    root.withdraw()
    
    # 创建框架和布局
    main_frame = tk.Frame(root)
    main_frame.pack(fill=tk.BOTH, expand=True)
    
    left_frame = tk.Frame(main_frame)
    left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    
    right_frame = tk.Frame(main_frame)
    right_frame.pack(side=tk.RIGHT, fill=tk.Y)
    
    # 添加一些控件
    canvas = tk.Canvas(left_frame, bg="gray", width=400, height=300)
    canvas.pack()
    
    label_frame = tk.LabelFrame(right_frame, text="Controls")
    label_frame.pack(fill=tk.X)
    
    canvas.destroy()
    label_frame.destroy()
    left_frame.destroy()
    right_frame.destroy()
    main_frame.destroy()
    root.destroy()

def test_canvas_operations():
    """测试画布操作"""
    root = tk.Tk()
    root.withdraw()
    
    canvas = tk.Canvas(root, bg="white", width=300, height=200)
    
    # 绘制基本图形
    canvas.create_rectangle(10, 10, 50, 50, fill="red")
    canvas.create_oval(60, 10, 100, 50, fill="blue")
    canvas.create_line(10, 60, 100, 60, fill="green", width=2)
    canvas.create_text(150, 30, text="Test Text", anchor=tk.NW)
    
    canvas.destroy()
    root.destroy()

def test_text_widget():
    """测试文本控件"""
    root = tk.Tk()
    root.withdraw()
    
    text_widget = tk.Text(root, height=5, width=30)
    text_widget.insert(tk.END, "Test text content\n")
    text_widget.insert(tk.END, "Multiple lines\n")
    
    text_widget.destroy()
    root.destroy()

def test_listbox_widget():
    """测试列表框控件"""
    root = tk.Tk()
    root.withdraw()
    
    listbox = tk.Listbox(root, height=5)
    listbox.insert(tk.END, "Item 1")
    listbox.insert(tk.END, "Item 2") 
    listbox.insert(tk.END, "Item 3")
    
    listbox.destroy()
    root.destroy()

def test_with_actual_display():
    """测试实际显示的窗口"""
    root = tk.Tk()
    root.title("Display Test")
    root.geometry("400x300")
    
    # 创建一些控件
    label = tk.Label(root, text="Visible Window Test")
    label.pack(pady=10)
    
    button = tk.Button(root, text="Test Button", 
                      command=lambda: print("Button clicked"))
    button.pack(pady=5)
    
    # 显示很短时间然后关闭
    root.after(1000, root.destroy)  # 1秒后自动关闭
    root.mainloop()

def test_problematic_patterns():
    """测试可能有问题的模式"""
    print("\n=== 测试可能有问题的模式 ===")
    
    # 测试1: 大量控件创建
    test_step("大量控件创建", lambda: test_many_widgets())
    
    # 测试2: 快速创建销毁
    test_step("快速创建销毁", lambda: test_rapid_create_destroy())
    
    # 测试3: 嵌套框架
    test_step("深度嵌套框架", lambda: test_nested_frames())

def test_many_widgets():
    """测试创建大量控件"""
    root = tk.Tk()
    root.withdraw()
    
    widgets = []
    for i in range(50):  # 创建50个控件
        label = tk.Label(root, text=f"Label {i}")
        button = tk.Button(root, text=f"Button {i}")
        widgets.extend([label, button])
    
    # 清理
    for widget in widgets:
        widget.destroy()
    root.destroy()

def test_rapid_create_destroy():
    """测试快速创建和销毁"""
    for i in range(10):
        root = tk.Tk()
        root.withdraw()
        
        frame = tk.Frame(root)
        label = tk.Label(frame, text=f"Test {i}")
        button = tk.Button(frame, text=f"Button {i}")
        
        frame.destroy()
        root.destroy()

def test_nested_frames():
    """测试深度嵌套的框架"""
    root = tk.Tk()
    root.withdraw()
    
    current_parent = root
    frames = []
    
    # 创建5层嵌套
    for i in range(5):
        frame = tk.Frame(current_parent)
        frames.append(frame)
        
        label = tk.Label(frame, text=f"Level {i}")
        label.pack()
        
        current_parent = frame
    
    # 清理
    for frame in reversed(frames):
        frame.destroy()
    root.destroy()

def main():
    """主测试函数"""
    print("开始tkinter字体问题调试")
    print("=" * 50)
    
    tests = [
        ("基本窗口创建", test_basic_window),
        ("基本控件", test_basic_widgets),
        ("TTK控件", test_ttk_widgets),
        ("复杂布局", test_complex_layout),
        ("画布操作", test_canvas_operations),
        ("文本控件", test_text_widget),
        ("列表框控件", test_listbox_widget),
    ]
    
    success_count = 0
    for test_name, test_func in tests:
        if test_step(test_name, test_func):
            success_count += 1
    
    print(f"\n基础测试结果: {success_count}/{len(tests)} 成功")
    
    # 测试可能有问题的模式
    test_problematic_patterns()
    
    print("\n最后测试实际显示窗口...")
    try:
        test_with_actual_display()
        print("✓ 实际显示测试成功")
    except Exception as e:
        print(f"✗ 实际显示测试失败: {e}")
        traceback.print_exc()
    
    print("\n调试完成")

if __name__ == "__main__":
    main() 