"""SMTP email notifications. Silently no-ops when SMTP env vars are absent."""
from __future__ import annotations
import smtplib
from email.mime.text import MIMEText
from . import config


def _enabled() -> bool:
    return bool(
        config.SMTP_HOST
        and config.SMTP_USER
        and config.SMTP_PASSWORD
        and config.EDITOR_EMAIL
    )


def notify(subject: str, body: str) -> bool:
    """Send a notification email. Returns True if sent."""
    if not _enabled():
        print(f"[notify-skipped] {subject}")
        return False
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = config.SMTP_FROM
    msg["To"] = config.EDITOR_EMAIL
    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as s:
            s.starttls()
            s.login(config.SMTP_USER, config.SMTP_PASSWORD)
            s.send_message(msg)
        return True
    except Exception as e:
        print(f"[notify-failed] {e}")
        return False
