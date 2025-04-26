# 环境设置 以Mac为例
## 注意：
* 保证有一个支持的tck/tk的python环境
* numpy cv 是必须模块
* icon文件在同级目录

```bash
➜  ~ brew --prefix python

/opt/homebrew/opt/python@3.13
➜  ~ uv venv .venv --python /opt/homebrew/opt/python@3.13/bin/python3.13

Using CPython 3.13.3 interpreter at: /opt/homebrew/opt/python@3.13/bin/python3.13
Creating virtual environment at: .venv
Activate with: source .venv/bin/activate
➜  ~ source .venv/bin/activate
(.venv) ➜  ~
(.venv) ➜  ~ uv pip install opencv-python numpy Pillow
```

# 使用
## homography 透视变化
> 底面到像素平面的投影变换

## cameraCalib 相机内参标定工具



---
GUI 中 Verify 功能的使用:

Verify（验证）功能用于检查你的 Homography 矩阵计算结果的准确性。它的使用步骤如下：

加载标定图像和 JSON 文件: 首先按照步骤加载标定图像和对应的 Label Studio JSON 文件。
为至少 4 个点输入世界坐标并保存: 在图像上点击需要进行标定的点，然后在右侧的输入框中输入这些点对应的实际世界坐标（例如，地面上的真实位置），并点击“Save”按钮保存。
点击“Calculate Homography”按钮: 当你为至少 4 个点输入并保存了世界坐标后，“Calculate Homography”按钮会启用。点击它来计算 Homography 矩阵。
点击“Verify”按钮: Homography 矩阵计算成功后，“Verify”按钮会启用。点击它。
点击 "Verify" 后，程序会执行以下操作：

它会遍历所有 没有输入世界坐标 的点（这些点是你在 Label Studio JSON 中标注但还没有手动输入世界坐标的点）。
对于每一个这样的点，它会使用刚才计算出的 Homography 矩阵，根据该点的原始像素坐标，来 预测 它在世界坐标系中的位置。
然后在图像上该点的像素位置附近，会绘制一个绿色的标记，并在标记旁边显示程序 预测 出来的世界坐标值。





