#!/bin/bash
# startup-memory-review.sh - 启动时回顾记忆
# 应在主会话启动时调用

WORKSPACE="/Users/zhouxinghao/.openclaw/workspace"
MEMORY_DIR="$WORKSPACE/memory"

 echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                    📚 每日记忆回顾                            ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# 获取最近3天的日期
for i in 2 1 0; do
    DAY=$(date -v-${i}d +%Y-%m-%d 2>/dev/null || date -d "-${i} days" +%Y-%m-%d)
    FILE="$MEMORY_DIR/${DAY}.md"
    
    if [ -f "$FILE" ]; then
        echo "📅 ${DAY}:"
        # 显示前20行（概要）
        head -20 "$FILE" | sed 's/^/   /'
        echo ""
    fi
done

# 检查长期记忆
if [ -f "$WORKSPACE/MEMORY.md" ]; then
    echo "🧠 长期记忆摘要:"
    # 显示 MEMORY.md 的前30行
    head -30 "$WORKSPACE/MEMORY.md" | sed 's/^/   /'
    echo ""
fi

echo "═══════════════════════════════════════════════════════════════"
echo "记忆回顾完成。如需查看完整内容，请阅读对应的记忆文件。"
echo "═══════════════════════════════════════════════════════════════"
