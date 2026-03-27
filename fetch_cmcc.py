#!/usr/bin/env python3
"""
移动招标信息抓取 - 简化版测试
"""

import json
import time
from datetime import datetime
from playwright.sync_api import sync_playwright

OUTPUT_FILE = "cmcc_bids.json"
KEYWORDS = ["数智化", "数据", "算力", "战略"]
TODAY = datetime.now().strftime("%Y-%m-%d")


def fetch_cmcc():
    print(f"=== 测试移动招标抓取 {datetime.now().strftime('%H:%M:%S')} ===")
    
    results = []
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1920, "height": 1080})
    page = context.new_page()
    
    try:
        # 访问页面
        print("访问招标采购公告...")
        page.goto("https://b2b.10086.cn/#/biddingProcurementBulletin", wait_until="load", timeout=90000)
        time.sleep(5)
        
        # 设置日期为今天并查询
        print("设置日期并查询...")
        try:
            date_input = page.locator(".cmcc-date-picker input").first
            if date_input.count() > 0:
                date_input.click()
                time.sleep(1)
                # 点击27号两次（开始和结束日期）
                day_27 = page.locator("text=27").first
                if day_27.count() > 0:
                    day_27.click()
                    time.sleep(0.5)
                    day_27.click()
                    time.sleep(0.5)
        except Exception as e:
            print(f"  日期设置跳过: {e}")
        
        # 点击查询
        try:
            search_btn = page.locator("button:has-text('查询')").first
            if search_btn.count() > 0:
                search_btn.click()
                time.sleep(5)
                print("已查询")
        except:
            pass
        
        # 翻页抓取
        page_num = 1
        max_pages = 5
        
        while page_num <= max_pages:
            print(f"\n第 {page_num} 页:")
            time.sleep(2)
            
            # 获取记录 - 使用正确的表格选择器
            rows = page.locator(".cmcc-table-row").all()
            if not rows:
                rows = page.locator(".cmcc-table-tbody tr").all()
            print(f"  找到 {len(rows)} 条记录")
            
            # 显示前3条
            for i, row in enumerate(rows[:3]):
                try:
                    cells = row.locator("td").all()
                    if len(cells) >= 4:
                        date = cells[3].inner_text().strip()
                        title = cells[2].inner_text().strip()[:50]
                        print(f"  [{i+1}] {date} | {title}...")
                except:
                    pass
            
            # 检查关键词匹配
            for row in rows:
                try:
                    cells = row.locator("td").all()
                    if len(cells) < 4:
                        continue
                    title = cells[2].inner_text().strip()
                    company = cells[1].inner_text().strip()
                    date_str = cells[3].inner_text().strip()
                    
                    # 只匹配今天的记录
                    if TODAY not in date_str:
                        continue
                    
                    # 检查关键词
                    if not any(kw in title for kw in KEYWORDS):
                        continue
                    
                    # 获取URL
                    cells[2].locator("a").first.click()
                    time.sleep(2)
                    detail_page = context.pages[-1]
                    url = detail_page.url
                    detail_page.close()
                    time.sleep(1)
                    
                    results.append({
                        "platform": "移动",
                        "province": "全国",
                        "type": "采购公告",
                        "company": company,
                        "title": title,
                        "url": url,
                        "date": date_str
                    })
                    print(f"  ✓ 匹配: {title[:40]}...")
                except:
                    continue
            
            # 翻页
            try:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(2)
                
                # 获取总页数
                page_items = page.locator(".cmcc-page-item").all()
                total = len(page_items)
                print(f"  共 {total} 页")
                
                if page_num >= total:
                    print("  已到最后一页")
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
        
    except Exception as e:
        print(f"错误: {e}")
    finally:
        page.close()
        browser.close()
        playwright.stop()
    
    # 保存
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n完成: {len(results)} 条匹配")
    return len(results)


if __name__ == "__main__":
    fetch_cmcc()
