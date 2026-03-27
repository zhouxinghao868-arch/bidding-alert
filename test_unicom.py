#!/usr/bin/env python3
"""测试：联通 /bidInformation 页面的搜索和列表结构"""
import sys, time, json
from playwright.sync_api import sync_playwright
sys.stdout.reconfigure(line_buffering=True)

pw = sync_playwright().start()
br = pw.chromium.launch(headless=True)
ctx = br.new_context(viewport={"width":1920,"height":1080},
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
page = ctx.new_page()

# 监听API响应
api_responses = []
def on_response(resp):
    if 'getAnnoList' in resp.url:
        try:
            body = resp.json()
            api_responses.append(body)
        except:
            pass
page.on("response", on_response)

print("访问 /bidInformation ...")
page.goto("https://www.chinaunicombidding.cn/bidInformation", wait_until="load", timeout=60000)
time.sleep(8)

# 检查API响应
print(f"\n=== API响应 ({len(api_responses)}个) ===")
for i, resp in enumerate(api_responses):
    if isinstance(resp, dict):
        print(f"响应{i+1} keys: {list(resp.keys())}")
        if 'data' in resp:
            data = resp['data']
            if isinstance(data, dict):
                print(f"  data keys: {list(data.keys())}")
                if 'records' in data:
                    records = data['records']
                    print(f"  records数量: {len(records)}")
                    if records:
                        print(f"  第1条 keys: {list(records[0].keys())}")
                        r = records[0]
                        print(f"  示例: title={r.get('title','')[:50]}")
                        print(f"         annoType={r.get('annoType')}")
                        print(f"         publishTime={r.get('publishTime')}")
                        print(f"         province={r.get('province')}")
                        print(f"         id={r.get('id')}")
                elif 'list' in data:
                    lst = data['list']
                    print(f"  list数量: {len(lst)}")

# 检查页面元素结构
print("\n=== 页面列表结构 ===")
info = page.evaluate("""() => {
    const results = {};
    // 检查列表项
    const items = document.querySelectorAll('.ant-list-item');
    results.antListItems = items.length;
    
    // 检查搜索框
    const inputs = document.querySelectorAll('input');
    results.inputs = [];
    inputs.forEach(inp => {
        results.inputs.push({
            placeholder: inp.placeholder,
            type: inp.type,
            class: inp.className.substring(0, 50)
        });
    });
    
    // 检查分页
    const pagination = document.querySelectorAll('.ant-pagination-item');
    results.paginationItems = pagination.length;
    
    // 检查卡片或列表
    const cards = document.querySelectorAll('[class*="card"], [class*="Card"]');
    results.cards = cards.length;
    
    // 获取所有class包含list的元素
    const listEls = document.querySelectorAll('[class*="list"], [class*="List"]');
    results.listElements = listEls.length;
    
    // 检查标题元素
    const titles = document.querySelectorAll('h5, [class*="title"], [class*="Title"]');
    results.titleElements = titles.length;
    
    // 获取前3个标题文本
    results.titleTexts = [];
    titles.forEach((t, i) => {
        if (i < 5) results.titleTexts.push(t.textContent.trim().substring(0, 60));
    });
    
    return results;
}""")
print(json.dumps(info, ensure_ascii=False, indent=2))

# 尝试搜索
print("\n=== 尝试搜索 '数据' ===")
api_responses.clear()
try:
    search_input = page.locator("input[placeholder*='搜索'], input[placeholder*='关键']").first
    if search_input.count() > 0:
        search_input.fill("数据")
        time.sleep(1)
        # 点搜索按钮
        page.locator("button:has-text('搜'), .ant-btn-primary:has-text('搜')").first.click()
        time.sleep(5)
        print(f"搜索后API响应: {len(api_responses)}")
        if api_responses:
            data = api_responses[-1].get('data', {})
            records = data.get('records', data.get('list', []))
            print(f"搜索结果数量: {len(records)}")
            for r in records[:3]:
                print(f"  - {r.get('title','')[:60]}")
                print(f"    publishTime={r.get('publishTime')} province={r.get('province')}")
    else:
        print("未找到搜索框")
        # 列出所有input
        inputs = page.locator("input").all()
        for inp in inputs:
            print(f"  input: placeholder={inp.get_attribute('placeholder')}")
except Exception as e:
    print(f"搜索失败: {e}")

br.close()
pw.stop()
