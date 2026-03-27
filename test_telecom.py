#!/usr/bin/env python3
"""测试：直接调用电信API"""
import sys, json, requests
sys.stdout.reconfigure(line_buffering=True)

url = "https://caigou.chinatelecom.com.cn/portal/base/announcementJoin/queryListNew"
headers = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://caigou.chinatelecom.com.cn/search",
    "Origin": "https://caigou.chinatelecom.com.cn"
}

# 尝试不同的payload格式
payloads = [
    # 空payload
    {},
    # 分页参数
    {"pageNum": 1, "pageSize": 10},
    # 更完整的参数
    {"pageNum": 1, "pageSize": 10, "noticeType": "", "keyword": "", "province": ""}
]

for i, payload in enumerate(payloads):
    print(f"\n=== 尝试 payload {i+1}: {json.dumps(payload)} ===")
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30, verify=True)
        print(f"状态码: {resp.status_code}")
        data = resp.json()
        print(f"响应keys: {list(data.keys())}")
        if data.get('code') == 200:
            page_info = data.get('data', {}).get('pageInfo', {})
            records = page_info.get('list', [])
            print(f"total: {page_info.get('total')}, records: {len(records)}")
            if records:
                r = records[0]
                print(f"第1条: {r.get('docTitle','')[:60]}")
                print(f"  日期: {r.get('createDate')}, 省份: {r.get('provinceName')}, 类型: {r.get('docType')}")
            break
        else:
            print(f"响应: {json.dumps(data, ensure_ascii=False)[:300]}")
    except Exception as e:
        print(f"失败: {e}")
