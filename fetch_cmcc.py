#!/usr/bin/env python3
"""
移动招标信息抓取 - 两个网页完整抓取
1. 招标采购公告 (biddingProcurementBulletin) - 直接抓取
2. 采购服务 (procurementServices) - 6个子分类逐个切换抓取
   信息核查公告/信息核查结果公示/采购意见征求公告/测试公告/招募甄选合作公告/招募甄选合作结果公告
"""

import json
import sys
import time
import random
from datetime import datetime, timezone, timedelta
from playwright.sync_api import sync_playwright

# UA轮换池
UA_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

def rand_sleep(lo=2, hi=5):
    """随机延迟"""
    t = random.uniform(lo, hi)
    time.sleep(t)

sys.stdout.reconfigure(line_buffering=True)

OUTPUT_FILE = "cmcc_bids.json"
KEYWORDS = []  # 不做关键词过滤，抓取所有当天记录
BJT = timezone(timedelta(hours=8))
TODAY = datetime.now(BJT).strftime("%Y-%m-%d")

# 招标采购公告的5个子分类
BIDDING_TABS = [
    "采购公告",
    "资格预审公告",
    "候选人公示",
    "中选结果公示",
    "直接采购公告",
]

# 采购服务的6个子分类
PROCUREMENT_SERVICE_TABS = [
    "信息核查公告",
    "信息核查结果公示",
    "采购意见征求公告",
    "测试公告",
    "招募甄选合作公告",
    "招募甄选合作结果公告",
]

def get_detail_url(context, row):
    """点击行获取详情页URL"""
    try:
        pages_before = len(context.pages)
        row.click()
        rand_sleep(2, 4)
        if len(context.pages) > pages_before:
            new_page = context.pages[-1]
            url = new_page.url
            new_page.close()
            rand_sleep(1, 2)
            return url
    except:
        pass
    return ""

def scrape_current_table(page, context, name):
    """抓取当前表格中所有当天匹配关键词的记录（含翻页）"""
    results = []
    page_num = 1
    max_pages = 30

    while page_num <= max_pages:
        print(f"\n  第 {page_num} 页:")
        rand_sleep(2, 4)

        rows = page.locator(".cmcc-table-row").all()
        print(f"    找到 {len(rows)} 条记录")

        if len(rows) == 0:
            print(f"    空页，停止")
            break

        page_has_today = False
        matched_indices = []
        earliest_date_on_page = None

        for i, row in enumerate(rows):
            try:
                cells = row.locator("td").all()
                if len(cells) < 4:
                    continue
                company = cells[0].inner_text().strip()
                bid_type = cells[1].inner_text().strip()
                title = cells[2].inner_text().strip()
                if title.startswith("NEW "):
                    title = title[4:]
                date_str = cells[3].inner_text().strip()

                if earliest_date_on_page is None or date_str < earliest_date_on_page:
                    earliest_date_on_page = date_str

                if date_str != TODAY:
                    continue
                page_has_today = True

                if not KEYWORDS or any(kw in title for kw in KEYWORDS):
                    matched_indices.append((i, company, bid_type, title, date_str))
                    print(f"    [✓] {company} | {title[:50]}...")
            except:
                continue

        # 停止条件
        if earliest_date_on_page and earliest_date_on_page < TODAY:
            if not page_has_today:
                print(f"    本页无今天记录 (最早: {earliest_date_on_page})，停止")
                break

        # 获取URL
        for idx, company, bid_type, title, date_str in matched_indices:
            print(f"    → 获取URL: {title[:40]}...")
            rows = page.locator(".cmcc-table-row").all()
            if idx < len(rows):
                detail_url = get_detail_url(context, rows[idx])
                print(f"      URL: {detail_url[:80]}..." if detail_url else "      URL: 获取失败")
            else:
                detail_url = ""
            results.append({
                "platform": "移动",
                "province": company,
                "type": bid_type,
                "company": company,
                "title": title,
                "url": detail_url or "https://b2b.10086.cn",
                "date": date_str
            })

        if earliest_date_on_page and earliest_date_on_page < TODAY:
            print(f"    本页已出现旧日期 ({earliest_date_on_page})，停止")
            break

        # 翻页
        try:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            rand_sleep(2, 4)
            next_btn = page.locator(f".cmcc-page-item[title='{page_num + 1}']").first
            if next_btn.count() > 0:
                next_btn.click()
                rand_sleep(2, 4)
                page_num += 1
            else:
                next_arrow = page.locator(".cmcc-page-next").first
                if next_arrow.count() > 0 and "cmcc-page-disabled" not in (next_arrow.get_attribute("class") or ""):
                    next_arrow.click()
                    rand_sleep(2, 4)
                    page_num += 1
                else:
                    print(f"    已到最后一页")
                    break
        except Exception as e:
            print(f"    翻页异常: {e}")
            break

    print(f"  {name} 完成: {len(results)} 条匹配 (翻了{page_num}页)")
    return results

