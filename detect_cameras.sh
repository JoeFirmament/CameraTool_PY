#!/bin/bash

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# 全局变量
TEMP_DIR="/tmp/camera_detect_$$"
DETECTION_TIMEOUT=5

echo -e "${CYAN}${BOLD}=== USB摄像头检测工具 ===${NC}"
echo -e "${BLUE}扫描系统中所有可用的USB摄像头设备${NC}"
echo ""

# 清理函数
cleanup() {
    if [ -d "$TEMP_DIR" ]; then
        rm -rf "$TEMP_DIR" 2>/dev/null
    fi
}

# 设置清理陷阱
trap cleanup EXIT

# 创建临时目录
mkdir -p "$TEMP_DIR"

# 检查必需的工具
echo -e "${YELLOW}🔍 检查必需的工具...${NC}"

missing_tools=()

if ! command -v ffmpeg &> /dev/null; then
    missing_tools+=("ffmpeg")
fi

if ! command -v v4l2-ctl &> /dev/null; then
    missing_tools+=("v4l-utils")
fi

if ! command -v lsusb &> /dev/null; then
    missing_tools+=("usbutils")
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
echo ""

# 函数：解析帧率
parse_framerate() {
    local fps_string="$1"
    if [[ $fps_string =~ ([0-9]+)/([0-9]+) ]]; then
        local num=${BASH_REMATCH[1]}
        local den=${BASH_REMATCH[2]}
        if [ "$den" != "0" ]; then
            echo "scale=1; $num / $den" | bc -l
        else
            echo "未知"
        fi
    else
        echo "$fps_string"
    fi
}

