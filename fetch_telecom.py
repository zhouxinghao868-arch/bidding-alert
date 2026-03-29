#!/usr/bin/env python3
"""
电信招标信息抓取 - Playwright浏览器 + API拦截
浏览器打开搜索页面（过WAF），拦截queryListNew响应获取完整数据
用docId构造详情URL
"""

import json
import sys
import re
import time
import random
from datetime import datetime, timezone, timedelta
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(line_buffering=True)

OUTPUT_FILE = "telecom_bids.json"
KEYWORDS = ["数智化", "数据", "算力", "战略", "算网", "软件开发", "云智算", "DICT", "ICT", "业务支撑"]
BJT = timezone(timedelta(hours=8))
TODAY = datetime.now(BJT).strftime("%Y-%m-%d")

BASE_URL = "https://caigou.chinatelecom.com.cn"
SEARCH_URL = f"{BASE_URL}/search"

UA_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

DOC_TYPE_MAP = {
    "TenderAnnouncement": "1", "PurchaseAnnounceBasic": "2",
    "PurchaseAnnounc": "2", "CompareSelect": "3",
    "NegotiationSelect": "5", "Prequalfication": "6",
    "ResultAnnounc": "7", "TerminationAnnounc": "15",
    "AuctionAnnounce": "19", "SingleSource": "2",
}


def construct_url(record):
    """用docId构造详情URL"""
    doc_id = str(record.get('docId', record.get('id', '')))
    dtc = record.get('docTypeCode', '')
    svc = record.get('securityViewCode', '')
    typ = DOC_TYPE_MAP.get(dtc, '7')
    return f"{BASE_URL}/DeclareDetails?id={doc_id}&type={typ}&docTypeCode={dtc}&securityViewCode={svc}"


def fetch_telecom():
    print(f"=== 抓取电信招标 {datetime.now(BJT).strftime('%H:%M:%S')} ===")
    print(f"限定日期: {TODAY}")

    results = []
    errors = []
    seen_ids = set()
    api_data = []  # API拦截获取的原始数据

    def on_response(response):
        """拦截搜索列表API响应"""
        try:
            if "queryListNew" in response.url and response.status == 200:
                body = response.json()
                records = (body.get("data") or {}).get("pageInfo", {}).get("list", [])
                if records:
                    api_data.extend(records)
                    today_count = sum(1 for r in records if (r.get("createDate", "") or "")[:10] == TODAY)
                    print(f"    拦截到 {len(records)} 条 (今天{today_count}条, 累计拦截{len(api_data)}条)")
        except:
            pass

    ua = random.choice(UA_LIST)
    print(f"UA: {ua[:50]}...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=ua,
            viewport={"width": 1920, "height": 1080}
        )
        page = context.new_page()
        page.on("response", on_response)

        try:
            # 打开搜索页面（触发第1页API请求）
            print("\n打开搜索页面...")
            page.goto(SEARCH_URL, wait_until="domcontentloaded", timeout=90000)
            time.sleep(8)
            print(f"  首页加载完成, 已拦截 {len(api_data)} 条")

            # 翻页获取更多数据
            empty_streak = 0
            for pg in range(2, 30):
                # 检查上一批数据是否有今天的
                last_batch = api_data[-20:] if len(api_data) >= 20 else api_data
                today_in_batch = sum(1 for r in last_batch if (r.get("createDate", "") or "")[:10] == TODAY)

                if today_in_batch == 0:
                    empty_streak += 1
                    if empty_streak >= 3:
                        print(f"\n  连续{empty_streak}页无今天数据，停止翻页")
                        break
                else:
                    empty_streak = 0

                # 点击下一页
                try:
                    next_btn = page.query_selector("button.btn-next:not([disabled])")
                    if not next_btn:
                        print(f"\n  没有下一页按钮，停止")
                        break
                    next_btn.click()
                    time.sleep(3)
                except Exception as e:
                    print(f"\n  翻页出错: {e}")
                    break

        except Exception as e:
            print(f"\n浏览器错误: {e}")
            errors.append(str(e))

        browser.close()

    # 从拦截的API数据中过滤今天的记录
    print(f"\n共拦截 {len(api_data)} 条API数据")
    today_count = 0
    for record in api_data:
        rid = str(record.get('id', ''))
        if rid in seen_ids:
            continue
        seen_ids.add(rid)

        create_date = (record.get('createDate', '') or '')[:10]
        if create_date != TODAY:
            continue
        today_count += 1

        title = record.get('docTitle', '')
        if KEYWORDS and not any(kw in title for kw in KEYWORDS):
            continue

        url = construct_url(record)
        doc_id = str(record.get('docId', record.get('id', '')))
        province = record.get('provinceName', '') or '总部'
        doc_type = record.get('docType', '公告')

        print(f"  [✓] {province} | {doc_type} | docId={doc_id} | {title[:40]}...")

        results.append({
            "platform": "电信",
            "province": province,
            "type": doc_type,
            "company": "中国电信",
            "title": title,
            "url": url,
            "date": create_date
        })

    # 保存结果
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    with open("telecom_status.json", 'w', encoding='utf-8') as f:
        json.dump({"errors": errors, "count": len(results)}, f, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"今天共 {today_count} 条记录，{len(results)} 条匹配")
    print(f"✅ 电信抓取完成: {len(results)} 条")
    for i, r in enumerate(results):
        print(f"  [{i+1}] 【{r['province']}-{r['type']}】{r['title'][:50]}...")
    print(f"{'='*60}")
    return len(results)


if __name__ == "__main__":
    fetch_telecom()
