#!/bin/bash
# 商机抓取本地运行脚本
# launchd每小时触发 → 本地直接执行抓取+推送
# 运行时段: 9:00-23:00（北京时间）

export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
WORKDIR="/Users/zhouxinghao/.openclaw/workspace"
LOG="$WORKDIR/scripts/bidding_cron.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# 时间范围控制：9点-次日0点运行（即9:08-0:08，共16轮）
HOUR=$(date '+%H')
if [ "$HOUR" -ge 1 ] && [ "$HOUR" -lt 9 ]; then
    exit 0
fi

cd "$WORKDIR" || { echo "$TIMESTAMP ❌ 工作目录不存在" >> "$LOG"; exit 1; }

echo "$TIMESTAMP 开始本地抓取..." >> "$LOG"

# 1. 抓取移动
python3 fetch_cmcc.py >> "$LOG" 2>&1
CMCC_EXIT=$?

# 2. 抓取联通
python3 fetch_unicom.py >> "$LOG" 2>&1
UNICOM_EXIT=$?

# 3. 抓取电信
python3 fetch_telecom.py >> "$LOG" 2>&1
TELECOM_EXIT=$?

# 4. 整合推送到飞书
python3 push_combined.py >> "$LOG" 2>&1
PUSH_EXIT=$?

# 5. 保存去重记录到git
git add pushed_bids_combined.json 2>/dev/null
git diff --staged --quiet || git commit -m "更新去重记录 $(date +'%Y-%m-%d %H:%M')" 2>/dev/null
git push 2>/dev/null || true

TIMESTAMP_END=$(date '+%Y-%m-%d %H:%M:%S')
echo "$TIMESTAMP_END 本地抓取完成 (移动:$CMCC_EXIT 联通:$UNICOM_EXIT 电信:$TELECOM_EXIT 推送:$PUSH_EXIT)" >> "$LOG"
echo "---" >> "$LOG"

# 日志保留最近1000行
tail -1000 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
