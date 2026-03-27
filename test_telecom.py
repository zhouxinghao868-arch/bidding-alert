#!/usr/bin/env python3
"""从电信搜索页的Vue组件数据中提取完整type映射"""
import sys, time, json
from playwright.sync_api import sync_playwright
sys.stdout.reconfigure(line_buffering=True)

pw = sync_playwright().start()
br = pw.chromium.launch(headless=True)
ctx = br.new_context(viewport={"width":1920,"height":1080},
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
page = ctx.new_page()

page.goto("https://caigou.chinatelecom.com.cn/search", wait_until="load", timeout=120000)
time.sleep(8)

# 方法1: 从Vue组件数据中搜索类型配置
result = page.evaluate("""() => {
    const app = document.querySelector('#app');
    if (!app || !app.__vue__) return 'no vue';
    
    // 深度搜索Vue组件树，找包含类型配置的数据
    function search(vm, depth) {
        if (depth > 10) return null;
        
        // 检查data中是否有类型相关的数组
        const data = vm._data || vm.$data || {};
        for (const key of Object.keys(data)) {
            const val = data[key];
            if (Array.isArray(val) && val.length > 3) {
                // 检查是否是类型配置数组
                const first = val[0];
                if (first && typeof first === 'object') {
                    const keys = Object.keys(first);
                    if (keys.some(k => k.includes('type') || k.includes('Type') || k.includes('code') || k.includes('Code'))) {
                        return {key, data: val.slice(0, 20), component: vm.$options.name || vm.$options._componentTag || 'unknown'};
                    }
                }
            }
        }
        
        // 递归搜索子组件
        for (const child of (vm.$children || [])) {
            const found = search(child, depth + 1);
            if (found) return found;
        }
        return null;
    }
    
    return search(app.__vue__, 0);
}""")
print(f"搜索结果: {json.dumps(result, ensure_ascii=False, indent=2)}")

# 方法2: 搜索所有JS全局变量
js_types = page.evaluate("""() => {
    // 搜索window上的类型配置
    const results = {};
    for (const key of Object.keys(window)) {
        try {
            const val = window[key];
            if (typeof val === 'object' && val !== null && !Array.isArray(val)) {
                const str = JSON.stringify(val);
                if (str && str.includes('docTypeCode') || str.includes('CompareSelect') || str.includes('ResultAnnounc')) {
                    results[key] = str.substring(0, 500);
                }
            }
        } catch(e) {}
    }
    return results;
}""")
if js_types:
    print(f"\n全局变量中的类型配置: {json.dumps(js_types, ensure_ascii=False, indent=2)}")

# 方法3: 直接从标签栏元素中提取
tabs = page.evaluate("""() => {
    // 找到类型标签栏
    const tabs = document.querySelectorAll('[class*="tab"], [class*="type"], [class*="category"]');
    const results = [];
    tabs.forEach(t => {
        const text = t.textContent.trim();
        if (text.length < 30 && text.length > 2) {
            // 检查有没有绑定的Vue数据
            const vue = t.__vue__;
            if (vue && vue._data) results.push({text, data: JSON.stringify(vue._data).substring(0, 200)});
        }
    });
    return results;
}""")
if tabs:
    print(f"\n标签Vue数据: {json.dumps(tabs, ensure_ascii=False, indent=2)}")

# 方法4: 暴力搜索 - 遍历所有script标签内容
scripts = page.evaluate("""() => {
    const scripts = document.querySelectorAll('script[src]');
    return Array.from(scripts).map(s => s.src).filter(s => s.includes('chunk') || s.includes('app'));
}""")
print(f"\nJS文件: {json.dumps(scripts)}")

br.close()
pw.stop()
