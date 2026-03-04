#!/bin/bash

# 小红书笔记转PDF工具 - 启动脚本

echo "=================================="
echo "  小红书笔记转PDF工具"
echo "=================================="
echo ""

# 检查Python是否安装
if ! command -v python &> /dev/null; then
    echo "错误：未找到Python，请先安装Python 3.8+"
    exit 1
fi

# 安装依赖
echo "正在检查依赖..."
pip install -q fastapi uvicorn playwright Pillow requests pydantic python-multipart 2>/dev/null

# 检查Playwright Chromium是否安装
if ! python -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); p.chromium.launch(headless=True); p.stop()" 2>/dev/null; then
    echo "正在安装Chromium浏览器..."
    playwright install chromium
fi

echo ""
echo "启动服务..."
echo "访问地址: http://localhost:8000"
echo ""

# 启动服务
cd /mnt/okcomputer/output/api
python app.py
