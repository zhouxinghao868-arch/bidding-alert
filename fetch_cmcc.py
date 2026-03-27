#!/usr/bin/env python3
"""
移动招标信息抓取 - 独立运行
结果保存到 cmcc_bids.json
优化：限定今天发布 + 翻页抓取
"""

import json
import os
import re
import time
from datetime import datetime, timedelta
from typing import List
from dateutil import parser as date_parser

from playwright.sync_api import sync_playwright

OUTPUT_FILE = "cmcc_bids.json"
KEYWORDS = ["数智化", "数据", "算力", "战略"]
TODAY = datetime.now().strftime("%Y-%m-%d")  # 今天日期，如 2026-03-27

CMCC_BID_TYPE_MAP = {
    "CANDIDATE_PUBLICITY": "候选人公示",
    "WIN_BID": "中选结果公示",
    "WIN_BID_PUBLICITY": "中选结果公示",
    "BIDDING": "采购公告",
    "BIDDING_PROCUREMENT": "采购公告",
    "PROCUREMENT": "直接采购公示",
    "PREQUALIFICATION": "资格预审公告",
}


def match_keywords(text: str) -> bool:
    if not text:
        return False
    return any(kw in text for kw in KEYWORDS)


def extract_province(text: str) -> str:
    if not text:
        return "全国"
    provinces = ["北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江",
                 "上海", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南",
                 "湖北", "湖南", "广东", "广西", "海南", "重庆", "四川", "贵州",
                 "云南", "西藏", "陕西", "甘肃", "青海", "宁夏", "新疆"]
    for p in provinces:
        if p in text:
            return p
    return "全国"


def is_today(date_str: str) -> bool:
    """检查日期是否为今天"""
    try:
        dt = date_parser.parse(date_str)
        return dt.strftime("%Y-%m-%d") == TODAY
    except:
        return False


def fetch_cmcc():
    print(f"=== 抓取中国移动招标信息 {datetime.now().strftime('%H:%M:%S')} ===")
    print(f"限定日期: {TODAY}")
    print(f"关键词: {' | '.join(KEYWORDS)}")
    
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
    
    urls = [
        ("https://b2b.10086.cn/#/biddingProcurementBulletin", "招标采购公告"),
        ("https://b2b.10086.cn/#/procurementServices", "采购意见征求公告")
    ]
    
    for url, page_name in urls:
        print(f"\n{'='*50}")
        print(f"正在访问: {page_name}")
        print(f"{'='*50}")
        
        page = context.new_page()
        
        try:
            print("  正在加载页面...")
            page.goto(url, wait_until="load", timeout=90000)
            time.sleep(5)
            
            # 设置日期筛选为今天
            print(f"  设置日期筛选: {TODAY}")
            try:
                # 尝试找到日期输入框并设置为今天
                date_inputs = page.locator("input[placeholder*='日期'], input[type='text']").all()
                if len(date_inputs) >= 2:
                    # 通常是两个输入框：开始日期和结束日期
                    date_inputs[0].fill(TODAY)
                    date_inputs[1].fill(TODAY)
                    print(f"    已设置日期范围: {TODAY} 至 {TODAY}")
                    
                    # 点击查询按钮
                    search_btn = page.locator("button:has-text('查询'), button[type='submit']").first
                    if search_btn:
                        search_btn.click()
                        time.sleep(3)
                        print("    已点击查询")
            except Exception as e:
                print(f"    设置日期筛选失败（可能不需要）: {e}")
            
            # 开始翻页抓取
            page_num = 1
            max_pages = 10  # 最多抓取10页
            
            while page_num <= max_pages:
                print(f"\n  📄 正在处理第 {page_num} 页...")
                
                # 获取当前页的所有行
                rows = page.locator("tr.ant-table-row").all()
                if not rows:
                    rows = page.locator("table tbody tr").all()
                
                print(f"     本页找到 {len(rows)} 条记录")
                
                page_has_today = False  # 标记本页是否有今天的记录
                
                for row in rows:
                    try:
                        cells = row.locator("td").all()
                        if len(cells) < 4:
                            continue
                        
                        bid_type = cells[0].inner_text().strip()
                        company = cells[1].inner_text().strip()
                        title = cells[2].inner_text().strip()
                        date_str = cells[3].inner_text().strip()
                        
                        # 检查是否为今天发布
                        if not is_today(date_str):
                            continue  # 跳过非今天的记录
                        
                        page_has_today = True
                        
                        # 检查关键词匹配
                        if not match_keywords(title) and not match_keywords(company):
                            continue
                        
                        # 点击获取详情URL
                        title_link = cells[2].locator("a").first
                        if not title_link:
                            continue
                        
                        title_link.click()
                        time.sleep(2)
                        
                        detail_page = context.pages[-1]
                        detail_url = detail_page.url
                        detail_page.close()
                        time.sleep(1)
                        
                        # 解析类型
                        bid_type_cn = "其他"
                        for key, value in CMCC_BID_TYPE_MAP.items():
                            if key in detail_url:
                                bid_type_cn = value
                                break
                        
                        province = extract_province(company)
                        
                        results.append({
                            "platform": "移动",
                            "province": province,
                            "type": bid_type_cn,
                            "company": company,
                            "title": title,
                            "url": detail_url,
                            "date": date_str
                        })
                        print(f"     ✓ 匹配 [{date_str}]: {title[:40]}...")
                        
                    except Exception as e:
                        continue
                
                # 检查是否需要翻页
                if not page_has_today:
                    print(f"     本页无今天发布的记录，停止翻页")
                    break
                
                # 尝试翻到下一页
                try:
                    # 查找下一页按钮
                    next_btn = page.locator(".ant-pagination-next, button:has-text('下一页'), .pagination-next").first
                    if next_btn:
                        is_disabled = next_btn.is_disabled() if hasattr(next_btn, 'is_disabled') else False
                        class_attr = next_btn.get_attribute("class") or ""
                        if "disabled" in class_attr or is_disabled:
                            print(f"     已到最后一页")
                            break
                        
                        next_btn.click()
                        time.sleep(3)
                        page_num += 1
                    else:
                        print(f"     无翻页按钮，结束")
                        break
                        
                except Exception as e:
                    print(f"     翻页结束: {e}")
                    break
            
            print(f"\n  完成 {page_name}，共抓取 {len(results)} 条")
                    
        except Exception as e:
            print(f"  抓取失败: {e}")
        finally:
            page.close()
    
    browser.close()
    playwright.stop()
    
    # 保存结果
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*50}")
    print(f"✅ 移动招标抓取完成: {len(results)} 条")
    print(f"{'='*50}")
    return len(results)


if __name__ == "__main__":
    fetch_cmcc()
