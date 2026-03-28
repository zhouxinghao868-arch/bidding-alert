#!/usr/bin/env python3
"""
电信招标信息抓取 - 纯API调用（无需浏览器）
直接调用 /portal/base/announcementJoin/queryListNew
"""

import json
import sys
import requests
from datetime import datetime, timezone, timedelta

sys.stdout.reconfigure(line_buffering=True)

OUTPUT_FILE = "telecom_bids.json"
KEYWORDS = []  # 不做关键词过滤，抓取所有当天记录
BJT = timezone(timedelta(hours=8))
TODAY = datetime.now(BJT).strftime("%Y-%m-%d")

API_URL = "https://caigou.chinatelecom.com.cn/portal/base/announcementJoin/queryListNew"
BASE_URL = "https://caigou.chinatelecom.com.cn"
HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://caigou.chinatelecom.com.cn/search",
    "Origin": "https://caigou.chinatelecom.com.cn"
}

# docTypeCode → type 映射（详情页URL必须参数）
DOC_TYPE_MAP = {
    "TenderAnnouncement": "1",
    "PurchaseAnnounceBasic": "2",
    "PurchaseAnnounc": "2",
    "CompareSelect": "3",
    "NegotiationSelect": "5",
    "Prequalfication": "6",
    "ResultAnnounc": "7",
    "TerminationAnnounc": "15",
    "AuctionAnnounce": "19",
    "SingleSource": "2",
}

def fetch_page(page_num, page_size=20):
    """获取一页数据，带重试"""
    payload = {"pageNum": page_num, "pageSize": page_size}
    for attempt in range(3):
        try:
            resp = requests.post(API_URL, json=payload, headers=HEADERS, timeout=60)
            data = resp.json()
            if data.get('code') == 200:
                page_info = data.get('data', {}).get('pageInfo', {})
                return page_info.get('list', []), page_info.get('total', 0)
        except Exception as e:
            if attempt < 2:
                print(f"    第{page_num}页请求失败，重试({attempt+1}/3)...")
                import time; time.sleep(3)
            else:
                print(f"    第{page_num}页请求失败: {e}")
    return [], 0

def fetch_telecom():
    print(f"=== 抓取电信招标 {datetime.now(BJT).strftime('%H:%M:%S')} ===")
    print(f"限定日期: {TODAY}")
    print(f"关键词: {' | '.join(KEYWORDS)}")
    
    results = []
    seen_ids = set()
    
    try:
        # 第1页
        records, total = fetch_page(1, 20)
        print(f"总记录: {total}, 第1页: {len(records)} 条")
        
        all_records = list(records)
        
        # 翻页 - 直到没有今天的记录
        page_num = 1
        max_pages = 20
        
        while page_num < max_pages:
            # 检查最后一条是否还是今天
            if all_records:
                last_date = all_records[-1].get('createDate', '')[:10]
                if last_date and last_date < TODAY:
                    print(f"最后记录日期 {last_date}，停止翻页")
                    break
            
            page_num += 1
            records, _ = fetch_page(page_num, 20)
            if not records:
                break
            
            all_records.extend(records)
            print(f"第{page_num}页: {len(records)} 条")
        
        print(f"\n共获取 {len(all_records)} 条记录")
        
        # 过滤
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
            
            # 日期过滤
            if create_date != TODAY:
                continue
            today_count += 1
            
            # 关键词匹配
            if KEYWORDS and not any(kw in title for kw in KEYWORDS):
                continue
            
            print(f"  [✓] {province} | {doc_type} | {title[:50]}...")
            
            results.append({
                "platform": "电信",
                "province": province or "总部",
                "type": doc_type,
                "company": "中国电信",
                "title": title,
                "url": f"{BASE_URL}/DeclareDetails?id={rid}&type={DOC_TYPE_MAP.get(record.get('docTypeCode',''), '7')}&docTypeCode={record.get('docTypeCode','')}&securityViewCode={record.get('securityViewCode','')}",
                "date": create_date
            })
        
        print(f"\n今天共 {today_count} 条记录，{len(results)} 条匹配关键词")
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*60}")
    print(f"✅ 电信抓取完成: {len(results)} 条匹配关键词的记录")
    for i, r in enumerate(results):
        print(f"  [{i+1}] 【{r['province']}-{r['type']}】{r['title'][:50]}...")
    print(f"{'='*60}")
    
    return len(results)

if __name__ == "__main__":
    fetch_telecom()
