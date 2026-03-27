#!/usr/bin/env python3
"""
移动+联通 招标信息整合推送系统
同时抓取中国移动(b2b.10086.cn)和中国联通(chinaunicombidding.cn)的招标公告
合并后统一推送到飞书
"""

import json
import os
import re
import hashlib
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dateutil import parser as date_parser

import requests
from playwright.sync_api import sync_playwright, Page

# 配置
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK", "https://open.feishu.cn/open-apis/bot/v2/hook/3f57d6e3-20d7-4511-bb85-695352fbd651")
FETCH_HOURS = int(os.getenv("FETCH_HOURS", "48"))  # 抓取48小时内的公告
PUSHED_RECORDS_FILE = "pushed_bids_combined.json"

# 关键词列表
KEYWORDS = [
    "数智化", "数据", "算力", "战略"
]

# 移动招标公告类型映射
CMCC_BID_TYPE_MAP = {
    "CANDIDATE_PUBLICITY": "候选人公示",
    "WIN_BID": "中选结果公示",
    "WIN_BID_PUBLICITY": "中选结果公示",
    "BIDDING": "采购公告",
    "BIDDING_PROCUREMENT": "采购公告",
    "PROCUREMENT": "直接采购公示",
    "PREQUALIFICATION": "资格预审公告",
}


