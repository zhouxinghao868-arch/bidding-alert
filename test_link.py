#!/usr/bin/env python3
"""测试：点击行获取详情页URL格式"""
import sys, time
from playwright.sync_api import sync_playwright
sys.stdout.reconfigure(line_buffering=True)

pw = sync_playwright().start()
br = pw.chromium.launch(headless=True)
ctx = br.new_context(viewport={"width":1920,"height":1080})
page = ctx.new_page()

page.goto("https://b2b.10086.cn/#/biddingProcurementBulletin", wait_until="load", timeout=90000)
time.sleep(5)

print(f"当前URL: {page.url}")

# 方案1: 尝试用JS获取Vue组件数据
vue_data = page.evaluate("""() => {
    const rows = document.querySelectorAll('.cmcc-table-row');
    if (!rows.length) return 'no rows';
    
    // 检查Vue实例
    const row = rows[0];
    const vue = row.__vue__ || row.__vue_app__;
    if (vue) return 'has vue: ' + JSON.stringify(Object.keys(vue));
    
    // 检查父元素的Vue
    const table = document.querySelector('.cmcc-table-tbody');
    if (table && table.__vue__) return 'table has vue';
    
    // 检查data属性
    const allAttrs = [];
    for (const el of document.querySelectorAll('[data-row-key]')) {
        allAttrs.push(el.getAttribute('data-row-key'));
    }
    if (allAttrs.length) return 'data-row-keys: ' + allAttrs.join(',');
    
    return 'no vue data found';
}""")
print(f"Vue数据: {vue_data}")

# 方案2: 直接点击第一行，看URL变化
print("\n点击第1行...")
row = page.locator(".cmcc-table-row").first
row.click()
time.sleep(3)
print(f"点击后URL: {page.url}")

# 如果打开了新页面
if len(ctx.pages) > 1:
    print(f"新页面URL: {ctx.pages[-1].url}")

# 回退
page.go_back()
time.sleep(3)
print(f"回退后URL: {page.url}")

# 点击第3行（标题列）
print("\n点击第3行的标题列...")
page.goto("https://b2b.10086.cn/#/biddingProcurementBulletin", wait_until="load", timeout=90000)
time.sleep(5)
rows = page.locator(".cmcc-table-row").all()
if len(rows) >= 3:
    cells = rows[2].locator("td").all()
    if len(cells) >= 3:
        cells[2].click()
        time.sleep(3)
        print(f"点击标题后URL: {page.url}")

br.close()
pw.stop()
