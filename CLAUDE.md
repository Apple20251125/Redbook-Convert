# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A web tool that converts Xiaohongshu (Little Red Book) notes into PDF files. Users paste a note URL, the backend scrapes the images using Playwright, downloads them, and generates a PDF.

**Tech Stack:**
- Backend: FastAPI + Playwright + Pillow
- Frontend: React + TypeScript + Vite + Tailwind CSS + shadcn/ui
- PDF Generation: Pillow (PIL)

## Architecture

The project supports two deployment modes:

### 1. Integrated Mode (app.py)
Serves both the frontend static files and backend API from a single FastAPI server. Frontend build output (`app/dist/`) is mounted at root path.

### 2. Separated Mode (main.py)
Pure backend API only. Frontend is served separately. The frontend communicates via `VITE_API_URL` environment variable.

### Web Scraping Flow
1. User submits Xiaohongshu URL (xhslink.com or xiaohongshu.com)
2. Playwright launches headless Chromium with mobile user agent
3. Page loads with `networkidle` wait + 5 second buffer
4. Images are extracted from `<img>` tags containing xiaohongshu/xhscdn domains
5. Images are sorted by page position (y, x coordinates) and deduplicated
6. Images downloaded to `downloads/{task_id}/` temporary directory
7. PDF generated with PIL, saved to `downloads/小红书笔记_{task_id[:8]}.pdf`
8. Temporary image files cleaned up

## Common Commands

### Backend Development
```bash
# Install Python dependencies
cd api
pip install -r requirements.txt

# Install Playwright Chromium browser
playwright install chromium

# Run integrated mode (frontend + backend)
python app.py

# Run API-only mode
python main.py
```

### Frontend Development
```bash
cd app

# Install dependencies
npm install

# Development server (with API proxy to localhost:8000)
npm run dev

# Build for production
npm run build

# Lint
npm run lint
```

### Root Startup Script
```bash
# Starts integrated mode (installs dependencies if needed)
./start.sh
```

## Important Implementation Details

### URL Extraction
Both frontend and backend use regex to extract Xiaohongshu URLs from pasted text, removing trailing punctuation:
```regex
https?://(?:[^\s]*?xiaohongshu\.com[^\s]*|xhslink\.com[^\s]*)
```

### Image Ordering
Images are sorted by their page bounding box position (y, x) to maintain reading order, not DOM order.

### Path Handling
- `OUTPUT_DIR` is relative to `api/` directory: `downloads/`
- Temporary task directories: `downloads/{task_id}/`
- PDF files: `downloads/小红书笔记_{task_id[:8]}.pdf`

### Browser Detection
The `get_chrome_executable_path()` function in app.py detects system Chrome across macOS, Windows, and Linux. Falls back to Playwright's bundled Chromium if not found.

### CORS Configuration
CORS is set to allow all origins (`allow_origins=["*"]`) for development flexibility.

### Frontend API Configuration
- `VITE_API_URL` in `app/.env`: Empty string uses relative paths (same origin)
- Vite dev server proxies `/api` to `http://localhost:8000`
- Production builds use the configured `VITE_API_URL` or relative paths

### API Endpoints
- `POST /api/convert` - Convert note URL to PDF
- `GET /api/download/{filename}` - Download generated PDF
- `GET /api/health` - Health check

## Dependencies

### Backend (api/requirements.txt)
- fastapi - Web framework
- uvicorn - ASGI server
- playwright - Browser automation
- Pillow - Image/PDF processing
- httpx - Async HTTP client
- pydantic - Data validation
- python-multipart - Form parsing

### Frontend (app/package.json)
- React 19 - UI framework
- TypeScript - Type safety
- Vite - Build tool
- Tailwind CSS - Styling
- shadcn/ui - Component library (Radix UI primitives)
- lucide-react - Icons
- sonner - Toast notifications
