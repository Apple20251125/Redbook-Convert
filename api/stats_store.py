import html
import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator, Optional

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "data", "stats.db")


def get_stats_db_path() -> str:
    """Return the configured SQLite path for stats storage."""
    return os.getenv("STATS_DB_PATH", DEFAULT_DB_PATH)


def ensure_stats_db_dir() -> None:
    db_path = get_stats_db_path()
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    ensure_stats_db_dir()
    connection = sqlite3.connect(get_stats_db_path())
    try:
        connection.row_factory = sqlite3.Row
        yield connection
        connection.commit()
    finally:
        connection.close()


def init_stats_db() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS page_visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                visitor_id TEXT NOT NULL,
                path TEXT NOT NULL DEFAULT '/',
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS conversions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                visitor_id TEXT,
                format TEXT NOT NULL,
                filename TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_page_visits_visitor_id
            ON page_visits(visitor_id)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_conversions_visitor_id
            ON conversions(visitor_id)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_conversions_format
            ON conversions(format)
            """
        )


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_visit(visitor_id: str, path: str = "/") -> None:
    if not visitor_id.strip():
        return

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO page_visits (visitor_id, path, created_at)
            VALUES (?, ?, ?)
            """,
            (visitor_id.strip(), path or "/", now_iso()),
        )


