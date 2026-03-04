# 小红书笔记转PDF工具

一个简单易用的Web工具，可以将小红书笔记转换为PDF文件。

## 功能特点

- 支持 xhslink.com 和 xiaohongshu.com 链接
- 自动提取笔记中的所有图片
- 按顺序生成PDF文件
- 一键下载PDF

## 项目结构

```
xhs-pdf/
├── app/                    # 前端React应用
│   ├── dist/              # 构建后的静态文件
│   ├── src/               # 源代码
│   └── ...
├── api/                    # 后端API
│   ├── app.py             # 主应用（整合前后端）
│   ├── main.py            # 纯后端API
│   ├── requirements.txt   # Python依赖
│   └── downloads/         # 生成的PDF文件
└── README.md              # 本文件
```

## 部署方式

### 方式一：整合部署（推荐）

使用整合的 `app.py`，同时提供前端静态文件和后端API服务：

```bash
cd api
pip install -r requirements.txt
playwright install chromium
python app.py
```

访问 http://localhost:8000 即可使用。

### 方式二：前后端分离部署

1. 部署前端静态文件到任意静态服务器：
   - 前端文件位于 `app/dist/`
   - 已部署到: https://jgg2tfhstnmu2.ok.kimi.link

2. 启动后端API服务：
   ```bash
   cd api
   pip install -r requirements.txt
   playwright install chromium
   python main.py
   ```

3. 修改前端配置：
   - 编辑 `app/.env`
   - 设置 `VITE_API_URL=http://your-backend-url:8000`
   - 重新构建前端

## API接口

### POST /api/convert

转换小红书笔记为PDF。

**请求体：**
```json
{
  "url": "http://xhslink.com/xxx"
}
```

**响应：**
```json
{
  "success": true,
  "message": "转换成功",
  "imageCount": 19,
  "pdfUrl": "/api/download/小红书笔记_xxx.pdf",
  "filename": "小红书笔记_xxx.pdf"
}
```

### GET /api/download/{filename}

下载生成的PDF文件。

### GET /api/health

健康检查接口。

## 依赖要求

- Python 3.8+
- Node.js 18+（仅开发前端时需要）
- Chromium 浏览器（Playwright会自动安装）

## Python依赖

- fastapi
- uvicorn
- playwright
- Pillow
- httpx
- pydantic

## 使用说明

1. 打开网页界面
2. 粘贴小红书笔记链接（支持 xhslink.com 和 xiaohongshu.com）
3. 点击"生成PDF"按钮
4. 等待处理完成
5. 点击"下载PDF文件"按钮下载

## 注意事项

- 工具仅供学习使用，请遵守相关法律法规
- 请尊重原创内容版权
- 生成的PDF文件会在服务器上临时存储，建议及时下载

## 技术栈

- 前端：React + TypeScript + Vite + Tailwind CSS + shadcn/ui
- 后端：FastAPI + Playwright
- 部署：Uvicorn
