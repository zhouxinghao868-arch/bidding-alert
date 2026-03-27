#!/usr/bin/env python3
"""
联通招标信息抓取 - 独立运行
结果保存到 unicom_bids.json
"""

import json
import os
import time
import traceback
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

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
    browser = playwright.chromium.launch(
        headless=True,
        args=['--no-sandbox', '--disable-dev-shm-usage']
    )
    context = browser.new_context(
        viewport={"width": 1920, "height": 1080},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        locale="zh-CN"
    )
    
    page = context.new_page()
    
    try:
        print("  正在访问网站...")
        
        # 使用 load 状态而不是 networkidle，避免等待过长时间
        try:
            page.goto("https://www.chinaunicombidding.cn", wait_until="load", timeout=60000)
        except PlaywrightTimeout:
            print("  页面加载超时，继续处理已加载内容...")
        
        # 等待内容渲染
        print("  等待页面渲染...")
        time.sleep(8)
        
        # 调试：保存页面截图和HTML
        # page.screenshot(path="unicom_debug.png")
        # with open("unicom_debug.html", "w", encoding="utf-8") as f:
        #     f.write(page.content())
        
        # 获取页面所有文本内容用于调试
        page_text = page.inner_text("body")[:500]
        print(f"  页面内容预览: {page_text}...")
        
        # 尝试多种选择器获取招标信息
        selectors = [
            "h5",
            ".ant-list-item h5",
            ".title",
            "[class*='title']",
            "a[href*='/bidDetail']",
            ".list-item .title",
            ".bid-title"
        ]
        
        title_elements = []
        for selector in selectors:
            try:
                elements = page.query_selector_all(selector)
                if elements:
                    print(f"  使用选择器 '{selector}' 找到 {len(elements)} 个元素")
                    title_elements = elements
                    break
            except Exception as e:
                continue
        
        if not title_elements:
            print("  ⚠️ 未找到任何招标信息元素")
        else:
            print(f"  共找到 {len(title_elements)} 条招标信息")
            
            for i, title_elem in enumerate(title_elements):
                try:
                    title = title_elem.inner_text().strip()
                    if not title or len(title) < 10:
                        continue
                    
                    print(f"  [{i+1}] 检查: {title[:50]}...")
                    
                    if not match_keywords(title):
                        continue
                    
                    # 提取公告类型
                    bid_type = "其他"
                    for t in ["采购公告", "采购结果", "采购计划", "采购准备", "中标", "招标"]:
                        if t in title:
                            bid_type = t
                            break
                    
                    # 获取详情URL
                    detail_url = "https://www.chinaunicombidding.cn/bidInformation"
                    try:
                        # 尝试从父链接获取
                        parent = title_elem.evaluate("el => el.parentElement")
                        if parent:
                            href = parent.get_attribute("href") if hasattr(parent, 'get_attribute') else None
                            if href:
                                detail_url = f"https://www.chinaunicombidding.cn{href}" if href.startswith("/") else href
                        
                        # 尝试从自身获取
                        if detail_url == "https://www.chinaunicombidding.cn/bidInformation":
                            href = title_elem.get_attribute("href")
                            if href:
                                detail_url = f"https://www.chinaunicombidding.cn{href}" if href.startswith("/") else href
                    except Exception as e:
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
                    print(f"      ✓ 匹配关键词: {title[:40]}...")
                    
                except Exception as e:
                    continue
                
    except Exception as e:
        print(f"  ❌ 抓取失败: {e}")
        traceback.print_exc()
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
