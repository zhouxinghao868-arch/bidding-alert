#!/usr/bin/env python3
"""
中国联通招标信息抓取与飞书推送系统
支持从 chinaunicombidding.cn 抓取招标公告
"""

import json
import os
import re
import time
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from dateutil import parser as date_parser

import requests
from playwright.sync_api import sync_playwright, Page

# 配置
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK_UNICOM", "https://open.feishu.cn/open-apis/bot/v2/hook/3f57d6e3-20d7-4511-bb85-695352fbd651")
FETCH_DAYS = int(os.getenv("FETCH_DAYS", "1"))  # 默认抓取今天的公告
PUSHED_RECORDS_FILE = "pushed_bids_unicom.json"

# 关键词列表（与移动招标保持一致）
KEYWORDS = [
    "数智化", "数据", "算力", "战略"
]


class UnicomBiddingScraper:
    """联通招标信息抓取类"""
    
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.pushed_records = self._load_pushed_records()
    
    def _load_pushed_records(self) -> Dict:
        """加载已推送的记录（使用标题哈希作为唯一标识）"""
        if os.path.exists(PUSHED_RECORDS_FILE):
            try:
                with open(PUSHED_RECORDS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {"hashes": [], "urls": []}
    
    def _save_pushed_records(self):
        """保存已推送的记录"""
        with open(PUSHED_RECORDS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.pushed_records, f, ensure_ascii=False)
    
    def _get_bid_hash(self, title: str) -> str:
        """生成招标信息的唯一哈希（基于标题）"""
        # 使用标题前50个字符生成哈希，过滤掉一些可变内容
        normalized_title = title.strip()[:50]
        return hashlib.md5(normalized_title.encode('utf-8')).hexdigest()
    
    def is_bid_pushed(self, title: str, url: str) -> bool:
        """检查招标信息是否已推送（基于标题哈希和URL双重检查）"""
        bid_hash = self._get_bid_hash(title)
        
        # 检查标题哈希
        if bid_hash in self.pushed_records.get("hashes", []):
            return True
        
        # 检查URL
        if url in self.pushed_records.get("urls", []):
            return True
        
        return False
    
    def mark_bid_pushed(self, title: str, url: str):
        """标记招标信息为已推送"""
        bid_hash = self._get_bid_hash(title)
        
        if "hashes" not in self.pushed_records:
            self.pushed_records["hashes"] = []
        if "urls" not in self.pushed_records:
            self.pushed_records["urls"] = []
        
        if bid_hash not in self.pushed_records["hashes"]:
            self.pushed_records["hashes"].append(bid_hash)
        if url not in self.pushed_records["urls"]:
            self.pushed_records["urls"].append(url)
    
    def init_browser(self):
        """初始化浏览器"""
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=True)
        self.context = self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        return self
    
    def close(self):
        """关闭浏览器"""
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
    
    def _get_detail_url(self, page: Page, title_text: str) -> Optional[str]:
        """点击标题获取详情页URL"""
        try:
            title_elem = page.locator(f"h5:has-text('{title_text}')").first
            if title_elem.count() == 0:
                return None
            
            clickable = title_elem.locator("..")
            if clickable.count() == 0:
                with self.context.expect_page() as new_page_info:
                    title_elem.click()
            else:
                with self.context.expect_page() as new_page_info:
                    clickable.click()
            
            new_page = new_page_info.value
            new_page.wait_for_load_state("networkidle")
            detail_url = new_page.url
            new_page.close()
            
            return detail_url
        except Exception as e:
            return None
    
    def _extract_region(self, company: str) -> str:
        """从公司名称中提取地区"""
        # 常见的省份/城市关键词
        regions = [
            "北京", "上海", "天津", "重庆",
            "黑龙江", "吉林", "辽宁", "河北", "山西", "山东",
            "河南", "江苏", "安徽", "浙江", "福建", "江西",
            "湖北", "湖南", "广东", "海南", "四川", "贵州",
            "云南", "陕西", "甘肃", "青海", "台湾",
            "内蒙古", "广西", "西藏", "宁夏", "新疆"
        ]
        
        for region in regions:
            if region in company:
                return region
        return ""
    
    def fetch_bid_information(self) -> List[Dict]:
        """抓取联通招标信息（筛选今天，翻页抓取全部）"""
        url = "https://www.chinaunicombidding.cn/bidInformation"
        results = []
        page = self.context.new_page()
        
        try:
            print(f"\n正在访问: {url}")
            page.goto(url, wait_until="networkidle", timeout=60000)
            time.sleep(3)
            
            # 点击"今天"筛选
            print("  点击'今天'筛选...")
            try:
                today_btn = page.locator("button:has-text('今 天')").first
                if today_btn.count() > 0:
                    today_btn.click()
                    time.sleep(3)
                    print("  已筛选今天的公告")
            except Exception as e:
                print(f"  筛选失败: {e}")
            
            # 翻页抓取所有公告
            page_num = 1
            while True:
                print(f"\n  正在抓取第 {page_num} 页...")
                
                try:
                    page.wait_for_selector("h5", timeout=10000)
                except:
                    print("  警告: 等待标题元素超时")
                
                time.sleep(2)
                
                title_elements = page.query_selector_all("h5")
                print(f"    本页找到 {len(title_elements)} 条招标信息")
                
                for title_elem in title_elements:
                    try:
                        title = title_elem.inner_text().strip()
                        if not title:
                            continue
                        
                        parent = title_elem.evaluate("el => el.parentElement")
                        if not parent:
                            continue
                        
                        parent_text = parent.inner_text() if hasattr(parent, 'inner_text') else ""
                        
                        # 提取公告类型
                        bid_type = "其他"
                        for t in ["采购公告", "采购结果", "采购计划", "采购准备"]:
                            if t in parent_text:
                                bid_type = t
                                break
                        
                        # 提取招标人
                        company = ""
                        if "招标人：" in parent_text:
                            parts = parent_text.split("招标人：")
                            if len(parts) > 1:
                                company = parts[1].split("\n")[0].strip()
                        
                        # 获取地区
                        region = self._extract_region(company)
                        
                        print(f"    发现: {title[:40]}...")
                        
                        # 获取详情URL
                        detail_url = self._get_detail_url(page, title)
                        if not detail_url:
                            detail_url = f"https://www.chinaunicombidding.cn/bidInformation"
                        
                        # 增强去重检查（基于标题哈希）
                        if self.is_bid_pushed(title, detail_url):
                            print(f"      已推送过，跳过")
                            continue
                        
                        bid_info = {
                            "title": title,
                            "url": detail_url,
                            "company": company or "中国联通",
                            "region": region,
                            "type": bid_type,
                            "publish_time": datetime.now().strftime("%Y-%m-%d"),
                        }
                        results.append(bid_info)
                        print(f"      ✓ 成功抓取")
                        
                    except Exception as e:
                        print(f"    处理卡片失败: {e}")
                        continue
                
                # 检查是否有下一页
                try:
                    pagination_text = page.locator("text=/第 \\d+-\\d+ 条/总共 \\d+ 条/").first.inner_text()
                    print(f"    分页信息: {pagination_text}")
                    
                    next_btns = page.locator(".ant-pagination-item-link").all()
                    if len(next_btns) >= 2:
                        next_btn = next_btns[1]
                        is_disabled = next_btn.is_disabled()
                        if not is_disabled:
                            next_btn.click()
                            time.sleep(3)
                            page_num += 1
                        else:
                            print(f"\n  已是最后一页，共抓取 {len(results)} 条")
                            break
                    else:
                        print(f"\n  找不到分页按钮，共抓取 {len(results)} 条")
                        break
                        
                except Exception as e:
                    print(f"\n  翻页处理: {e}，共抓取 {len(results)} 条")
                    break
            
        except Exception as e:
            print(f"  抓取页面失败: {e}")
        finally:
            page.close()
        
        return results
    
    def fetch_all(self) -> List[Dict]:
        """抓取所有公告"""
        print("\n=== 抓取中国联通招标信息 ===")
        bids = self.fetch_bid_information()
        return bids


