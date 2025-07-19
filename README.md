# CameraTool_PY

专业的摄像头标定和录制工具集，支持篮球场地分析和双摄像头同步录制。

## 🛠️ 工具列表

### 1. 双摄像头录制器 (`dual_camera_recorder.py`)
- **功能**: 同步录制两个摄像头，支持实时预览
- **特色**: 录制时保持预览、自动摄像头检测、静帧导出
- **用途**: 篮球训练录制、多角度视频采集

### 2. 透视变换标定工具 (`homography_fixed.py`)
- **功能**: 计算地面到像素平面的透视变换矩阵
- **特色**: 图形化标定界面、验证功能
- **用途**: 运动轨迹分析、场地坐标映射

### 3. 相机内参标定工具 (`cameraCalib.py`)
- **功能**: 标定相机内参数（焦距、畸变等）
- **特色**: 棋盘格检测、自动标定流程
- **用途**: 相机校正、精确测量

### 4. 摄像头检测工具 (`test_camera_detection.py`)
- **功能**: 检测系统中可用的摄像头设备
- **特色**: 显示设备详细信息
- **用途**: 设备调试、兼容性检查

## 📋 系统要求

- Python 3.7+
- 支持Tkinter的Python环境
- Linux系统（支持v4l2）
- 摄像头设备

## 🚀 快速安装

### 1. 克隆项目
```bash
git clone https://github.com/JoeFirmament/CameraTool_PY.git
cd CameraTool_PY
```

### 2. 安装依赖
```bash
pip install -r requirements.txt
# 或者手动安装
pip install opencv-python numpy Pillow
```

### 3. 安装系统依赖（Linux）
```bash
# Ubuntu/Debian
sudo apt install v4l-utils

# 或运行检测脚本
chmod +x run_camera_tool.sh
```

## 📖 使用说明

### 双摄像头录制器
```bash
python3 dual_camera_recorder.py
```
**功能操作**:
1. 自动检测连接的摄像头
2. 设置输出目录和录制参数
3. 开始录制（预览界面保持开启）
4. 停止录制后可导出静帧

**文件输出**:
- `camera1_recording.avi` - 摄像头1录制
- `camera2_recording.avi` - 摄像头2录制  
- `recording_info.json` - 录制信息
- `frames_export_*/` - 导出的静帧（按摄像头分文件夹）

### 透视变换标定
```bash
python3 homography_fixed.py
```
**标定流程**:
1. 加载标定图像
2. 导入Label Studio JSON标注文件
3. 为至少4个点输入世界坐标
4. 计算Homography矩阵
5. 使用Verify功能验证结果

### 相机内参标定
```bash
python3 cameraCalib.py
```
**标定流程**:
1. 准备棋盘格标定板
2. 从多个角度拍摄标定图像
3. 程序自动检测棋盘格角点
4. 计算相机内参和畸变系数

### 摄像头检测
```bash
python3 test_camera_detection.py
```
查看系统中所有可用摄像头的详细信息。

## 🎯 典型使用场景

### 篮球训练分析
1. 使用双摄像头录制器同步录制比赛
2. 用透视变换标定工具建立场地坐标系
3. 分析球员运动轨迹和位置数据

### 科研数据采集
1. 相机内参标定确保测量精度
2. 双摄像头提供立体视觉数据
3. 导出静帧进行详细分析

## ⚠️ 注意事项

- 确保Python环境支持Tkinter图形界面
- Linux系统需要安装v4l-utils支持
- 双摄像头录制需要足够的USB带宽
- 导出静帧功能需要完整的视频文件

## 🔧 故障排除

**摄像头无法检测**:
- 检查设备权限：`ls -la /dev/video*`
- 安装v4l2工具：`sudo apt install v4l-utils`

**录制画面旋转**:
- 检查摄像头物理安装方向
- 确保视频文件完整录制

**静帧导出失败**:
- 确认AVI文件未损坏
- 检查输出目录权限

## 📄 文件说明

- `dual_camera_recorder.py` - 主要录制工具
- `homography_fixed.py` - 透视变换标定
- `cameraCalib.py` - 相机内参标定  
- `test_camera_detection.py` - 设备检测
- `requirements.txt` - Python依赖
- `run_camera_tool.sh` - 启动脚本

---

**项目作者**: JoeFirmament  
**更新时间**: 2025年7月