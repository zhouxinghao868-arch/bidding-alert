#!/usr/bin/env python3
"""
移动招标信息抓取 - 简化版
直接抓取，然后过滤今天的记录
"""

import json
import time
from datetime import datetime
from dateutil import parser as date_parser
from playwright.sync_api import sync_playwright

OUTPUT_FILE = "cmcc_bids.json"
KEYWORDS = ["数智化", "数据", "算力", "战略"]
TODAY = datetime.now().strftime("%Y-%m-%d")

def fetch_cmcc():
    print(f"=== 抓取移动招标 {datetime.now().strftime('%H:%M:%S')} ===")
    print(f"限定日期: {TODAY}")
    
    results = []
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1920, "height": 1080})
    page = context.new_page()
    
    try:
        # 访问页面
        print("访问页面...")
        page.goto("https://b2b.10086.cn/#/biddingProcurementBulletin", wait_until="load", timeout=90000)
        time.sleep(5)
        
        # 直接开始翻页抓取（不设置日期筛选，抓取后过滤）
        page_num = 1
        max_pages = 10
        today_found = False
        
        while page_num <= max_pages and not today_found:
            print(f"\n第 {page_num} 页:")
            time.sleep(3)
            
            # 获取记录
            rows = page.locator(".cmcc-table-row").all()
            print(f"  找到 {len(rows)} 条记录")
            
            page_has_today = False
            
            for i, row in enumerate(rows):
                try:
                    cells = row.locator("td").all()
                    if len(cells) < 4:
                        continue
                    
                    # 表格列：单位、类型、标题、发布时间
                    company = cells[0].inner_text().strip()
                    bid_type = cells[1].inner_text().strip()
                    title = cells[2].inner_text().strip()
                    date_str = cells[3].inner_text().strip()
                    
                    # 检查是否为今天
                    if TODAY not in date_str:
                        if i == 0 and page_num == 1:
                            # 第一页第一条不是今天，说明今天无记录
                            print(f"  最新记录日期: {date_str}，不是今天")
                            today_found = True  # 退出循环
                            break
                        continue
                    
                    page_has_today = True
                    
                    # 检查关键词
                    if not any(kw in title for kw in KEYWORDS):
                        continue
                    
                    print(f"  ✓ [{date_str}] {title[:50]}...")
                    
                    # 获取URL
                    try:
                        cells[2].locator("a").first.click()
                        time.sleep(2)
                        detail_page = context.pages[-1]
                        url = detail_page.url
                        detail_page.close()
                        time.sleep(1)
                    except:
                        url = "https://b2b.10086.cn"
                    
                    results.append({
                        "platform": "移动",
                        "province": company,
                        "type": bid_type,
                        "company": company,
                        "title": title,
                        "url": url,
                        "date": date_str
                    })
                    
                except Exception as e:
                    continue
            
            if not page_has_today:
                print("  本页无今天记录，停止")
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
                    break
            except:
                break
        
    except Exception as e:
        print(f"错误: {e}")
    finally:
        page.close()
        browser.close()
        playwright.stop()
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n完成: {len(results)} 条匹配")
    return len(results)

if __name__ == "__main__":
    fetch_cmcc()
