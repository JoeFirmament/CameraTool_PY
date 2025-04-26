#!/bin/bash
source .venv/bin/activate
uv pip install -r requirements.txt
python cameraCalib.py