# Markdown 导出功能实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**目标：** 为小红书笔记转 PDF 工具增加 Markdown 导出功能，用户可选择 PDF 或 Markdown 格式。

**架构：** 扩展现有 `/api/convert` 接口增加 `format` 参数，根据参数调用不同的生成流程。前端添加单选按钮组让用户选择格式。Markdown 模式下提取标题、正文、图片，生成 .md 文件并打包 ZIP。

**技术栈：** FastAPI、Playwright、Python zipfile、React、TypeScript、shadcn/ui

---

## Task 1: 扩展后端数据模型

**Files:**
- Modify: `api/app.py:39-48`

**Step 1: 修改 ConvertRequest 增加 format 字段**

找到 `class ConvertRequest(BaseModel)`，增加 `format` 字段：

```python
class ConvertRequest(BaseModel):
    url: str
    format: str = "pdf"  # 新增：默认 pdf，可选 "pdf" 或 "markdown"
```

**Step 2: 修改 ConvertResponse 增加相关字段**

找到 `class ConvertResponse(BaseModel)`，增加 `format` 字段并将 `pdfUrl` 改名为 `downloadUrl`：

```python
class ConvertResponse(BaseModel):
    success: bool
    message: str
    imageCount: int = 0
    format: str = "pdf"  # 新增
    downloadUrl: str = ""  # 重命名：原 pdfUrl
    filename: str = ""
```

**Step 3: 提交**

```bash
cd /Users/tonyl/project/xhs-pdf
git add api/app.py
git commit -m "feat: 扩展请求/响应模型支持 format 参数"
```

---

## Task 2: 增强 parse_xiaohongshu 函数提取文本

**Files:**
- Modify: `api/app.py:103-154`

**Step 1: 修改函数签名返回结构化数据**

找到 `async def parse_xiaohongshu(url: str) -> List[str]`，修改为返回包含标题、正文、图片的结构：

```python
from typing import Dict, List

class NoteContent(BaseModel):
    title: str
    content: str
    images: List[str]

async def parse_xiaohongshu(url: str) -> NoteContent:
    """解析小红书笔记，获取标题、正文和图片URL"""
    chrome_path = get_chrome_executable_path()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, executable_path=chrome_path)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15A372 Safari/604.1"
        )
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(5000)

            # 提取标题
            title = await page.title()
            # 尝试从 h1 标签获取更准确的标题
            h1_element = await page.query_selector("h1")
            if h1_element:
                h1_text = await h1_element.text_content()
                if h1_text:
                    title = h1_text.strip()

            # 提取正文 - 尝试多个可能的选择器
            content_selectors = [
                "div[class*='content']",
                "div[class*='note']",
                "div[class*='text']",
                "article",
                ".note-text",
                ".desc-text"
            ]
            content = ""
            for selector in content_selectors:
                content_element = await page.query_selector(selector)
                if content_element:
                    text = await content_element.text_content()
                    if text and len(text) > 20:  # 确保是正文内容
                        content = text.strip()
                        break

            # 获取所有图片及其位置信息
            images = await page.query_selector_all("img")
            image_data = []

            for img in images:
                src = await img.get_attribute("src")
                if src and ("xiaohongshu" in src or "xhscdn" in src):
                    # 过滤掉头像图片
                    if "avatar" not in src:
                        # 获取图片在页面中的位置（用于排序）
                        box = await img.bounding_box()
                        if box:
                            position = (box.get("y", 0), box.get("x", 0))
                            image_data.append({"url": src, "position": position})

            # 按页面位置排序（先上下后左右）
            image_data.sort(key=lambda x: x["position"])

            # 去重（保持顺序）- 使用有序去重方法
            seen = set()
            unique_urls = []
            for item in image_data:
                url = item["url"]
                # 提取基础URL（去除可能的查询参数）
                base_url = url.split("?")[0]
                if base_url not in seen:
                    seen.add(base_url)
                    unique_urls.append(url)

            await browser.close()
            return NoteContent(title=title or "小红书笔记", content=content, images=unique_urls)

        except Exception as e:
            await browser.close()
            raise e
```

