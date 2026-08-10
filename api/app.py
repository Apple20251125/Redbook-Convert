from fastapi import FastAPI, Form, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from playwright.async_api import async_playwright
from PIL import Image
import html
import io
import httpx
import os
import uuid
import zipfile
import logging
from typing import List, Literal
import platform

from stats_store import (
    get_stats_summary,
    record_conversion,
    record_visit,
    render_stats_dashboard,
    render_stats_login_page,
    safe_init_stats_db,
)
from note_cache import (
    NoteCacheEntry,
    entry_has_images,
    evict_expired,
    get_entry,
    save_entry,
)
from xhs_parser import extract_page_note, fetch_note_via_http, navigate_to_note

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(title="小红书笔记转PDF工具")
safe_init_stats_db()

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 存储目录 - 使用相对路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "downloads")
os.makedirs(OUTPUT_DIR, exist_ok=True)
logger.info(f"输出目录: {OUTPUT_DIR}")


class ConvertRequest(BaseModel):
    url: str
    format: Literal["pdf", "markdown"] = "pdf"  # 使用 Literal 进行验证
    originalText: str = ""  # 原始输入文本，用于提取文件名
    sessionId: str = ""  # 复用同笔记已解析结果，切换 PDF/Markdown 时免重复解析


class VisitRequest(BaseModel):
    visitorId: str
    path: str = "/"


class NoteContent(BaseModel):
    title: str
    content: str
    images: List[str]


class ConvertResponse(BaseModel):
    success: bool
    message: str
    imageCount: int = 0
    format: str = "pdf"  # 新增
    downloadUrl: str = ""  # 重命名：原 pdfUrl
    filename: str = ""
    sessionId: str = ""
    fromCache: bool = False


class StatsResponse(BaseModel):
    totalVisits: int
    uniqueVisitors: int
    totalConversions: int
    pdfCount: int
    markdownCount: int
    lastVisitAt: str | None = None
    lastConversionAt: str | None = None
    databasePath: str
    statsProtected: bool


def extract_url(text: str) -> str:
    """从文本中提取小红书链接"""
    import re

    # 匹配 http/https 开头的小红书链接
    url_pattern = r"(https?://(?:[^\s]*?xiaohongshu\.com[^\s]*|xhslink\.(?:com|cn)[^\s]*))"
    match = re.search(url_pattern, text, re.IGNORECASE)
    if match:
        # 移除尾部可能包含的标点符号
        url = match.group(1)
        url = re.sub(r"[。，！！？?、,，]+$", "", url)
        return url
    return text.strip()


def extract_title_from_text(text: str) -> str:
    """从原始文本中提取标题（链接前的文字）"""
    import re

    # 匹配链接前的所有文字
    match = re.search(r"(.*?)\s*(https?://(?:[^\s]*?xiaohongshu\.com[^\s]*|xhslink\.(?:com|cn)[^\s]*))", text, re.IGNORECASE)
    if match:
        title = match.group(1).strip()
        # 移除常见的复制提示文字
        title = re.sub(r'复制后打开【.*?】查看笔记！.*$', '', title)
        return title.strip()
    return ""


def sanitize_filename(filename: str) -> str:
    """清理文件名中的非法字符"""
    import re

    # Windows不允许的字符: \ / : * ? " < > |
    # 同时移除一些可能导致问题的字符
    illegal_chars = r'[\\/:*?"<>|\x00-\x1f]'
    cleaned = re.sub(illegal_chars, '', filename)

    # 替换连续空格和换行为单个空格
    cleaned = re.sub(r'\s+', ' ', cleaned)

    # 移除首尾空格
    cleaned = cleaned.strip()

    # 如果清理后为空，使用默认名称
    if not cleaned:
        cleaned = "小红书笔记"

    return cleaned


def is_valid_stats_api_key(stats_key: str | None) -> bool:
    configured_key = os.getenv("STATS_API_KEY")
    if not configured_key:
        return True

    return stats_key == configured_key


def require_stats_api_key(x_stats_key: str | None) -> None:
    if not is_valid_stats_api_key(x_stats_key):
        raise HTTPException(status_code=401, detail="未授权访问统计接口")


