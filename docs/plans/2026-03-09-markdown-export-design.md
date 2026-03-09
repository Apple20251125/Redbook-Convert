# Markdown 导出功能设计

**日期**: 2026-03-09
**状态**: 已批准

## 概述

为小红书笔记转 PDF 工具增加 Markdown 导出功能，用户可以选择将笔记导出为 PDF 或 Markdown 格式。

## 功能需求

### 核心功能
- 支持将小红书笔记导出为 Markdown 格式
- 用户可选择 PDF 或 Markdown 格式（单选）
- Markdown 包含：标题 + 正文文本 + 图片
- 图片本地保存到 `images/` 文件夹，使用相对路径引用
- 打包成 ZIP 文件下载（包含 .md 和 images/）

### 用户交互
- 前端添加单选按钮组：PDF 格式 / Markdown 格式
- 下载按钮文案根据格式调整

## 架构设计

### 后端架构

#### API 扩展
修改 `/api/convert` 接口，增加 `format` 参数：

```python
class ConvertRequest(BaseModel):
    url: str
    format: str = "pdf"  # 新增：默认 pdf
```

#### 响应结构
```python
class ConvertResponse(BaseModel):
    success: bool
    message: str
    imageCount: int = 0
    format: str  # 新增："pdf" | "markdown"
    downloadUrl: str  # 重命名：原 pdfUrl
    filename: str
```

### 核心流程

#### Markdown 生成流程
```
1. parse_xiaohongshu() — 增强现有函数：
   - 提取标题（<h1> 或 <title>）
   - 提取正文文本（笔记内容区域）
   - 提取图片 URL（现有逻辑）

2. download_images() — 复用现有函数

3. create_markdown() — 新增函数：
   - 生成 .md 文件内容
   - 格式：# 标题\n\n正文\n\n![图片](images/image_01.jpg)

4. create_zip() — 新增函数：
   - 使用 zipfile 库打包
   - 结构：note.md + images/*.jpg
   - 保存到 downloads/小红书笔记_{id}.zip
```

#### 文本提取策略
- 标题：从 `document.title` 或页面 `<h1>` 标签
- 正文：从笔记内容容器（通过 selector 定位）

### 前端设计

#### UI 布局
```
[ 输入框 ]
━━━━━━━━━━━━━━━━━━
○ PDF 格式   ○ Markdown 格式
━━━━━━━━━━━━━━━━━━
[ 生成PDF 按钮 ]
```

#### 状态管理
```typescript
const [format, setFormat] = useState<'pdf' | 'markdown'>('pdf');

fetch('/api/convert', {
  body: JSON.stringify({ url: extractedUrl, format })
});
```

#### 下载按钮
- PDF: `下载PDF文件`
- Markdown: `下载Markdown文件 (ZIP)`

### 文件结构

#### 输出目录
```
downloads/
├── 小红书笔记_{task_id[:8]}.pdf      # PDF 格式
├── 小红书笔记_{task_id[:8]}.zip      # Markdown ZIP 包
└── {task_id}/                        # 临时文件夹（转换后删除）
    ├── image_01.jpg
    └── ...
```

#### ZIP 包结构
```
小红书笔记_abc123.zip
├── 小红书笔记.md
└── images/
    ├── image_01.jpg
    └── image_02.jpg
```

#### Markdown 内容示例
```markdown
# 笔记标题

这是笔记的正文内容...

![图片](images/image_01.jpg)

更多正文内容...

![图片](images/image_02.jpg)
```

### 错误处理

1. **文本提取失败**：返回 400，"未找到笔记正文，请检查链接"
2. **图片部分失败**：跳过，在 Markdown 末尾添加注释
3. **ZIP 创建失败**：返回 500，"文件打包失败"
4. **文件名冲突**：使用 task_id 确保唯一性

### 技术实现

#### 后端依赖
- `zipfile` — Python 标准库，用于 ZIP 打包

#### 前端组件
- 使用 shadcn/ui 的 Radio Group 组件
- 复用现有的 Button、Card、Progress 等组件

## 实现计划

1. 后端实现
   - 扩展 ConvertRequest 和 ConvertResponse
   - 增强 parse_xiaohongshu() 提取文本
   - 实现 create_markdown() 函数
   - 实现 create_zip() 函数
   - 修改 /api/convert 路由逻辑

2. 前端实现
   - 添加格式选择状态
   - 添加单选按钮组 UI
   - 修改请求携带 format 参数
   - 调整下载按钮文案

3. 测试
   - PDF 导出回归测试
   - Markdown 导出功能测试
   - ZIP 包结构验证
   - 错误场景测试
