#!/bin/bash
# 视频关键帧提取工具
# 用法: ./extract_video_frames.sh <视频URL或本地路径> [输出目录]

VIDEO_INPUT="$1"
OUTPUT_DIR="${2:-./video_frames}"
MAX_FRAMES=10

# 创建输出目录
mkdir -p "$OUTPUT_DIR"

# 如果是URL，先下载
if [[ "$VIDEO_INPUT" == http* ]]; then
    echo "正在下载视频..."
    VIDEO_FILE="$OUTPUT_DIR/temp_video.mp4"
    curl -L -o "$VIDEO_FILE" "$VIDEO_INPUT" --max-time 120
else
    VIDEO_FILE="$VIDEO_INPUT"
fi

# 获取视频时长
duration=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$VIDEO_FILE" 2>/dev/null)

if [ -z "$duration" ]; then
    echo "无法获取视频信息"
    exit 1
fi

echo "视频时长: ${duration}s"
echo "提取 $MAX_FRAMES 个关键帧..."

# 计算间隔
interval=$(echo "$duration / ($MAX_FRAMES + 1)" | bc -l)

# 提取帧
for i in $(seq 1 $MAX_FRAMES); do
    timestamp=$(echo "$interval * $i" | bc -l)
    ffmpeg -ss "$timestamp" -i "$VIDEO_FILE" -vframes 1 -q:v 2 "$OUTPUT_DIR/frame_$(printf %02d $i).jpg" -y 2>/dev/null
    echo "  提取帧 $i/${MAX_FRAMES}"
done

echo "完成！帧保存在: $OUTPUT_DIR/"
ls -la "$OUTPUT_DIR/"/*.jpg 2>/dev/null

# 清理临时文件
if [[ "$VIDEO_INPUT" == http* ]]; then
    rm -f "$VIDEO_FILE"
fi
