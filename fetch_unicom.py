#!/usr/bin/env python3
"""
联通招标信息抓取 - 双模式（API拦截优先 + DOM降级）
模式1: 拦截getAnnoList API响应获取结构化数据
模式2: 点击「今天」筛选后读取DOM卡片列表（API失败时降级）
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

UNICOM_URL = "https://www.chinaunicombidding.cn/bidInformation"


def mode_api(page):
    """模式1: API拦截抓取"""
    api_data = []
    all_records = []
    seen_ids = set()
    results = []
    today_count = 0

    def on_response(resp):
        if 'getAnnoList' in resp.url:
            try:
                body = resp.json()
                if body.get('success') and body.get('data', {}).get('records'):
                    api_data.append(body['data'])
            except:
                pass

    page.on("response", on_response)

    page.goto(UNICOM_URL, wait_until="load", timeout=60000)
    time.sleep(8)

    if not api_data:
        page.remove_listener("response", on_response)
        return None  # API失败，触发降级

    # 首页数据
    data = api_data[-1]
    total = data.get('total', 0)
    pages = data.get('pages', 0)
    records = data.get('records', [])
    all_records.extend(records)
    print(f"  总记录: {total}, 总页数: {pages}")
    print(f"  第1页: {len(records)} 条")

    # 翻页
    max_pages = min(10, pages)
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
                    print(f"  第{p}页: {len(records)} 条")
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

    page.remove_listener("response", on_response)
    print(f"  共获取 {len(all_records)} 条记录")

    # 过滤
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

        if create_date and create_date != TODAY:
            continue
        today_count += 1

        if KEYWORDS and not any(kw in title for kw in KEYWORDS):
            continue

        detail_url = f"{UNICOM_URL}/detail?id={rid}"
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

    return {"results": results, "today_count": today_count, "mode": "API"}


def mode_dom(page):
    """模式2: DOM页面抓取（降级方案）—— 点击「今天」筛选后读取卡片列表"""
    results = []
    seen_titles = set()
    today_count = 0

    try:
        if "bidInformation" not in page.url:
            page.goto(UNICOM_URL, wait_until="load", timeout=60000)
            time.sleep(8)
    except:
        page.goto(UNICOM_URL, wait_until="load", timeout=60000)
        time.sleep(8)

    # 点击「今天」筛选按钮（前端筛选）
    try:
        today_btn = page.locator("text=今 天").first
        if today_btn.count() > 0:
            today_btn.click()
            time.sleep(3)
            print("  ✓ 已点击「今天」筛选")
        else:
            # 备用选择器
            today_btn = page.locator("text=今天").first
            if today_btn.count() > 0:
                today_btn.click()
                time.sleep(3)
                print("  ✓ 已点击「今天」筛选")
            else:
                print("  ⚠ 未找到「今天」按钮")
    except Exception as e:
        print(f"  ⚠ 点击筛选失败: {e}")

    # 读取页面上的公告卡片
    body_text = page.locator('body').inner_text()
    lines = [l.strip() for l in body_text.split('\n') if l.strip()]

    # 解析卡片内容：寻找标题行（包含"公告"、"公示"、"招募"等关键词的长文本行）
    i = 0
    while i < len(lines):
        line = lines[i]
        # 识别公告标题（通常是较长的行，包含项目名称）
        if len(line) > 20 and ('项目' in line or '公告' in line or '公示' in line or '招募' in line or '采购' in line):
            # 排除导航菜单和筛选栏的文本
            if any(skip in line for skip in ['搜索公告', '公告类型', '招标单位', '项目类型', '发布时间',
                                              '全 部', '联通官网', 'Copyright', '联通首页']):
                i += 1
                continue

            title = line
            today_count += 1

            if title in seen_titles:
                i += 1
                continue
            seen_titles.add(title)

            # 尝试获取上下文中的省份和类型
            province = "全国"
            anno_type = "公告"
            # 往上找省份/类型标记
            for j in range(max(0, i-3), i):
                if lines[j] in ['采购结果', '采购公告', '采购准备', '采购计划']:
                    anno_type = lines[j]
                if '招标人：' in lines[j]:
                    bidder = lines[j].replace('招标人：', '')
                    # 从招标人名称中提取省份
                    for prov in ['北京','天津','河北','山西','内蒙古','辽宁','吉林','黑龙江',
                                 '上海','江苏','浙江','安徽','福建','江西','山东','河南',
                                 '湖北','湖南','广东','广西','海南','重庆','四川','贵州',
                                 '云南','西藏','陕西','甘肃','青海','宁夏','新疆']:
                        if prov in bidder:
                            province = prov
                            break

            # 关键词匹配
            if KEYWORDS and not any(kw in title for kw in KEYWORDS):
                i += 1
                continue

            print(f"  [✓] {province} | {anno_type} | {title[:50]}...")
            results.append({
                "platform": "联通",
                "province": province,
                "type": anno_type,
                "company": "中国联通",
                "title": title,
                "url": UNICOM_URL,
                "date": TODAY
            })
        i += 1

    return {"results": results, "today_count": today_count, "mode": "DOM"}


def fetch_unicom():
    print(f"=== 抓取联通招标 {datetime.now(BJT).strftime('%H:%M:%S')} ===")
    print(f"限定日期: {TODAY}")
    print(f"关键词: {' | '.join(KEYWORDS)}")

    errors = []

    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={"width": 1920, "height": 1080},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    )
    page = context.new_page()

    data = None

    # 模式1: API拦截
    try:
        print("\n[模式1] API拦截抓取...")
        data = mode_api(page)
        if data is None:
            print("  API未拦截到数据，降级到DOM模式")
    except Exception as e:
        print(f"  API模式异常: {e}")
        errors.append(f"API: {e}")

    # 模式2: DOM降级
    if data is None:
        try:
            print("\n[模式2] DOM页面抓取...")
            data = mode_dom(page)
        except Exception as e:
            print(f"  DOM模式异常: {e}")
            errors.append(f"DOM: {e}")
            data = {"results": [], "today_count": 0, "mode": "失败"}

    page.close()
    browser.close()
    playwright.stop()

    results = data["results"]
    today_count = data["today_count"]
    mode = data["mode"]

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    with open("unicom_status.json", 'w', encoding='utf-8') as f:
        json.dump({"errors": errors, "count": len(results), "mode": mode}, f, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"[{mode}模式] ✅ 联通抓取完成: 今日{today_count}条, {len(results)}条匹配关键词")
    for i, r in enumerate(results):
        print(f"  [{i+1}] 【{r['province']}-{r['type']}】{r['title'][:50]}...")
    print(f"{'='*60}")

    return len(results)


if __name__ == "__main__":
    fetch_unicom()
