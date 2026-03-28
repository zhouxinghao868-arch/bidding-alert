#!/usr/bin/env python3
"""
电信招标信息抓取 - Playwright浏览器方式
通过搜索页面点击每条记录，从浏览器地址栏获取真实详情URL
"""

import json
import sys
import re
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


# ─── 辅助: API获取类型信息 ───────────────────────────────
def fetch_type_map_via_api():
    """通过API获取今天记录的 title→docType 映射（补充类型信息）"""
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": SEARCH_URL, "Origin": BASE_URL
    }
    title_type = {}
    for pn in range(1, 20):
        try:
            resp = requests.post(API_URL, json={"pageNum": pn, "pageSize": 20},
                                 headers=headers, timeout=60)
            records = resp.json().get('data', {}).get('pageInfo', {}).get('list', [])
            if not records:
                break
            for r in records:
                if r.get('createDate', '')[:10] == TODAY:
                    title_type[r.get('docTitle', '').strip()] = r.get('docType', '公告')
            if records[-1].get('createDate', '')[:10] < TODAY:
                break
        except:
            break
    return title_type


# ─── 主逻辑 ─────────────────────────────────────────────
def fetch_telecom():
    print(f"=== 抓取电信招标 {datetime.now(BJT).strftime('%H:%M:%S')} ===")
    print(f"限定日期: {TODAY}")

    # 1. API 获取类型映射
    print("\n步骤1: API获取记录类型信息...")
    type_map = fetch_type_map_via_api()
    print(f"  API返回 {len(type_map)} 条今天的记录")

    results = []
    seen_titles = set()

    # 2. 浏览器点击获取URL
    print("\n步骤2: 浏览器获取详情URL...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = context.new_page()

        print("  打开搜索页面...")
        page.goto(SEARCH_URL, wait_until="load", timeout=90000)
        time.sleep(8)  # WAF JS-challenge + 首次渲染

        for pg in range(1, 11):
            print(f"\n  ── 搜索第 {pg} 页 ──")

            # 等表格
            try:
                page.wait_for_selector("table tbody tr", timeout=15000)
            except:
                print("    等待表格超时，停止")
                break
            time.sleep(2)

            rows = page.query_selector_all("table tbody tr")
            row_count = len(rows)
            print(f"    共 {row_count} 行")
            if row_count == 0:
                break

            found_today = False
            i = 0

            while i < row_count:
                try:
                    # go_back 后重新获取行
                    cur_rows = page.query_selector_all("table tbody tr")
                    if i >= len(cur_rows):
                        break
                    row = cur_rows[i]
                    cells = row.query_selector_all("td")
                    if len(cells) < 4:
                        i += 1
                        continue

                    date_str = cells[3].inner_text().strip()

                    if date_str != TODAY:
                        if found_today:
                            break  # 已经过了今天区域
                        i += 1
                        continue

                    found_today = True
                    full_title = cells[0].inner_text().strip()

                    # 解析省份
                    province, title = "", full_title
                    m = re.match(r'【(.+?)】\s*(.*)', full_title, re.DOTALL)
                    if m:
                        province, title = m.group(1).strip(), m.group(2).strip()

                    if title in seen_titles:
                        i += 1
                        continue

                    # 关键词过滤
                    if KEYWORDS and not any(kw in title for kw in KEYWORDS):
                        seen_titles.add(title)
                        i += 1
                        continue

                    seen_titles.add(title)

                    # ★ 核心: 点击 → 获取浏览器地址栏URL（带重试）
                    print(f"    [{len(results)+1}] 点击: {full_title[:55]}...")
                    detail_url = None
                    for attempt in range(3):
                        # 每次重试重新获取行（DOM可能变化）
                        retry_rows = page.query_selector_all("table tbody tr")
                        if i >= len(retry_rows):
                            break
                        retry_cells = retry_rows[i].query_selector_all("td")
                        if not retry_cells:
                            break

                        retry_cells[0].click()
                        time.sleep(5)

                        cur_url = page.url
                        if cur_url != SEARCH_URL and "search" not in cur_url:
                            detail_url = cur_url
                            print(f"        ✓ {detail_url[:90]}")
                            break

                        if attempt < 2:
                            print(f"        未跳转，重试({attempt+2}/3)...")

                    if not detail_url:
                        print(f"        ✗ 跳过（多次点击仍未跳转）")
                        i += 1
                        continue

                    results.append({
                        "platform": "电信",
                        "province": province or "总部",
                        "type": type_map.get(title, "公告"),
                        "company": "中国电信",
                        "title": title,
                        "url": detail_url,
                        "date": date_str
                    })

                    # 返回搜索页
                    page.go_back()
                    try:
                        page.wait_for_selector("table tbody tr", timeout=15000)
                    except:
                        # 恢复失败则重新导航
                        page.goto(SEARCH_URL, wait_until="load", timeout=60000)
                        time.sleep(6)
                    time.sleep(2)

                except Exception as e:
                    print(f"    第{i}行出错: {e}")
                    if "search" not in page.url:
                        try:
                            page.goto(SEARCH_URL, wait_until="load", timeout=60000)
                            time.sleep(6)
                        except:
                            pass

                i += 1

            if not found_today:
                print("    本页无今天数据，停止翻页")
                break

            # 翻页
            try:
                next_btn = page.query_selector(
                    "button.btn-next:not([disabled]), "
                    ".el-pagination .btn-next:not([disabled])"
                )
                if next_btn:
                    next_btn.click()
                    time.sleep(4)
                else:
                    print("    没有下一页")
                    break
            except Exception as e:
                print(f"    翻页出错: {e}")
                break

        browser.close()

    # 保存
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"今天共 {len(seen_titles)} 条记录，{len(results)} 条匹配")
    print(f"✅ 电信抓取完成: {len(results)} 条")
    for idx, r in enumerate(results):
        print(f"  [{idx+1}] 【{r['province']}-{r['type']}】{r['title'][:50]}...")
    print(f"{'='*60}")
    return len(results)


if __name__ == "__main__":
    fetch_telecom()
