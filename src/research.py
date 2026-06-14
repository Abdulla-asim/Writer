"""Optional web-research tool. Uses DuckDuckGo (no API key required)."""
from __future__ import annotations
from typing import List


def web_research(query: str, max_results: int = 5) -> str:
    """Run a web search and return a compact context string.

    Returns "" on any failure so the pipeline is never blocked by research.
    """
    try:
        from ddgs import DDGS
    except Exception as e:
        return f"[research unavailable: {e}]"

    try:
        out: List[str] = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                title = r.get("title", "")
                body = r.get("body", "")
                href = r.get("href", "")
                out.append(f"- {title}\n  {body}\n  ({href})")
        if not out:
            return ""
        return "Research notes for: " + query + "\n" + "\n".join(out)
    except Exception as e:
        return f"[research failed: {e}]"


def research_for_chapter(
    book_title: str, chapter_title: str, chapter_outline: str
) -> str:
    """Build a focused query from chapter metadata and fetch context."""
    query = f"{book_title} {chapter_title} {chapter_outline}"[:300]
    return web_research(query, max_results=5)
