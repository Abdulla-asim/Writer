"""LangGraph pipeline for one book.

Design:
  Each invocation of `run_step(book_id)` advances the book by ONE step,
  then exits. Review gates (waiting_for_review) terminate the graph; the
  dashboard re-triggers the worker once an editor flips the status to
  `ready_to_generate` (or `approved` for chapters / final compile).
"""
from __future__ import annotations
import json
from typing import TypedDict, Literal, Optional
from langgraph.graph import StateGraph, END

from . import compiler, db, llm, notifications, prompts

from . import research


# --------------------------------------------------------------------------- state
class BookState(TypedDict, total=False):
    book_id: str
    action: str          # which node ran ('outline', 'chapter', 'compile', 'gated', 'done')
    message: str         # human-readable summary of what happened


# --------------------------------------------------------------------------- helpers
def _parse_outline_json(text: str) -> dict:
    """Best-effort JSON parse: strip code fences if model added them."""
    s = text.strip()
    if s.startswith("```"):
        s = s.strip("`")
        if s.lower().startswith("json"):
            s = s[4:]
        s = s.strip()
    # find the first { ... last }
    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1:
        s = s[start : end + 1]
    return json.loads(s)


# --------------------------------------------------------------------------- nodes
def router(state: BookState) -> BookState:
    """Read DB state and decide what to do next. The conditional edge does the routing."""
    return state


def route_decision(state: BookState) -> Literal["outline", "chapter", "compile", "gated", "done"]:
    book = db.get_book(state["book_id"])
    if not book:
        return "done"

    # 1) Outline stage
    if book["outline_status"] == "ready_to_generate":
        return "outline"
    if book["outline_status"] in ("waiting_for_review", "generating"):
        return "gated"

    # outline is approved -> chapter stage
    if book["outline_status"] == "approved":
        chapters = db.list_chapters(book["id"])
        outline = book.get("outline") or {}
        planned = outline.get("chapters", []) if isinstance(outline, dict) else []

        # find first chapter that needs work
        for planned_ch in planned:
            n = planned_ch["chapter_number"]
            existing = next((c for c in chapters if c["chapter_number"] == n), None)
            if existing is None or existing["status"] in ("pending", "ready_to_generate"):
                return "chapter"
            if existing["status"] in ("waiting_for_review", "generating"):
                return "gated"
            # approved -> keep looking

        # all chapters approved -> compile
        if book["status"] != "done":
            return "compile"
        return "done"

    return "gated"


def outline_node(state: BookState) -> BookState:
    book_id = state["book_id"]
    book = db.get_book(book_id)
    db.update_book(book_id, {"outline_status": "generating", "status": "outlining"})
    db.log_event(book_id, "outline", "Generating outline...")

    user = prompts.OUTLINE_USER.format(
        title=book["title"],
        pre_notes=book.get("pre_notes") or "(none)",
        genre=book.get("genre") or "(unspecified)",
        audience=book.get("audience") or "general",
        style=book.get("style") or "engaging",
        num_chapters=book.get("num_chapters") or 10,
        editor_notes=book.get("outline_notes_before") or book.get("outline_notes_after") or "(none)",
    )

    try:
        text = llm.write(prompts.OUTLINE_SYSTEM, user, temperature=0.6, max_tokens=4096)
        parsed = _parse_outline_json(text)
        if "chapters" not in parsed or not isinstance(parsed["chapters"], list):
            raise ValueError("Outline JSON missing 'chapters' list")

        db.update_book(
            book_id,
            {
                "outline": parsed,
                "outline_status": "waiting_for_review",
                "status": "outlining",
            },
        )
        # Seed pending chapter rows for visibility
        for ch in parsed["chapters"]:
            db.upsert_chapter(
                {
                    "book_id": book_id,
                    "chapter_number": ch["chapter_number"],
                    "title": ch.get("title", f"Chapter {ch['chapter_number']}"),
                    "outline": ch.get("summary", ""),
                    "status": "pending",
                }
            )
        db.log_event(book_id, "outline", "Outline ready -- awaiting editor review.")
        notifications.notify(
            f"[BookGen] Outline ready for: {book['title']}",
            f"The outline for '{book['title']}' is ready for your review in the dashboard.",
        )
        return {"book_id": book_id, "action": "outline", "message": "outline generated"}
    except Exception as e:
        db.update_book(book_id, {"outline_status": "ready_to_generate", "status": "error", "error": str(e)})
        db.log_event(book_id, "error", f"Outline failed: {e}")
        return {"book_id": book_id, "action": "outline", "message": f"error: {e}"}


