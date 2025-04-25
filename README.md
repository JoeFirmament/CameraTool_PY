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





