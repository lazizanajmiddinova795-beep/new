# config.py — Markaziy konfiguratsiya moduli
# Barcha sozlamalar .env fayldan o'qiladi va type-safe holda taqdim etiladi.

import os
import logging
from dataclasses import dataclass, field
from typing import List
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


# -------------------------------------------------------
# RSS MANBALAR RO'YXATI
# Kerakli yangiliklar manbalarini shu yerga qo'shing.
# -------------------------------------------------------
RSS_FEEDS: List[dict] = [
    {
        "url": "https://feeds.bbci.co.uk/news/technology/rss.xml",
        "category": "texnologiya",
        "hashtags": ["#texnologiya", "#yangiliklar", "#tech"],
    },
    {
        "url": "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
        "category": "texnologiya",
        "hashtags": ["#texnologiya", "#NYTimes", "#tech"],
    },
    {
        "url": "https://www.aljazeera.com/xml/rss/all.xml",
        "category": "dunyo",
        "hashtags": ["#AlJazeera", "#dunyo", "#yangiliklar"],
    },
    {
        "url": "https://www.theverge.com/rss/index.xml",
        "category": "texnologiya",
        "hashtags": ["#TheVerge", "#texnologiya", "#gadjet"],
    },
    {
        "url": "https://techcrunch.com/feed/",
        "category": "startap",
        "hashtags": ["#TechCrunch", "#startap", "#texnologiya"],
    },
    {
        "url": "https://www.wired.com/feed/rss",
        "category": "ilm-fan",
        "hashtags": ["#Wired", "#ilmfan", "#texnologiya"],
    },
]


def _get_required(key: str) -> str:
    """Majburiy env o'zgaruvchisini oladi; yo'q bo'lsa xato chiqaradi."""
    value = os.getenv(key)
    if not value:
        raise EnvironmentError(
            f"Muhit o'zgaruvchisi '{key}' topilmadi. "
            f"Iltimos, .env faylini tekshiring."
        )
    return value.strip()


def _get_optional(key: str, default: str = "") -> str:
    return (os.getenv(key) or default).strip()


def _get_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except (ValueError, TypeError):
        logger.warning(
            f"'{key}' uchun noto'g'ri qiymat, default={default} ishlatiladi."
        )
        return default


@dataclass(frozen=True)
class Config:
    # --- Telegram ---
    bot_token: str
    channel_id: str

    # --- AI ---
    ai_provider: str          # "openai", "anthropic" yoki "gemini"
    openai_api_key: str
    openai_model: str
    anthropic_api_key: str
    anthropic_model: str
    gemini_api_key: str
    gemini_model: str

    # --- Scheduler ---
    fetch_interval_minutes: int
    post_delay_seconds: int
    max_posts_per_cycle: int

    # --- Database ---
    database_url: str

    # --- Logging ---
    log_level: str

    # --- RSS ---
    rss_feeds: List[dict] = field(default_factory=list)


def load_config() -> Config:
    """Barcha konfiguratsiyalarni yuklaydi va validatsiya qiladi."""
    ai_provider = _get_optional("AI_PROVIDER", "openai").lower()
    if ai_provider not in ("openai", "anthropic", "gemini"):
        raise ValueError(
            f"AI_PROVIDER '{ai_provider}' qo'llab-quvvatlanmaydi. "
            "'openai', 'anthropic' yoki 'gemini' tanlang."
        )

    config = Config(
        bot_token=_get_required("BOT_TOKEN"),
        channel_id=_get_optional("CHANNEL_ID", "@NLMINI_12"),
        ai_provider=ai_provider,
        openai_api_key=_get_optional("OPENAI_API_KEY"),
        openai_model=_get_optional("OPENAI_MODEL", "gpt-4o-mini"),
        anthropic_api_key=_get_optional("ANTHROPIC_API_KEY"),
        anthropic_model=_get_optional("ANTHROPIC_MODEL", "claude-3-5-haiku-20241022"),
        gemini_api_key=_get_optional("GEMINI_API_KEY"),
        gemini_model=_get_optional("GEMINI_MODEL", "gemini-2.0-flash"),
        fetch_interval_minutes=_get_int("FETCH_INTERVAL_MINUTES", 30),
        post_delay_seconds=_get_int("POST_DELAY_SECONDS", 5),
        max_posts_per_cycle=_get_int("MAX_POSTS_PER_CYCLE", 5),
        database_url=_get_optional(
            "DATABASE_URL", "sqlite+aiosqlite:///./data/news_bot.db"
        ),
        log_level=_get_optional("LOG_LEVEL", "INFO").upper(),
        rss_feeds=RSS_FEEDS,
    )

    # AI kalitlari mavjudligini tekshirish
    if config.ai_provider == "openai" and not config.openai_api_key:
        raise EnvironmentError(
            "AI_PROVIDER='openai' tanlangan, lekin OPENAI_API_KEY topilmadi."
        )
    if config.ai_provider == "anthropic" and not config.anthropic_api_key:
        raise EnvironmentError(
            "AI_PROVIDER='anthropic' tanlangan, lekin ANTHROPIC_API_KEY topilmadi."
        )
    if config.ai_provider == "gemini" and not config.gemini_api_key:
        raise EnvironmentError(
            "AI_PROVIDER='gemini' tanlangan, lekin GEMINI_API_KEY topilmadi."
        )

    return config