def record_conversion(file_format: str, filename: str, visitor_id: Optional[str] = None) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO conversions (visitor_id, format, filename, created_at)
            VALUES (?, ?, ?, ?)
            """,
            ((visitor_id or "").strip() or None, file_format, filename, now_iso()),
        )


def get_stats_summary() -> dict:
    with get_connection() as connection:
        total_visits = connection.execute(
            "SELECT COUNT(*) AS count FROM page_visits"
        ).fetchone()["count"]

        unique_visitors = connection.execute(
            """
            SELECT COUNT(DISTINCT visitor_id) AS count
            FROM (
                SELECT visitor_id FROM page_visits
                UNION ALL
                SELECT visitor_id
                FROM conversions
                WHERE visitor_id IS NOT NULL AND visitor_id != ''
            )
            """
        ).fetchone()["count"]

        conversion_counts = {
            row["format"]: row["count"]
            for row in connection.execute(
                """
                SELECT format, COUNT(*) AS count
                FROM conversions
                GROUP BY format
                """
            ).fetchall()
        }

        total_conversions = sum(conversion_counts.values())

        last_visit_row = connection.execute(
            "SELECT MAX(created_at) AS last_visit_at FROM page_visits"
        ).fetchone()
        last_conversion_row = connection.execute(
            "SELECT MAX(created_at) AS last_conversion_at FROM conversions"
        ).fetchone()

    return {
        "totalVisits": total_visits,
        "uniqueVisitors": unique_visitors,
        "totalConversions": total_conversions,
        "pdfCount": conversion_counts.get("pdf", 0),
        "markdownCount": conversion_counts.get("markdown", 0),
        "lastVisitAt": last_visit_row["last_visit_at"],
        "lastConversionAt": last_conversion_row["last_conversion_at"],
        "databasePath": get_stats_db_path(),
        "statsProtected": bool(os.getenv("STATS_API_KEY")),
    }


def format_stat_time(value: Optional[str]) -> str:
    if not value:
        return "暂无"
    return html.escape(value.replace("T", " ")[:19])


def render_stats_dashboard(stats: dict) -> str:
    pdf_count = int(stats.get("pdfCount", 0) or 0)
    markdown_count = int(stats.get("markdownCount", 0) or 0)
    total_conversions = int(stats.get("totalConversions", 0) or 0)
    total_visits = int(stats.get("totalVisits", 0) or 0)
    unique_visitors = int(stats.get("uniqueVisitors", 0) or 0)
    pdf_share = round((pdf_count / total_conversions) * 100, 1) if total_conversions else 0
    markdown_share = round((markdown_count / total_conversions) * 100, 1) if total_conversions else 0
    protected_badge = "已开启" if stats.get("statsProtected") else "未开启"

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>XHS PDF Stats Dashboard</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #fff7f7;
      --card: rgba(255,255,255,.86);
      --border: rgba(255, 120, 120, .18);
      --text: #1f2937;
      --muted: #6b7280;
      --accent: #ef4444;
      --accent-2: #fb7185;
      --shadow: 0 20px 60px rgba(239, 68, 68, .12);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(251, 113, 133, .18), transparent 30%),
        radial-gradient(circle at top right, rgba(239, 68, 68, .12), transparent 30%),
        linear-gradient(180deg, #fff 0%, var(--bg) 100%);
    }}
    .wrap {{ max-width: 1100px; margin: 0 auto; padding: 40px 20px 56px; }}
    .hero {{
      display: flex; justify-content: space-between; gap: 24px; align-items: end;
      margin-bottom: 24px;
    }}
    .eyebrow {{
      display: inline-flex; align-items: center; gap: 8px;
      padding: 6px 12px; border-radius: 999px; background: rgba(239, 68, 68, .08);
      color: var(--accent); font-weight: 700; font-size: 12px; letter-spacing: .08em; text-transform: uppercase;
    }}
    h1 {{ margin: 12px 0 10px; font-size: clamp(32px, 4vw, 54px); line-height: 1; }}
    .sub {{ margin: 0; color: var(--muted); max-width: 56ch; }}
    .chip {{
      display: inline-flex; align-items: center; gap: 8px;
      padding: 10px 14px; border: 1px solid var(--border); border-radius: 999px;
      background: rgba(255,255,255,.7); box-shadow: var(--shadow); white-space: nowrap;
    }}
    .grid {{
      display: grid; grid-template-columns: repeat(12, 1fr); gap: 16px; margin-top: 24px;
    }}
    .card {{
      grid-column: span 3; padding: 20px; border-radius: 24px;
      background: var(--card); border: 1px solid var(--border); box-shadow: var(--shadow);
      backdrop-filter: blur(12px);
    }}
    .card.big {{ grid-column: span 6; }}
    .label {{ color: var(--muted); font-size: 13px; margin-bottom: 10px; }}
    .value {{ font-size: 34px; font-weight: 800; letter-spacing: -0.04em; }}
    .hint {{ margin-top: 8px; color: var(--muted); font-size: 13px; }}
    .section {{
      margin-top: 18px; padding: 22px; border-radius: 28px; background: rgba(255,255,255,.78);
      border: 1px solid var(--border); box-shadow: var(--shadow);
    }}
    .section h2 {{ margin: 0 0 14px; font-size: 18px; }}
    .row {{ display: flex; justify-content: space-between; gap: 12px; margin-top: 12px; }}
    .bar {{
      height: 12px; border-radius: 999px; overflow: hidden; background: rgba(0,0,0,.06);
      margin-top: 10px;
    }}
    .fill {{ height: 100%; border-radius: inherit; }}
    .fill.pdf {{ background: linear-gradient(90deg, var(--accent), #f97316); width: {pdf_share}%; }}
    .fill.md {{ background: linear-gradient(90deg, #f59e0b, var(--accent-2)); width: {markdown_share}%; }}
    .meta {{
      display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px;
      color: var(--muted); font-size: 14px;
    }}
    code {{ background: rgba(0,0,0,.05); padding: 2px 6px; border-radius: 8px; }}
    @media (max-width: 900px) {{
      .hero {{ flex-direction: column; align-items: start; }}
      .card, .card.big {{ grid-column: span 12; }}
      .meta {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hero">
      <div>
        <div class="eyebrow">XHS PDF Analytics</div>
        <h1>网站统计面板</h1>
        <p class="sub">这是匿名统计仪表盘，帮你快速判断这个项目有没有流量、是不是值得继续做广告投入。</p>
      </div>
      <div class="chip">Stats DB: <code>{html.escape(str(stats.get("databasePath", "")))}</code></div>
    </div>

    <div class="grid">
      <div class="card">
        <div class="label">访问次数</div>
        <div class="value">{total_visits}</div>
        <div class="hint">总页面访问</div>
      </div>
      <div class="card">
        <div class="label">独立访客</div>
        <div class="value">{unique_visitors}</div>
        <div class="hint">浏览器匿名 ID 去重</div>
      </div>
      <div class="card">
        <div class="label">PDF 生成</div>
        <div class="value">{pdf_count}</div>
        <div class="hint">{pdf_share}% of all conversions</div>
      </div>
      <div class="card">
        <div class="label">Markdown 生成</div>
        <div class="value">{markdown_count}</div>
        <div class="hint">{markdown_share}% of all conversions</div>
      </div>
      <div class="card big">
        <div class="label">总转换次数</div>
        <div class="value">{total_conversions}</div>
        <div class="hint">成功进入后端生成流程的次数</div>
        <div class="bar"><div class="fill pdf"></div></div>
        <div class="bar"><div class="fill md"></div></div>
      </div>
      <div class="card big">
        <div class="label">保护状态</div>
        <div class="value">{protected_badge}</div>
        <div class="hint">统计接口是否需要 <code>X-Stats-Key</code></div>
      </div>
    </div>

    <div class="section">
      <h2>Recent</h2>
      <div class="meta">
        <div>最后访问：<code>{format_stat_time(stats.get("lastVisitAt"))}</code></div>
        <div>最后转换：<code>{format_stat_time(stats.get("lastConversionAt"))}</code></div>
      </div>
      <div class="row">
        <span>JSON 数据仍可通过 <code>?format=json</code> 获取</span>
        <span>刷新即可更新</span>
      </div>
    </div>
  </div>
</body>
</html>"""


