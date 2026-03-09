from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from playwright.async_api import async_playwright
from PIL import Image
import httpx
import os
import uuid
import re
import logging
from typing import List, Literal
import asyncio

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="小红书笔记转PDF API")

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

class ConvertResponse(BaseModel):
    success: bool
    message: str
    imageCount: int = 0
    format: str = "pdf"
    downloadUrl: str = ""
    filename: str = ""

def extract_url(text: str) -> str:
    """从文本中提取小红书链接"""
    # 匹配 http/https 开头的小红书链接
    url_pattern = r'(https?://(?:[^\s]*?xiaohongshu\.com[^\s]*|xhslink\.com[^\s]*))'
    match = re.search(url_pattern, text, re.IGNORECASE)
    if match:
        # 移除尾部可能包含的标点符号
        url = match.group(1)
        url = re.sub(r'[。，！！？?、,，]+$', '', url)
        return url
    return text.strip()

async def parse_xiaohongshu(url: str) -> List[str]:
    """解析小红书笔记，获取所有图片URL"""
    # 使用系统安装的 Chrome 浏览器
    chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            executable_path=chrome_path if os.path.exists(chrome_path) else None
        )
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15A372 Safari/604.1'
        )
        page = await context.new_page()
        
        try:
            await page.goto(url, wait_until='networkidle', timeout=30000)
            await page.wait_for_timeout(5000)
            
            # 获取所有图片
            images = await page.query_selector_all('img')
            image_urls = []
            
            for img in images:
                src = await img.get_attribute('src')
                if src and ('xiaohongshu' in src or 'xhscdn' in src):
                    # 过滤掉头像图片
                    if 'avatar' not in src:
                        image_urls.append(src)
            
            # 去重
            unique_urls = list(set(image_urls))
            await browser.close()
            return unique_urls
            
        except Exception as e:
            await browser.close()
            raise e

async def download_images(image_urls: List[str], task_id: str) -> List[str]:
    """下载图片到本地"""
    task_dir = os.path.join(OUTPUT_DIR, task_id)
    os.makedirs(task_dir, exist_ok=True)

    downloaded_paths = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://www.xiaohongshu.com/'
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        for i, url in enumerate(image_urls):
            try:
                response = await client.get(url, headers=headers)
                if response.status_code == 200:
                    img_path = os.path.join(task_dir, f"image_{i+1:02d}.jpg")
                    with open(img_path, 'wb') as f:
                        f.write(response.content)
                    downloaded_paths.append(img_path)
                    logger.info(f"成功下载图片 {i+1}/{len(image_urls)}")
            except Exception as e:
                logger.error(f"下载图片失败 {url}: {e}")

    return downloaded_paths

def create_pdf(image_paths: List[str], output_path: str):
    """将图片合并为PDF"""
    if not image_paths:
        raise ValueError("没有图片可以生成PDF")
    
    images = []
    for path in image_paths:
        img = Image.open(path)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        images.append(img)
    
    first_image = images[0]
    other_images = images[1:] if len(images) > 1 else []
    
    first_image.save(
        output_path,
        save_all=True,
        append_images=other_images,
        dpi=(100, 100)
    )

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
async def convert_note(request: ConvertRequest):
    """转换小红书笔记为PDF"""
    task_id = str(uuid.uuid4())
    
    try:
        # 1. 解析小红书笔记
        # 从输入中提取实际的URL
        extracted_url = extract_url(request.url)
        logger.info(f"开始解析笔记: {extracted_url}")
        image_urls = await parse_xiaohongshu(extracted_url)

        if not image_urls:
            raise HTTPException(status_code=400, detail="未找到笔记图片，请检查链接是否正确")

        logger.info(f"找到 {len(image_urls)} 张图片")

        # 2. 下载图片
        logger.info("开始下载图片...")
        image_paths = await download_images(image_urls, task_id)

        if not image_paths:
            raise HTTPException(status_code=500, detail="图片下载失败")

        logger.info(f"成功下载 {len(image_paths)} 张图片")

        # 3. 生成PDF
        pdf_filename = f"小红书笔记_{task_id[:8]}.pdf"
        pdf_path = os.path.join(OUTPUT_DIR, pdf_filename)

        logger.info("开始生成PDF...")
        create_pdf(image_paths, pdf_path)

        # 4. 清理临时图片文件
        cleanup_task_files(task_id)

        return ConvertResponse(
            success=True,
            message="转换成功",
            imageCount=len(image_paths),
            downloadUrl=f"/api/download/{pdf_filename}",
            filename=pdf_filename,
            format="pdf",
        )

    except HTTPException:
        cleanup_task_files(task_id)
        raise
    except Exception as e:
        cleanup_task_files(task_id)
        logger.error(f"转换失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"转换失败: {str(e)}")

@app.get("/api/download/{filename}")
async def download_pdf(filename: str):
    """下载PDF文件"""
    pdf_path = os.path.join(OUTPUT_DIR, filename)
    
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="文件不存在或已过期")
    
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=filename
    )

@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
