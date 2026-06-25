import json
import sys
from pathlib import Path

def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR        = _get_base_dir()
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"


def _ddg_search(query: str, max_results: int = 8) -> list[dict]:
    try:
        from ddgs import DDGS
    except ImportError:
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            return _ddg_scrape(query, max_results)

    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title":   r.get("title",  ""),
                    "snippet": r.get("body",   ""),
                    "url":     r.get("href",   ""),
                })
    except Exception as e:
        print(f"[WebSearch] ⚠️ DDGS lib failed: {e} — scraping instead")
        results = _ddg_scrape(query, max_results)
    return results


def _ddg_scrape(query: str, max_results: int = 8) -> list[dict]:
    import requests
    from bs4 import BeautifulSoup

    results = []
    try:
        resp = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
            },
            timeout=10,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for item in soup.select(".result")[:max_results]:
            title_el = item.select_one(".result__title a, .result__a")
            snippet_el = item.select_one(".result__snippet")
            url_el = item.select_one(".result__url, .result__extras__url")
            title   = title_el.get_text(strip=True) if title_el else ""
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""
            url     = url_el.get_text(strip=True) if url_el else ""
            if not url and title_el and title_el.get("href"):
                url = title_el["href"]
            if title:
                results.append({"title": title, "snippet": snippet, "url": url})
    except Exception as e:
        print(f"[WebSearch] ❌ DDG scrape failed: {e}")
    return results


def _format_results(query: str, results: list[dict]) -> str:
    if not results:
        return f"No results found for: {query}"

    lines = [f"Search results for: {query}\n"]
    for i, r in enumerate(results, 1):
        if r.get("title"):   lines.append(f"{i}. {r['title']}")
        if r.get("snippet"): lines.append(f"   {r['snippet']}")
        if r.get("url"):     lines.append(f"   {r['url']}")
        lines.append("")
    return "\n".join(lines).strip()


def _compare(items: list[str], aspect: str) -> str:
    all_results: dict[str, list] = {}
    for item in items:
        try:
            all_results[item] = _ddg_search(f"{item} {aspect}", max_results=3)
        except Exception:
            all_results[item] = []

    lines = [f"Comparison — {aspect.upper()}", "─" * 40]
    for item in items:
        lines.append(f"\n▸ {item}")
        for r in all_results.get(item, [])[:2]:
            if r.get("snippet"):
                lines.append(f"  • {r['snippet']}")
    return "\n".join(lines)


def web_search(
    parameters:     dict,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    query  = params.get("query", "").strip()
    mode   = params.get("mode",  "search").lower().strip()
    items  = params.get("items", [])
    aspect = params.get("aspect", "general").strip() or "general"

    if not query and not items:
        return "Please provide a search query, sir."

    if items and mode != "compare":
        mode = "compare"

    if player:
        player.write_log(f"[Search] {query or ', '.join(items)}")

    print(f"[WebSearch] 🔍 Query: {query!r}  Mode: {mode}")

    try:
        if mode == "compare" and items:
            print(f"[WebSearch] 📊 Comparing: {items}")
            result = _compare(items, aspect)
            print("[WebSearch] ✅ Compare done.")
            return result

        results = _ddg_search(query)
        result  = _format_results(query, results)
        print(f"[WebSearch] ✅ {len(results)} result(s).")
        return result

    except Exception as e:
        print(f"[WebSearch] ❌ Search failed: {e}")
        return f"Search failed, sir: {e}"
