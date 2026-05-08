# Xiaohongshu to PDF/Markdown Converter

<div align="center">

![Redbook-Convert](./xhs-pdf-en.png)

### A lightweight web tool that converts Xiaohongshu notes into PDF and Markdown formats

[Demo](https://redbook-convert-production.up.railway.app) • [中文](README-ZH.md) • [Features](#features) • [Quick Start](#deployment) • [API](#api-endpoints)

</div>

## Features

- Supports xhslink.com and xiaohongshu.com links
- Export to PDF or Markdown format
- Automatically extracts all images from notes
- Generates files in reading order
- Bilingual interface (Chinese/English)
- One-click download

## Project Structure

```
xhs-pdf/
├── app/                    # Frontend React application
│   ├── src/               # Source code
│   └── dist/              # Built static files
├── api/                    # Backend API
│   ├── app.py             # Main app (integrated frontend + backend)
│   ├── main.py            # API-only mode
│   ├── requirements.txt   # Python dependencies
│   └── downloads/         # Generated files
├── docs/                   # Documentation
├── README.md              # English documentation
└── README-ZH.md          # Chinese documentation
```

## Deployment

### Option 1: Integrated Deployment (Recommended)

Use integrated `app.py` to serve both frontend and backend:

```bash
cd api
pip install -r requirements.txt
playwright install chromium
python app.py
```

Visit http://localhost:8000 to use.

### Railway (Dockerfile deployment)

This repo is configured for Railway via `Dockerfile` + `railway.json`.

- Runtime entrypoint is `api/app.py` (integrated frontend + backend), not `api/main.py`
- Build includes `playwright install chromium`
- Linux container launch flags are tuned in both `api/app.py` and `api/main.py` for Railway stability

After pushing to `main`, Railway will auto-redeploy.

### Option 2: Separate Frontend and Backend

1. Deploy frontend static files to any static hosting:
   - Frontend files are in `app/dist/`

2. Start backend API:
   ```bash
   cd api
   pip install -r requirements.txt
   playwright install chromium
   python main.py
   ```

3. Update frontend configuration:
   - Edit `app/.env`
   - Set `VITE_API_URL=http://your-backend-url:8000`
   - Rebuild the frontend

## Troubleshooting (Railway / Playwright)

If logs show `chrome_crashpad_handler: Resource temporarily unavailable (11)`:

- Ensure latest code is deployed (contains Linux launch args in `api/app.py`)
- Confirm service actually runs `uvicorn app:app` (from `Dockerfile`)
- Trigger a manual redeploy once after updating

Quick checks:

- `GET /api/health` should return `{"status":"ok"}`
- Then call `POST /api/convert` with a valid `xhslink.com` URL

## API Endpoints

### POST /api/convert

Convert Xiaohongshu note to PDF or Markdown.

**Request Body:**
```json
{
  "url": "http://xhslink.com/xxx",
  "format": "pdf" // or "markdown"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Conversion successful",
  "imageCount": 19,
  "downloadUrl": "/api/download/xxx.pdf",
  "filename": "xxx.pdf"
}
```

### GET /api/download/{filename}

Download generated file.

### GET /api/health

Health check endpoint.

### POST /api/track-visit

Track an anonymous site visit.

**Request Body:**
```json
{
  "visitorId": "anonymous-uuid",
  "path": "/"
}
```

### GET /api/stats

Get traffic and conversion stats.

Open in a browser to view the dashboard; append `?format=json` for raw JSON.

**Response:**
```json
{
  "totalVisits": 120,
  "uniqueVisitors": 87,
  "totalConversions": 42,
  "pdfCount": 30,
  "markdownCount": 12,
  "lastVisitAt": "2026-05-08T03:12:00+00:00",
  "lastConversionAt": "2026-05-08T03:18:00+00:00",
  "databasePath": "/data/stats.db",
  "statsProtected": true
}
```

If `STATS_API_KEY` is configured, browser access shows a login page first; scripts can still include header `X-Stats-Key: your-key`.

## Traffic & Conversion Stats

The project now tracks:

- `totalVisits`: total site opens recorded by the frontend
- `uniqueVisitors`: approximate unique users based on an anonymous browser-local visitor ID
- `pdfCount`: number of successful PDF generations
- `markdownCount`: number of successful Markdown ZIP generations

Data is stored in SQLite. By default the backend writes to:

```bash
api/data/stats.db
```

You can override the path with:

```bash
STATS_DB_PATH=/data/stats.db
```

Recommended Railway setup:

- Add a persistent volume and mount it to `/data`
- Set `STATS_DB_PATH=/data/stats.db`
- Optionally set `STATS_API_KEY=your-secret-key` to protect `/api/stats`

## Requirements

- Python 3.8+
- Node.js 18+ (for frontend development only)
- Chromium browser (automatically installed by Playwright)

## Tech Stack

- Frontend: React + TypeScript + Vite + Tailwind CSS + shadcn/ui
- Backend: FastAPI + Playwright + Pillow
- Deployment: Uvicorn

## Disclaimer

- For learning purposes only, please comply with relevant laws and regulations
- Please respect original content copyright
- Generated files are temporarily stored on the server, recommended to download promptly