def _build_launch_args() -> List[str]:
    """Build browser args by OS.

    Linux containers need sandbox-related args; macOS/Windows should avoid them.
    """
    common_args = ["--disable-blink-features=AutomationControlled"]
    if platform.system() == "Linux":
        return common_args + [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-crashpad",
            "--disable-crash-reporter",
            "--no-zygote",
            "--disable-gpu",
        ]
    return common_args


async def _launch_chromium(playwright_instance):
    """Launch browser: preferred channel first, then fallback."""
    common = {"headless": True, "args": _build_launch_args()}
    is_macos = platform.system() == "Darwin"

    try:
        if is_macos:
            # Use Chrome for Testing channel on macOS to avoid headless-shell path issues.
            return await playwright_instance.chromium.launch(**common, channel="chromium")
        return await playwright_instance.chromium.launch(**common)
    except Exception as e:
        logger.warning(
            "Primary chromium launch failed (%s); retrying with channel=chrome. "
            "If this keeps failing, run: playwright install chromium",
            e,
        )
        return await playwright_instance.chromium.launch(**common, channel="chrome")


async def parse_xiaohongshu(url: str) -> NoteContent:
    """解析小红书笔记，获取标题、正文和图片URL"""
    http_result = await fetch_note_via_http(url)
    if http_result and http_result[2]:
        title, content, unique_urls = http_result
        return NoteContent(title=title, content=content, images=unique_urls)

    async with async_playwright() as p:
        browser = await _launch_chromium(p)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15A372 Safari/604.1"
        )
        context.set_default_timeout(60000)
        context.set_default_navigation_timeout(60000)
        page = await context.new_page()

        try:
            await navigate_to_note(page, url)
            title, content, unique_urls = await extract_page_note(page)

            await browser.close()
            return NoteContent(title=title, content=content, images=unique_urls)

        except Exception as e:
            await browser.close()
            raise e


async def download_images(image_urls: List[str], task_id: str, title: str = "小红书笔记") -> List[str]:
    """下载图片到本地"""
    task_dir = os.path.join(OUTPUT_DIR, task_id)
    os.makedirs(task_dir, exist_ok=True)

    downloaded_paths = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.xiaohongshu.com/",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        for i, url in enumerate(image_urls):
            try:
                response = await client.get(url, headers=headers)
                if response.status_code == 200:
                    # 使用标题作为图片文件名
                    img_path = os.path.join(task_dir, f"{title}-{i + 1}.jpg")
                    with open(img_path, "wb") as f:
                        f.write(response.content)
                    downloaded_paths.append(img_path)
                    logger.info(f"成功下载图片 {i + 1}/{len(image_urls)}")
            except Exception as e:
                logger.error(f"下载图片失败 {url}: {e}")

    return downloaded_paths


async def build_text_page(title: str, content: str):
    safe_title = html.escape(title or "小红书笔记")
    safe_content = html.escape(content or "未提取到正文，以下为图片内容。")
    page_html = f"""
    <!doctype html>
    <html>
      <head>
        <meta charset="utf-8" />
        <style>
          @font-face {{
            font-family: 'Noto Sans CJK';
            src: local('Noto Sans CJK SC'), local('Noto Sans SC'), local('Noto Sans CJK');
          }}
          body {{
            margin: 0;
            width: 1240px;
            min-height: 1754px;
            box-sizing: border-box;
            padding: 100px 92px 80px;
            background: #fff;
            font-family: 'Noto Sans CJK', 'Apple Color Emoji', 'Segoe UI Emoji', 'Noto Color Emoji', sans-serif;
            color: #111827;
          }}
          h1 {{
            margin: 0 0 28px;
            font-size: 48px;
            line-height: 1.2;
            font-weight: 800;
            word-break: break-word;
          }}
          .content {{
            font-size: 28px;
            line-height: 1.9;
            white-space: pre-wrap;
            word-break: break-word;
            color: #374151;
          }}
          .footer {{
            position: fixed;
            right: 92px;
            bottom: 70px;
            color: #9ca3af;
            font-size: 22px;
          }}
        </style>
      </head>
      <body>
        <h1>{safe_title}</h1>
        <div class="content">{safe_content}</div>
        <div class="footer">Generated by Redbook Convert</div>
      </body>
    </html>
    """

    async with async_playwright() as p:
        browser = await _launch_chromium(p)
        page = await browser.new_page(viewport={"width": 1240, "height": 1754}, device_scale_factor=2)
        await page.set_content(page_html, wait_until="load")
        element = await page.query_selector("body")
        if not element:
            await browser.close()
            raise ValueError("无法渲染正文页")

        image = await element.screenshot(type="png")
        await browser.close()
        return Image.open(io.BytesIO(image)).convert("RGB")


