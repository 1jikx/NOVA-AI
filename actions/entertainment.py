"""
entertainment.py — Movie/show finder and game recommendations.
Uses DuckDuckGo scraping (no API key needed).
"""
import re
import sys
from pathlib import Path
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def _search_ddg(query: str, max_results: int = 5) -> list[dict]:
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
            title   = title_el.get_text(strip=True) if title_el else ""
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""
            if title:
                results.append({"title": title, "snippet": snippet})
    except Exception as e:
        print(f"[Entertainment] DDG search failed: {e}")
    return results


def movie_finder(parameters: dict, player=None, **kwargs) -> str:
    params = parameters or {}
    query = params.get("query", "").strip()
    genre = params.get("genre", "").strip()
    platform = params.get("platform", "").strip()

    if not query and genre:
        q = f"best {genre} movies {platform} recommend 2025 2026"
    elif not query:
        q = "what to watch tonight best movies streaming now"
    else:
        q = f"{query} movie show watch {platform}".strip()

    if player:
        player.write_log(f"[Movies] Searching: {q[:40]}")

    results = _search_ddg(q, max_results=6)
    if not results:
        return "Couldn't find movie/show recommendations right now."

    lines = [f"🎬 Recommendations:\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r['title']}")
        if r.get("snippet"):
            lines.append(f"   {r['snippet'][:120]}")
        lines.append("")

    return "\n".join(lines).strip()


def game_recommendations(parameters: dict, player=None, **kwargs) -> str:
    params = parameters or {}
    based_on = params.get("based_on", "").strip()
    genre = params.get("genre", "").strip()

    if based_on:
        q = f"games like {based_on} recommend similar"
    elif genre:
        q = f"best {genre} games 2025 2026 recommend"
    else:
        q = "best games to play right now 2025 2026"

    if player:
        player.write_log(f"[Games] Searching: {q[:40]}")

    results = _search_ddg(q, max_results=6)
    if not results:
        return "Couldn't find game recommendations right now."

    lines = [f"🎮 Game Recommendations:\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r['title']}")
        if r.get("snippet"):
            lines.append(f"   {r['snippet'][:120]}")
        lines.append("")

    return "\n".join(lines).strip()
