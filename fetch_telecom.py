#!/usr/bin/env python3
"""
电信招标信息抓取 - API + Playwright验证
1. API快速获取今天的记录列表
2. Playwright打开搜索页建立cookie
3. 逐个导航到详情页获取浏览器实际URL
"""

import json
import sys
import time
import requests
from datetime import datetime, timezone, timedelta
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(line_buffering=True)

OUTPUT_FILE = "telecom_bids.json"
KEYWORDS = []  # 空=不过滤
BJT = timezone(timedelta(hours=8))
TODAY = datetime.now(BJT).strftime("%Y-%m-%d")

BASE_URL = "https://caigou.chinatelecom.com.cn"
SEARCH_URL = f"{BASE_URL}/search"
API_URL = f"{BASE_URL}/portal/base/announcementJoin/queryListNew"
HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": SEARCH_URL, "Origin": BASE_URL
}

DOC_TYPE_MAP = {
    "TenderAnnouncement": "1", "PurchaseAnnounceBasic": "2",
    "PurchaseAnnounc": "2", "CompareSelect": "3",
    "NegotiationSelect": "5", "Prequalfication": "6",
    "ResultAnnounc": "7", "TerminationAnnounc": "15",
    "AuctionAnnounce": "19", "SingleSource": "2",
}


def fetch_today_via_api():
    """API获取今天的全部记录"""
    all_records = []
    for pn in range(1, 20):
        try:
            resp = requests.post(API_URL, json={"pageNum": pn, "pageSize": 20},
                                 headers=HEADERS, timeout=60)
            data = resp.json()
            records = data.get('data', {}).get('pageInfo', {}).get('list', [])
            if not records:
                break
            all_records.extend(records)
            total = data.get('data', {}).get('pageInfo', {}).get('total', 0)
            if pn == 1:
                print(f"  总记录: {total}, 第1页: {len(records)} 条")
            else:
                print(f"  第{pn}页: {len(records)} 条")
            if records[-1].get('createDate', '')[:10] < TODAY:
                break
        except Exception as e:
            print(f"  API第{pn}页失败: {e}")
            break
    
    # 过滤今天+去重
    seen = set()
    today = []
    for r in all_records:
        if r.get('createDate', '')[:10] != TODAY:
            continue
        rid = str(r.get('id', ''))
        if rid in seen:
            continue
        seen.add(rid)
        today.append(r)
    return today


def construct_url(record):
    """用API数据构造详情URL"""
    rid = str(record.get('id', ''))
    dtc = record.get('docTypeCode', '')
    svc = record.get('securityViewCode', '')
    typ = DOC_TYPE_MAP.get(dtc, '7')
    return f"{BASE_URL}/DeclareDetails?id={rid}&type={typ}&docTypeCode={dtc}&securityViewCode={svc}"


def fetch_telecom():
    print(f"=== 抓取电信招标 {datetime.now(BJT).strftime('%H:%M:%S')} ===")
    print(f"限定日期: {TODAY}")

    # 1. API获取今天记录
    print("\n步骤1: API获取今天的记录...")
    api_records = fetch_today_via_api()
    print(f"  共 {len(api_records)} 条今天的记录")

    if not api_records:
        print("  无数据")
        with open(OUTPUT_FILE, 'w') as f:
            json.dump([], f)
        return 0

    # 2. 关键词过滤
    filtered = []
    for r in api_records:
        title = r.get('docTitle', '')
        if KEYWORDS and not any(kw in title for kw in KEYWORDS):
            continue
        filtered.append(r)
    print(f"  关键词过滤后: {len(filtered)} 条")

    # 3. Playwright浏览器：先建立cookie，再逐个验证URL
    print("\n步骤2: 浏览器验证详情URL...")
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = context.new_page()

        # 先访问搜索页面，通过WAF challenge，建立cookie
        print("  打开搜索页面建立cookie...")
        try:
            page.goto(SEARCH_URL, wait_until="load", timeout=90000)
            time.sleep(8)
            print("  ✓ 搜索页面已加载")
        except Exception as e:
            print(f"  ✗ 搜索页面加载失败: {e}")

        # 逐个导航到详情页获取浏览器实际URL
        for idx, record in enumerate(filtered):
            title = record.get('docTitle', '').strip()
            province = record.get('provinceName', '') or '总部'
            doc_type = record.get('docType', '公告')
            date_str = record.get('createDate', '')[:10]

            constructed = construct_url(record)
            print(f"\n  [{idx+1}/{len(filtered)}] 【{province}】{title[:50]}...")
            print(f"    构造URL: ...{constructed[-60:]}")

            # 导航到详情页
            actual_url = constructed  # fallback
            try:
                page.goto(constructed, wait_until="load", timeout=30000)
                time.sleep(4)
                actual_url = page.url

                if "DeclareDetails" in actual_url:
                    print(f"    ✓ 浏览器URL: ...{actual_url[-60:]}")
                elif actual_url == constructed:
                    print(f"    ✓ URL未变（SPA路由正常）")
                else:
                    print(f"    ⚠ 被重定向到: {actual_url[:80]}")
                    # 即使被重定向也用构造的URL（浏览器有cookie时能打开）
                    actual_url = constructed
            except Exception as e:
                print(f"    ✗ 导航失败: {e}，使用构造URL")

            results.append({
                "platform": "电信",
                "province": province,
                "type": doc_type,
                "company": "中国电信",
                "title": title,
                "url": actual_url,
                "date": date_str
            })

        browser.close()

    # 保存
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"今天共 {len(api_records)} 条记录，{len(results)} 条匹配")
    print(f"✅ 电信抓取完成: {len(results)} 条")
    for i, r in enumerate(results):
        print(f"  [{i+1}] 【{r['province']}-{r['type']}】{r['title'][:50]}...")
    print(f"{'='*60}")
    return len(results)


if __name__ == "__main__":
    fetch_telecom()
