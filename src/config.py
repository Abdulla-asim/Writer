"""Centralized configuration loaded from environment."""
import os
from dotenv import load_dotenv

load_dotenv()


def _req(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing required env var: {name}")
    return v


# Groq
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_WRITER_MODEL = os.getenv("GROQ_WRITER_MODEL", "moonshotai/kimi-k2-instruct")
GROQ_SUMMARIZER_MODEL = os.getenv("GROQ_SUMMARIZER_MODEL", "llama-3.1-8b-instant")

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# SMTP
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)
EDITOR_EMAIL = os.getenv("EDITOR_EMAIL", "")

OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./output")
os.makedirs(OUTPUT_DIR, exist_ok=True)
