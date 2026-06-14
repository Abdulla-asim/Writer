"""Supabase data-access layer."""
from __future__ import annotations
from typing import Any, Optional
from supabase import create_client, Client
from . import config


_client: Optional[Client] = None


def client() -> Client:
    global _client
    if _client is None:
        if not config.SUPABASE_URL or not config.SUPABASE_KEY:
            raise RuntimeError("SUPABASE_URL / SUPABASE_KEY not set in .env")
        _client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
    return _client


# ---------------- books ----------------
def create_book(data: dict) -> dict:
    res = client().table("books").insert(data).execute()
    return res.data[0]


def get_book(book_id: str) -> Optional[dict]:
    res = client().table("books").select("*").eq("id", book_id).limit(1).execute()
    return res.data[0] if res.data else None


def update_book(book_id: str, patch: dict) -> dict:
    patch = {**patch, "updated_at": "now()"}
    res = client().table("books").update(patch).eq("id", book_id).execute()
    return res.data[0] if res.data else {}


def list_books() -> list[dict]:
    res = (
        client()
        .table("books")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )
    return res.data or []


# ---------------- chapters ----------------
def upsert_chapter(row: dict) -> dict:
    res = (
        client()
        .table("chapters")
        .upsert(row, on_conflict="book_id,chapter_number")
        .execute()
    )
    return res.data[0] if res.data else {}


def get_chapter(book_id: str, chapter_number: int) -> Optional[dict]:
    res = (
        client()
        .table("chapters")
        .select("*")
        .eq("book_id", book_id)
        .eq("chapter_number", chapter_number)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


def update_chapter(chapter_id: str, patch: dict) -> dict:
    patch = {**patch, "updated_at": "now()"}
    res = client().table("chapters").update(patch).eq("id", chapter_id).execute()
    return res.data[0] if res.data else {}


def list_chapters(book_id: str) -> list[dict]:
    res = (
        client()
        .table("chapters")
        .select("*")
        .eq("book_id", book_id)
        .order("chapter_number")
        .execute()
    )
    return res.data or []


# ---------------- events ----------------
def log_event(book_id: str, kind: str, message: str) -> None:
    try:
        client().table("events").insert(
            {"book_id": book_id, "kind": kind, "message": message}
        ).execute()
    except Exception as e:
        # logging should never break the pipeline
        print(f"[events] failed to log: {e}")


def list_events(book_id: str, limit: int = 50) -> list[dict]:
    res = (
        client()
        .table("events")
        .select("*")
        .eq("book_id", book_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data or []
