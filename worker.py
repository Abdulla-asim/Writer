"""Background worker.

Polls Supabase for books that have work to do and advances each by one
LangGraph step at a time. Run with:  python worker.py
"""
from __future__ import annotations
import time
import sys
import traceback

from src import graph
from src import db

POLL_SECONDS = 5


def find_actionable_books() -> list[dict]:
    """Books whose state shows pending work the worker can pick up."""
    books = db.list_books()
    actionable = []
    for b in books:
        # Skip if stop was requested
        if b.get("stop_requested"):
            continue
        if b["outline_status"] == "ready_to_generate":
            actionable.append(b)
            continue
        if b["outline_status"] == "approved" and b["status"] != "done":
            # check if any chapter is ready_to_generate or if all approved (compile)
            chapters = db.list_chapters(b["id"])
            outline = b.get("outline") or {}
            planned = outline.get("chapters", []) if isinstance(outline, dict) else []
            if not planned:
                continue
            any_work = False
            all_approved = True
            for p in planned:
                existing = next(
                    (c for c in chapters if c["chapter_number"] == p["chapter_number"]),
                    None,
                )
                if existing is None or existing["status"] == "ready_to_generate":
                    any_work = True
                    all_approved = False
                    break
                if existing["status"] != "approved":
                    all_approved = False
            if any_work or all_approved:
                actionable.append(b)
    return actionable


def main_loop():
    print("Worker started. Polling every", POLL_SECONDS, "seconds.")
    while True:
        try:
            for book in find_actionable_books():
                print(f"-> advancing book {book['id'][:8]} '{book['title']}'")
                try:
                    result = graph.run_step(book["id"])
                    print(f"   {result.get('action')}: {result.get('message')}")
                except Exception as e:
                    print(f"   ERROR: {e}")
                    traceback.print_exc()
        except Exception as e:
            print(f"[worker] loop error: {e}")
            traceback.print_exc()
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    try:
        main_loop()
    except KeyboardInterrupt:
        print("\nWorker stopped.")
        sys.exit(0)