def render_stats_login_page(error_message: str | None = None) -> str:
    error_html = ""
    if error_message:
        error_html = f'<div class="error">{html.escape(error_message)}</div>'

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Stats Login</title>
  <style>
    :root {{
      --bg: #fff8f6;
      --card: rgba(255,255,255,.92);
      --border: rgba(251, 113, 133, .2);
      --text: #1f2937;
      --muted: #6b7280;
      --accent: #ef4444;
      --shadow: 0 20px 60px rgba(239, 68, 68, .14);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: 24px;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(251, 113, 133, .18), transparent 26%),
        radial-gradient(circle at bottom right, rgba(239, 68, 68, .10), transparent 28%),
        linear-gradient(180deg, #fff 0%, var(--bg) 100%);
    }}
    .card {{
      width: min(100%, 420px);
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 28px;
      box-shadow: var(--shadow);
      padding: 28px;
      backdrop-filter: blur(12px);
    }}
    .eyebrow {{
      display: inline-flex;
      padding: 6px 12px;
      border-radius: 999px;
      background: rgba(239, 68, 68, .08);
      color: var(--accent);
      font-weight: 700;
      font-size: 12px;
      letter-spacing: .08em;
      text-transform: uppercase;
    }}
    h1 {{ margin: 14px 0 10px; font-size: 32px; line-height: 1.05; }}
    p {{ margin: 0 0 18px; color: var(--muted); line-height: 1.6; }}
    label {{ display: block; margin-bottom: 8px; font-size: 14px; font-weight: 600; }}
    input {{
      width: 100%;
      padding: 14px 16px;
      border-radius: 16px;
      border: 1px solid rgba(0,0,0,.08);
      font-size: 15px;
      outline: none;
    }}
    input:focus {{
      border-color: rgba(239, 68, 68, .45);
      box-shadow: 0 0 0 4px rgba(239, 68, 68, .08);
    }}
    button {{
      width: 100%;
      margin-top: 16px;
      border: 0;
      border-radius: 16px;
      padding: 14px 16px;
      font-size: 15px;
      font-weight: 700;
      color: white;
      background: linear-gradient(135deg, #ef4444, #fb7185);
      cursor: pointer;
    }}
    .error {{
      margin-bottom: 14px;
      padding: 12px 14px;
      border-radius: 14px;
      color: #b91c1c;
      background: rgba(239, 68, 68, .08);
      border: 1px solid rgba(239, 68, 68, .14);
      font-size: 14px;
    }}
    .hint {{
      margin-top: 14px;
      font-size: 13px;
      color: var(--muted);
    }}
    code {{
      background: rgba(0,0,0,.05);
      padding: 2px 6px;
      border-radius: 8px;
    }}
  </style>
</head>
<body>
  <div class="card">
    <div class="eyebrow">Protected Stats</div>
    <h1>输入访问密钥</h1>
    <p>这个统计面板已受保护。输入正确的密钥后，浏览器会记住本次登录状态。</p>
    {error_html}
    <form method="post" action="/api/stats/login">
      <label for="stats_key">X-Stats-Key</label>
      <input id="stats_key" name="stats_key" type="password" placeholder="请输入统计访问密钥" autocomplete="current-password" required />
      <button type="submit">进入 Dashboard</button>
    </form>
    <div class="hint">脚本调用仍可继续使用请求头 <code>X-Stats-Key</code>。</div>
  </div>
</body>
</html>"""


def safe_init_stats_db() -> None:
    try:
        init_stats_db()
        logger.info("统计数据库已初始化: %s", get_stats_db_path())
    except Exception as exc:
        logger.error("初始化统计数据库失败: %s", exc)
        raise
