# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Fixed
- Stabilized Playwright browser launch on macOS and Railway environments.
- Added Linux-specific Chromium launch flags to avoid `chrome_crashpad_handler` startup failures on Railway.
- Unified browser launch behavior between `api/app.py` (integrated mode) and `api/main.py` (API-only mode).

### Docs
- Added Railway deployment notes and Playwright troubleshooting sections to `README.md` and `README-ZH.md`.

## [1.0.0] - 2026-03-13

### Added
- PDF export functionality for Xiaohongshu notes
- Markdown export functionality
- Bilingual interface (Chinese/English)
- Custom filename based on user input
- Real-time conversion progress display
- Format selection (PDF/Markdown)

### Features
- Support for xhslink.com and xiaohongshu.com links
- Automatic image extraction and ordering
- One-click download
- Integrated deployment mode (frontend + backend)
- Separate deployment mode support

### Tech Stack
- Frontend: React + TypeScript + Vite + Tailwind CSS + shadcn/ui
- Backend: FastAPI + Playwright + Pillow
