#!/usr/bin/env python3
"""
移动招标信息抓取 - 翻页抓取全部
"""

import json
import time
from datetime import datetime
from playwright.sync_api import sync_playwright

OUTPUT_FILE = "cmcc_bids.json"
KEYWORDS = ["数智化", "数据", "算力", "战略"]
TODAY = datetime.now().strftime("%Y-%m-%d")

def fetch_page(page, page_num):
    """抓取当前页的数据"""
    print(f"\n  第 {page_num} 页:")
    time.sleep(3)
    
    rows = page.locator(".cmcc-table-row").all()
    print(f"    找到 {len(rows)} 条记录")
    
    page_results = []
    page_has_today = False
    
    for i, row in enumerate(rows):
        try:
            cells = row.locator("td").all()
            if len(cells) < 4:
                continue
            
            company = cells[0].inner_text().strip()
            bid_type = cells[1].inner_text().strip()
            title = cells[2].inner_text().strip()
            date_str = cells[3].inner_text().strip()
            
            # 检查是否为今天
            if TODAY not in date_str:
                if i == 0 and page_num == 1:
                    print(f"    最新记录日期: {date_str}，不是今天")
                    return [], True  # 今天无记录
                continue
            
            page_has_today = True
            
            # 检查关键词
            has_keyword = any(kw in title for kw in KEYWORDS)
            match_mark = "✓" if has_keyword else " "
            print(f"    [{match_mark}] {date_str} | {company} | {title[:40]}...")
            
            # 只保存匹配关键词的
            if has_keyword:
                try:
                    cells[2].locator("a").first.click()
                    time.sleep(2)
                    detail_page = page.context.pages[-1]
                    url = detail_page.url
                    detail_page.close()
                    time.sleep(1)
                except:
                    url = "https://b2b.10086.cn"
                
                page_results.append({
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
    
    return page_results, not page_has_today

def fetch_cmcc():
    print(f"=== 抓取移动招标 {datetime.now().strftime('%H:%M:%S')} ===")
    print(f"限定日期: {TODAY}")
    print(f"关键词: {' | '.join(KEYWORDS)}")
    
    results = []
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1920, "height": 1080})
    page = context.new_page()
    
    urls = [
        ("https://b2b.10086.cn/#/biddingProcurementBulletin", "招标采购公告"),
        ("https://b2b.10086.cn/#/procurementServices", "采购意见征求公告")
    ]
    
    for url, name in urls:
        print(f"\n{'='*60}")
        print(f"开始抓取: {name}")
        print(f"{'='*60}")
        
        try:
            page.goto(url, wait_until="load", timeout=90000)
            time.sleep(5)
            
            # 获取总记录数信息
            page_info = page.locator(".cmcc-page-total").first
            if page_info.count() > 0:
                print(f"  分页信息: {page_info.inner_text()}")
            
            # 翻页抓取
            page_num = 1
            max_pages = 10  # 最多10页
            
            while page_num <= max_pages:
                page_results, stop = fetch_page(page, page_num)
                results.extend(page_results)
                
                if stop:
                    print(f"  本页无今天记录，停止翻页")
                    break
                
                # 尝试翻页
                try:
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(2)
                    
                    # 获取总页数
                    page_items = page.locator(".cmcc-page-item").all()
                    total_pages = len(page_items)
                    
                    if page_num >= total_pages:
                        print(f"  已到最后一页 ({total_pages}页)")
                        break
                    
                    # 点击下一页
                    next_btn = page.locator(f".cmcc-page-item[title='{page_num + 1}']").first
                    if next_btn.count() > 0:
                        next_btn.click()
                        time.sleep(3)
                        page_num += 1
                    else:
                        break
                        
                except Exception as e:
                    print(f"  翻页结束: {e}")
                    break
            
            print(f"\n  {name} 抓取完成，共 {len([r for r in results if name in str(r)])} 条匹配")
            
        except Exception as e:
            print(f"  错误: {e}")
    
    page.close()
    browser.close()
    playwright.stop()
    
    # 保存结果
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*60}")
    print(f"✅ 全部抓取完成: {len(results)} 条匹配关键词的记录")
    print(f"{'='*60}")
    return len(results)

if __name__ == "__main__":
    fetch_cmcc()