class CombinedBiddingScraper:
    """整合招标信息抓取类（移动+联通）"""
    
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.pushed_records = self._load_pushed_records()
        self.cmcc_bids = []
        self.unicom_bids = []
    
    def _load_pushed_records(self) -> Dict:
        """加载已推送的记录"""
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
        """生成招标信息的唯一哈希"""
        normalized_title = title.strip()[:50]
        return hashlib.md5(normalized_title.encode('utf-8')).hexdigest()
    
    def is_bid_pushed(self, title: str, url: str) -> bool:
        """检查招标信息是否已推送"""
        bid_hash = self._get_bid_hash(title)
        if bid_hash in self.pushed_records.get("hashes", []):
            return True
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
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
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
    
    def _match_keywords(self, text: str) -> bool:
        """检查文本是否匹配关键词"""
        if not text:
            return False
        text = text.lower()
        return any(kw in text for kw in KEYWORDS)
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """解析日期字符串"""
        try:
            return date_parser.parse(date_str)
        except:
            return None
    
    def _extract_province(self, text: str) -> str:
        """从文本提取省份"""
        if not text:
            return "全国"
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
            if province in text:
                return short_name
        return "全国"
    
    # ============ 移动招标抓取 ============
    def fetch_cmcc_bids(self) -> List[Dict]:
        """抓取移动招标信息"""
        print("\n=== 抓取中国移动招标信息 ===")
        bids = []
        bids.extend(self._fetch_cmcc_page("https://b2b.10086.cn/#/biddingProcurementBulletin", "招标采购公告"))
        bids.extend(self._fetch_cmcc_page("https://b2b.10086.cn/#/procurementServices", "采购意见征求公告"))
        self.cmcc_bids = bids
        return bids
    
    def _fetch_cmcc_page(self, url: str, page_name: str) -> List[Dict]:
        """抓取移动单个页面"""
        print(f"\n正在访问: {page_name}")
        results = []
        page = self.context.new_page()
        
        try:
            page.goto(url, wait_until="networkidle", timeout=60000)
            time.sleep(5)
            
            # 等待表格加载
            page.wait_for_selector("tr.ant-table-row", timeout=10000)
            
            rows = page.locator("tr.ant-table-row").all()
            print(f"  找到 {len(rows)} 条记录")
            
            for row in rows:
                try:
                    cells = row.locator("td").all()
                    if len(cells) < 4:
                        continue
                    
                    bid_type = cells[0].inner_text().strip()
                    company = cells[1].inner_text().strip()
                    title = cells[2].inner_text().strip()
                    date_str = cells[3].inner_text().strip()
                    
                    # 点击获取详情URL
                    title_link = cells[2].locator("a").first
                    if title_link:
                        title_link.click()
                        time.sleep(2)
                        
                        detail_page = self.context.pages[-1]
                        detail_url = detail_page.url
                        detail_page.close()
                        time.sleep(1)
                    else:
                        continue
                    
                    # 关键词匹配
                    if not self._match_keywords(title) and not self._match_keywords(company):
                        continue
                    
                    # 时间检查
                    bid_date = self._parse_date(date_str)
                    if bid_date:
                        cutoff = datetime.now() - timedelta(hours=FETCH_HOURS)
                        if bid_date < cutoff:
                            continue
                    
                    # 去重检查
                    if self.is_bid_pushed(title, detail_url):
                        continue
                    
                    # 解析类型
                    bid_type_cn = "其他"
                    for key, value in CMCC_BID_TYPE_MAP.items():
                        if key in detail_url:
                            bid_type_cn = value
                            break
                    
                    province = self._extract_province(company)
                    
                    results.append({
                        "platform": "移动",
                        "province": province,
                        "type": bid_type_cn,
                        "company": company,
                        "title": title,
                        "url": detail_url,
                        "date": date_str
                    })
                    print(f"  ✓ 发现匹配: {title[:40]}...")
                    
                except Exception as e:
                    continue
                    
        except Exception as e:
            print(f"  抓取失败: {e}")
        finally:
            page.close()
        
        return results
    
    # ============ 联通招标抓取 ============
    def fetch_unicom_bids(self) -> List[Dict]:
        """抓取联通招标信息"""
        print("\n=== 抓取中国联通招标信息 ===")
        bids = []
        page = self.context.new_page()
        
        try:
            page.goto("https://www.chinaunicombidding.cn", wait_until="networkidle", timeout=60000)
            time.sleep(5)
            
            page.wait_for_selector("h5", timeout=10000)
            
            page_num = 1
            max_pages = 5
            
            while page_num <= max_pages:
                print(f"\n  正在处理第 {page_num} 页...")
                time.sleep(2)
                
                title_elements = page.query_selector_all("h5")
                print(f"    本页找到 {len(title_elements)} 条招标信息")
                
                for title_elem in title_elements:
                    try:
                        title = title_elem.inner_text().strip()
                        if not title:
                            continue
                        
                        # 关键词匹配
                        if not self._match_keywords(title):
                            continue
                        
                        # 提取公告类型
                        bid_type = "其他"
                        for t in ["采购公告", "采购结果", "采购计划", "采购准备"]:
                            if t in title:
                                bid_type = t
                                break
                        
                        # 获取详情URL
                        detail_url = "https://www.chinaunicombidding.cn/bidInformation"
                        try:
                            link_elem = title_elem.evaluate("el => el.closest('a')")
                            if link_elem:
                                href = link_elem.get_attribute("href")
                                if href:
                                    detail_url = f"https://www.chinaunicombidding.cn{href}" if href.startswith("/") else href
                        except:
                            pass
                        
                        # 去重检查
                        if self.is_bid_pushed(title, detail_url):
                            print(f"      已推送过，跳过")
                            continue
                        
                        bids.append({
                            "platform": "联通",
                            "province": "全国",
                            "type": bid_type,
                            "company": "中国联通",
                            "title": title,
                            "url": detail_url,
                            "date": datetime.now().strftime("%Y-%m-%d")
                        })
                        print(f"    ✓ 发现匹配: {title[:40]}...")
                        
                    except Exception as e:
                        continue
                
                # 翻页
                try:
                    next_btn = page.locator(".ant-pagination-next").first
                    if next_btn:
                        is_disabled = next_btn.get_attribute("aria-disabled")
                        if is_disabled != "true":
                            next_btn.click()
                            time.sleep(3)
                            page_num += 1
                        else:
                            print(f"\n  已是最后一页，共抓取 {len(bids)} 条")
                            break
                    else:
                        break
                except Exception as e:
                    print(f"\n  翻页结束: {e}，共抓取 {len(bids)} 条")
                    break
                    
        except Exception as e:
            print(f"  抓取失败: {e}")
        finally:
            page.close()
        
        self.unicom_bids = bids
        return bids
    
    def fetch_all(self) -> List[Dict]:
        """抓取所有招标信息"""
        cmcc = self.fetch_cmcc_bids()
        unicom = self.fetch_unicom_bids()
        return cmcc + unicom


