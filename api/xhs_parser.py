"""Xiaohongshu note page navigation and extraction helpers."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, List, Tuple

import httpx
from playwright.async_api import Page

logger = logging.getLogger(__name__)

XHS_HOST_PATTERN = re.compile(r"xiaohongshu\.com", re.I)
NOTE_IMAGE_SELECTOR = (
    "img[src*='xhscdn'], img[src*='xiaohongshu'], "
    "img[data-src*='xhscdn'], img[data-src*='xiaohongshu']"
)

EXTRACT_IMAGES_JS = """
() => {
  const items = [];
  for (const img of document.querySelectorAll('img')) {
    const src =
      img.currentSrc ||
      img.src ||
      img.getAttribute('src') ||
      img.getAttribute('data-src') ||
      '';
    if (!src) continue;
    if (!(src.includes('xiaohongshu') || src.includes('xhscdn'))) continue;
    // Skip app UI/static assets, keep only likely note media.
    if (src.includes('picasso-static') || src.includes('/fe-platform/')) continue;
    if (src.includes('avatar')) continue;
    if ((img.naturalWidth || 0) < 120 || (img.naturalHeight || 0) < 120) continue;
    const rect = img.getBoundingClientRect();
    items.push({
      src,
      y: rect.top + window.scrollY,
      x: rect.left + window.scrollX,
    });
  }
  return items;
}
"""

MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15A372 Safari/604.1"
)
XHSLINK_PATTERN = re.compile(r"xhslink\.com", re.I)
NOTE_ID_PATTERN = re.compile(
    r"xiaohongshu\.com/(?:discovery/item|explore)/([a-f0-9]+)", re.I
)
INITIAL_STATE_PATTERN = re.compile(
    r"window\.__INITIAL_STATE__\s*=\s*(\{.+?\})\s*</script>", re.S
)


def _pick_image_url(item: dict[str, Any]) -> str:
    url = item.get("url") or item.get("urlDefault") or ""
    if url:
        return url
    for info in item.get("infoList") or []:
        if isinstance(info, dict):
            candidate = info.get("url") or info.get("urlDefault") or ""
            if candidate:
                return candidate
    return ""


def _parse_initial_state(html: str) -> Tuple[str, str, List[str]] | None:
    match = INITIAL_STATE_PATTERN.search(html)
    if not match:
        return None

    try:
        state = json.loads(match.group(1).replace("undefined", "null"))
    except json.JSONDecodeError:
        return None

    note_data = _find_note_payload(state)
    if not note_data:
        return None

    title = (note_data.get("title") or "").strip()
    content = (note_data.get("desc") or note_data.get("content") or "").strip()

    seen: set[str] = set()
    images: List[str] = []
    for item in note_data.get("imageList") or []:
        if not isinstance(item, dict):
            continue
        url = _pick_image_url(item)
        base = url.split("?")[0]
        if url and base not in seen:
            seen.add(base)
            images.append(url)

    if not images:
        return None

    return title or "小红书笔记", content, images


def _find_note_payload(state: Any) -> dict[str, Any] | None:
    """Locate note payload that contains imageList in INITIAL_STATE."""
    if not isinstance(state, dict):
        return None

    for path in (
        ("noteData", "data", "noteData"),
        ("note", "noteData", "data", "noteData"),
    ):
        node: Any = state
        for key in path:
            if not isinstance(node, dict):
                node = None
                break
            node = node.get(key)
        if isinstance(node, dict) and node.get("imageList"):
            return node

    def walk(obj: Any) -> dict[str, Any] | None:
        if isinstance(obj, dict):
            image_list = obj.get("imageList")
            if isinstance(image_list, list) and image_list:
                if obj.get("title") or obj.get("desc") or obj.get("content"):
                    return obj
            for value in obj.values():
                found = walk(value)
                if found:
                    return found
        elif isinstance(obj, list):
            for value in obj:
                found = walk(value)
                if found:
                    return found
        return None

    return walk(state)


async def _resolve_fetch_url(url: str) -> str:
    normalized = normalize_url(url)
    if XHSLINK_PATTERN.search(normalized):
        resolved = await resolve_note_url_http(normalized)
        if resolved:
            return resolved
    if XHS_HOST_PATTERN.search(normalized):
        return canonical_note_url(normalized) or normalized
    return normalized


async def fetch_note_via_http(url: str) -> Tuple[str, str, List[str]] | None:
    """Fetch note via page HTML — avoids headless browser login redirects."""
    fetch_url = await _resolve_fetch_url(url)
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=30.0,
            headers={"User-Agent": MOBILE_UA},
        ) as client:
            response = await client.get(fetch_url)
            response.raise_for_status()
            parsed = _parse_initial_state(response.text)
            if parsed:
                title, content, images = parsed
                logger.info(
                    "HTTP parse ok: title=%s, images=%s",
                    title[:40],
                    len(images),
                )
                return parsed
    except Exception as exc:
        logger.warning("HTTP note parse failed: %s", exc)
    return None


async def parse_note_content(url: str, page: Page | None = None) -> Tuple[str, str, List[str]]:
    """Parse note via HTTP first; fall back to Playwright DOM extraction."""
    http_result = await fetch_note_via_http(url)
    if http_result and http_result[2]:
        return http_result

    if page is None:
        raise ValueError("Browser page required when HTTP parse finds no images")

    await navigate_to_note(page, url)
    return await extract_page_note(page)


GOTO_RETRYABLE = (
    "ERR_CONNECTION_CLOSED",
    "ERR_CONNECTION_RESET",
    "ERR_NETWORK_CHANGED",
    "ERR_EMPTY_RESPONSE",
    "ERR_TIMED_OUT",
)


def normalize_url(url: str) -> str:
    if url.startswith("http://"):
        return url.replace("http://", "https://", 1)
    return url


def canonical_note_url(url: str) -> str | None:
    """Strip share tokens/query — headless browsers often get blocked on long URLs."""
    match = NOTE_ID_PATTERN.search(url)
    if not match:
        return None
    return f"https://www.xiaohongshu.com/discovery/item/{match.group(1)}"


async def resolve_note_url_http(url: str) -> str | None:
    """Resolve xhslink via HTTP (for canonical URL only, not primary browser navigation)."""
    if not XHSLINK_PATTERN.search(url):
        return None

    normalized = normalize_url(url)
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=20.0,
            headers={"User-Agent": MOBILE_UA},
        ) as client:
            response = await client.get(normalized)
            final_url = str(response.url)
            if XHS_HOST_PATTERN.search(final_url):
                logger.info("xhslink resolved (http): %s -> %s", normalized, final_url[:120])
                return final_url
    except Exception as exc:
        logger.warning("xhslink HTTP resolve failed: %s", exc)
    return None


def build_goto_candidates(url: str, resolved: str | None) -> List[str]:
    """Order matters: short link / clean URL first; full token URL last."""
    normalized = normalize_url(url)
    seen: set[str] = set()
    candidates: List[str] = []

    def add(candidate: str | None) -> None:
        if not candidate or candidate in seen:
            return
        seen.add(candidate)
        candidates.append(candidate)

    if XHSLINK_PATTERN.search(normalized):
        add(normalized)

    if resolved:
        add(canonical_note_url(resolved))
        add(resolved)

    if XHS_HOST_PATTERN.search(normalized):
        add(canonical_note_url(normalized))
        add(normalized)

    return candidates


async def _goto_note_page(page: Page, url: str) -> None:
    last_error: Exception | None = None
    for wait_until in ("domcontentloaded", "commit"):
        try:
            await page.goto(url, wait_until=wait_until, timeout=45000)
            return
        except Exception as exc:
            last_error = exc
            message = str(exc)
            if not any(token in message for token in GOTO_RETRYABLE):
                raise
            logger.warning("goto failed (%s) for %s: %s", wait_until, url[:80], message)
    assert last_error is not None
    raise last_error


async def navigate_to_note(page: Page, url: str) -> None:
    """Open URL and wait through xhslink redirects until note page is ready."""
    normalized = normalize_url(url)
    resolved = await resolve_note_url_http(normalized) if XHSLINK_PATTERN.search(normalized) else None
    candidates = build_goto_candidates(normalized, resolved)

    last_error: Exception | None = None
    for candidate in candidates:
        try:
            logger.info("Navigating to note: %s", candidate[:120])
            await _goto_note_page(page, candidate)
            last_error = None
            break
        except Exception as exc:
            last_error = exc
            logger.warning("Navigation candidate failed: %s", candidate[:120])

    if last_error is not None:
        raise last_error

    if not XHS_HOST_PATTERN.search(page.url):
        for _ in range(20):
            if XHS_HOST_PATTERN.search(page.url):
                break
            await page.wait_for_timeout(1000)
        else:
            logger.warning("Timed out waiting for xiaohongshu.com redirect from %s", url)

    try:
        await page.wait_for_load_state("load", timeout=30000)
    except Exception:
        pass

    try:
        await page.wait_for_selector(NOTE_IMAGE_SELECTOR, timeout=30000)
    except Exception:
        logger.warning("Timed out waiting for note images on %s", page.url)

    await page.wait_for_timeout(2000)


async def _extract_once(page: Page) -> Tuple[str, str, List[str]]:
    # Trigger lazy-loaded note images before extraction.
    await page.evaluate(
        """async () => {
          const total = Math.max(
            document.body ? document.body.scrollHeight : 0,
            document.documentElement ? document.documentElement.scrollHeight : 0
          );
          const step = 900;
          const maxStep = Math.min(total, 7000);
          for (let y = 0; y <= maxStep; y += step) {
            window.scrollTo(0, y);
            await new Promise((resolve) => setTimeout(resolve, 250));
          }
          window.scrollTo(0, 0);
        }"""
    )

    title = await page.title()
    h1_element = await page.query_selector("h1")
    if h1_element:
        h1_text = await h1_element.text_content()
        if h1_text:
            title = h1_text.strip()

    content_selectors = [
        "div[class*='content']",
        "div[class*='note']",
        "div[class*='text']",
        "article",
        ".note-text",
        ".desc-text",
    ]
    content = ""
    for selector in content_selectors:
        content_element = await page.query_selector(selector)
        if content_element:
            text = await content_element.text_content()
            if text and len(text) > 20:
                content = text.strip()
                break

    raw_images = await page.evaluate(EXTRACT_IMAGES_JS)
    raw_images.sort(key=lambda item: (item.get("y", 0), item.get("x", 0)))

    seen: set[str] = set()
    unique_urls: List[str] = []
    for item in raw_images:
        src = item.get("src", "")
        base_url = src.split("?")[0]
        if base_url and base_url not in seen:
            seen.add(base_url)
            unique_urls.append(src)

    return title or "小红书笔记", content, unique_urls


async def extract_page_note(page: Page, retries: int = 3) -> Tuple[str, str, List[str]]:
    """Extract note fields; retry when redirect destroys the execution context."""
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            # navigate_to_note() already waited for redirects + a note-image selector.
            # Waiting again for "domcontentloaded" can hang on SPAs / intermediate redirects,
            # and in our server context it inherits a 60s default timeout.
            # We keep a short "load" wait to reduce stale-context issues.
            try:
                await page.wait_for_load_state("load", timeout=15000)
            except Exception:
                pass
            return await _extract_once(page)
        except Exception as exc:
            last_error = exc
            message = str(exc)
            if attempt >= retries - 1:
                break
            if "Execution context was destroyed" in message or "navigation" in message.lower():
                logger.warning(
                    "Note extract interrupted by navigation (attempt %s/%s), retrying...",
                    attempt + 1,
                    retries,
                )
                await page.wait_for_timeout(2000)
                try:
                    await page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass
                continue
            raise

    assert last_error is not None
    raise last_error
