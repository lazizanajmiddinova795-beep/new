# fetcher.py — RSS yangiliklar yig'ish moduli
# feedparser orqali RSS manbalardan maqolalar o'qiydi.
# HTML teglarni tozalaydi va tuzilgan ma'lumotlar qaytaradi.

import asyncio
import hashlib
import html
import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

import feedparser
import httpx

logger = logging.getLogger(__name__)


@dataclass
class ArticleItem:
    """Bir maqolaning normalangan ma'lumotlari."""

    # Unikal ID (RSS entry.id yoki URL asosida)
    article_id: str

    # Sarlavha
    title: str

    # Maqola URL manzili
    url: str

    # Maqola qisqacha tavsifi yoki to'liq matni
    summary: str

    # Nashr sanasi (ixtiyoriy)
    published: Optional[str]

    # Manba nomi
    source_name: str

    # Manba URL
    source_url: str

    # Kategoriya (config.py dagi feed'dan olinadi)
    category: str

    # Xesh-teglar
    hashtags: List[str] = field(default_factory=list)


def _clean_html(raw: str) -> str:
    """HTML teglarni va ortiqcha bo'sh joylarni olib tashlaydi."""
    if not raw:
        return ""
    # HTML entities ni decode qilish
    text = html.unescape(raw)
    # HTML teglarni olib tashlash
    text = re.sub(r"<[^>]+>", " ", text)
    # Ko'p bo'sh joylarni bitta bo'sh joyga almashtirish
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _make_article_id(entry: feedparser.FeedParserDict) -> str:
    """
    Maqola uchun unikal ID yaratadi.
    Avval entry.id ni ishlatadi, yo'q bo'lsa URL asosida hash yaratadi.
    """
    raw_id = getattr(entry, "id", None) or getattr(entry, "link", None) or ""
    if raw_id:
        # Tozalash: faqat alfanumerik va oddiy belgilar
        return hashlib.sha256(raw_id.encode()).hexdigest()[:64]
    # Sarlavha + manbadan hash
    title = getattr(entry, "title", "") or ""
    return hashlib.sha256(title.encode()).hexdigest()[:64]


def _extract_summary(entry: feedparser.FeedParserDict, max_len: int = 800) -> str:
    """
    Maqola matnini ajratib oladi.
    content → summary → description tartibida izlaydi.
    """
    # 1. To'liq content
    if hasattr(entry, "content") and entry.content:
        raw = entry.content[0].get("value", "")
        if raw:
            return _clean_html(raw)[:max_len]

    # 2. summary
    if hasattr(entry, "summary") and entry.summary:
        return _clean_html(entry.summary)[:max_len]

    # 3. description
    if hasattr(entry, "description") and entry.description:
        return _clean_html(entry.description)[:max_len]

    return ""


async def _fetch_feed_async(
    feed_config: dict,
    http_client: httpx.AsyncClient,
) -> List[ArticleItem]:
    """
    Bitta RSS manbadan asinxron ravishda maqolalar yig'adi.
    feedparser sinxron bo'lgani uchun executor orqali chaqiriladi.
    """
    url = feed_config["url"]
    category = feed_config.get("category", "yangiliklar")
    hashtags = feed_config.get("hashtags", ["#yangiliklar"])

    try:
        # Avval httpx bilan content yuklab olamiz (timeout bilan)
        response = await http_client.get(url, timeout=20.0)
        response.raise_for_status()
        content = response.content

        # feedparser sinxron — executor orqali ishlatamiz
        loop = asyncio.get_event_loop()
        feed = await loop.run_in_executor(
            None, lambda: feedparser.parse(content)
        )

        if feed.bozo and not feed.entries:
            logger.warning(
                "RSS feed muvaffaqiyatsiz o'qildi: %s — %s",
                url,
                feed.bozo_exception,
            )
            return []

        source_name = feed.feed.get("title", url) if feed.feed else url
        articles: List[ArticleItem] = []

        for entry in feed.entries:
            try:
                article_id = _make_article_id(entry)
                title = _clean_html(getattr(entry, "title", "") or "")
                link = getattr(entry, "link", "") or url
                summary = _extract_summary(entry)
                published = getattr(entry, "published", None)

                if not title or not link:
                    continue

                articles.append(
                    ArticleItem(
                        article_id=article_id,
                        title=title,
                        url=link,
                        summary=summary,
                        published=published,
                        source_name=source_name,
                        source_url=url,
                        category=category,
                        hashtags=hashtags,
                    )
                )
            except Exception as entry_err:
                logger.warning(
                    "Maqolani qayta ishlashda xato (%s): %s", url, entry_err
                )
                continue

        logger.info(
            "Feed o'qildi: %s -> %d maqola topildi.", url, len(articles)
        )
        return articles

    except httpx.TimeoutException:
        logger.error("Feed o'qishda timeout: %s", url)
        return []
    except httpx.HTTPStatusError as e:
        logger.error("HTTP xato (%s): %s", url, e)
        return []
    except Exception as e:
        logger.error("Kutilmagan xato (%s): %s", url, e, exc_info=True)
        return []


async def fetch_all_feeds(feed_configs: List[dict]) -> List[ArticleItem]:
    """
    Barcha belgilangan RSS manbalardan parallel ravishda maqolalar yig'adi.
    Qaytarish tartibi: eng yangi maqolalar birinchi.
    """
    if not feed_configs:
        logger.warning("RSS manbalar ro'yxati bo'sh.")
        return []

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; NewsBot/1.0; +https://t.me/NLMINI_12)"
        ),
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
    }

    async with httpx.AsyncClient(
        headers=headers,
        follow_redirects=True,
        verify=False,          # Ba'zi RSS manbalar sertifikat bilan muammo
    ) as client:
        tasks = [
            _fetch_feed_async(feed_config, client)
            for feed_config in feed_configs
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    all_articles: List[ArticleItem] = []
    for result in results:
        if isinstance(result, Exception):
            logger.error("Feed yig'ishda xato: %s", result)
            continue
        if isinstance(result, list):
            all_articles.extend(result)

    logger.info(
        "Jami barcha feedlardan %d maqola yig'ildi.", len(all_articles)
    )
    return all_articles