class FeishuPusher:
    """飞书推送类"""
    
    def __init__(self, webhook: str):
        self.webhook = webhook
    
    def send_combined_message(self, bids: List[Dict]) -> bool:
        """发送整合后的招标信息到飞书"""
        if not bids:
            print("\n没有新消息需要推送")
            return True
        
        cmcc_bids = [b for b in bids if b.get("platform") == "移动"]
        unicom_bids = [b for b in bids if b.get("platform") == "联通"]
        
        lines = [
            "📢 运营商招标信息汇总",
            f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"📊 共找到 {len(bids)} 条匹配公告",
            f"   中国移动: {len(cmcc_bids)}条 | 中国联通: {len(unicom_bids)}条"
        ]
        
        # 类型统计
        type_stats = {}
        for bid in bids:
            key = f"{bid['platform']}-{bid['type']}"
            type_stats[key] = type_stats.get(key, 0) + 1
        
        if type_stats:
            stats_str = " | ".join([f"{k}:{v}" for k, v in sorted(type_stats.items())])
            lines.append(f"📋 {stats_str}")
        lines.append("")
        
        # 中国移动部分
        if cmcc_bids:
            lines.append("=" * 40)
            lines.append("📱 中国移动招标信息")
            lines.append("=" * 40)
            lines.append("")
            
            for i, bid in enumerate(cmcc_bids, 1):
                lines.append(f"【{bid['province']}-{bid['type']}-{i}】")
                lines.append(f"日期：{bid['date']}")
                lines.append(f"标题：{bid['title']}")
                lines.append(f"链接：{bid['url']}")
                lines.append("")
        
        # 中国联通部分
        if unicom_bids:
            lines.append("=" * 40)
            lines.append("🌐 中国联通招标信息")
            lines.append("=" * 40)
            lines.append("")
            
            for i, bid in enumerate(unicom_bids, 1):
                lines.append(f"【{bid['province']}-{bid['type']}-{i}】")
                lines.append(f"日期：{bid['date']}")
                lines.append(f"标题：{bid['title']}")
                lines.append(f"链接：{bid['url']}")
                lines.append("")
        
        lines.append("=" * 40)
        lines.append(f"数据来源: 中国移动采购与招标网 | 中国联通采购与招标网")
        lines.append(f"关键词: {' | '.join(KEYWORDS)} | 更新时间: {datetime.now().strftime('%H:%M')}")
        
        message = "\n".join(lines)
        
        payload = {
            "msg_type": "text",
            "content": {"text": message}
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
    print(f"=== 运营商招标信息整合抓取开始 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
    print(f"关键词: {' | '.join(KEYWORDS)}")
    
    scraper = CombinedBiddingScraper()
    scraper.init_browser()
    
    try:
        bids = scraper.fetch_all()
        
        if not bids:
            print("\n未找到新的招标公告")
            return
        
        print(f"\n共找到 {len(bids)} 条新招标信息")
        print(f"  中国移动: {len(scraper.cmcc_bids)}条")
        print(f"  中国联通: {len(scraper.unicom_bids)}条")
        
        pusher = FeishuPusher(FEISHU_WEBHOOK)
        if pusher.send_combined_message(bids):
            for bid in bids:
                scraper.mark_bid_pushed(bid["title"], bid["url"])
            scraper._save_pushed_records()
        
    finally:
        scraper.close()
    
    print(f"\n=== 抓取完成 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")


if __name__ == "__main__":
    main()