class FeishuPusher:
    """飞书推送类"""
    
    def __init__(self, webhook: str):
        self.webhook = webhook
    
    def _extract_province(self, region: str) -> str:
        """从地区信息提取省份简称"""
        if not region:
            return "未知"
        
        # 省份映射表
        province_map = {
            "北京": "北京", "天津": "天津", "河北": "河北", "山西": "山西", "内蒙古": "内蒙古",
            "辽宁": "辽宁", "吉林": "吉林", "黑龙江": "黑龙江",
            "上海": "上海", "江苏": "江苏", "浙江": "浙江", "安徽": "安徽", "福建": "福建",
            "江西": "江西", "山东": "山东",
            "河南": "河南", "湖北": "湖北", "湖南": "湖南", "广东": "广东", "广西": "广西",
            "海南": "海南",
            "重庆": "重庆", "四川": "四川", "贵州": "贵州", "云南": "云南", "西藏": "西藏",
            "陕西": "陕西", "甘肃": "甘肃", "青海": "青海", "宁夏": "宁夏", "新疆": "新疆"
        }
        
        for province, short_name in province_map.items():
            if province in region:
                return short_name
        
        return "全国"
    
    def send_message(self, bids: List[Dict]) -> bool:
        """发送招标信息到飞书（统一格式：【省份-类型-序号】）"""
        if not bids:
            print("\n没有新消息需要推送")
            return True
        
        # 统计信息
        type_count = {}
        for bid in bids:
            bid_type = bid.get("type", "其他")
            type_count[bid_type] = type_count.get(bid_type, 0) + 1
        
        # 构建消息内容
        lines = [
            "📢 中国联通招标信息",
            f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"📊 共找到 {len(bids)} 条匹配公告"
        ]
        
        # 类型统计
        type_order = ["采购公告", "采购结果", "采购计划", "采购准备", "其他"]
        type_stats = []
        for bid_type in type_order:
            if bid_type in type_count:
                type_stats.append(f"{bid_type}: {type_count[bid_type]}条")
        if type_stats:
            lines.append(f"📋 {' | '.join(type_stats)}")
        lines.append("")
        
        # 详细列表（按【省份-类型-序号】格式）
        counter = 1
        for bid in bids:
            region = bid.get('region', '')
            province = self._extract_province(region)
            bid_type = bid.get("type", "其他")
            title = bid['title']
            url = bid['url']
            pub_date = bid.get('date', datetime.now().strftime('%Y-%m-%d'))
            
            lines.append(f"【{province}-{bid_type}-{counter}】")
            lines.append(f"日期：{pub_date}")
            lines.append(f"标题：{title}")
            lines.append(f"链接：{url}")
            lines.append("")
            counter += 1
        
        lines.append(f"\n{'='*40}")
        lines.append("数据来源: 中国联通采购与招标网")
        lines.append(f"共计 {len(bids)} 条 | 更新时间: {datetime.now().strftime('%H:%M')}")
        
        message = "\n".join(lines)
        
        # 发送消息
        payload = {
            "msg_type": "text",
            "content": {
                "text": message
            }
        }
        
        try:
            response = requests.post(
                self.webhook,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            result = response.json()
            if result.get("code") == 0:
                print(f"\n✅ 成功推送 {len(bids)} 条消息到飞书")
                return True
            else:
                print(f"\n❌ 推送失败: {result}")
                return False
        except Exception as e:
            print(f"\n❌ 推送异常: {e}")
            return False


def main():
    """主函数"""
    print(f"=== 中国联通招标信息抓取开始 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
    
    scraper = UnicomBiddingScraper()
    scraper.init_browser()
    
    try:
        # 抓取所有公告
        bids = scraper.fetch_all()
        
        if not bids:
            print("\n未找到新的招标公告")
            return
        
        print(f"\n共找到 {len(bids)} 条新招标信息")
        
        # 推送到飞书
        pusher = FeishuPusher(FEISHU_WEBHOOK)
        if pusher.send_message(bids):
            # 保存推送记录（使用增强的去重）
            for bid in bids:
                scraper.mark_bid_pushed(bid["title"], bid["url"])
            scraper._save_pushed_records()
        
    finally:
        scraper.close()
    
    print(f"\n=== 抓取完成 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")


if __name__ == "__main__":
    main()
