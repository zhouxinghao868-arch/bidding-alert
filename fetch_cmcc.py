#!/usr/bin/env python3
"""
移动招标信息抓取 - 翻页 + URL获取
只抓当天数据，翻页上限30页，基于日期判断停止
"""

import json
import sys
import time
from datetime import datetime, timezone, timedelta
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(line_buffering=True)

OUTPUT_FILE = "cmcc_bids.json"
KEYWORDS = ["数智化", "数智", "数据", "算力", "战略"]
BJT = timezone(timedelta(hours=8))
TODAY = datetime.now(BJT).strftime("%Y-%m-%d")

def get_detail_url(context, row):
    """点击行获取详情页URL"""
    try:
        pages_before = len(context.pages)
        row.click()
        time.sleep(3)
        
        if len(context.pages) > pages_before:
            new_page = context.pages[-1]
            url = new_page.url
            new_page.close()
            time.sleep(1)
            return url
    except:
        pass
    return ""

def fetch_section(page, context, url, name):
    """抓取一个板块的所有当天记录"""
    print(f"\n{'='*60}")
    print(f"开始抓取: {name}")
    print(f"目标日期: {TODAY}")
    print(f"{'='*60}")
    
    results = []
    
    try:
        page.goto(url, wait_until="load", timeout=90000)
        time.sleep(5)
        
        page_num = 1
        max_pages = 30  # 覆盖工作日高峰（30页=600条）
        
        while page_num <= max_pages:
            print(f"\n  第 {page_num} 页:")
            time.sleep(3)
            
            rows = page.locator(".cmcc-table-row").all()
            print(f"    找到 {len(rows)} 条记录")
            
            if len(rows) == 0:
                print(f"    空页，停止")
                break
            
            page_has_today = False
            matched_indices = []
            earliest_date_on_page = None
            
            # 第一遍：扫描所有行，找出匹配的
            for i, row in enumerate(rows):
                try:
                    cells = row.locator("td").all()
                    if len(cells) < 4:
                        continue
                    
                    company = cells[0].inner_text().strip()
                    bid_type = cells[1].inner_text().strip()
                    title = cells[2].inner_text().strip()
                    # 去掉标题中的 "NEW " 前缀
                    if title.startswith("NEW "):
                        title = title[4:]
                    date_str = cells[3].inner_text().strip()
                    
                    # 记录本页最早日期
                    if earliest_date_on_page is None or date_str < earliest_date_on_page:
                        earliest_date_on_page = date_str
                    
                    # 只抓当天数据
                    if date_str != TODAY:
                        continue
                    
                    page_has_today = True
                    
                    if any(kw in title for kw in KEYWORDS):
                        matched_indices.append((i, company, bid_type, title, date_str))
                        print(f"    [✓] {company} | {title[:50]}...")
                    
                except:
                    continue
            
            # 停止条件：本页最早日期已早于今天（数据按日期降序排列）
            if earliest_date_on_page and earliest_date_on_page < TODAY:
                if not page_has_today:
                    # 整页都不是今天的，直接停
                    print(f"    本页无今天记录 (最早: {earliest_date_on_page})，停止")
                    break
                else:
                    # 本页有部分今天的，处理完后翻页看下一页是否还有
                    pass
            
            # 第二遍：对匹配的行点击获取URL
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
            
            # 如果本页最早日期已早于今天，说明后面不会再有今天的数据了
            if earliest_date_on_page and earliest_date_on_page < TODAY:
                print(f"    本页已出现旧日期 ({earliest_date_on_page})，后续无今天数据，停止")
                break
            
            # 翻页
            try:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(2)
                
                next_btn = page.locator(f".cmcc-page-item[title='{page_num + 1}']").first
                if next_btn.count() > 0:
                    next_btn.click()
                    time.sleep(3)
                    page_num += 1
                else:
                    # 尝试点击"下一页"按钮
                    next_arrow = page.locator(".cmcc-page-next").first
                    if next_arrow.count() > 0 and "cmcc-page-disabled" not in (next_arrow.get_attribute("class") or ""):
                        next_arrow.click()
                        time.sleep(3)
                        page_num += 1
                    else:
                        print(f"    已到最后一页")
                        break
            except Exception as e:
                print(f"    翻页异常: {e}")
                break
        
    except Exception as e:
        print(f"  错误: {e}")
    
    print(f"\n  {name} 完成: {len(results)} 条匹配 (翻了{page_num}页)")
    return results

def fetch_cmcc():
    print(f"=== 抓取移动招标 {datetime.now(BJT).strftime('%H:%M:%S')} ===")
    print(f"限定日期: {TODAY}")
    print(f"关键词: {' | '.join(KEYWORDS)}")
    
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1920, "height": 1080})
    page = context.new_page()
    
    results = []
    
    sections = [
        ("https://b2b.10086.cn/#/biddingProcurementBulletin", "招标采购公告"),
        ("https://b2b.10086.cn/#/procurementServices", "采购意见征求公告")
    ]
    
    for url, name in sections:
        section_results = fetch_section(page, context, url, name)
        results.extend(section_results)
    
    page.close()
    browser.close()
    playwright.stop()
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*60}")
    print(f"✅ 全部完成: {len(results)} 条匹配关键词的记录")
    for i, r in enumerate(results):
        print(f"  [{i+1}] 【{r['province']}-{r['type']}】{r['title'][:40]}...")
        print(f"       URL: {r['url'][:80]}")
    print(f"{'='*60}")
    
    return len(results)

if __name__ == "__main__":
    fetch_cmcc()