**Step 3: 更新调用 parse_xiaohongshu 的代码**

找到 `convert_note` 函数中调用 `parse_xiaohongshu` 的地方（约第 228 行），修改解包方式：

```python
# 原代码：
# image_urls = await parse_xiaohongshu(extracted_url)

# 修改为：
note_content = await parse_xiaohongshu(extracted_url)
image_urls = note_content.images
note_title = note_content.title
note_text = note_content.content
```

**Step 4: 提交**

```bash
git add api/app.py
git commit -m "feat: 增强 parse_xiaohongshu 提取标题和正文"
```

---

## Task 3: 实现 create_markdown 函数

**Files:**
- Modify: `api/app.py` (在 `create_pdf` 函数后添加)

**Step 1: 添加 create_markdown 函数**

在 `create_pdf` 函数后（约第 201 行后）添加：

```python
def create_markdown(title: str, content: str, image_paths: List[str], output_path: str):
    """生成 Markdown 文件"""
    markdown_lines = []

    # 标题
    markdown_lines.append(f"# {title}\n")

    # 正文内容
    if content:
        markdown_lines.append(f"{content}\n")

    # 图片引用
    for i, img_path in enumerate(image_paths, 1):
        img_filename = os.path.basename(img_path)
        markdown_lines.append(f"\n![图片{i}](images/{img_filename})\n")

    # 写入文件
    with open(output_path, 'w', encoding='utf-8') as f:
        f.writelines(markdown_lines)

    logger.info(f"Markdown 文件已生成: {output_path}")
```

**Step 2: 提交**

```bash
git add api/app.py
git commit -m "feat: 添加 create_markdown 函数"
```

---

## Task 4: 实现 create_zip 函数

**Files:**
- Modify: `api/app.py` (在 `create_markdown` 函数后添加)

**Step 1: 添加 create_zip 函数**

```python
import zipfile

def create_zip(markdown_path: str, image_dir: str, output_path: str):
    """将 markdown 和图片打包成 ZIP"""
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # 添加 markdown 文件
        zipf.write(markdown_path, os.path.basename(markdown_path))

        # 添加图片文件夹
        if os.path.exists(image_dir):
            for filename in os.listdir(image_dir):
                file_path = os.path.join(image_dir, filename)
                if os.path.isfile(file_path):
                    # 在 ZIP 中创建 images/ 子目录
                    zipf.write(file_path, f"images/{filename}")

    logger.info(f"ZIP 文件已生成: {output_path}")
```

**Step 2: 提交**

```bash
git add api/app.py
git commit -m "feat: 添加 create_zip 函数"
```

---

## Task 5: 修改 convert_note 路由支持两种格式

**Files:**
- Modify: `api/app.py:218-271`

**Step 1: 重构 convert_note 函数**

找到 `@app.post("/api/convert", response_model=ConvertResponse)` 函数，修改为：

