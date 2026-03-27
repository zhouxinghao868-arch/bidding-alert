#!/bin/bash
# check-web-search.sh - 检查网络搜索配置

echo "🔍 检查网络搜索配置..."
echo ""

# 检查环境变量
if [ -z "$BRAVE_API_KEY" ]; then
    echo "❌ BRAVE_API_KEY 环境变量未设置"
    echo ""
    echo "解决方法:"
    echo "1. 获取 API Key: https://brave.com/search/api/"
    echo "2. 添加到 ~/.zshrc: export BRAVE_API_KEY='你的_Key'"
    echo "3. 运行: source ~/.zshrc"
    echo "4. 运行: openclaw gateway restart"
else
    echo "✅ BRAVE_API_KEY 已设置"
    echo "   前8位: ${BRAVE_API_KEY:0:8}..."
fi

echo ""
echo "📄 配置文件检查:"
if grep -q "brave:" ~/.openclaw/config.yaml 2>/dev/null; then
    echo "✅ 配置文件中已包含 brave 配置"
else
    echo "❌ 配置文件缺少 brave 配置"
fi

echo ""
echo "🌐 Gateway 状态:"
openclaw gateway status 2>/dev/null || echo "   无法获取状态"
