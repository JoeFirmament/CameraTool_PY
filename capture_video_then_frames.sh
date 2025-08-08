 #!/bin/bash

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 设置参数
DEVICE="/dev/video0"
RESOLUTION="1280x960"
FPS=30
DURATION=10  # 秒
OUTPUT_DIR="basketball_$(date +%Y%m%d_%H%M%S)"
VIDEO_NAME="raw_capture.mkv"  # 使用MKV格式支持高帧率
EXTRACT_FPS=30  # 提取帧的帧率（可以低于录制帧率）

echo -e "${CYAN}=== 篮球场高效视频录制+帧提取工具 ===${NC}"
echo -e "${BLUE}设备: ${DEVICE}${NC}"
echo -e "${BLUE}分辨率: ${RESOLUTION}${NC}"
echo -e "${BLUE}录制帧率: ${FPS} FPS${NC}"
echo -e "${BLUE}录制时长: ${DURATION} 秒${NC}"
echo -e "${BLUE}提取帧率: ${EXTRACT_FPS} FPS${NC}"
echo -e "${BLUE}输出目录: ${OUTPUT_DIR}${NC}"
echo ""

# 检查设备是否存在
if [ ! -e "$DEVICE" ]; then
    echo -e "${RED}❌ 错误: 摄像头设备 $DEVICE 不存在!${NC}"
    exit 1
fi

# 检查必需的工具
echo -e "${YELLOW}🔍 检查必需的工具...${NC}"

missing_tools=()

if ! command -v ffmpeg &> /dev/null; then
    missing_tools+=("ffmpeg")
fi

if ! command -v v4l2-ctl &> /dev/null; then
    missing_tools+=("v4l-utils")
fi

