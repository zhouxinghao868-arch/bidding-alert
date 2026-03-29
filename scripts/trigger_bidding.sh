#!/bin/bash
# 商机抓取定时触发脚本
# launchd每小时第8分钟触发 → GitHub Actions执行抓取
# 运行时段: 9:00-23:00（北京时间）
# 日志: ~/.openclaw/workspace/scripts/bidding_cron.log

export PATH="/opt/homebrew/bin:$PATH"
WORKDIR="/Users/zhouxinghao/.openclaw/workspace"
LOG="$WORKDIR/scripts/bidding_cron.log"

# 时间范围控制：仅9-23点运行
HOUR=$(date '+%H')
if [ "$HOUR" -lt 9 ] || [ "$HOUR" -gt 23 ]; then
    exit 0
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') 触发商机抓取..." >> "$LOG"

cd "$WORKDIR" || { echo "$(date) 工作目录不存在" >> "$LOG"; exit 1; }

OUTPUT=$(gh workflow run combined-bidding-monitor.yml 2>&1)
if [ $? -eq 0 ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') ✅ 触发成功: $OUTPUT" >> "$LOG"
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') ❌ 触发失败: $OUTPUT" >> "$LOG"
fi

# 日志保留最近500行
tail -500 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