def create_pdf(text_page: Image.Image, image_paths: List[str], output_path: str):
    """将正文页和图片合并为 PDF"""
    if not image_paths and not text_page:
        raise ValueError("没有内容可以生成PDF")

    images = [text_page]

    for path in image_paths:
        img = Image.open(path)
        if img.mode != "RGB":
            img = img.convert("RGB")
        images.append(img)

    first_image = images[0]
    other_images = images[1:] if len(images) > 1 else []

    first_image.save(
        output_path, save_all=True, append_images=other_images, dpi=(100, 100)
    )


def create_markdown(title: str, content: str, image_paths: List[str], output_path: str):
    """生成 Markdown 文件

    Args:
        title: 笔记标题
        content: 笔记正文内容
        image_paths: 图片路径列表
        output_path: Markdown 文件输出路径

    Raises:
        ValueError: 如果标题和内容均为空
        IOError: 如果文件写入失败
    """
    # 输入验证
    if not title and not content and not image_paths:
        raise ValueError("标题、内容和图片不能全部为空")

    if not isinstance(title, str):
        raise ValueError("标题必须是字符串")

    if not isinstance(content, str):
        raise ValueError("内容必须是字符串")

    if not isinstance(image_paths, list):
        raise ValueError("图片路径必须是列表")

    # 验证图片路径
    for img_path in image_paths:
        if not isinstance(img_path, str) or not img_path.strip():
            raise ValueError("图片路径必须是非空字符串")

    markdown_lines = []

    # 标题
    if title:
        markdown_lines.append(f"# {title}\n")

    # 正文内容
    if content:
        markdown_lines.append(f"{content}\n")

    # 图片引用 - 添加额外的换行以改善格式
    if image_paths:
        # 确保内容后有额外换行
        if content:
            markdown_lines.append("\n")

        for i, img_path in enumerate(image_paths, 1):
            img_filename = os.path.basename(img_path)
            markdown_lines.append(f"![图片{i}](images/{img_filename})\n\n")

    # 写入文件，添加错误处理
    try:
        # 确保输出目录存在
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.writelines(markdown_lines)

        logger.info(f"Markdown 文件已生成: {output_path}")
    except IOError as e:
        logger.error(f"写入 Markdown 文件失败: {output_path}, 错误: {e}")
        raise IOError(f"无法写入 Markdown 文件: {e}")


def create_zip(markdown_path: str, image_dir: str, output_path: str):
    """将 markdown 和图片打包成 ZIP

    Args:
        markdown_path: Markdown 文件路径
        image_dir: 图片目录路径
        output_path: ZIP 文件输出路径

    Raises:
        FileNotFoundError: 如果 markdown 文件或图片目录不存在
        ValueError: 如果图片目录为空
        IOError: 如果 ZIP 文件创建失败
    """
    try:
        # 验证 markdown 文件存在
        if not os.path.exists(markdown_path):
            raise FileNotFoundError(f"Markdown 文件不存在: {markdown_path}")

        # 验证图片目录存在
        if not os.path.exists(image_dir):
            raise FileNotFoundError(f"图片目录不存在: {image_dir}")

        # 确保输出目录存在
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # 添加 markdown 文件
            zipf.write(markdown_path, os.path.basename(markdown_path))

            # 添加图片文件夹
            image_files = [f for f in os.listdir(image_dir) if os.path.isfile(os.path.join(image_dir, f))]

            if not image_files:
                logger.warning(f"图片目录为空: {image_dir}")
            else:
                for filename in image_files:
                    file_path = os.path.join(image_dir, filename)
                    # 在 ZIP 中创建 images/ 子目录
                    zipf.write(file_path, f"images/{filename}")

        logger.info(f"ZIP 文件已生成: {output_path}")

    except FileNotFoundError as e:
        logger.error(f"文件或目录不存在: {e}")
        raise
    except zipfile.BadZipFile as e:
        logger.error(f"创建 ZIP 文件失败: {e}")
        raise IOError(f"无法创建 ZIP 文件: {e}")
    except IOError as e:
        logger.error(f"写入 ZIP 文件失败: {output_path}, 错误: {e}")
        raise IOError(f"无法写入 ZIP 文件: {e}")
    except Exception as e:
        logger.error(f"创建 ZIP 文件时发生未知错误: {e}")
        raise


