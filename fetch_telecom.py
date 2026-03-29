#!/usr/bin/env python3
"""
电信招标信息抓取 - 双模式（API拦截优先 + DOM降级）
模式1: 拦截queryListNew API响应获取结构化数据（白天稳定）
模式2: 直接读取页面DOM表格（API失败时降级）
"""

import json
import os
import sys
import time
import random
from datetime import datetime, timezone, timedelta
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(line_buffering=True)

OUTPUT_FILE = "telecom_bids.json"
KEYWORDS = ["数智化", "数据", "算力", "战略", "算网", "软件开发", "云智算", "DICT", "ICT", "业务支撑"]
BJT = timezone(timedelta(hours=8))
TODAY = os.environ.get("BIDDING_DATE") or datetime.now(BJT).strftime("%Y-%m-%d")

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


def construct_api_url(record):
    """用API数据中的docId构造详情URL"""
    doc_id = str(record.get('docId', record.get('id', '')))
    dtc = record.get('docTypeCode', '')
    svc = record.get('securityViewCode', '')
    typ = DOC_TYPE_MAP.get(dtc, '7')
    return f"{BASE_URL}/DeclareDetails?id={doc_id}&type={typ}&docTypeCode={dtc}&securityViewCode={svc}"


def mode_api(page, context):
    """模式1: API拦截抓取"""
    api_data = []
    seen_ids = set()
    results = []
    today_count = 0

    def on_response(response):
        try:
            if "queryListNew" in response.url and response.status == 200:
                body = response.json()
                records = (body.get("data") or {}).get("pageInfo", {}).get("list", [])
                if records:
                    api_data.extend(records)
                    tc = sum(1 for r in records if (r.get("createDate", "") or "")[:10] == TODAY)
                    print(f"    拦截到 {len(records)} 条 (今天{tc}条, 累计{len(api_data)}条)")
        except:
            pass

    page.on("response", on_response)

    # 首页加载触发API
    page.goto(SEARCH_URL, wait_until="domcontentloaded", timeout=90000)
    time.sleep(8)
    print(f"  首页拦截: {len(api_data)} 条")

    if len(api_data) == 0:
        page.remove_listener("response", on_response)
        return None  # API失败，触发降级

    # 翻页
    empty_streak = 0
    for pg in range(2, 30):
        last_batch = api_data[-20:] if len(api_data) >= 20 else api_data
        today_in_batch = sum(1 for r in last_batch if (r.get("createDate", "") or "")[:10] == TODAY)
        if today_in_batch == 0:
            empty_streak += 1
            if empty_streak >= 3:
                print(f"  连续{empty_streak}页无今天数据，停止翻页")
                break
        else:
            empty_streak = 0

        try:
            next_btn = page.query_selector('button.btn-next:not([disabled])')
            if not next_btn:
                break
            next_btn.click()
            time.sleep(3)
        except:
            break

    page.remove_listener("response", on_response)
    print(f"  API模式共拦截 {len(api_data)} 条")

    # 过滤
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

        results.append({
            "platform": "电信",
            "province": record.get('provinceName', '') or '总部',
            "type": record.get('docType', '公告'),
            "company": "中国电信",
            "title": title,
            "url": construct_api_url(record),
            "date": create_date
        })

    return {"results": results, "today_count": today_count, "mode": "API"}


