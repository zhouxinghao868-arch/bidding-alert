#!/usr/bin/env python3
"""
联通招标信息抓取 - 独立运行
结果保存到 unicom_bids.json
"""

import json
import os
import time
from datetime import datetime
from playwright.sync_api import sync_playwright

OUTPUT_FILE = "unicom_bids.json"
KEYWORDS = ["数智化", "数据", "算力", "战略"]


def match_keywords(text: str) -> bool:
    if not text:
        return False
    return any(kw in text for kw in KEYWORDS)


def fetch_unicom():
    print(f"=== 抓取中国联通招标信息 {datetime.now().strftime('%H:%M:%S')} ===")
    
    results = []
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={"width": 1920, "height": 1080},
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    )
    
    page = context.new_page()
    
    try:
        page.goto("https://www.chinaunicombidding.cn", wait_until="networkidle", timeout=90000)
        time.sleep(10)
        
        # 不等待特定选择器，直接获取所有h5
        title_elements = page.query_selector_all("h5")
        
        if not title_elements:
            # 尝试其他选择器
            title_elements = page.query_selector_all(".title, .ant-list-item h5, [class*='title']")
        
        print(f"  找到 {len(title_elements)} 条招标信息")
        
        for title_elem in title_elements:
            try:
                title = title_elem.inner_text().strip()
                if not title:
                    continue
                
                if not match_keywords(title):
                    continue
                
                # 提取公告类型
                bid_type = "其他"
                for t in ["采购公告", "采购结果", "采购计划", "采购准备"]:
                    if t in title:
                        bid_type = t
                        break
                
                # 获取详情URL
                detail_url = "https://www.chinaunicombidding.cn/bidInformation"
                try:
                    link_elem = title_elem.evaluate("el => el.closest('a')")
                    if link_elem:
                        href = link_elem.get_attribute("href")
                        if href:
                            detail_url = f"https://www.chinaunicombidding.cn{href}" if href.startswith("/") else href
                except:
                    pass
                
                results.append({
                    "platform": "联通",
                    "province": "全国",
                    "type": bid_type,
                    "company": "中国联通",
                    "title": title,
                    "url": detail_url,
                    "date": datetime.now().strftime("%Y-%m-%d")
                })
                print(f"  ✓ 匹配: {title[:40]}...")
                
            except Exception as e:
                continue
                
    except Exception as e:
        print(f"  抓取失败: {e}")
    finally:
        page.close()
        browser.close()
        playwright.stop()
    
    # 保存结果
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 联通招标抓取完成: {len(results)} 条")
    return len(results)


if __name__ == "__main__":
    fetch_unicom()