def cleanup_task_files(task_id: str):
    """清理临时文件"""
    task_dir = os.path.join(OUTPUT_DIR, task_id)
    if os.path.exists(task_dir):
        for file in os.listdir(task_dir):
            try:
                os.remove(os.path.join(task_dir, file))
            except Exception as e:
                logger.warning(f"删除文件失败 {file}: {e}")
        try:
            os.rmdir(task_dir)
        except Exception as e:
            logger.warning(f"删除目录失败 {task_dir}: {e}")


@app.post("/api/convert", response_model=ConvertResponse)
async def convert_note(request: ConvertRequest, x_visitor_id: str | None = Header(default=None)):
    """转换小红书笔记为 PDF 或 Markdown"""
    evict_expired(cleanup_task_files)

    title = extract_title_from_text(request.originalText or request.url)
    clean_title = sanitize_filename(title)
    extracted_url = extract_url(request.url)
    previous_entry, cache_key = get_entry(request.sessionId or None, extracted_url)
    cache_entry = previous_entry
    from_cache = False
    task_id = cache_entry.task_id if cache_entry else str(uuid.uuid4())

    logger.info(f"提取的标题: {clean_title}, 格式: {request.format}, session: {cache_key[:8]}...")

    try:
        if cache_entry and cache_entry.extracted_url == extracted_url and entry_has_images(cache_entry):
            logger.info("复用已缓存的笔记解析与图片")
            note_content = NoteContent(
                title=cache_entry.title,
                content=cache_entry.content,
                images=cache_entry.image_urls,
            )
            image_paths = cache_entry.image_paths
            task_id = cache_entry.task_id
            from_cache = True
            if clean_title != cache_entry.clean_title:
                cache_entry.clean_title = clean_title
        else:
            logger.info(f"开始解析笔记: {extracted_url}")
            note_content = await parse_xiaohongshu(extracted_url)

            if not note_content.images:
                raise HTTPException(
                    status_code=400, detail="未找到笔记图片，请检查链接是否正确"
                )

            logger.info(f"找到 {len(note_content.images)} 张图片，开始下载图片...")
            image_paths = await download_images(note_content.images, task_id, clean_title)

            if not image_paths:
                raise HTTPException(status_code=500, detail="图片下载失败")

            cache_entry = NoteCacheEntry(
                extracted_url=extracted_url,
                task_id=task_id,
                clean_title=clean_title,
                title=note_content.title,
                content=note_content.content,
                image_urls=note_content.images,
                image_paths=image_paths,
                pdf_filename=previous_entry.pdf_filename if previous_entry else None,
                zip_filename=previous_entry.zip_filename if previous_entry else None,
            )
            save_entry(cache_key, cache_entry)

        if request.format == "markdown" and not note_content.content:
            raise HTTPException(
                status_code=400, detail="未找到笔记正文，请检查链接是否正确"
            )

        task_dir = os.path.join(OUTPUT_DIR, task_id)

        if request.format == "pdf":
            pdf_filename = f"{clean_title}.pdf"
            pdf_path = os.path.join(OUTPUT_DIR, pdf_filename)

            if (
                cache_entry
                and cache_entry.pdf_filename == pdf_filename
                and os.path.isfile(pdf_path)
            ):
                logger.info("复用已生成的 PDF")
                return ConvertResponse(
                    success=True,
                    message="转换成功",
                    imageCount=len(image_paths),
                    format="pdf",
                    downloadUrl=f"/api/download/{pdf_filename}",
                    filename=pdf_filename,
                    sessionId=cache_key,
                    fromCache=True,
                )

            logger.info("开始生成 PDF...")
            text_page = await build_text_page(note_content.title, note_content.content)
            create_pdf(text_page, image_paths, pdf_path)
            record_conversion("pdf", pdf_filename, x_visitor_id)
            cache_entry.pdf_filename = pdf_filename
            save_entry(cache_key, cache_entry)

            return ConvertResponse(
                success=True,
                message="转换成功",
                imageCount=len(image_paths),
                format="pdf",
                downloadUrl=f"/api/download/{pdf_filename}",
                filename=pdf_filename,
                sessionId=cache_key,
                fromCache=from_cache,
            )

        if request.format == "markdown":
            zip_filename = f"{clean_title}.zip"
            zip_path = os.path.join(OUTPUT_DIR, zip_filename)

            if (
                cache_entry
                and cache_entry.zip_filename == zip_filename
                and os.path.isfile(zip_path)
            ):
                logger.info("复用已生成的 Markdown ZIP")
                return ConvertResponse(
                    success=True,
                    message="转换成功",
                    imageCount=len(image_paths),
                    format="markdown",
                    downloadUrl=f"/api/download/{zip_filename}",
                    filename=zip_filename,
                    sessionId=cache_key,
                    fromCache=True,
                )

            md_filename = f"{clean_title}.md"
            md_path = os.path.join(task_dir, md_filename)

            logger.info("开始生成 Markdown...")
            create_markdown(note_content.title, note_content.content, image_paths, md_path)

            logger.info("开始打包 ZIP...")
            create_zip(md_path, task_dir, zip_path)
            record_conversion("markdown", zip_filename, x_visitor_id)
            cache_entry.zip_filename = zip_filename
            save_entry(cache_key, cache_entry)

            return ConvertResponse(
                success=True,
                message="转换成功",
                imageCount=len(image_paths),
                format="markdown",
                downloadUrl=f"/api/download/{zip_filename}",
                filename=zip_filename,
                sessionId=cache_key,
                fromCache=from_cache,
            )

        raise HTTPException(status_code=400, detail=f"不支持的格式: {request.format}")

    except HTTPException:
        if not cache_entry:
            cleanup_task_files(task_id)
        raise
    except Exception as e:
        if not cache_entry:
            cleanup_task_files(task_id)
        logger.error(f"转换失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"转换失败: {str(e)}")


@app.get("/api/download/{filename}")
async def download_pdf(filename: str):
    """下载PDF文件"""
    pdf_path = os.path.join(OUTPUT_DIR, filename)

    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="文件不存在或已过期")

    return FileResponse(pdf_path, media_type="application/pdf", filename=filename)