def mode_dom(page):
    """模式2: 页面DOM抓取（降级方案）"""
    results = []
    seen_titles = set()
    today_count = 0

    try:
        # 如果页面还没打开（API模式没打开过），先打开
        if "search" not in page.url:
            page.goto(SEARCH_URL, wait_until="domcontentloaded", timeout=90000)
            time.sleep(8)
    except:
        page.goto(SEARCH_URL, wait_until="domcontentloaded", timeout=90000)
        time.sleep(8)

    empty_streak = 0

    for pg in range(1, 30):
        rows = page.query_selector_all('.el-table__row')
        if not rows:
            print(f"  第{pg}页: 无数据行，停止")
            break

        page_today = 0
        for row in rows:
            try:
                prov_el = row.query_selector('.noticeTitleProvince')
                province = prov_el.inner_text().strip().strip('【】') if prov_el else '总部'

                title_el = row.query_selector('.noticeTitle')
                title = title_el.inner_text().strip() if title_el else ''

                tds = row.query_selector_all('td')
                date_str = tds[3].inner_text().strip() if len(tds) >= 4 else ''

                if not title or not date_str:
                    continue
                if date_str != TODAY:
                    continue
                page_today += 1
                today_count += 1

                if title in seen_titles:
                    continue
                seen_titles.add(title)

                if KEYWORDS and not any(kw in title for kw in KEYWORDS):
                    continue

                print(f"  [✓] {province} | {title[:50]}...")
                results.append({
                    "platform": "电信",
                    "province": province,
                    "type": "公告",
                    "company": "中国电信",
                    "title": title,
                    "url": f"{SEARCH_URL}",
                    "date": date_str
                })
            except:
                continue

        print(f"  第{pg}页: {len(rows)}行, 今日{page_today}条")

        if page_today == 0:
            empty_streak += 1
            if empty_streak >= 3:
                print(f"  连续{empty_streak}页无今天数据，停止翻页")
                break
        else:
            empty_streak = 0

        # 翻页：先尝试btn-next，再尝试点击下一个页码
        try:
            next_btn = page.query_selector('button.btn-next:not([disabled])')
            if next_btn:
                next_btn.click()
            else:
                # 降级：点击当前页码+1的数字按钮
                active = page.query_selector('.el-pager .active')
                if active:
                    current_num = int(active.inner_text().strip())
                    next_num = page.query_selector(f'.el-pager li.number:text-is("{current_num + 1}")')
                    if next_num:
                        next_num.click()
                    else:
                        print(f"  已到最后一页，停止")
                        break
                else:
                    break
            time.sleep(3)
        except Exception as e:
            print(f"  翻页出错: {e}")
            break

    return {"results": results, "today_count": today_count, "mode": "DOM"}


def fetch_telecom():
    print(f"=== 抓取电信招标 {datetime.now(BJT).strftime('%H:%M:%S')} ===")
    print(f"限定日期: {TODAY}")
    print(f"关键词: {' | '.join(KEYWORDS)}")

    errors = []
    ua = random.choice(UA_LIST)
    print(f"UA: {ua[:50]}...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=ua,
            viewport={"width": 1920, "height": 1080}
        )
        page = context.new_page()

        data = None

        # 模式1: API拦截
        try:
            print("\n[模式1] API拦截抓取...")
            data = mode_api(page, context)
            if data is None:
                print("  API未拦截到数据，降级到DOM模式")
        except Exception as e:
            print(f"  API模式异常: {e}")
            errors.append(f"API: {e}")

        # 模式2: DOM降级
        if data is None:
            try:
                print("\n[模式2] DOM页面抓取...")
                data = mode_dom(page)
            except Exception as e:
                print(f"  DOM模式异常: {e}")
                errors.append(f"DOM: {e}")
                data = {"results": [], "today_count": 0, "mode": "失败"}

        browser.close()

    results = data["results"]
    today_count = data["today_count"]
    mode = data["mode"]

    # 保存
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    with open("telecom_status.json", 'w', encoding='utf-8') as f:
        json.dump({"errors": errors, "count": len(results), "mode": mode}, f, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"[{mode}模式] 今天共 {today_count} 条记录，{len(results)} 条匹配")
    print(f"✅ 电信抓取完成: {len(results)} 条")
    for i, r in enumerate(results):
        print(f"  [{i+1}] 【{r['province']}】{r['title'][:50]}...")
    print(f"{'='*60}")
    return len(results)


if __name__ == "__main__":
    fetch_telecom()
