"""Thin wrapper around the Groq SDK with retries."""
from __future__ import annotations
from typing import Optional
from groq import Groq
from tenacity import retry, stop_after_attempt, wait_exponential
from . import config


_groq: Optional[Groq] = None


def groq() -> Groq:
    global _groq
    if _groq is None:
        if not config.GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY not set in .env")
        _groq = Groq(api_key=config.GROQ_API_KEY)
    return _groq


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=30))
def chat(
    system: str,
    user: str,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> str:
    """Run a single chat completion. Returns text."""
    resp = groq().chat.completions.create(
        model=model or config.GROQ_WRITER_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content or ""


def write(system: str, user: str, **kw) -> str:
    """Use the strong writer model (default: kimi-k2-instruct)."""
    return chat(system, user, model=config.GROQ_WRITER_MODEL, **kw)


def summarize(system: str, user: str, **kw) -> str:
    """Use the cheap/fast summarizer model."""
    kw.setdefault("temperature", 0.3)
    kw.setdefault("max_tokens", 1024)
    return chat(system, user, model=config.GROQ_SUMMARIZER_MODEL, **kw)