if [ ${#missing_tools[@]} -ne 0 ]; then
    echo -e "${RED}❌ 错误: 缺少必需的工具!${NC}"
    echo -e "${YELLOW}请安装以下软件包:${NC}"
    for tool in "${missing_tools[@]}"; do
        echo -e "${YELLOW}  sudo apt install $tool${NC}"
    done
    exit 1
fi

echo -e "${GREEN}✅ 所有必需工具已安装${NC}"

# 创建输出目录
mkdir -p "$OUTPUT_DIR"
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ 错误: 无法创建输出目录 $OUTPUT_DIR${NC}"
    exit 1
fi

echo -e "${GREEN}✅ 输出目录创建成功: $OUTPUT_DIR${NC}"

# 设置摄像头格式（使用ffmpeg更可靠）
echo -e "${YELLOW}🔧 检查摄像头支持的格式...${NC}"

# 检查摄像头支持的分辨率和帧率
ffmpeg -f v4l2 -list_formats all -i "$DEVICE" 2>&1 | head -20

echo ""
echo -e "${YELLOW}🔧 设置摄像头参数...${NC}"
v4l2-ctl -d "$DEVICE" --set-fmt-video=width=1920,height=1080,pixelformat=MJPG
v4l2-ctl -d "$DEVICE" --set-parm=$FPS

# 验证设置
echo -e "${BLUE}当前摄像头设置:${NC}"
v4l2-ctl -d "$DEVICE" --get-fmt-video
v4l2-ctl -d "$DEVICE" --get-parm

# 计算预期的视频文件大小
expected_frames=$((FPS * DURATION))
echo ""
echo -e "${PURPLE}📊 录制参数:${NC}"
echo -e "${BLUE}  录制时长: ${DURATION} 秒${NC}"
echo -e "${BLUE}  录制帧率: ${FPS} FPS${NC}"
echo -e "${BLUE}  预期总帧数: ${expected_frames}${NC}"
echo -e "${BLUE}  视频文件: ${OUTPUT_DIR}/${VIDEO_NAME}${NC}"
echo -e "${BLUE}  预估文件大小: ~$(( (FPS * DURATION * 200) / 1024 ))MB (1080p@${FPS}fps)${NC}"
echo ""

# 倒计时开始提示
echo -e "${YELLOW}⏰ 准备开始录制，5秒倒计时:${NC}"
for i in {5..1}; do
    echo -ne "${RED}${i}${NC}"
    sleep 0.5
    echo -ne "${YELLOW}...${NC}"
    sleep 0.5
done
echo -e "\n${GREEN}🚀 开始录制视频!${NC}"

# 使用ffmpeg录制视频
echo -e "${CYAN}📹 开始录制 ${DURATION} 秒的视频...${NC}"

start_time=$(date +%s)

# FFmpeg录制命令 - 使用高效的编码设置
ffmpeg -y \
    -f v4l2 \
    -framerate $FPS \
    -video_size $RESOLUTION \
    -i "$DEVICE" \
    -t $DURATION \
    -c:v libx264 \
    -preset ultrafast \
    -crf 18 \
    -pix_fmt yuv420p \
    -g $FPS \
    "$OUTPUT_DIR/$VIDEO_NAME" \
    2>&1 | while read line; do
        # 解析FFmpeg的进度信息
        if [[ $line == *"time="* ]]; then
            time_str=$(echo "$line" | grep -o 'time=[0-9:]*\.[0-9]*' | cut -d'=' -f2)
            if [[ $time_str =~ ([0-9]+):([0-9]+):([0-9]+)\.([0-9]+) ]]; then
                hours=${BASH_REMATCH[1]}
                minutes=${BASH_REMATCH[2]}
                seconds=${BASH_REMATCH[3]}
                current_seconds=$((hours * 3600 + minutes * 60 + seconds))
                progress=$((current_seconds * 100 / DURATION))
                remaining=$((DURATION - current_seconds))
                
                printf "\r${BLUE}录制进度: [${GREEN}"
                for ((j=0; j<progress/2; j++)); do printf "█"; done
                for ((j=progress/2; j<50; j++)); do printf "░"; done
                printf "${BLUE}] ${progress}%% | 已录制: ${current_seconds}s | 剩余: ${remaining}s${NC}"
            fi
        fi
    done

echo ""

# 检查录制是否成功
if [ ! -f "$OUTPUT_DIR/$VIDEO_NAME" ]; then
    echo -e "${RED}❌ 错误: 视频录制失败!${NC}"
    exit 1
fi

end_time=$(date +%s)
record_duration=$((end_time - start_time))

echo -e "\n${GREEN}✅ 视频录制完成!${NC}"

# 获取视频信息
video_info=$(ffprobe -v quiet -print_format json -show_format -show_streams "$OUTPUT_DIR/$VIDEO_NAME" 2>/dev/null)
video_size=$(stat -c%s "$OUTPUT_DIR/$VIDEO_NAME" 2>/dev/null)
video_size_mb=$((video_size / 1024 / 1024))

echo -e "${BLUE}📊 录制统计:${NC}"
echo -e "${BLUE}  实际录制时间: ${record_duration} 秒${NC}"
echo -e "${BLUE}  视频文件大小: ${video_size_mb} MB${NC}"
echo -e "${BLUE}  视频文件路径: ${OUTPUT_DIR}/${VIDEO_NAME}${NC}"

# 获取视频实际帧率和时长
actual_fps=$(ffprobe -v quiet -select_streams v:0 -show_entries stream=r_frame_rate -of csv=p=0 "$OUTPUT_DIR/$VIDEO_NAME" 2>/dev/null)
actual_duration=$(ffprobe -v quiet -select_streams v:0 -show_entries format=duration -of csv=p=0 "$OUTPUT_DIR/$VIDEO_NAME" 2>/dev/null)

if [ ! -z "$actual_fps" ] && [ ! -z "$actual_duration" ]; then
    echo -e "${BLUE}  视频实际帧率: ${actual_fps} FPS${NC}"
    echo -e "${BLUE}  视频实际时长: $(printf "%.2f" "$actual_duration") 秒${NC}"
fi

echo ""
echo -e "${CYAN}🎬 开始从视频提取帧...${NC}"

# 创建帧输出目录
FRAMES_DIR="$OUTPUT_DIR/frames"
mkdir -p "$FRAMES_DIR"

# 从视频提取帧
extract_start_time=$(date +%s)

echo -e "${YELLOW}正在以 ${EXTRACT_FPS} FPS 提取帧...${NC}"

ffmpeg -y \
    -i "$OUTPUT_DIR/$VIDEO_NAME" \
    -vf "fps=$EXTRACT_FPS" \
    -qscale:v 2 \
    "$FRAMES_DIR/frame_%04d.jpg" \
    2>&1 | while read line; do
        if [[ $line == *"time="* ]]; then
            time_str=$(echo "$line" | grep -o 'time=[0-9:]*\.[0-9]*' | cut -d'=' -f2)
            if [[ $time_str =~ ([0-9]+):([0-9]+):([0-9]+)\.([0-9]+) ]]; then
                hours=${BASH_REMATCH[1]}
                minutes=${BASH_REMATCH[2]}
                seconds=${BASH_REMATCH[3]}
                current_seconds=$((hours * 3600 + minutes * 60 + seconds))
                progress=$((current_seconds * 100 / DURATION))
                
                printf "\r${BLUE}提取进度: [${GREEN}"
                for ((j=0; j<progress/2; j++)); do printf "█"; done
                for ((j=progress/2; j<50; j++)); do printf "░"; done
                printf "${BLUE}] ${progress}%% | 处理时间: ${current_seconds}s${NC}"
            fi
        fi
    done

echo ""

extract_end_time=$(date +%s)
extract_duration=$((extract_end_time - extract_start_time))

# 统计提取的帧数
extracted_frames=$(ls "$FRAMES_DIR"/*.jpg 2>/dev/null | wc -l)
expected_extract_frames=$((EXTRACT_FPS * DURATION))

echo -e "\n${GREEN}🎉 帧提取完成!${NC}"
echo -e "${BLUE}📊 提取统计:${NC}"
echo -e "${BLUE}  提取时间: ${extract_duration} 秒${NC}"
echo -e "${BLUE}  预期帧数: ${expected_extract_frames}${NC}"
echo -e "${BLUE}  实际提取: ${extracted_frames} 帧${NC}"
echo -e "${BLUE}  提取目录: ${FRAMES_DIR}/${NC}"

if [ "$extracted_frames" -eq "$expected_extract_frames" ]; then
    echo -e "${GREEN}✅ 帧提取完全成功!${NC}"
elif [ "$extracted_frames" -gt 0 ]; then
    echo -e "${YELLOW}⚠️  部分帧提取成功 (${extracted_frames}/${expected_extract_frames})${NC}"
else
    echo -e "${RED}❌ 帧提取失败!${NC}"
    exit 1
fi

# 文件大小统计
if [ "$extracted_frames" -gt 0 ]; then
    first_frame=$(ls "$FRAMES_DIR"/frame_*.jpg | head -1)
    last_frame=$(ls "$FRAMES_DIR"/frame_*.jpg | tail -1)
    frames_total_size=$(du -sm "$FRAMES_DIR" | cut -f1)
    
    echo -e "${BLUE}📏 帧文件统计:${NC}"
    echo -e "${BLUE}  首帧: $(basename "$first_frame") - $(stat -c%s "$first_frame" 2>/dev/null) bytes${NC}"
    echo -e "${BLUE}  末帧: $(basename "$last_frame") - $(stat -c%s "$last_frame" 2>/dev/null) bytes${NC}"
    echo -e "${BLUE}  帧总大小: ${frames_total_size} MB${NC}"
fi

total_end_time=$(date +%s)
total_duration=$((total_end_time - start_time))

echo ""
echo -e "${PURPLE}⏱️  总体性能统计:${NC}"
echo -e "${BLUE}  录制效率: $(bc -l <<< "scale=2; $DURATION / $record_duration")x 实时${NC}"
echo -e "${BLUE}  总处理时间: ${total_duration} 秒${NC}"
echo -e "${BLUE}  传统方法预估: $((expected_extract_frames * 2)) 秒 (假设每帧0.2秒)${NC}"
echo -e "${BLUE}  效率提升: $(bc -l <<< "scale=1; ($expected_extract_frames * 2) / $total_duration")x${NC}"

echo ""
echo -e "${CYAN}✨ 使用建议:${NC}"
echo -e "${YELLOW}  查看视频: ffplay ${OUTPUT_DIR}/${VIDEO_NAME}${NC}"
echo -e "${YELLOW}  查看帧: ls -la ${FRAMES_DIR}/${NC}"
echo -e "${YELLOW}  生成预览视频: ffmpeg -framerate 15 -i ${FRAMES_DIR}/frame_%04d.jpg -c:v libx264 ${OUTPUT_DIR}/preview.mp4${NC}"
echo -e "${YELLOW}  删除原视频节省空间: rm ${OUTPUT_DIR}/${VIDEO_NAME}${NC}"

echo ""
echo -e "${GREEN}🎊 全部完成! 高效录制 + 精确提取 = 最佳方案${NC}"
