# Frontend (app)

This directory contains the React + TypeScript + Vite frontend for the Xiaohongshu converter.

## Local Development

```bash
cd app
npm install
npm run dev
```

By default, Vite runs at `http://localhost:5173`.

## API Proxy

In development, API requests under `/api` are proxied to:

- `http://localhost:8000`

This is configured in `vite.config.ts`.

## Build

```bash
cd app
npm run build
```

Build output is generated in `app/dist/`.

## Notes

- For integrated deployment (frontend + backend in one service), use `api/app.py`.
- For separate deployment, run backend via `api/main.py` and configure `VITE_API_URL` as needed.
