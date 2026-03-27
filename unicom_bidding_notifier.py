#!/usr/bin/env python3
"""
中国联通招标信息抓取与飞书推送系统
支持从 chinaunicombidding.cn 抓取招标公告
"""

import json
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dateutil import parser as date_parser

import requests
from playwright.sync_api import sync_playwright, Page

# 配置
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK_UNICOM", "https://open.feishu.cn/open-apis/bot/v2/hook/3f57d6e3-20d7-4511-bb85-695352fbd651")
FETCH_DAYS = int(os.getenv("FETCH_DAYS", "1"))  # 默认抓取今天的公告
PUSHED_RECORDS_FILE = "pushed_bids_unicom.json"

# 关键词列表（可根据需要配置）
KEYWORDS = [
    "算力", "数据", "战略", "云", "网络", "系统", "软件", "硬件", "集成"
]


class UnicomBiddingScraper:
    """联通招标信息抓取类"""
    
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
            # 找到包含该标题的链接/卡片
            title_elem = page.locator(f"h5:has-text('{title_text}')").first
            if title_elem.count() == 0:
                return None
            
            # 获取父级可点击元素
            clickable = title_elem.locator("..")
            if clickable.count() == 0:
                # 尝试直接点击标题
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
            print(f"  获取详情URL失败: {e}")
            return None
    
    def _check_keywords(self, title: str, company: str) -> List[str]:
        """检查标题和公司名是否包含关键词"""
        text = f"{title} {company}"
        matched = []
        for keyword in KEYWORDS:
            if keyword in text:
                matched.append(keyword)
        return matched
    
    def _parse_bid_info(self, card_element, page) -> Optional[Dict]:
        """解析单个招标卡片信息"""
        try:
            # 提取公告类型
            bid_type_elem = card_element.query_selector("[class*='tag']")
            bid_type = bid_type_elem.inner_text().strip() if bid_type_elem else "未知"
            
            # 提取标题
            title_elem = card_element.query_selector("h5")
            title = title_elem.inner_text().strip() if title_elem else ""
            
            # 提取招标人
            company_elem = card_element.query_selector("text=招标人：")
            company = ""
            if company_elem:
                # 获取父元素文本
                parent = company_elem.evaluate("el => el.parentElement.innerText")
                if parent:
                    company = parent.replace("招标人：", "").strip()
            
            # 提取招标编号
            bid_no_elem = card_element.query_selector("text=招标编号：")
            bid_no = ""
            if bid_no_elem:
                parent = bid_no_elem.evaluate("el => el.parentElement.innerText")
                if parent:
                    bid_no = parent.replace("招标编号：", "").strip()
            
            # 获取详情URL
            detail_url = self._get_detail_url(page, title)
            if not detail_url:
                # 构造列表页URL作为备选
                detail_url = "https://www.chinaunicombidding.cn/bidInformation"
            
            # 检查是否已推送
            if detail_url in self.pushed_records:
                return None
            
            bid_info = {
                "title": title,
                "url": detail_url,
                "company": company or "中国联通",
                "type": bid_type,
                "bid_no": bid_no,
                "publish_time": datetime.now().strftime("%Y-%m-%d"),
            }
            
            return bid_info
            
        except Exception as e:
            print(f"  解析卡片失败: {e}")
            return None
    
    def fetch_bid_information(self) -> List[Dict]:
        """抓取联通招标信息（筛选今天，翻页抓取全部）"""
        url = "https://www.chinaunicombidding.cn/bidInformation"
        results = []
        page = self.context.new_page()
        
        try:
            print(f"\n正在访问: {url}")
            page.goto(url, wait_until="networkidle", timeout=60000)
            time.sleep(3)  # 等待页面完全加载
            
            # 点击"今天"筛选
            print("  点击'今天'筛选...")
            try:
                today_btn = page.locator("button:has-text('今 天')").first
                if today_btn.count() > 0:
                    today_btn.click()
                    time.sleep(3)  # 等待筛选结果
                    print("  已筛选今天的公告")
                else:
                    print("  警告: 未找到'今天'按钮")
            except Exception as e:
                print(f"  筛选失败: {e}")
            
            # 翻页抓取所有公告
            page_num = 1
            while True:
                print(f"\n  正在抓取第 {page_num} 页...")
                
                # 等待列表加载
                try:
                    page.wait_for_selector("h5", timeout=10000)
                except:
                    print("  警告: 等待标题元素超时")
                
                time.sleep(2)
                
                # 获取当前页的招标信息
                title_elements = page.query_selector_all("h5")
                print(f"    本页找到 {len(title_elements)} 条招标信息")
                
                for title_elem in title_elements:
                    try:
                        title = title_elem.inner_text().strip()
                        if not title:
                            continue
                        
                        # 获取父元素来提取其他信息
                        parent = title_elem.evaluate("el => el.parentElement")
                        if not parent:
                            continue
                        
                        parent_text = parent.inner_text() if hasattr(parent, 'inner_text') else ""
                        
                        # 提取公告类型
                        bid_type = "未知"
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
                        
                        print(f"    发现: {title[:40]}...")
                        
                        # 尝试获取详情URL
                        detail_url = self._get_detail_url(page, title)
                        if not detail_url:
                            detail_url = f"https://www.chinaunicombidding.cn/bidInformation?keyword={title[:30]}"
                        
                        # 检查是否已推送
                        if detail_url in self.pushed_records:
                            print(f"      已推送过，跳过")
                            continue
                        
                        bid_info = {
                            "title": title,
                            "url": detail_url,
                            "company": company or "中国联通",
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
                    # 查找分页信息，看是否已经是最后一页
                    pagination_text = page.locator("text=/第 \\d+-\\d+ 条/总共 \\d+ 条/").first.inner_text()
                    print(f"    分页信息: {pagination_text}")
                    
                    # 查找下一页按钮（使用 ant-pagination 类）
                    # 找所有 ant-pagination-item-link 按钮，第二个是下一页
                    next_btns = page.locator(".ant-pagination-item-link").all()
                    if len(next_btns) >= 2:
                        next_btn = next_btns[1]  # 第二个是下一页按钮
                        is_disabled = next_btn.is_disabled()
                        if not is_disabled:
                            next_btn.click()
                            time.sleep(3)  # 等待页面加载
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
    
    def send_message(self, bids: List[Dict]) -> bool:
        """发送招标信息到飞书"""
        if not bids:
            print("\n没有新消息需要推送")
            return True
        
        # 按公告类型分组统计
        type_count = {}
        for bid in bids:
            bid_type = bid.get("type", "其他")
            type_count[bid_type] = type_count.get(bid_type, 0) + 1
        
        type_summary = " | ".join([f"{t}{c}条" for t, c in type_count.items()])
        
        # 构建消息内容 - 显示全部公告
        content_parts = [f"🎯 中国联通招标信息（今天）\n共检索到{len(bids)}条公告（{type_summary}）\n"]
        
        for bid in bids:
            title = bid['title']
            # 如果标题太长，截断显示
            if len(title) > 40:
                title = title[:37] + "..."
            
            part = f"\n【{bid.get('type', '公告')}】"
            if bid.get('company'):
                company = bid['company']
                if len(company) > 15:
                    company = company[:12] + "..."
                part += f" {company}"
            part += f"\n{title}"
            part += f"\n{bid['url']}\n"
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
    print(f"=== 中国联通招标信息抓取开始 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
    print(f"抓取范围: 今天发布的公告")
    print(f"关键词: {', '.join(KEYWORDS)}")
    
    # 初始化抓取器
    scraper = UnicomBiddingScraper()
    scraper.init_browser()
    
    try:
        # 抓取所有公告
        bids = scraper.fetch_all()
        
        if not bids:
            print("\n未找到新的招标公告")
            return
        
        print(f"\n共找到 {len(bids)} 条招标信息")
        
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