# 函数：检测设备是否为摄像头
is_video_device() {
    local device="$1"
    
    # 检查设备文件是否存在
    if [ ! -e "$device" ]; then
        return 1
    fi
    
    # 检查设备是否可读
    if [ ! -r "$device" ]; then
        return 1
    fi
    
    # 使用v4l2-ctl检查设备能力
    if v4l2-ctl -d "$device" --list-formats >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# 函数：获取设备信息
get_device_info() {
    local device="$1"
    local info_file="$TEMP_DIR/device_info_$(basename $device)"
    
    echo -e "${BLUE}📹 检测设备: ${device}${NC}"
    
    # 获取设备基本信息
    local device_name=""
    local driver_name=""
    local bus_info=""
    
    if v4l2-ctl -d "$device" --info > "$info_file" 2>&1; then
        device_name=$(grep "Card type" "$info_file" | cut -d: -f2 | xargs)
        driver_name=$(grep "Driver name" "$info_file" | cut -d: -f2 | xargs)
        bus_info=$(grep "Bus info" "$info_file" | cut -d: -f2 | xargs)
    fi
    
    echo -e "  ${CYAN}设备名称:${NC} ${device_name:-未知}"
    echo -e "  ${CYAN}驱动名称:${NC} ${driver_name:-未知}"
    echo -e "  ${CYAN}总线信息:${NC} ${bus_info:-未知}"
    
    # 获取USB设备信息
    if [[ $bus_info =~ usb-([0-9]+):([0-9]+) ]]; then
        local bus=${BASH_REMATCH[1]}
        local device_num=${BASH_REMATCH[2]}
        
        # 查找对应的USB设备
        local usb_info=$(lsusb -s ${bus}:${device_num} 2>/dev/null)
        if [ ! -z "$usb_info" ]; then
            local vendor_product=$(echo "$usb_info" | awk '{for(i=7;i<=NF;i++) printf "%s ", $i; print ""}' | sed 's/[[:space:]]*$//')
            echo -e "  ${CYAN}USB信息:${NC} ${vendor_product}"
        fi
    fi
    
    echo ""
}

# 函数：获取支持的格式
get_supported_formats() {
    local device="$1"
    local formats_file="$TEMP_DIR/formats_$(basename $device)"
    
    echo -e "  ${PURPLE}${BOLD}支持的像素格式:${NC}"
    
    if v4l2-ctl -d "$device" --list-formats-ext > "$formats_file" 2>&1; then
        # 解析格式信息
        local current_format=""
        local format_count=0
        
        while IFS= read -r line; do
            if [[ $line =~ Index.*:.*Type.*:.*Pixel\ Format:\ \'([^\']+)\'.*Description:\ \'([^\']+)\' ]]; then
                current_format="${BASH_REMATCH[1]}"
                local description="${BASH_REMATCH[2]}"
                format_count=$((format_count + 1))
                echo -e "    ${CYAN}[$format_count] ${current_format}${NC} - ${description}"
                
                # 获取该格式支持的分辨率和帧率
                echo -e "        ${YELLOW}支持的分辨率和帧率:${NC}"
                
            elif [[ $line =~ Size:\ Discrete\ ([0-9]+)x([0-9]+) ]]; then
                local width="${BASH_REMATCH[1]}"
                local height="${BASH_REMATCH[2]}"
                echo -ne "          ${width}x${height}: "
                
            elif [[ $line =~ Interval:\ Discrete\ ([0-9\.]+)s\ \(([0-9\.]+)\ fps\) ]]; then
                local fps="${BASH_REMATCH[2]}"
                echo -ne "${fps}fps "
                
            elif [[ $line =~ Size:\ Stepwise ]]; then
                echo -e "          ${YELLOW}支持连续分辨率调整${NC}"
                
            elif [[ $line == "" ]] && [[ $current_format != "" ]]; then
                echo ""
            fi
            
        done < "$formats_file"
        
        if [ $format_count -eq 0 ]; then
            echo -e "    ${RED}无法获取格式信息${NC}"
        fi
        
    else
        echo -e "    ${RED}无法检测支持的格式${NC}"
    fi
    
    echo ""
}

# 函数：获取当前设置
get_current_settings() {
    local device="$1"
    
    echo -e "  ${PURPLE}${BOLD}当前设备设置:${NC}"
    
    # 获取当前视频格式
    local current_format=$(v4l2-ctl -d "$device" --get-fmt-video 2>/dev/null)
    if [ ! -z "$current_format" ]; then
        echo "$current_format" | while IFS= read -r line; do
            if [[ $line =~ Width/Height ]]; then
                echo -e "    ${CYAN}分辨率:${NC} $(echo $line | grep -o '[0-9]\+/[0-9]\+' | tr '/' 'x')"
            elif [[ $line =~ Pixel\ Format ]]; then
                local format=$(echo $line | grep -o "'[^']*'" | tr -d "'")
                echo -e "    ${CYAN}像素格式:${NC} $format"
            fi
        done
    fi
    
    # 获取当前帧率参数
    local current_parm=$(v4l2-ctl -d "$device" --get-parm 2>/dev/null)
    if [ ! -z "$current_parm" ]; then
        local fps=$(echo "$current_parm" | grep -o "([0-9\.]\+fps)" | grep -o "[0-9\.]\+")
        if [ ! -z "$fps" ]; then
            echo -e "    ${CYAN}当前帧率:${NC} ${fps} fps"
        fi
    fi
    
    echo ""
}

# 函数：测试设备可用性
test_device_availability() {
    local device="$1"
    
    echo -e "  ${PURPLE}${BOLD}设备可用性测试:${NC}"
    
    # 尝试使用ffmpeg检测设备
    local test_file="$TEMP_DIR/test_$(basename $device).log"
    
    echo -e "    ${YELLOW}正在测试设备访问...${NC}"
    
    timeout $DETECTION_TIMEOUT ffmpeg -f v4l2 -list_formats all -i "$device" > "$test_file" 2>&1
    local ffmpeg_result=$?
    
    if [ $ffmpeg_result -eq 0 ]; then
        echo -e "    ${GREEN}✅ 设备可以被ffmpeg访问${NC}"
        
        # 显示ffmpeg检测到的格式
        if grep -q "Compressed:" "$test_file"; then
            echo -e "    ${CYAN}FFmpeg检测到的压缩格式:${NC}"
            grep "Compressed:" -A 20 "$test_file" | grep -E "^\[" | head -5 | while read line; do
                echo -e "      $line"
            done
        fi
        
        if grep -q "Raw       :" "$test_file"; then
            echo -e "    ${CYAN}FFmpeg检测到的原始格式:${NC}"
            grep "Raw       :" -A 20 "$test_file" | grep -E "^\[" | head -5 | while read line; do
                echo -e "      $line"
            done
        fi
        
    elif [ $ffmpeg_result -eq 124 ]; then
        echo -e "    ${YELLOW}⚠️  设备响应超时 (可能正在被其他程序使用)${NC}"
    else
        echo -e "    ${RED}❌ 设备无法被ffmpeg访问${NC}"
        
        # 显示错误信息
        if [ -f "$test_file" ]; then
            local error_msg=$(tail -3 "$test_file" | head -1)
            if [ ! -z "$error_msg" ]; then
                echo -e "    ${RED}错误信息: $error_msg${NC}"
            fi
        fi
    fi
    
    echo ""
}

# 函数：推荐最佳设置
recommend_settings() {
    local device="$1"
    
    echo -e "  ${PURPLE}${BOLD}推荐设置:${NC}"
    
    # 分析支持的格式，推荐最佳设置
    local formats_file="$TEMP_DIR/formats_$(basename $device)"
    
    if [ -f "$formats_file" ]; then
        # 查找最高分辨率
        local max_width=0
        local max_height=0
        local best_format=""
        local best_fps=""
        
        while IFS= read -r line; do
            if [[ $line =~ Pixel\ Format:\ \'([^\']+)\' ]]; then
                current_format="${BASH_REMATCH[1]}"
            elif [[ $line =~ Size:\ Discrete\ ([0-9]+)x([0-9]+) ]]; then
                local width="${BASH_REMATCH[1]}"
                local height="${BASH_REMATCH[2]}"
                
                if [ $width -gt $max_width ] || ([ $width -eq $max_width ] && [ $height -gt $max_height ]); then
                    max_width=$width
                    max_height=$height
                    best_format=$current_format
                fi
            elif [[ $line =~ fps\) ]] && [ $max_width -gt 0 ]; then
                # 提取最高帧率
                local fps_list=$(echo "$line" | grep -o "[0-9\.]\+fps" | grep -o "[0-9\.]\+")
                for fps in $fps_list; do
                    if (( $(echo "$fps > ${best_fps:-0}" | bc -l) )); then
                        best_fps=$fps
                    fi
                done
            fi
        done < "$formats_file"
        
        if [ $max_width -gt 0 ]; then
            echo -e "    ${GREEN}最高分辨率:${NC} ${max_width}x${max_height}"
            echo -e "    ${GREEN}推荐格式:${NC} ${best_format:-MJPG}"
            if [ ! -z "$best_fps" ]; then
                echo -e "    ${GREEN}最高帧率:${NC} ${best_fps} fps"
            fi
            
            echo -e "    ${CYAN}建议命令:${NC}"
            echo -e "      v4l2-ctl -d $device --set-fmt-video=width=${max_width},height=${max_height},pixelformat=${best_format:-MJPG}"
            if [ ! -z "$best_fps" ]; then
                echo -e "      v4l2-ctl -d $device --set-parm=${best_fps}"
            fi
        else
            echo -e "    ${YELLOW}无法确定最佳设置${NC}"
        fi
    else
        echo -e "    ${YELLOW}无格式信息，无法提供推荐${NC}"
    fi
    
    echo ""
}

# 主检测流程
echo -e "${YELLOW}🔍 搜索视频设备...${NC}"

# 查找所有video设备
video_devices=()
for device in /dev/video*; do
    if [ -e "$device" ]; then
        video_devices+=("$device")
    fi
done

if [ ${#video_devices[@]} -eq 0 ]; then
    echo -e "${RED}❌ 未找到任何视频设备${NC}"
    exit 1
fi

echo -e "${GREEN}✅ 找到 ${#video_devices[@]} 个视频设备${NC}"
echo ""

# 检测每个设备
camera_count=0

for device in "${video_devices[@]}"; do
    echo -e "${CYAN}${BOLD}===========================================${NC}"
    
    if is_video_device "$device"; then
        camera_count=$((camera_count + 1))
        echo -e "${GREEN}${BOLD}摄像头 #${camera_count}: ${device}${NC}"
        echo ""
        
        # 获取设备信息
        get_device_info "$device"
        
        # 获取当前设置
        get_current_settings "$device"
        
        # 获取支持的格式
        get_supported_formats "$device"
        
        # 测试设备可用性
        test_device_availability "$device"
        
        # 推荐设置
        recommend_settings "$device"
        
    else
        echo -e "${YELLOW}⚠️  设备 ${device} 不是有效的摄像头或无法访问${NC}"
        echo ""
    fi
done

echo -e "${CYAN}${BOLD}===========================================${NC}"

# 总结
if [ $camera_count -eq 0 ]; then
    echo -e "${RED}❌ 未检测到可用的USB摄像头${NC}"
    echo ""
    echo -e "${YELLOW}💡 故障排除建议:${NC}"
    echo -e "  1. 检查摄像头是否正确连接到USB端口"
    echo -e "  2. 检查摄像头是否被其他程序占用"
    echo -e "  3. 尝试重新插拔摄像头"
    echo -e "  4. 检查系统日志: dmesg | grep -i video"
    echo -e "  5. 查看USB设备: lsusb"
else
    echo -e "${GREEN}🎉 检测完成! 共找到 ${camera_count} 个可用摄像头${NC}"
    echo ""
    echo -e "${CYAN}💡 使用建议:${NC}"
    echo -e "  - 选择最高分辨率的设备获得最佳画质"
    echo -e "  - MJPG格式通常有最好的性能表现"
    echo -e "  - 高帧率设备适合运动场景录制"
    echo -e "  - 在录制前先用推荐命令设置设备参数"
fi

echo ""
echo -e "${GREEN}检测完成!${NC}"