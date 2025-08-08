# 🎬 CameraTool_PY - 专业摄像头工具集

**2分钟快速上手** | 双摄同步录制 | 智能静帧导出 | 篮球场地分析

> 为篮球训练和科研数据采集打造的专业工具套件

## ⚡ 一分钟快速开始

```bash
# 克隆并运行（3步完成）
git clone <repo> && cd CameraTool_PY
pip install opencv-python numpy Pillow
python3 dual_camera_recorder.py  # 🚀 立即开始录制！
```

## 🎯 核心功能概览

| 工具 | 用途 | 特色功能 | 运行命令 |
|------|------|----------|----------|
| **双摄录制器** 📹 | 同步录制多角度视频 | • 自动检测摄像头<br>• 录制时实时预览<br>• 智能静帧导出<br>• 稳定设备路径管理 | `python3 dual_camera_recorder.py` |
| **透视标定** 📐 | 场地坐标映射 | • 图形化标定界面<br>• 运动轨迹分析<br>• 统一摄像头管理 | `python3 homography.py` |
| **相机校正** 🔧 | 消除镜头畸变 | • 棋盘格自动检测<br>• 精确测量校正 | `python3 camera_calibration.py` |
| **设备检测** 🔍 | 摄像头兼容性测试 | • 显示设备详细信息<br>• by-id路径支持<br>• 排查连接问题 | `python3 test_camera_detection.py` |

## 📦 系统要求

- **Python**: 3.7+ (支持Tkinter)
- **系统**: Linux (推荐 Ubuntu/Debian)  
- **硬件**: 2个USB摄像头
- **依赖**: `sudo apt install v4l-utils` (Linux)

## 🚀 双摄录制器详细操作

### 快速开始（30秒上手）
```bash
python3 dual_camera_recorder.py
```

### 📱 界面操作流程
1. **自动检测**: 程序启动时自动识别摄像头
2. **参数设置**: 选择输出目录，调整FPS（默认30）
3. **开始录制**: 点击"● Start Recording"
4. **实时预览**: 录制时可看到两个摄像头画面
5. **停止录制**: 点击"■ Stop Recording"
6. **导出静帧**: 点击"📸 Export Frames"

### 📁 输出文件格式（更新后）

录制完成后自动生成：
```
basketball_recording_20250123_143052/
├── camera1_20250123_143052.avi      # 摄像头1视频（带时间戳）
├── camera2_20250123_143052.avi      # 摄像头2视频（带时间戳）
└── recording_info.json              # 录制信息

导出静帧后：
frames_export_20250123_143500_basketball_recording_20250123_143052/
├── camera1/
│   ├── camera1_20250123_143052_frame_000030_t1.00s.jpg
│   └── camera1_20250123_143052_frame_000060_t2.00s.jpg
└── camera2/
    ├── camera2_20250123_143052_frame_000030_t1.00s.jpg
    └── camera2_20250123_143052_frame_000060_t2.00s.jpg
```

> 💡 **命名规律**: `摄像头_日期时间_frame_帧数_t时间戳.jpg`

### 🎛️ 高级功能

- **智能摄像头检测**: 自动使用稳定的by-id设备路径，硬件重插后仍能识别
- **手动选择摄像头**: 勾选"Manual camera selection"进行精确控制
- **画面旋转**: 支持0°、90°、180°、270°旋转
- **分辨率调整**: 支持多种分辨率（自动检测摄像头支持，显示FPS信息）
- **静帧间隔**: 可设置每N帧导出一张图片
- **设备路径显示**: 界面显示by-id和/dev/videoX对应关系，便于理解

## 🛠️ 其他工具快速参考

### 透视变换标定 (`homography.py`)
**用途**: 建立篮球场地坐标系，分析球员位置轨迹
```bash
python3 homography.py
# 1. 加载场地图像 → 2. 导入JSON标注 → 3. 输入坐标 → 4. 验证结果
```

### 相机校正 (`camera_calibration.py`) 
**用途**: 消除镜头畸变，提高测量精度
```bash
python3 camera_calibration.py
# 1. 准备棋盘格 → 2. 多角度拍摄 → 3. 自动检测 → 4. 计算参数
```

### 设备检测 (`test_camera_detection.py`)
**用途**: 检查摄像头兼容性，显示稳定设备路径
```bash
python3 test_camera_detection.py  # 显示by-id路径、分辨率、FPS等详细信息

# 或者直接测试camera_utils模块
python3 -c "from camera_utils import CameraManager; CameraManager.test_camera_detection()"
```

## 🚨 常见问题速查

| 问题 | 解决方案 |
|------|----------|
| 😵 摄像头检测失败 | `sudo apt install v4l-utils`<br>`ls -la /dev/video*` 检查权限<br>运行 `python3 test_camera_detection.py` 诊断 |
| 🔄 画面旋转错误 | 使用界面中的"旋转"选项调整 |
| 📷 预览画面黑屏 | 检查摄像头被其他程序占用<br>查看控制台输出的设备路径尝试信息 |
| 💾 导出静帧失败 | 确认视频文件完整，检查输出目录权限 |
| 🐌 录制卡顿 | 降低分辨率或FPS，检查USB带宽 |
| 🔌 设备路径变化 | 新版本使用by-id稳定路径，硬件重插后自动适配 |

## 🎯 使用场景示例

- **🏀 篮球训练**: 双角度同步录制 → 战术分析 → 静帧导出关键动作
- **🔬 科研数据**: 校正镜头畸变 → 精确测量 → 立体视觉重建  
- **📊 运动分析**: 场地标定 → 轨迹追踪 → 数据可视化

---

## 📝 快速备忘

```bash
# 最常用命令
python3 dual_camera_recorder.py          # 🎬 开始录制
python3 test_camera_detection.py         # 🔍 检测摄像头
pip install opencv-python numpy Pillow   # 📦 安装依赖
sudo apt install v4l-utils              # 🔧 Linux支持
```

**💡 小贴士**: 首次使用建议先运行设备检测，确认摄像头正常后再开始录制

---
*最后更新: 2025年8月 | 统一摄像头管理模块 | 稳定设备路径支持 | by-id路径自动识别*