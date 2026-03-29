#!/usr/bin/env python3
"""
联通招标信息抓取 - 基于API拦截
访问 /bidInformation，拦截API响应获取结构化数据
"""

import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(line_buffering=True)

OUTPUT_FILE = "unicom_bids.json"
KEYWORDS = ["数智化", "数据", "算力", "战略", "算网", "软件开发", "云智算", "DICT", "ICT", "业务支撑"]
BJT = timezone(timedelta(hours=8))
TODAY = os.environ.get("BIDDING_DATE") or datetime.now(BJT).strftime("%Y-%m-%d")

def fetch_unicom():
    print(f"=== 抓取联通招标 {datetime.now(BJT).strftime('%H:%M:%S')} ===")
    print(f"限定日期: {TODAY}")
    print(f"关键词: {' | '.join(KEYWORDS)}")
    
    results = []
    errors = []
    seen_ids = set()
    all_records = []
    
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={"width": 1920, "height": 1080},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    )
    page = context.new_page()
    
    # 拦截API响应
    api_data = []
    def on_response(resp):
        if 'getAnnoList' in resp.url:
            try:
                body = resp.json()
                if body.get('success') and body.get('data', {}).get('records'):
                    api_data.append(body['data'])
            except:
                pass
    page.on("response", on_response)
    
    try:
        print("访问 /bidInformation ...")
        page.goto("https://www.chinaunicombidding.cn/bidInformation", wait_until="load", timeout=60000)
        time.sleep(8)
        
        # 获取首页API数据
        if api_data:
            data = api_data[-1]
            total = data.get('total', 0)
            pages = data.get('pages', 0)
            print(f"总记录: {total}, 总页数: {pages}")
            
            records = data.get('records', [])
            all_records.extend(records)
            print(f"第1页: {len(records)} 条")
        
        # 翻页获取更多（最多翻10页，连续2页无今日数据则停止）
        max_pages = min(10, api_data[-1].get('pages', 1)) if api_data else 1
        no_today_streak = 0
        
        for p in range(2, max_pages + 1):
            api_data.clear()
            
            try:
                next_btn = page.locator(f".ant-pagination-item[title='{p}']").first
                if next_btn.count() > 0:
                    next_btn.click()
                    time.sleep(3)
                    
                    if api_data:
                        records = api_data[-1].get('records', [])
                        all_records.extend(records)
                        print(f"第{p}页: {len(records)} 条")
                        
                        # 检查本页是否有今天的记录
                        has_today = any(r.get('createDate', '')[:10] == TODAY for r in records)
                        if has_today:
                            no_today_streak = 0
                        else:
                            no_today_streak += 1
                            if no_today_streak >= 2:
                                print(f"  连续{no_today_streak}页无今日数据，停止翻页")
                                break
                else:
                    break
            except:
                break
        
        print(f"\n共获取 {len(all_records)} 条记录")
        
        # 统计今日数据 + 过滤匹配
        today_count = 0
        for record in all_records:
            rid = str(record.get('id', ''))
            if rid in seen_ids:
                continue
            seen_ids.add(rid)
            
            title = record.get('annoName', '')
            province = record.get('provinceName', '')
            anno_type = record.get('annoType', '')
            create_date = record.get('createDate', '')[:10]
            bid_company = record.get('bidCompany', '')
            
            # 日期过滤
            if create_date and create_date != TODAY:
                continue
            today_count += 1
            
            # 关键词匹配
            if KEYWORDS and not any(kw in title for kw in KEYWORDS):
                continue
            
            # 构建详情URL（联通网站改版后新格式）
            detail_url = f"https://www.chinaunicombidding.cn/bidInformation/detail?id={rid}"
            
            print(f"  [✓] {province} | {anno_type} | {title[:50]}...")
            
            results.append({
                "platform": "联通",
                "province": province or "全国",
                "type": anno_type,
                "company": bid_company or "中国联通",
                "title": title,
                "url": detail_url,
                "date": create_date or TODAY
            })
        
    except Exception as e:
        print(f"错误: {e}")
        errors.append(str(e))
        import traceback
        traceback.print_exc()
    finally:
        page.close()
        browser.close()
        playwright.stop()
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    with open("unicom_status.json", 'w', encoding='utf-8') as f:
        json.dump({"errors": errors, "count": len(results)}, f, ensure_ascii=False)
    
    print(f"\n{'='*60}")
    print(f"✅ 联通抓取完成: 今日{today_count}条, {len(results)}条匹配关键词")
    for i, r in enumerate(results):
        print(f"  [{i+1}] 【{r['province']}-{r['type']}】{r['title'][:50]}...")
        print(f"       URL: {r['url']}")
    print(f"{'='*60}")
    
    return len(results)

if __name__ == "__main__":
    fetch_unicom()
