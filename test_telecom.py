#!/usr/bin/env python3
"""测试：用popup事件捕获电信详情页"""
import sys, time
from playwright.sync_api import sync_playwright
sys.stdout.reconfigure(line_buffering=True)

pw = sync_playwright().start()
br = pw.chromium.launch(headless=True)
ctx = br.new_context(viewport={"width":1920,"height":1080},
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
page = ctx.new_page()

page.goto("https://caigou.chinatelecom.com.cn/search", wait_until="load", timeout=120000)
time.sleep(8)

# 用expect_popup捕获新窗口
print("=== 方法1: expect_popup 点击表格行 ===")
try:
    row = page.locator(".el-table__row").first
    print(f"表格行文本: {row.inner_text()[:80]}")
    
    with page.expect_popup(timeout=10000) as popup_info:
        row.click()
    popup = popup_info.value
    time.sleep(3)
    print(f"弹窗URL: {popup.url}")
    popup.close()
except Exception as e:
    print(f"方法1失败: {e}")

# 方法2: 监听navigation
print("\n=== 方法2: 用JS拦截window.open ===")
try:
    # 注入JS，拦截window.open
    page.evaluate("""() => {
        window.__openedUrls = [];
        const origOpen = window.open;
        window.open = function(url, ...args) {
            window.__openedUrls.push(url);
            return origOpen.call(this, url, ...args);
        };
    }""")
    
    row = page.locator(".el-table__row").nth(1)
    row.click()
    time.sleep(3)
    
    opened = page.evaluate("() => window.__openedUrls")
    print(f"拦截到的URL: {opened}")
except Exception as e:
    print(f"方法2失败: {e}")

# 方法3: 直接检查所有页面
print(f"\n=== 当前所有页面 ({len(ctx.pages)}) ===")
for i, p in enumerate(ctx.pages):
    print(f"  页面{i}: {p.url}")

# 方法4: 检查router
print("\n=== 方法4: 检查Vue Router ===")
route_info = page.evaluate("""() => {
    const app = document.querySelector('#app');
    if (app && app.__vue__) {
        const router = app.__vue__.$router;
        if (router) {
            return {
                currentRoute: router.currentRoute ? router.currentRoute.fullPath : 'none',
                routes: router.options.routes ? router.options.routes.map(r => ({path: r.path, name: r.name})) : []
            };
        }
    }
    // 检查 umi 路由
    if (window.g_routes) return {routes: window.g_routes.map(r => r.path)};
    return 'no router found';
}""")
print(f"路由信息: {route_info}")

br.close()
pw.stop()
