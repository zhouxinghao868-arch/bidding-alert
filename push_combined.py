#!/usr/bin/env python3
"""
整合推送脚本
读取 cmcc_bids.json 和 unicom_bids.json，合并推送到飞书
"""

import json
import os
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, List

import requests

# 北京时间
BJT = timezone(timedelta(hours=8))

def now_bjt():
    return datetime.now(BJT)

FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK", "https://open.feishu.cn/open-apis/bot/v2/hook/3f57d6e3-20d7-4511-bb85-695352fbd651")
PUSHED_RECORDS_FILE = "pushed_bids_combined.json"
KEYWORDS = ["数智化", "数据", "算力", "战略"]


def load_pushed_records() -> Dict:
    if os.path.exists(PUSHED_RECORDS_FILE):
        try:
            with open(PUSHED_RECORDS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {"hashes": [], "urls": []}


def save_pushed_records(records: Dict):
    with open(PUSHED_RECORDS_FILE, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False)


def get_bid_hash(title: str) -> str:
    return hashlib.md5(title.strip()[:50].encode('utf-8')).hexdigest()


def is_bid_pushed(title: str, url: str, records: Dict) -> bool:
    bid_hash = get_bid_hash(title)
    if bid_hash in records.get("hashes", []):
        return True
    if url in records.get("urls", []):
        return True
    return False


def mark_bid_pushed(title: str, url: str, records: Dict):
    bid_hash = get_bid_hash(title)
    if "hashes" not in records:
        records["hashes"] = []
    if "urls" not in records:
        records["urls"] = []
    if bid_hash not in records["hashes"]:
        records["hashes"].append(bid_hash)
    if url not in records["urls"]:
        records["urls"].append(url)


def load_bids():
    """加载两个抓取结果文件"""
    cmcc_bids = []
    unicom_bids = []
    
    try:
        with open("cmcc_bids.json", 'r', encoding='utf-8') as f:
            cmcc_bids = json.load(f)
    except:
        print("⚠️ 未找到移动招标数据")
    
    try:
        with open("unicom_bids.json", 'r', encoding='utf-8') as f:
            unicom_bids = json.load(f)
    except:
        print("⚠️ 未找到联通招标数据")
    
    return cmcc_bids, unicom_bids


def send_combined_message(cmcc_bids: List[Dict], unicom_bids: List[Dict]) -> bool:
    """发送整合消息到飞书"""
    
    # 去重过滤
    records = load_pushed_records()
    
    cmcc_new = [b for b in cmcc_bids if not is_bid_pushed(b["title"], b["url"], records)]
    unicom_new = [b for b in unicom_bids if not is_bid_pushed(b["title"], b["url"], records)]
    
    total = len(cmcc_new) + len(unicom_new)
    
    if total == 0:
        print("\n没有新消息需要推送")
        return True
    
    lines = [
        "📢 运营商招标信息汇总",
        f"📅 {now_bjt().strftime('%Y-%m-%d %H:%M')}",
        f"📊 共找到 {total} 条新公告",
        f"   中国移动: {len(cmcc_new)}条 | 中国联通: {len(unicom_new)}条"
    ]
    
    # 类型统计
    all_bids = cmcc_new + unicom_new
    type_stats = {}
    for bid in all_bids:
        key = f"{bid['platform']}-{bid['type']}"
        type_stats[key] = type_stats.get(key, 0) + 1
    
    if type_stats:
        stats_str = " | ".join([f"{k}:{v}" for k, v in sorted(type_stats.items())])
        lines.append(f"📋 {stats_str}")
    lines.append("")
    
    # 中国移动部分
    if cmcc_new:
        lines.append("=" * 40)
        lines.append("📱 中国移动招标信息")
        lines.append("=" * 40)
        lines.append("")
        
        for i, bid in enumerate(cmcc_new, 1):
            lines.append(f"【{bid['province']}-{bid['type']}-{i}】")
            lines.append(f"日期：{bid['date']}")
            lines.append(f"标题：{bid['title']}")
            lines.append(f"链接：{bid['url']}")
            lines.append("")
    
    # 中国联通部分
    if unicom_new:
        lines.append("=" * 40)
        lines.append("🌐 中国联通招标信息")
        lines.append("=" * 40)
        lines.append("")
        
        for i, bid in enumerate(unicom_new, 1):
            lines.append(f"【{bid['province']}-{bid['type']}-{i}】")
            lines.append(f"日期：{bid['date']}")
            lines.append(f"标题：{bid['title']}")
            lines.append(f"链接：{bid['url']}")
            lines.append("")
    
    lines.append("=" * 40)
    lines.append(f"数据来源: 中国移动采购与招标网 | 中国联通采购与招标网")
    lines.append(f"关键词: {' | '.join(KEYWORDS)} | 更新时间: {now_bjt().strftime('%H:%M')}")
    
    message = "\n".join(lines)
    
    payload = {
        "msg_type": "text",
        "content": {"text": message}
    }
    
    try:
        response = requests.post(
            FEISHU_WEBHOOK,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        result = response.json()
        if result.get("code") == 0:
            print(f"\n✅ 成功推送 {total} 条消息到飞书")
            # 更新推送记录
            for bid in cmcc_new + unicom_new:
                mark_bid_pushed(bid["title"], bid["url"], records)
            save_pushed_records(records)
            return True
        else:
            print(f"\n❌ 推送失败: {result}")
            return False
    except Exception as e:
        print(f"\n❌ 推送异常: {e}")
        return False


def main():
    print(f"=== 整合推送开始 {now_bjt().strftime('%Y-%m-%d %H:%M:%S')} ===")
    
    cmcc_bids, unicom_bids = load_bids()
    print(f"\n加载数据:")
    print(f"  移动: {len(cmcc_bids)} 条")
    print(f"  联通: {len(unicom_bids)} 条")
    
    send_combined_message(cmcc_bids, unicom_bids)
    
    print(f"\n=== 整合推送完成 {now_bjt().strftime('%Y-%m-%d %H:%M:%S')} ===")


if __name__ == "__main__":
    main()
