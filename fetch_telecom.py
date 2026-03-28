#!/usr/bin/env python3
"""
电信招标信息抓取 - 纯API调用
关键：详情URL中的id必须用 docId 字段（不是 id 字段）
"""

import json
import sys
import requests
from datetime import datetime, timezone, timedelta

sys.stdout.reconfigure(line_buffering=True)

OUTPUT_FILE = "telecom_bids.json"
KEYWORDS = []  # 空=不过滤
BJT = timezone(timedelta(hours=8))
TODAY = datetime.now(BJT).strftime("%Y-%m-%d")

BASE_URL = "https://caigou.chinatelecom.com.cn"
API_URL = f"{BASE_URL}/portal/base/announcementJoin/queryListNew"
HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": f"{BASE_URL}/search",
    "Origin": BASE_URL
}

DOC_TYPE_MAP = {
    "TenderAnnouncement": "1", "PurchaseAnnounceBasic": "2",
    "PurchaseAnnounc": "2", "CompareSelect": "3",
    "NegotiationSelect": "5", "Prequalfication": "6",
    "ResultAnnounc": "7", "TerminationAnnounc": "15",
    "AuctionAnnounce": "19", "SingleSource": "2",
}


def fetch_page(page_num, page_size=20):
    payload = {"pageNum": page_num, "pageSize": page_size}
    for attempt in range(3):
        try:
            resp = requests.post(API_URL, json=payload, headers=HEADERS, timeout=60)
            data = resp.json()
            if data.get('code') == 200:
                info = data.get('data', {}).get('pageInfo', {})
                return info.get('list', []), info.get('total', 0)
        except Exception as e:
            if attempt < 2:
                print(f"    第{page_num}页请求失败，重试({attempt+1}/3)...")
                import time; time.sleep(3)
            else:
                print(f"    第{page_num}页请求失败: {e}")
    return [], 0


def construct_url(record):
    """构造详情URL — 关键：用 docId 不是 id"""
    # ★ 浏览器实际使用的是 docId 字段
    doc_id = str(record.get('docId', record.get('id', '')))
    dtc = record.get('docTypeCode', '')
    svc = record.get('securityViewCode', '')
    typ = DOC_TYPE_MAP.get(dtc, '7')
    return f"{BASE_URL}/DeclareDetails?id={doc_id}&type={typ}&docTypeCode={dtc}&securityViewCode={svc}"


def fetch_telecom():
    print(f"=== 抓取电信招标 {datetime.now(BJT).strftime('%H:%M:%S')} ===")
    print(f"限定日期: {TODAY}")
    print(f"关键词: {'无过滤' if not KEYWORDS else ' | '.join(KEYWORDS)}")

    results = []
    errors = []
    seen_ids = set()

    records, total = fetch_page(1, 20)
    if not records and total == 0:
        errors.append("API请求失败，无法获取数据")
    print(f"总记录: {total}, 第1页: {len(records)} 条")

    all_records = list(records)
    page_num = 1

    while page_num < 20:
        if all_records:
            last_date = all_records[-1].get('createDate', '')[:10]
            if last_date and last_date < TODAY:
                break
        page_num += 1
        recs, _ = fetch_page(page_num, 20)
        if not recs:
            break
        all_records.extend(recs)
        print(f"第{page_num}页: {len(recs)} 条")

    print(f"\n共获取 {len(all_records)} 条记录")

    today_count = 0
    for record in all_records:
        rid = str(record.get('id', ''))
        if rid in seen_ids:
            continue
        seen_ids.add(rid)

        title = record.get('docTitle', '')
        province = record.get('provinceName', '')
        doc_type = record.get('docType', '')
        create_date = record.get('createDate', '')[:10]

        if create_date != TODAY:
            continue
        today_count += 1

        if KEYWORDS and not any(kw in title for kw in KEYWORDS):
            continue

        url = construct_url(record)
        doc_id = str(record.get('docId', record.get('id', '')))
        print(f"  [✓] {province} | {doc_type} | docId={doc_id} | {title[:45]}...")

        results.append({
            "platform": "电信",
            "province": province or "总部",
            "type": doc_type,
            "company": "中国电信",
            "title": title,
            "url": url,
            "date": create_date
        })

    print(f"\n今天共 {today_count} 条记录，{len(results)} 条匹配")
    print(f"\n{'='*60}")
    print(f"✅ 电信抓取完成: {len(results)} 条")
    for i, r in enumerate(results):
        print(f"  [{i+1}] 【{r['province']}-{r['type']}】{r['title'][:50]}...")
    print(f"{'='*60}")

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    with open("telecom_status.json", 'w', encoding='utf-8') as f:
        json.dump({"errors": errors, "count": len(results)}, f, ensure_ascii=False)

    return len(results)


if __name__ == "__main__":
    fetch_telecom()
