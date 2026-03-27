#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2026年Q2移动云盘方案PDF生成脚本 - 增强版
使用Playwright生成高质量PDF
"""

import markdown
from markdown_pdf import MarkdownPdf
from markdown_pdf import Section
from pathlib import Path
import os

def create_enhanced_pdf():
    """生成高质量PDF文件"""
    
    # 读取Markdown文件
    md_path = Path("/Users/zhouxinghao/.openclaw/workspace/2026年Q2移动云盘方案_完整版.md")
    pdf_path = Path("/Users/zhouxinghao/.openclaw/workspace/2026年Q2移动云盘方案_完整优化版.pdf")
    
    with open(md_path, 'r', encoding='utf-8') as f:
        md_content = f.read()
    
    # 创建PDF对象 - 不使用自动目录
    pdf = MarkdownPdf(toc_level=0)
    
    # 添加详细的CSS样式
    css = """
    <style>
        @page {
            size: A4;
            margin: 20mm 15mm 25mm 15mm;
            @bottom-center {
                content: "第 " counter(page) " 页";
                font-size: 9pt;
                color: #666;
            }
            @top-left {
                content: "2026年Q2移动云盘及云手机自媒体运营支撑项目方案";
                font-size: 8pt;
                color: #999;
            }
        }
        body {
            font-family: 'Helvetica Neue', Helvetica, Arial, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
            font-size: 11pt;
            line-height: 1.7;
            color: #333;
        }
        h1 {
            font-size: 26pt;
            color: #1a5276;
            text-align: center;
            margin-top: 40pt;
            margin-bottom: 25pt;
            page-break-before: always;
            font-weight: bold;
            border-bottom: 3px solid #1a5276;
            padding-bottom: 15pt;
        }
        h1:first-of-type {
            page-break-before: avoid;
        }
        h2 {
            font-size: 18pt;
            color: #2874a6;
            margin-top: 30pt;
            margin-bottom: 15pt;
            border-bottom: 2px solid #2874a6;
            padding-bottom: 8pt;
            page-break-after: avoid;
            font-weight: bold;
        }
        h3 {
            font-size: 14pt;
            color: #3498db;
            margin-top: 22pt;
            margin-bottom: 12pt;
            page-break-after: avoid;
            font-weight: bold;
        }
        h4 {
            font-size: 12pt;
            color: #5d6d7e;
            margin-top: 16pt;
            margin-bottom: 10pt;
            font-weight: bold;
        }
        p {
            margin-bottom: 12pt;
            text-align: justify;
            text-indent: 0;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 18pt 0;
            font-size: 9pt;
            page-break-inside: avoid;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        th {
            background-color: #2874a6;
            color: white;
            padding: 10pt 8pt;
            text-align: left;
            font-weight: bold;
            border: 1px solid #1a5276;
        }
        td {
            padding: 8pt;
            border: 1px solid #ddd;
            vertical-align: top;
        }
        tr:nth-child(even) {
            background-color: #f8f9fa;
        }
        tr:hover {
            background-color: #ebf5fb;
        }
        code {
            background-color: #f4f6f7;
            padding: 2pt 5pt;
            border-radius: 3pt;
            font-family: 'Courier New', Consolas, monospace;
            font-size: 9pt;
            color: #c0392b;
            border: 1px solid #e5e8e8;
        }
        pre {
            background-color: #f4f6f7;
            padding: 12pt;
            border-radius: 5pt;
            overflow-x: auto;
            font-size: 9pt;
            border: 1px solid #e5e8e8;
            margin: 15pt 0;
        }
        ul, ol {
            margin-bottom: 12pt;
            padding-left: 25pt;
        }
        li {
            margin-bottom: 6pt;
        }
        strong {
            color: #1a5276;
            font-weight: bold;
        }
        blockquote {
            border-left: 4px solid #3498db;
            padding: 12pt 15pt;
            margin: 18pt 0;
            color: #555;
            font-style: italic;
            background-color: #f8f9fa;
            border-radius: 0 5pt 5pt 0;
        }
        hr {
            border: none;
            border-top: 2px solid #e5e8e8;
            margin: 25pt 0;
        }
        a {
            color: #2874a6;
            text-decoration: none;
        }
        .cover-title {
            font-size: 32pt;
            color: #1a5276;
            text-align: center;
            margin-top: 80pt;
            margin-bottom: 30pt;
            font-weight: bold;
            line-height: 1.4;
        }
        .cover-subtitle {
            font-size: 16pt;
            color: #5d6d7e;
            text-align: center;
            margin-bottom: 60pt;
        }
        .cover-info {
            text-align: center;
            color: #777;
            font-size: 11pt;
            line-height: 2;
        }
    </style>
    """
    
    # 将Markdown转换为HTML
    html_content = markdown.markdown(
        md_content,
        extensions=[
            'tables',
            'fenced_code',
            'toc',
            'nl2br',
            'sane_lists'
        ]
    )
    
    # 添加CSS样式
    full_html = css + html_content
    
    # 添加封面页HTML
    cover_html = """
    <div style="page-break-after: always;">
        <div class="cover-title">
            2026年Q2移动云盘及云手机<br>
            自媒体运营支撑项目方案
        </div>
        <div class="cover-subtitle">
            优化版（整合517电信日+毕业季亮点）
        </div>
        <div style="text-align: center; margin-top: 100pt;">
            <div style="color: #1a5276; font-size: 14pt; margin-bottom: 40pt;">
                智存美好，感动常在
            </div>
        </div>
        
        <div class="cover-info">
            <p><strong>方案版本：</strong> V2.0 优化版</p>
            <p><strong>编制日期：</strong> 2026年3月</p>
            <p><strong>执行周期：</strong> 2026年4月-6月</p>
            <p><strong>适用平台：</strong> 小红书、公众号、抖音、视频号</p>
        </div>
        
        <div style="margin-top: 80pt; padding: 20pt; background-color: #f8f9fa; border-radius: 10pt;">
            <div style="color: #555; font-size: 10pt; text-align: center; line-height: 1.8;">
                <p><strong>核心节点：</strong></p>
                <p>母亲节（5月）| 517电信日（5月17日）| 父亲节（6月）| 毕业季（6-7月）| 爱家日（5月15日）</p>
            </div>
        </div>
    </div>
    """
    
    full_html = cover_html + full_html
    
    # 添加章节
    pdf.add_section(Section(full_html, paper_size='A4', borders=(40, 40, -40, -50)))
    
    # 保存PDF
    pdf.save(str(pdf_path))
    
    print(f"PDF生成成功！")
    print(f"文件路径: {pdf_path}")
    file_size = pdf_path.stat().st_size / 1024 / 1024
    print(f"文件大小: {file_size:.2f} MB")
    
    return file_size

if __name__ == '__main__':
    create_enhanced_pdf()
