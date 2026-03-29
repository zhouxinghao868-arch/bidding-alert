#!/usr/bin/env python3
"""
电信招标信息抓取 - 纯页面DOM抓取
直接读取搜索页面表格数据，不依赖API拦截
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

SEARCH_URL = "https://caigou.chinatelecom.com.cn/search"

UA_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


def fetch_telecom():
    print(f"=== 抓取电信招标 {datetime.now(BJT).strftime('%H:%M:%S')} ===")
    print(f"限定日期: {TODAY}")
    print(f"关键词: {' | '.join(KEYWORDS)}")

    results = []
    errors = []
    seen_titles = set()
    today_count = 0

    ua = random.choice(UA_LIST)
    print(f"UA: {ua[:50]}...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=ua,
            viewport={"width": 1920, "height": 1080}
        )
        page = context.new_page()

        try:
            print("\n打开搜索页面...")
            page.goto(SEARCH_URL, wait_until="domcontentloaded", timeout=90000)
            time.sleep(8)

            empty_streak = 0

            for pg in range(1, 30):
                # 读取当前页表格行
                rows = page.query_selector_all('.el-table__row')
                if not rows:
                    print(f"  第{pg}页: 无数据行，停止")
                    break

                page_today = 0
                for row in rows:
                    try:
                        # 省份
                        prov_el = row.query_selector('.noticeTitleProvince')
                        province = prov_el.inner_text().strip().strip('【】') if prov_el else '总部'

                        # 标题
                        title_el = row.query_selector('.noticeTitle')
                        title = title_el.inner_text().strip() if title_el else ''

                        # 发布日期（第4列）
                        tds = row.query_selector_all('td')
                        date_str = tds[3].inner_text().strip() if len(tds) >= 4 else ''

                        if not title or not date_str:
                            continue

                        if date_str != TODAY:
                            continue
                        page_today += 1
                        today_count += 1

                        # 去重
                        if title in seen_titles:
                            continue
                        seen_titles.add(title)

                        # 关键词匹配
                        if KEYWORDS and not any(kw in title for kw in KEYWORDS):
                            continue

                        # 构造搜索URL（不点击行，避免干扰翻页）
                        detail_url = f"https://caigou.chinatelecom.com.cn/search?keyword={title[:30]}"

                        print(f"  [✓] {province} | {title[:50]}...")

                        results.append({
                            "platform": "电信",
                            "province": province,
                            "type": "公告",
                            "company": "中国电信",
                            "title": title,
                            "url": detail_url,
                            "date": date_str
                        })
                    except Exception as e:
                        continue

                print(f"  第{pg}页: {len(rows)}行, 今日{page_today}条")

                # 停止条件
                if page_today == 0:
                    empty_streak += 1
                    if empty_streak >= 3:
                        print(f"\n  连续{empty_streak}页无今天数据，停止翻页")
                        break
                else:
                    empty_streak = 0

                # 翻页
                try:
                    next_btn = page.query_selector('button.btn-next:not([disabled])')
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

    # 保存结果
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    with open("telecom_status.json", 'w', encoding='utf-8') as f:
        json.dump({"errors": errors, "count": len(results)}, f, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"今天共 {today_count} 条记录，{len(results)} 条匹配")
    print(f"✅ 电信抓取完成: {len(results)} 条")
    for i, r in enumerate(results):
        print(f"  [{i+1}] 【{r['province']}】{r['title'][:50]}...")
    print(f"{'='*60}")
    return len(results)


if __name__ == "__main__":
    fetch_telecom()
