#!/usr/bin/env python3
"""
X11字体问题诊断和修复脚本
用于解决tkinter应用的字体渲染错误
"""

import os
import sys
import subprocess
import tkinter as tk
from tkinter import messagebox

def check_x11_environment():
    """检查X11环境配置"""
    print("=== X11环境检查 ===")
    
    # 检查DISPLAY变量
    display = os.environ.get('DISPLAY')
    print(f"DISPLAY: {display}")
    
    # 检查X11是否运行
    try:
        result = subprocess.run(['xdpyinfo'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("✓ X11服务器正在运行")
        else:
            print("✗ X11服务器无法访问")
            print(f"错误: {result.stderr}")
    except Exception as e:
        print(f"✗ 无法检查X11状态: {e}")

def check_fonts():
    """检查系统字体"""
    print("\n=== 字体检查 ===")
    
    # 检查fc-list是否可用
    try:
        result = subprocess.run(['fc-list'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            font_count = len(result.stdout.strip().split('\n'))
            print(f"✓ 系统字体数量: {font_count}")
            
            # 检查常用字体
            common_fonts = ['DejaVu', 'Liberation', 'Noto', 'Ubuntu']
            for font_name in common_fonts:
                font_result = subprocess.run(['fc-list', ':', 'family'], 
                                           capture_output=True, text=True)
                if font_name.lower() in font_result.stdout.lower():
                    print(f"✓ 找到字体: {font_name}")
                else:
                    print(f"? 未找到字体: {font_name}")
        else:
            print("✗ fc-list命令失败")
    except Exception as e:
        print(f"✗ 字体检查失败: {e}")

def test_tkinter_minimal():
    """测试最简tkinter应用"""
    print("\n=== 测试最简tkinter应用 ===")
    try:
        root = tk.Tk()
        root.withdraw()  # 隐藏主窗口
        
        # 测试基本控件创建
        label = tk.Label(root, text="测试")
        label.destroy()
        
        root.destroy()
        print("✓ 基本tkinter测试通过")
        return True
    except Exception as e:
        print(f"✗ 基本tkinter测试失败: {e}")
        return False

def test_tkinter_with_fonts():
    """测试带字体的tkinter应用"""
    print("\n=== 测试带字体的tkinter应用 ===")
    try:
        root = tk.Tk()
        root.withdraw()
        
        # 测试不同字体
        fonts_to_test = [
            None,  # 系统默认
            ("TkDefaultFont", 10),
            ("DejaVu Sans", 10),
            ("Liberation Sans", 10),
            ("Ubuntu", 10),
        ]
        
        successful_fonts = []
        for font in fonts_to_test:
            try:
                label = tk.Label(root, text="测试字体", font=font)
                label.destroy()
                successful_fonts.append(font if font else "系统默认")
                print(f"✓ 字体测试通过: {font if font else '系统默认'}")
            except Exception as e:
                print(f"✗ 字体测试失败: {font} - {e}")
        
        root.destroy()
        return successful_fonts
    except Exception as e:
        print(f"✗ 字体测试整体失败: {e}")
        return []

def fix_font_cache():
    """修复字体缓存"""
    print("\n=== 修复字体缓存 ===")
    try:
        # 清理字体缓存
        subprocess.run(['fc-cache', '-fv'], check=True, timeout=30)
        print("✓ 字体缓存已更新")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ 字体缓存更新失败: {e}")
        return False
    except Exception as e:
        print(f"✗ 字体缓存修复过程出错: {e}")
        return False

def install_missing_fonts():
    """安装缺失的字体包"""
    print("\n=== 安装字体包 ===")
    
    font_packages = [
        'fonts-dejavu-core',
        'fonts-liberation',
        'fonts-noto-core',
        'fontconfig'
    ]
    
    for package in font_packages:
        try:
            print(f"检查包: {package}")
            result = subprocess.run(['dpkg', '-l', package], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print(f"✓ {package} 已安装")
            else:
                print(f"! {package} 未安装，建议手动安装:")
                print(f"  sudo apt install {package}")
        except Exception as e:
            print(f"? 无法检查包 {package}: {e}")

def create_safe_font_config():
    """创建安全的字体配置文件"""
    print("\n=== 创建安全字体配置 ===")
    
    config_content = '''<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
  <!-- 默认字体映射 -->
  <alias>
    <family>sans-serif</family>
    <prefer>
      <family>DejaVu Sans</family>
      <family>Liberation Sans</family>
      <family>Noto Sans</family>
    </prefer>
  </alias>
  
  <!-- 防止字体渲染错误 -->
  <match target="font">
    <edit name="antialias" mode="assign">
      <bool>true</bool>
    </edit>
    <edit name="hinting" mode="assign">
      <bool>true</bool>
    </edit>
    <edit name="hintstyle" mode="assign">
      <const>hintslight</const>
    </edit>
  </match>
</fontconfig>
'''
    
    config_dir = os.path.expanduser('~/.config/fontconfig')
    config_file = os.path.join(config_dir, 'fonts.conf')
    
    try:
        os.makedirs(config_dir, exist_ok=True)
        with open(config_file, 'w') as f:
            f.write(config_content)
        print(f"✓ 字体配置已创建: {config_file}")
        return True
    except Exception as e:
        print(f"✗ 字体配置创建失败: {e}")
        return False

def main():
    """主函数"""
    print("X11字体问题诊断和修复工具")
    print("=" * 40)
    
    # 检查环境
    check_x11_environment()
    check_fonts()
    
    # 测试tkinter
    basic_works = test_tkinter_minimal()
    if not basic_works:
        print("\n❌ 基本tkinter功能失败，请检查X11环境")
        return
    
    successful_fonts = test_tkinter_with_fonts()
    
    if not successful_fonts:
        print("\n⚠️  所有字体测试失败，尝试修复...")
        
        # 尝试修复
        print("\n🔧 开始修复过程...")
        fix_font_cache()
        create_safe_font_config()
        install_missing_fonts()
        
        print("\n建议重启终端并重新测试")
    else:
        print(f"\n✅ 找到可用字体: {successful_fonts}")
        print("\n建议在应用中使用系统默认字体或TkDefaultFont")
    
    print("\n修复建议:")
    print("1. 重启终端会话")
    print("2. 设置安全的字体 - 在代码中使用 font=None 或 ('TkDefaultFont', 10)")
    print("3. 如果问题仍然存在，请运行:")
    print("   sudo apt update && sudo apt install fonts-dejavu-core fontconfig")
    print("   fc-cache -fv")

if __name__ == "__main__":
    main() 