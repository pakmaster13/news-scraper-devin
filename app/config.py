import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv("MARKET_BRIEF_DB", BASE_DIR / "market_brief.db"))

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "25"))

NEWS_CACHE_SECONDS = int(os.getenv("NEWS_CACHE_SECONDS", "300"))
TOP_N = int(os.getenv("TOP_N", "10"))
MAX_PER_SOURCE = int(os.getenv("MAX_PER_SOURCE", "3"))

RECAP_HOUR = int(os.getenv("RECAP_HOUR", "8"))
RECAP_MINUTE = int(os.getenv("RECAP_MINUTE", "0"))
RECAP_TIMEZONE = os.getenv("RECAP_TIMEZONE", "America/New_York")
RECAP_DAYS = os.getenv("RECAP_DAYS", "mon-fri")

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_STARTTLS = os.getenv("SMTP_STARTTLS", "true").lower() == "true"
RECAP_EMAIL_FROM = os.getenv("RECAP_EMAIL_FROM", SMTP_USER)
RECAP_EMAIL_TO = [a.strip() for a in os.getenv("RECAP_EMAIL_TO", "").split(",") if a.strip()]

RECAP_WEBHOOK_URL = os.getenv("RECAP_WEBHOOK_URL", "")


def email_configured() -> bool:
    return bool(SMTP_HOST and RECAP_EMAIL_FROM and RECAP_EMAIL_TO)


def webhook_configured() -> bool:
    return bool(RECAP_WEBHOOK_URL)
