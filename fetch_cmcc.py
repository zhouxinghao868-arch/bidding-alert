#!/usr/bin/env python3
"""
移动招标信息抓取 - 独立运行
结果保存到 cmcc_bids.json
"""

import json
import os
import hashlib
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dateutil import parser as date_parser

from playwright.sync_api import sync_playwright

FETCH_HOURS = int(os.getenv("FETCH_HOURS", "48"))
OUTPUT_FILE = "cmcc_bids.json"
KEYWORDS = ["数智化", "数据", "算力", "战略"]

CMCC_BID_TYPE_MAP = {
    "CANDIDATE_PUBLICITY": "候选人公示",
    "WIN_BID": "中选结果公示",
    "WIN_BID_PUBLICITY": "中选结果公示",
    "BIDDING": "采购公告",
    "BIDDING_PROCUREMENT": "采购公告",
    "PROCUREMENT": "直接采购公示",
    "PREQUALIFICATION": "资格预审公告",
}


def match_keywords(text: str) -> bool:
    if not text:
        return False
    return any(kw in text for kw in KEYWORDS)


def extract_province(text: str) -> str:
    if not text:
        return "全国"
    provinces = ["北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江",
                 "上海", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南",
                 "湖北", "湖南", "广东", "广西", "海南", "重庆", "四川", "贵州",
                 "云南", "西藏", "陕西", "甘肃", "青海", "宁夏", "新疆"]
    for p in provinces:
        if p in text:
            return p
    return "全国"


def fetch_cmcc():
    print(f"=== 抓取中国移动招标信息 {datetime.now().strftime('%H:%M:%S')} ===")
    
    results = []
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={"width": 1920, "height": 1080},
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    )
    
    urls = [
        ("https://b2b.10086.cn/#/biddingProcurementBulletin", "招标采购公告"),
        ("https://b2b.10086.cn/#/procurementServices", "采购意见征求公告")
    ]
    
    for url, page_name in urls:
        print(f"\n正在访问: {page_name}")
        page = context.new_page()
        
        try:
            page.goto(url, wait_until="networkidle", timeout=90000)
            time.sleep(8)
            
            rows = page.locator("tr.ant-table-row").all()
            print(f"  找到 {len(rows)} 条记录")
            
            for row in rows:
                try:
                    cells = row.locator("td").all()
                    if len(cells) < 4:
                        continue
                    
                    bid_type = cells[0].inner_text().strip()
                    company = cells[1].inner_text().strip()
                    title = cells[2].inner_text().strip()
                    date_str = cells[3].inner_text().strip()
                    
                    if not match_keywords(title) and not match_keywords(company):
                        continue
                    
                    title_link = cells[2].locator("a").first
                    if not title_link:
                        continue
                    
                    title_link.click()
                    time.sleep(2)
                    
                    detail_page = context.pages[-1]
                    detail_url = detail_page.url
                    detail_page.close()
                    time.sleep(1)
                    
                    # 时间检查
                    try:
                        bid_date = parser.parse(date_str)
                        cutoff = datetime.now() - timedelta(hours=FETCH_HOURS)
                        if bid_date < cutoff:
                            continue
                    except:
                        pass
                    
                    bid_type_cn = "其他"
                    for key, value in CMCC_BID_TYPE_MAP.items():
                        if key in detail_url:
                            bid_type_cn = value
                            break
                    
                    results.append({
                        "platform": "移动",
                        "province": extract_province(company),
                        "type": bid_type_cn,
                        "company": company,
                        "title": title,
                        "url": detail_url,
                        "date": date_str
                    })
                    print(f"  ✓ 匹配: {title[:40]}...")
                    
                except Exception as e:
                    continue
                    
        except Exception as e:
            print(f"  抓取失败: {e}")
        finally:
            page.close()
    
    browser.close()
    playwright.stop()
    
    # 保存结果
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 移动招标抓取完成: {len(results)} 条")
    return len(results)


if __name__ == "__main__":
    from dateutil import parser
    fetch_cmcc()
