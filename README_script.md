# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述
这是一个用于篮球场高效视频录制和帧提取的Shell脚本工具集。主要功能是通过摄像头设备录制高帧率视频，然后从视频中提取帧图像，专门为体育运动分析场景设计。

## 核心架构
### 主要脚本
- `capture_video_then_frames.sh` - 主工具脚本，集成了视频录制和帧提取功能

### 核心流程
1. **环境检查** - 检查摄像头设备存在性和必需工具（ffmpeg, v4l-utils）
2. **摄像头配置** - 设置摄像头参数（分辨率、帧率、格式）
3. **视频录制** - 使用ffmpeg录制高帧率视频（90fps@1080p）
4. **帧提取** - 从录制的视频中提取指定帧率的图像帧
5. **性能统计** - 提供详细的录制和处理性能统计

## 关键技术参数
- **默认摄像头设备**: `/dev/video2`
- **默认分辨率**: 1920x1080
- **录制帧率**: 90 FPS
- **录制时长**: 30秒
- **提取帧率**: 30 FPS
- **视频格式**: MKV (支持高帧率)
- **图像格式**: JPG

## 系统依赖
- `ffmpeg` - 视频录制和帧提取
- `v4l-utils` - 摄像头设备控制
- `bc` - 数学计算

## 运行方式
```bash
# 直接运行脚本
./capture_video_then_frames.sh

# 确保脚本有执行权限
chmod +x capture_video_then_frames.sh
```

## 输出结构
```
basketball_YYYYMMDD_HHMMSS/
├── raw_capture.mkv      # 录制的原始视频
└── frames/              # 提取的帧图像目录
    ├── frame_0001.jpg
    ├── frame_0002.jpg
    └── ...
```

## 自定义配置
脚本内的关键参数可以通过修改脚本顶部的变量来调整：
- `DEVICE` - 摄像头设备路径
- `RESOLUTION` - 录制分辨率
- `FPS` - 录制帧率
- `DURATION` - 录制时长
- `EXTRACT_FPS` - 帧提取率

## 性能优化特点
- 使用ultrafast预设进行实时录制
- 并行处理录制和进度显示
- 高效的帧提取算法
- 详细的性能统计和效率对比

## 使用场景
专为体育运动（特别是篮球）的高速动作分析设计，可用于：
- 动作分析
- 技术动作分解
- 慢动作回放制作
- 运动数据采集