def click_left_nav_tab(page, tab_name):
    """点击采购服务页面左侧导航中的子分类标签"""
    try:
        # 方法1: 通过text在div.left下查找
        tab = page.locator(f"div.left >> text='{tab_name}'").first
        if tab.count() > 0:
            tab.click()
            rand_sleep(2, 4)
            return True
    except:
        pass
    
    try:
        # 方法2: 用evaluate精确查找并点击
        clicked = page.evaluate(f"""() => {{
            const divs = document.querySelectorAll('div.left div, div.left span');
            for (const d of divs) {{
                if (d.innerText.trim() === '{tab_name}') {{
                    d.click();
                    return true;
                }}
            }}
            return false;
        }}""")
        if clicked:
            rand_sleep(2, 4)
            return True
    except:
        pass
    
    return False

def fetch_cmcc():
    print(f"=== 抓取移动招标 {datetime.now(BJT).strftime('%H:%M:%S')} ===")
    print(f"限定日期: {TODAY}")
    print(f"关键词: {' | '.join(KEYWORDS)}")

    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=True)
    ua = random.choice(UA_LIST)
    print(f"UA: {ua[:50]}...")
    context = browser.new_context(viewport={"width": 1920, "height": 1080}, user_agent=ua)
    page = context.new_page()

    all_results = []
    errors = []

    # ========== 第一个网页：招标采购公告（5个子分类） ==========
    print(f"\n{'='*60}")
    print(f"开始抓取: 招标采购公告 (共{len(BIDDING_TABS)}个子分类)")
    print(f"{'='*60}")

    try:
        page.goto("https://b2b.10086.cn/#/biddingProcurementBulletin", wait_until="load", timeout=90000)
        rand_sleep(4, 7)

        for tab_name in BIDDING_TABS:
            print(f"\n  --- 切换到子分类: {tab_name} ---")

            if click_left_nav_tab(page, tab_name):
                print(f"  ✓ 已切换到 [{tab_name}]")
                rand_sleep(2, 4)

                rows = page.locator(".cmcc-table-row").all()
                if len(rows) == 0:
                    print(f"  {tab_name}: 无数据，跳过")
                    continue

                first_date = ""
                try:
                    first_cells = rows[0].locator("td").all()
                    if len(first_cells) >= 4:
                        first_date = first_cells[3].inner_text().strip()
                except:
                    pass

                if first_date and first_date < TODAY:
                    print(f"  {tab_name}: 最新记录日期 {first_date}，无今天数据，跳过")
                    continue

                results = scrape_current_table(page, context, tab_name)
                all_results.extend(results)
            else:
                print(f"  ✗ 无法切换到 [{tab_name}]，跳过")

    except Exception as e:
        print(f"  招标采购公告错误: {e}")
        errors.append(f"招标采购公告: {e}")

    # ========== 第二个网页：采购服务（6个子分类） ==========
    print(f"\n{'='*60}")
    print(f"开始抓取: 采购服务 (共{len(PROCUREMENT_SERVICE_TABS)}个子分类)")
    print(f"{'='*60}")

    try:
        page.goto("https://b2b.10086.cn/#/procurementServices", wait_until="load", timeout=90000)
        rand_sleep(4, 7)

        for tab_name in PROCUREMENT_SERVICE_TABS:
            print(f"\n  --- 切换到子分类: {tab_name} ---")

            if click_left_nav_tab(page, tab_name):
                print(f"  ✓ 已切换到 [{tab_name}]")
                rand_sleep(2, 4)

                # 检查表格是否有数据
                rows = page.locator(".cmcc-table-row").all()
                if len(rows) == 0:
                    print(f"  {tab_name}: 无数据，跳过")
                    continue

                # 快速检查第一行日期，如果不是今天就跳过
                first_date = ""
                try:
                    first_cells = rows[0].locator("td").all()
                    if len(first_cells) >= 4:
                        first_date = first_cells[3].inner_text().strip()
                except:
                    pass

                if first_date and first_date < TODAY:
                    print(f"  {tab_name}: 最新记录日期 {first_date}，无今天数据，跳过")
                    continue

                results = scrape_current_table(page, context, tab_name)
                all_results.extend(results)
            else:
                print(f"  ✗ 无法切换到 [{tab_name}]，跳过")

    except Exception as e:
        print(f"  采购服务错误: {e}")
        errors.append(f"采购服务: {e}")

    page.close()
    browser.close()
    playwright.stop()

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    # 写状态文件（供push_combined.py检查告警）
    with open("cmcc_status.json", 'w', encoding='utf-8') as f:
        json.dump({"errors": errors, "count": len(all_results)}, f, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"✅ 全部完成: {len(all_results)} 条匹配关键词的记录")
    for i, r in enumerate(all_results):
        print(f"  [{i+1}] 【{r['province']}-{r['type']}】{r['title'][:40]}...")
        print(f"       URL: {r['url'][:80]}")
    print(f"{'='*60}")

    return len(all_results)

if __name__ == "__main__":
    fetch_cmcc()