def chapter_node(state: BookState) -> BookState:
    book_id = state["book_id"]
    book = db.get_book(book_id)
    chapters = db.list_chapters(book_id)
    outline = book["outline"] or {}
    planned = outline.get("chapters", [])

    # find the next chapter to generate
    target = None
    for planned_ch in planned:
        existing = next(
            (c for c in chapters if c["chapter_number"] == planned_ch["chapter_number"]),
            None,
        )
        if existing is None or existing["status"] in ("pending", "ready_to_generate"):
            target = (planned_ch, existing)
            break

    if target is None:
        return {"book_id": book_id, "action": "chapter", "message": "no chapter to generate"}

    planned_ch, existing = target
    n = planned_ch["chapter_number"]
    chapter_title = planned_ch.get("title", f"Chapter {n}")
    chapter_outline = planned_ch.get("summary", "")

    db.update_book(book_id, {"status": "chapters"})
    db.upsert_chapter(
        {
            "book_id": book_id,
            "chapter_number": n,
            "title": chapter_title,
            "outline": chapter_outline,
            "status": "generating",
        }
    )
    db.log_event(book_id, "chapter", f"Generating chapter {n}: {chapter_title}")

    # Build prior summaries
    prior_summaries_parts = []
    for c in sorted(chapters, key=lambda x: x["chapter_number"]):
        if c["chapter_number"] < n and c.get("summary"):
            prior_summaries_parts.append(
                f"Chapter {c['chapter_number']} -- {c.get('title','')}:\n{c['summary']}"
            )
    prior_summaries = "\n\n".join(prior_summaries_parts) or "(this is the first chapter)"

    full_outline_text = "\n".join(
        f"  {c['chapter_number']}. {c.get('title','')} -- {c.get('summary','')}"
        for c in planned
    )

    research_context = ""
    if book.get("use_research"):
        research_context = research.research_for_chapter(
            book["title"], chapter_title, chapter_outline
        )

    editor_notes = (existing or {}).get("notes") or "(none)"

    user = prompts.CHAPTER_USER.format(
        title=book["title"],
        genre=book.get("genre") or "(unspecified)",
        audience=book.get("audience") or "general",
        style=book.get("style") or "engaging",
        full_outline=full_outline_text,
        prior_summaries=prior_summaries,
        n=n,
        chapter_title=chapter_title,
        chapter_outline=chapter_outline,
        editor_notes=editor_notes,
        research_context=research_context or "(none)",
    )

    try:
        content = llm.write(
            prompts.CHAPTER_SYSTEM, user, temperature=0.8, max_tokens=6000
        )
        # Summarize for context chaining
        summary = llm.summarize(
            prompts.SUMMARY_SYSTEM,
            prompts.SUMMARY_USER.format(n=n, title=chapter_title, content=content),
        )

        db.upsert_chapter(
            {
                "book_id": book_id,
                "chapter_number": n,
                "title": chapter_title,
                "outline": chapter_outline,
                "content": content,
                "summary": summary,
                "status": "waiting_for_review",
            }
        )
        db.log_event(book_id, "chapter", f"Chapter {n} ready -- awaiting editor review.")
        notifications.notify(
            f"[BookGen] Chapter {n} ready: {book['title']}",
            f"Chapter {n} ('{chapter_title}') of '{book['title']}' is ready for review.",
        )
        return {"book_id": book_id, "action": "chapter", "message": f"chapter {n} generated"}
    except Exception as e:
        db.upsert_chapter(
            {
                "book_id": book_id,
                "chapter_number": n,
                "title": chapter_title,
                "outline": chapter_outline,
                "status": "ready_to_generate",
            }
        )
        db.update_book(book_id, {"error": str(e)})
        db.log_event(book_id, "error", f"Chapter {n} failed: {e}")
        return {"book_id": book_id, "action": "chapter", "message": f"error: {e}"}


def compile_node(state: BookState) -> BookState:
    book_id = state["book_id"]
    db.update_book(book_id, {"status": "compiling"})
    db.log_event(book_id, "compile", "Compiling manuscript...")
    try:
        path = compiler.compile_book(book_id)
        db.update_book(book_id, {"final_path": path, "status": "done"})
        db.log_event(book_id, "compile", f"Manuscript compiled: {path}")
        book = db.get_book(book_id)
        notifications.notify(
            f"[BookGen] Manuscript ready: {book['title']}",
            f"The manuscript for '{book['title']}' has been compiled to: {path}",
        )
        return {"book_id": book_id, "action": "compile", "message": f"compiled: {path}"}
    except Exception as e:
        db.update_book(book_id, {"status": "error", "error": str(e)})
        db.log_event(book_id, "error", f"Compile failed: {e}")
        return {"book_id": book_id, "action": "compile", "message": f"error: {e}"}


def gated_node(state: BookState) -> BookState:
    return {**state, "action": "gated", "message": "waiting for editor"}


def done_node(state: BookState) -> BookState:
    return {**state, "action": "done", "message": "done"}


# --------------------------------------------------------------------------- graph
def build_graph():
    g = StateGraph(BookState)
    g.add_node("router", router)
    g.add_node("outline", outline_node)
    g.add_node("chapter", chapter_node)
    g.add_node("compile", compile_node)
    g.add_node("gated", gated_node)
    g.add_node("done", done_node)

    g.set_entry_point("router")
    g.add_conditional_edges(
        "router",
        route_decision,
        {
            "outline": "outline",
            "chapter": "chapter",
            "compile": "compile",
            "gated": "gated",
            "done": "done",
        },
    )
    for n in ("outline", "chapter", "compile", "gated", "done"):
        g.add_edge(n, END)
    return g.compile()


_graph = None


def run_step(book_id: str) -> BookState:
    """Advance the book by one step. Safe to call repeatedly."""
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph.invoke({"book_id": book_id})
