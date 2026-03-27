#!/usr/bin/env python3
"""
中国移动招标信息抓取与飞书推送系统
支持抓取：
- 采购公告、资格预审公告、候选人公示、中选结果公示、直接采购公示
- 采购意见征求公告
"""

import json
import os
import re
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dateutil import parser as date_parser

import requests
from playwright.sync_api import sync_playwright, Page

# 配置
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK", "https://open.feishu.cn/open-apis/bot/v2/hook/3f57d6e3-20d7-4511-bb85-695352fbd651")
FETCH_HOURS = int(os.getenv("FETCH_HOURS", "48"))  # 抓取48小时内的公告
PUSHED_RECORDS_FILE = "pushed_bids.json"

# 关键词列表
KEYWORDS = [
    "算力", "数据", "战略"
]

# 公告类型映射（只保留需要的6种类型）
BID_TYPE_MAP = {
    "CANDIDATE_PUBLICITY": "候选人公示",
    "WIN_BID": "中选结果公示",
    "WIN_BID_PUBLICITY": "中选结果公示",
    "BIDDING": "采购公告",
    "BIDDING_PROCUREMENT": "采购公告",
    "PROCUREMENT": "直接采购公示",
    "PREQUALIFICATION": "资格预审公告",
}


class BiddingScraper:
    """招标信息抓取类"""
    
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.pushed_records = self._load_pushed_records()
    
    def _load_pushed_records(self) -> set:
        """加载已推送的记录"""
        if os.path.exists(PUSHED_RECORDS_FILE):
            try:
                with open(PUSHED_RECORDS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return set(data.get("urls", []))
            except:
                pass
        return set()
    
    def _save_pushed_records(self):
        """保存已推送的记录"""
        with open(PUSHED_RECORDS_FILE, 'w', encoding='utf-8') as f:
            json.dump({"urls": list(self.pushed_records)}, f, ensure_ascii=False)
    
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
            # 点击包含该标题的元素
            title_elem = page.locator(f"text={title_text}").first
            if title_elem.count() == 0:
                return None
            
            # 新开标签页
            with self.context.expect_page() as new_page_info:
                title_elem.click()
            
            new_page = new_page_info.value
            new_page.wait_for_load_state("networkidle")
            detail_url = new_page.url
            new_page.close()
            
            return detail_url
        except Exception as e:
            print(f"  获取详情URL失败: {e}")
            return None
    
    def _parse_bid_type_from_url(self, url: str) -> Optional[str]:
        """从URL解析公告类型，只返回需要的6种类型"""
        # 采购意见征求公告（特殊处理）
        if "opinionSolicitationDetail" in url or "opinion" in url.lower():
            return "采购意见征求公告"

        match = re.search(r'publishType=([A-Z_]+)', url)
        if match:
            publish_type = match.group(1)
            # 只返回需要的类型
            if publish_type in BID_TYPE_MAP:
                return BID_TYPE_MAP[publish_type]

        # 不符合要求的类型返回None
        return None

    def _extract_province(self, company: str) -> str:
        """从公司名称中提取省份/地区"""
        # 省份列表
        provinces = [
            "北京", "天津", "上海", "重庆", "河北", "山西", "辽宁", "吉林", "黑龙江",
            "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南",
            "广东", "海南", "四川", "贵州", "云南", "陕西", "甘肃", "青海", "台湾",
            "内蒙古", "广西", "西藏", "宁夏", "新疆",
            "香港", "澳门"
        ]

        # 检查是否包含省份名
        for province in provinces:
            if province in company:
                return province

        # 特殊情况处理
        if "紫金研究院" in company:
            return "江苏"
        if "中移铁通" in company or "中移在线" in company or "中移终端" in company:
            return "总部"
        if "网络优化中心" in company or "DICT中心" in company:
            return "总部"

        # 返回原公司名（缩短）
        return company[:6] if len(company) > 6 else company
    
    def _check_keywords(self, title: str, company: str) -> List[str]:
        """检查标题是否包含关键词"""
        matched = []
        for keyword in KEYWORDS:
            if keyword in title:
                matched.append(keyword)
        return matched
    
    def _is_within_time_range(self, pub_time_str: str) -> bool:
        """检查发布时间是否在抓取时间范围内"""
        try:
            # 尝试解析时间
            bid_datetime = date_parser.parse(pub_time_str)
            cutoff_time = datetime.now() - timedelta(hours=FETCH_HOURS)
            return bid_datetime >= cutoff_time
        except:
            # 如果解析失败，默认保留
            return True
    
    def fetch_bidding_procurement(self) -> List[Dict]:
        """抓取招标采购公告页面（前三页）"""
        url = "https://b2b.10086.cn/#/biddingProcurementBulletin"
        return self._fetch_multiple_pages(url, "bidding", max_pages=3)
    
    def fetch_procurement_services(self) -> List[Dict]:
        """抓取采购服务页面（意见征求公告，前三页）"""
        url = "https://b2b.10086.cn/#/procurementServices"
        return self._fetch_multiple_pages(url, "opinion", max_pages=3)
    
    def _fetch_multiple_pages(self, url: str, page_type: str, max_pages: int = 3) -> List[Dict]:
        """抓取多页招标信息"""
        results = []
        page = self.context.new_page()
        
        try:
            print(f"\n正在访问: {url}")
            page.goto(url, wait_until="networkidle", timeout=60000)
            time.sleep(5)  # 等待页面完全加载
            
            for current_page in range(1, max_pages + 1):
                print(f"\n  正在抓取第 {current_page} 页...")
                
                # 等待表格加载
                try:
                    page.wait_for_selector(".el-table__body-wrapper table tbody tr", timeout=30000)
                except:
                    try:
                        page.wait_for_selector("table tbody tr", timeout=10000)
                    except:
                        print("  警告: 表格加载超时，尝试继续...")
                
                time.sleep(2)
                
                # 获取当前页数据
                page_results = self._parse_current_page(page)
                results.extend(page_results)
                
                # 如果不是最后一页，点击下一页
                if current_page < max_pages:
                    try:
                        # 尝试多种方式找到下一页按钮
                        next_button = None
                        
                        # 方式1: 通过 aria-label="下一页" 或包含 "下一页" 文本
                        next_btn = page.locator("button[aria-label='下一页'], button:has-text('下一页'), .el-pagination .btn-next").first
                        if next_btn.count() > 0 and next_btn.is_enabled():
                            next_button = next_btn
                        
                        # 方式2: 通过 class 名查找
                        if not next_button:
                            next_btn2 = page.locator(".el-pagination button.btn-next, .pagination .next, [class*='next']").first
                            if next_btn2.count() > 0 and next_btn2.is_enabled():
                                next_button = next_btn2
                        
                        if next_button:
                            # 检查是否已禁用（最后一页）
                            is_disabled = next_button.is_disabled() if hasattr(next_button, 'is_disabled') else False
                            if not is_disabled:
                                next_button.click()
                                time.sleep(3)  # 等待页面加载
                                print(f"  已切换到第 {current_page + 1} 页")
                            else:
                                print(f"  已是最后一页，停止抓取")
                                break
                        else:
                            print(f"  未找到下一页按钮，停止抓取")
                            break
                            
                    except Exception as e:
                        print(f"  翻页失败: {e}，停止抓取")
                        break
            
        except Exception as e:
            print(f"  抓取页面失败: {e}")
        finally:
            page.close()
        
        print(f"\n  共抓取 {len(results)} 条匹配的招标信息")
        return results
    
    def _parse_current_page(self, page) -> List[Dict]:
        """解析当前页面的招标信息"""
        results = []
        
        # 获取所有数据行
        rows = page.query_selector_all(".el-table__body-wrapper table tbody tr")
        if not rows:
            rows = page.query_selector_all("table tbody tr")
        
        print(f"    当前页找到 {len(rows)} 条记录")
        
        for row in rows:
            try:
                # 获取所有单元格
                cells = row.query_selector_all("td")
                if len(cells) < 4:
                    continue
                
                # 提取数据
                company = cells[0].inner_text().strip()  # 采购需求单位
                bid_type_text = cells[1].inner_text().strip()  # 公告类型
                title = cells[2].inner_text().strip()  # 标题
                pub_time = cells[3].inner_text().strip()  # 发布时间
                
                # 检查时间范围
                if not self._is_within_time_range(pub_time):
                    continue
                
                # 检查关键词匹配
                matched_keywords = self._check_keywords(title, company)
                if not matched_keywords:
                    continue
                
                print(f"    发现匹配: {title[:50]}...")
                
                # 获取详情URL（点击标题）
                detail_url = self._get_detail_url(page, title)
                if not detail_url:
                    continue
                
                # 再次检查URL是否已推送
                if detail_url in self.pushed_records:
                    print(f"    已推送过，跳过")
                    continue
                
                # 获取准确的公告类型（只保留需要的6种）
                bid_type = self._parse_bid_type_from_url(detail_url)
                if not bid_type:
                    print(f"    跳过: 不在目标公告类型范围内")
                    continue
                
                # 使用原始公告类型（从网页表格）
                original_type = bid_type_text if bid_type_text else bid_type
                
                bid_info = {
                    "title": title,
                    "url": detail_url,
                    "company": company,
                    "type": original_type,
                    "publish_time": pub_time,
                    "keywords": matched_keywords,
                }
                results.append(bid_info)
                print(f"    ✓ 成功抓取: {title[:50]}...")
                
            except Exception as e:
                print(f"    处理行数据失败: {e}")
                continue
        
        return results
    
    def fetch_all(self) -> List[Dict]:
        """抓取所有公告"""
        all_bids = []
        
        # 抓取招标采购公告
        print("\n=== 抓取招标采购公告 ===")
        bids = self.fetch_bidding_procurement()
        all_bids.extend(bids)
        
        # 抓取采购意见征求公告
        print("\n=== 抓取采购意见征求公告 ===")
        opinions = self.fetch_procurement_services()
        all_bids.extend(opinions)
        
        return all_bids


class FeishuPusher:
    """飞书推送类"""
    
    def __init__(self, webhook: str):
        self.webhook = webhook
    
    def send_message(self, bids: List[Dict]) -> bool:
        """发送招标信息到飞书"""
        if not bids:
            print("\n没有新消息需要推送")
            return True
        
        # 按(采购需求单位, 公告类型)分组
        from collections import defaultdict
        group_bids = defaultdict(list)
        for bid in bids:
            key = (bid['company'], bid['type'])
            group_bids[key].append(bid)
        
        # 按类型分组统计（用于摘要）
        type_count = {}
        for bid in bids:
            bid_type = bid["type"]
            type_count[bid_type] = type_count.get(bid_type, 0) + 1
        
        type_summary = " | ".join([f"{t}{c}条" for t, c in type_count.items()])
        
        # 构建消息内容
        content_parts = [f"您好，此次一共检索{len(bids)}条新消息（{type_summary}）～\n"]
        
        # 按分组输出，格式：【采购需求单位-公告类型-数量】
        for (company, bid_type), bid_list in group_bids.items():
            count = len(bid_list)
            part = f"\n【{company}-{bid_type}-{count}】\n"

            for bid in bid_list:
                part += f"\n日期：{bid['publish_time']}\n"
                part += f"标题：{bid['title']}\n"
                part += f"链接：{bid['url']}\n"

            content_parts.append(part)
        
        message = "".join(content_parts)
        
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
    print(f"=== 招标信息抓取开始 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
    print(f"抓取时间范围: 过去 {FETCH_HOURS} 小时")
    print(f"关键词数量: {len(KEYWORDS)} 个")
    
    # 初始化抓取器
    scraper = BiddingScraper()
    scraper.init_browser()
    
    try:
        # 抓取所有公告
        bids = scraper.fetch_all()
        
        if not bids:
            print("\n未找到匹配关键词的新公告")
            return
        
        print(f"\n共找到 {len(bids)} 条匹配的公告")
        
        # 去重（基于URL）
        unique_bids = []
        seen_urls = set()
        for bid in bids:
            if bid["url"] not in seen_urls:
                unique_bids.append(bid)
                seen_urls.add(bid["url"])
        
        print(f"去重后: {len(unique_bids)} 条")
        
        # 推送到飞书
        pusher = FeishuPusher(FEISHU_WEBHOOK)
        if pusher.send_message(unique_bids):
            # 保存推送记录
            for bid in unique_bids:
                scraper.pushed_records.add(bid["url"])
            scraper._save_pushed_records()
        
    finally:
        scraper.close()
    
    print(f"\n=== 抓取完成 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")


if __name__ == "__main__":
    main()