```python
@app.post("/api/convert", response_model=ConvertResponse)
async def convert_note(request: ConvertRequest):
    """转换小红书笔记为 PDF 或 Markdown"""
    task_id = str(uuid.uuid4())

    try:
        # 1. 解析小红书笔记
        extracted_url = extract_url(request.url)
        logger.info(f"开始解析笔记: {extracted_url}, 格式: {request.format}")

        note_content = await parse_xiaohongshu(extracted_url)

        if not note_content.images:
            raise HTTPException(
                status_code=400, detail="未找到笔记图片，请检查链接是否正确"
            )

        # Markdown 格式需要检查是否有正文
        if request.format == "markdown" and not note_content.content:
            raise HTTPException(
                status_code=400, detail="未找到笔记正文，请检查链接是否正确"
            )

        logger.info(f"找到 {len(note_content.images)} 张图片")

        # 2. 下载图片
        logger.info("开始下载图片...")
        image_paths = await download_images(note_content.images, task_id)

        if not image_paths:
            raise HTTPException(status_code=500, detail="图片下载失败")

        logger.info(f"成功下载 {len(image_paths)} 张图片")

        # 3. 根据格式生成文件
        task_dir = os.path.join(OUTPUT_DIR, task_id)

        if request.format == "pdf":
            # PDF 流程
            pdf_filename = f"小红书笔记_{task_id[:8]}.pdf"
            pdf_path = os.path.join(OUTPUT_DIR, pdf_filename)

            logger.info("开始生成 PDF...")
            create_pdf(image_paths, pdf_path)

            cleanup_task_files(task_id)

            return ConvertResponse(
                success=True,
                message="转换成功",
                imageCount=len(image_paths),
                format="pdf",
                downloadUrl=f"/api/download/{pdf_filename}",
                filename=pdf_filename
            )

        elif request.format == "markdown":
            # Markdown 流程
            md_filename = f"小红书笔记_{task_id[:8]}.md"
            md_path = os.path.join(task_dir, md_filename)

            # 生成 markdown
            logger.info("开始生成 Markdown...")
            create_markdown(note_content.title, note_content.content, image_paths, md_path)

            # 打包 ZIP
            zip_filename = f"小红书笔记_{task_id[:8]}.zip"
            zip_path = os.path.join(OUTPUT_DIR, zip_filename)

            logger.info("开始打包 ZIP...")
            create_zip(md_path, task_dir, zip_path)

            cleanup_task_files(task_id)

            return ConvertResponse(
                success=True,
                message="转换成功",
                imageCount=len(image_paths),
                format="markdown",
                downloadUrl=f"/api/download/{zip_filename}",
                filename=zip_filename
            )

        else:
            cleanup_task_files(task_id)
            raise HTTPException(status_code=400, detail=f"不支持的格式: {request.format}")

    except HTTPException:
        cleanup_task_files(task_id)
        raise
    except Exception as e:
        cleanup_task_files(task_id)
        logger.error(f"转换失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"转换失败: {str(e)}")
```

**Step 2: 提交**

```bash
git add api/app.py
git commit -m "feat: convert_note 支持 PDF 和 Markdown 格式"
```

---

## Task 6: 同步修改 main.py

**Files:**
- Modify: `api/main.py`

将上述 Task 1-5 的相同修改应用到 `api/main.py`（main.py 是纯后端版本，需要保持同步）。

**Step 1-5:** 重复 Task 1-5 的步骤，修改 main.py

**Step 6: 提交**

```bash
git add api/main.py
git commit -m "feat: main.py 同步 Markdown 导出功能"
```

---

## Task 7: 前端添加格式选择状态

**Files:**
- Modify: `app/src/App.tsx`

**Step 1: 添加 format 状态**

找到 `useState` 声明部分（约第 34 行），添加：

```typescript
const [format, setFormat] = useState<'pdf' | 'markdown'>('pdf');
```

**Step 2: 提交**

```bash
git add app/src/App.tsx
git commit -m "feat: 添加格式选择状态"
```

---

## Task 8: 前端添加单选按钮组 UI

**Files:**
- Modify: `app/src/App.tsx`

**Step 1: 导入 RadioGroup 组件**

在 import 语句中添加：

```typescript
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
```

**Step 2: 添加单选按钮组 UI**

在输入框和生成按钮之间（约第 167 行后）添加：

```tsx
{/* Format Selection */}
<div className="space-y-2">
  <label className="text-sm font-medium text-gray-700">选择格式</label>
  <RadioGroup value={format} onValueChange={(value) => setFormat(value as 'pdf' | 'markdown')}>
    <div className="flex items-center space-x-4">
      <div className="flex items-center space-x-2">
        <RadioGroupItem value="pdf" id="pdf" />
        <label htmlFor="pdf" className="text-sm">PDF 格式</label>
      </div>
      <div className="flex items-center space-x-2">
        <RadioGroupItem value="markdown" id="markdown" />
        <label htmlFor="markdown" className="text-sm">Markdown 格式</label>
      </div>
    </div>
  </RadioGroup>
</div>
```

**Step 3: 提交**

