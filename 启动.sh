#!/bin/bash
# 协议工具箱 - 启动脚本 (Linux/macOS)
# 作者: Lion
cd "$(dirname "$0")"

if ! command -v python3 &> /dev/null; then
    echo "❌ 请先安装 Python 3.10+"
    exit 1
fi

echo "📦 安装依赖..."
python3 -m pip install -r 依赖文件.txt --break-system-packages

if [ ! -f .env ]; then
    cp .env示例 .env
    echo "⚠️  请编辑 .env 填写 BOT_TOKEN / API_ID / API_HASH"
fi

echo "🚀 启动 协议工具箱..."
python3 并发启动.py