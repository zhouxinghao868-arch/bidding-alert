#!/bin/bash
# memory-autosave.sh - 每5分钟自动保存会话状态
# 由 cron 定时调用

WORKSPACE="/Users/zhouxinghao/.openclaw/workspace"
AUTOSAVE_DIR="$WORKSPACE/memory/autosave"
DATE=$(date +%Y-%m-%d)
TIME=$(date +%H:%M:%S)
TIMESTAMP=$(date +%s)

# 确保目录存在
mkdir -p "$AUTOSAVE_DIR"

# 创建自动保存文件
cat > "$AUTOSAVE_DIR/${DATE}_${TIME}.md" << EOF
---
timestamp: $TIMESTAMP
date: $DATE
time: $TIME
type: autosave
---

# 自动保存 - $DATE $TIME

这个文件由系统自动生成，用于记录会话的时间节点。

EOF

# 保留最近7天的自动保存文件，清理旧的
find "$AUTOSAVE_DIR" -name "*.md" -mtime +7 -delete 2>/dev/null

echo "[$(date)] 记忆自动保存完成: ${DATE}_${TIME}.md"
