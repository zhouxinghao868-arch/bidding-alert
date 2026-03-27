#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2026年Q2移动云盘方案PDF生成脚本 - WeasyPrint版本
生成更高质量的PDF
"""

import markdown
from weasyprint import HTML, CSS
from pathlib import Path

def create_weasyprint_pdf():
    """使用WeasyPrint生成高质量PDF"""
    
    # 读取Markdown文件
    md_path = Path("/Users/zhouxinghao/.openclaw/workspace/2026年Q2移动云盘方案_完整版.md")
    pdf_path = Path("/Users/zhouxinghao/.openclaw/workspace/2026年Q2移动云盘方案_完整优化版.pdf")
    
    with open(md_path, 'r', encoding='utf-8') as f:
        md_content = f.read()
    
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
    
    # 详细的CSS样式
    css_styles = '''
    @page {
        size: A4;
        margin: 2cm 1.5cm 2.5cm 1.5cm;
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
        font-family: "Helvetica Neue", Helvetica, Arial, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
        font-size: 11pt;
        line-height: 1.7;
        color: #333;
    }
    
    h1 {
        font-size: 24pt;
        color: #1a5276;
        margin-top: 1.5em;
        margin-bottom: 0.8em;
        page-break-before: always;
        font-weight: bold;
        border-bottom: 3px solid #1a5276;
        padding-bottom: 0.3em;
    }
    
    h1:first-of-type {
        page-break-before: avoid;
    }
    
    h2 {
        font-size: 17pt;
        color: #2874a6;
        margin-top: 1.3em;
        margin-bottom: 0.6em;
        border-bottom: 2px solid #2874a6;
        padding-bottom: 0.2em;
        page-break-after: avoid;
        font-weight: bold;
    }
    
    h3 {
        font-size: 13pt;
        color: #3498db;
        margin-top: 1.1em;
        margin-bottom: 0.5em;
        page-break-after: avoid;
        font-weight: bold;
    }
    
    h4 {
        font-size: 11pt;
        color: #5d6d7e;
        margin-top: 0.9em;
        margin-bottom: 0.4em;
        font-weight: bold;
    }
    
    p {
        margin-bottom: 0.7em;
        text-align: justify;
    }
    
    table {
        width: 100%;
        border-collapse: collapse;
        margin: 1em 0;
        font-size: 9pt;
        page-break-inside: avoid;
    }
    
    th {
        background-color: #2874a6;
        color: white;
        padding: 8px 6px;
        text-align: left;
        font-weight: bold;
        border: 1px solid #1a5276;
    }
    
    td {
        padding: 6px;
        border: 1px solid #ddd;
        vertical-align: top;
    }
    
    tr:nth-child(even) {
        background-color: #f8f9fa;
    }
    
    code {
        background-color: #f4f6f7;
        padding: 2px 5px;
        border-radius: 3px;
        font-family: "Courier New", Consolas, monospace;
        font-size: 9pt;
        color: #c0392b;
        border: 1px solid #e5e8e8;
    }
    
    pre {
        background-color: #f4f6f7;
        padding: 12px;
        border-radius: 5px;
        overflow-x: auto;
        font-size: 9pt;
        border: 1px solid #e5e8e8;
        margin: 1em 0;
    }
    
    ul, ol {
        margin-bottom: 0.8em;
        padding-left: 2em;
    }
    
    li {
        margin-bottom: 0.3em;
    }
    
    strong {
        color: #1a5276;
        font-weight: bold;
    }
    
    blockquote {
        border-left: 4px solid #3498db;
        padding: 10px 15px;
        margin: 1em 0;
        color: #555;
        font-style: italic;
        background-color: #f8f9fa;
    }
    
    hr {
        border: none;
        border-top: 2px solid #e5e8e8;
        margin: 1.5em 0;
    }
    '''
    
    # 添加封面
    cover_html = '''
    <div style="page-break-after: always; text-align: center; padding-top: 3cm;">
        <div style="font-size: 28pt; color: #1a5276; margin-bottom: 1cm; font-weight: bold; line-height: 1.4;">
            2026年Q2移动云盘及云手机<br>
            自媒体运营支撑项目方案
        </div>
        
        <div style="font-size: 16pt; color: #5d6d7e; margin-bottom: 2cm;">
            优化版（整合517电信日+毕业季亮点）
        </div>
        
        <div style="color: #1a5276; font-size: 14pt; margin-bottom: 2cm; font-weight: bold;">
            智存美好，感动常在
        </div>
        
        <div style="color: #777; font-size: 11pt; line-height: 2; margin-top: 3cm;">
            <p><strong>方案版本：</strong> V2.0 优化版</p>
            <p><strong>编制日期：</strong> 2026年3月</p>
            <p><strong>执行周期：</strong> 2026年4月-6月</p>
            <p><strong>适用平台：</strong> 小红书、公众号、抖音、视频号</p>
        </div>
        
        <div style="margin-top: 2cm; padding: 15px; background-color: #f8f9fa; border-radius: 8px; display: inline-block;">
            <div style="color: #555; font-size: 10pt; text-align: center; line-height: 1.8;">
                <p><strong>核心节点：</strong></p>
                <p>母亲节 | 517电信日 | 父亲节 | 毕业季 | 爱家日</p>
            </div>
        </div>
    </div>
    '''
    
    full_html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>2026年Q2移动云盘方案</title>
    <style>{css_styles}</style>
</head>
<body>
    {cover_html}
    {html_content}
</body>
</html>'''
    
    # 生成PDF
    HTML(string=full_html).write_pdf(str(pdf_path))
    
    print(f"PDF生成成功！")
    print(f"文件路径: {pdf_path}")
    file_size = pdf_path.stat().st_size / 1024 / 1024
    print(f"文件大小: {file_size:.2f} MB")
    
    return file_size

if __name__ == '__main__':
    create_weasyprint_pdf()