```bash
git add app/src/App.tsx
git commit -m "feat: 添加格式选择单选按钮组 UI"
```

---

## Task 9: 前端修改请求携带 format 参数

**Files:**
- Modify: `app/src/App.tsx`

**Step 1: 修改 fetch 请求体**

找到 `handleSubmit` 中的 `fetch` 调用（约第 74 行），修改请求体：

```typescript
const response = await fetch(`${API_BASE_URL}/api/convert`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({ url: extractedUrl, format }),
});
```

**Step 2: 更新状态处理**

找到成功响应处理部分（约第 89 行），更新状态：

```typescript
setConversion({
  status: 'completed',
  message: `成功生成${format === 'pdf' ? 'PDF' : 'Markdown'}！共 ${data.imageCount} 张图片`,
  progress: 100,
  pdfUrl: fullPdfUrl,
  filename: data.filename,
});
```

**Step 3: 调整下载按钮文案**

找到下载按钮部分（约第 218 行），修改：

```typescript
<Button
  onClick={handleDownload}
  className="w-full h-12 bg-gradient-to-r from-green-500 to-emerald-500 hover:from-green-600 hover:to-emerald-600"
>
  <Download className="w-4 h-4 mr-2" />
  {format === 'pdf' ? '下载PDF文件' : '下载Markdown文件 (ZIP)'}
</Button>
```

**Step 4: 提交**

```bash
git add app/src/App.tsx
git commit -m "feat: 请求携带 format 参数，调整 UI 文案"
```

---

## Task 10: 前端构建和部署

**Files:**
- Build: `app/dist/`

**Step 1: 构建前端**

```bash
cd /Users/tonyl/project/xhs-pdf/app
npm run build
```

**Step 2: 验证构建产物**

```bash
ls -la dist/
```

预期看到：
- `index.html`
- `assets/` 目录

**Step 3: 提交构建产物**

```bash
cd /Users/tonyl/project/xhs-pdf
git add app/dist/
git commit -m "build: 更新前端构建产物"
```

---

## Task 11: 功能测试

**Files:**
- Test: 手动测试

**Step 1: 重启后端服务**

```bash
# 停止现有服务（如果正在运行）
pkill -f "python app.py"

# 启动新服务
cd /Users/tonyl/project/xhs-pdf/api
python app.py
```

**Step 2: 测试 PDF 导出**

1. 访问 http://localhost:8000
2. 选择 "PDF 格式"
3. 输入小红书链接
4. 点击生成
5. 验证下载 PDF 文件

**Step 3: 测试 Markdown 导出**

1. 刷新页面
2. 选择 "Markdown 格式"
3. 输入小红书链接
4. 点击生成
5. 下载 ZIP 文件
6. 解压验证结构：
   - `小红书笔记.md`
   - `images/` 文件夹

**Step 4: 测试错误场景**

1. 输入无效链接
2. 输入没有正文的笔记（选择 Markdown）

**Step 5: 记录测试结果**

如果测试通过：
```bash
git commit --allow-empty -m "test: Markdown 导出功能测试通过"
```

---

## 完成检查清单

- [ ] ConvertRequest 包含 format 字段，默认 "pdf"
- [ ] ConvertResponse 包含 format 和 downloadUrl 字段
- [ ] parse_xiaohongshu 返回 NoteContent（标题、正文、图片）
- [ ] create_markdown 生成正确的 markdown 文件
- [ ] create_zip 正确打包 markdown 和 images
- [ ] convert_note 根据 format 调用不同流程
- [ ] 前端有格式选择单选按钮
- [ ] 请求携带 format 参数
- [ ] 下载按钮文案根据格式变化
- [ ] PDF 导出功能正常
- [ ] Markdown 导出功能正常
- [ ] ZIP 包结构正确
- [ ] 错误处理正常

---

## 总结

完成所有任务后，用户将能够：
1. 选择 PDF 或 Markdown 格式
2. 一键转换小红书笔记
3. 下载对应格式的文件

Markdown 文件包含：
- 笔记标题
- 笔记正文
- 图片（本地引用，打包在 ZIP 中）