@app.post("/api/track-visit")
async def track_visit(request: VisitRequest):
    """记录页面访问"""
    visitor_id = request.visitorId.strip()
    if not visitor_id:
        raise HTTPException(status_code=400, detail="visitorId 不能为空")

    record_visit(visitor_id, request.path)
    return {"success": True}


@app.get("/api/stats", response_model=StatsResponse)
async def get_stats(request: Request, x_stats_key: str | None = Header(default=None)):
    """获取访问与转换统计"""
    stats_key = x_stats_key or request.cookies.get("stats_key")
    wants_json = request.query_params.get("format") == "json" or "application/json" in request.headers.get("accept", "")

    if not is_valid_stats_api_key(stats_key):
        if wants_json:
            raise HTTPException(status_code=401, detail="未授权访问统计接口")

        from fastapi.responses import HTMLResponse

        return HTMLResponse(render_stats_login_page(), status_code=401)

    stats = get_stats_summary()

    if wants_json:
        return stats

    from fastapi.responses import HTMLResponse

    return HTMLResponse(render_stats_dashboard(stats))


@app.post("/api/stats/login")
async def stats_login(request: Request, stats_key: str = Form(...)):
    if not is_valid_stats_api_key(stats_key):
        from fastapi.responses import HTMLResponse

        return HTMLResponse(render_stats_login_page("密钥不正确，请重试。"), status_code=401)

    from fastapi.responses import RedirectResponse

    response = RedirectResponse(url="/api/stats", status_code=303)
    response.set_cookie(
        key="stats_key",
        value=stats_key,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
    )
    return response


@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {"status": "ok"}


# 挂载前端静态文件 - 尝试多个可能路径
possible_paths = [
    os.path.join(os.path.dirname(BASE_DIR), "app", "dist"),  # 本地开发
    os.path.join(BASE_DIR, "app", "dist"),                   # Docker
    "/app/app/dist",                                         # Docker 绝对路径
]

frontend_dir = None
for path in possible_paths:
    if os.path.exists(path):
        frontend_dir = path
        break

if frontend_dir:
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="static")
    logger.info(f"前端静态文件目录: {frontend_dir}")
else:
    logger.warning("前端静态文件目录不存在")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
