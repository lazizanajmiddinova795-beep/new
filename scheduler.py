# scheduler.py — Asosiy ish jarayoni moduli
# RSS yig'ish → dedup tekshirish → AI qayta ishlash → Telegram yuborish
# APScheduler bilan vaqt bo'yicha avtomatik ishlatiladi.

import asyncio
import logging
from typing import Optional

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import (
    TelegramForbiddenError,
    TelegramNotFound,
    TelegramRetryAfter,
    TelegramBadRequest,
)
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from ai_processor import AIProcessor
from config import Config
from database import Database
from fetcher import ArticleItem, fetch_all_feeds

from games import run_daily_game
from challenges import run_weekly_challenge
from media_fetcher import run_media_post

logger = logging.getLogger(__name__)


def _make_inline_keyboard(source_url: str) -> InlineKeyboardMarkup:
    """Manba havolasi uchun inline-button yaratadi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔗 To'liq o'qish",
                    url=source_url,
                )
            ]
        ]
    )


async def _send_post_to_channel(
    bot: Bot,
    channel_id: str,
    post_text: str,
    source_url: str,
    delay_seconds: int = 5,
) -> Optional[int]:
    """
    Telegram kanaliga post yuboradi.

    Returns:
        Muvaffaqiyatli bo'lsa Telegram message_id, aks holda None.
    """
    keyboard = _make_inline_keyboard(source_url)

    try:
        message = await bot.send_message(
            chat_id=channel_id,
            text=post_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
            disable_web_page_preview=False,
        )
        logger.info(
            "Post muvaffaqiyatli yuborildi! Message ID: %d", message.message_id
        )
        await asyncio.sleep(delay_seconds)  # Rate limit
        return message.message_id

    except TelegramRetryAfter as e:
        logger.warning(
            "Telegram Rate Limit! %d soniya kutiladi...", e.retry_after
        )
        await asyncio.sleep(e.retry_after + 1)
        # Bir marta qayta urinish
        try:
            message = await bot.send_message(
                chat_id=channel_id,
                text=post_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
                disable_web_page_preview=False,
            )
            await asyncio.sleep(delay_seconds)
            return message.message_id
        except Exception as retry_err:
            logger.error("Rate Limit dan keyin ham xato: %s", retry_err)
            return None

    except TelegramForbiddenError:
        logger.error(
            "Bot kanalga kirishiga ruxsat yo'q: %s. "
            "Bot kanal admin sifatida qo'shilganligini tekshiring.",
            channel_id,
        )
        return None

    except TelegramNotFound:
        logger.error(
            "Kanal topilmadi: %s. CHANNEL_ID ni tekshiring.", channel_id
        )
        return None

    except TelegramBadRequest as e:
        logger.error("Telegram Bad Request: %s", e)
        # Markdown xatosi bo'lsa, formatsiz qayta urinish
        if "can't parse entities" in str(e).lower():
            logger.info("Markdown xatosi, plain text bilan qayta yuborilmoqda...")
            try:
                plain_text = post_text.replace("**", "").replace("*", "")
                message = await bot.send_message(
                    chat_id=channel_id,
                    text=plain_text,
                    reply_markup=keyboard,
                    disable_web_page_preview=False,
                )
                await asyncio.sleep(delay_seconds)
                return message.message_id
            except Exception as plain_err:
                logger.error("Plain text bilan ham xato: %s", plain_err)
        return None

    except Exception as e:
        logger.error(
            "Post yuborishda kutilmagan xato: %s", e, exc_info=True
        )
        return None


async def run_posting_cycle(
    bot: Bot,
    db: Database,
    ai_processor: AIProcessor,
    config: Config,
) -> None:
    """
    Bir to'liq posting sikli:
    1. Barcha RSS manbalardan maqolalar yig'iladi.
    2. Har bir maqola bazada borligini tekshiradi.
    3. Yangi maqolalar AI orqali qayta ishlanadi.
    4. Tayyor post Telegram kanaliga yuboriladi.
    5. Bazaga saqlanadi.

    config.max_posts_per_cycle dan ortiq post bir siklda yuborilmaydi.
    """
    logger.info("=" * 50)
    logger.info("Yangi posting sikli boshlandi.")

    # --- 1. RSS manbalardan maqolalar yig'ish ---
    try:
        articles = await fetch_all_feeds(config.rss_feeds)
    except Exception as e:
        logger.error("RSS yig'ishda kritik xato: %s", e, exc_info=True)
        return

    if not articles:
        logger.info("Hech qanday maqola topilmadi. Sikl yakunlandi.")
        return

    logger.info("Jami %d maqola yig'ildi.", len(articles))

    # --- 2. Yangi maqolalarni filtrlash ---
    new_articles = []
    for article in articles:
        try:
            already_published = await db.is_article_published(article.article_id)
            if not already_published:
                new_articles.append(article)
        except Exception as e:
            logger.error(
                "Bazani tekshirishda xato (%s): %s",
                article.article_id[:30],
                e,
            )

    if not new_articles:
        logger.info("Barcha maqolalar allaqachon yuborilgan. Sikl yakunlandi.")
        return

    logger.info(
        "%d ta yangi maqola topildi (limit: %d).",
        len(new_articles),
        config.max_posts_per_cycle,
    )

    # Siklda yuborish limitini qo'llash
    articles_to_post: list[ArticleItem] = new_articles[: config.max_posts_per_cycle]
    sent_count = 0
    failed_count = 0

    # --- 3-4-5. AI qayta ishlash → Yuborish → Saqlash ---
    for article in articles_to_post:
        logger.info(
            "Qayta ishlanmoqda [%d/%d]: '%s'",
            sent_count + failed_count + 1,
            len(articles_to_post),
            article.title[:60],
        )

        # AI qayta ishlash
        try:
            processed = await ai_processor.process_article(article)
        except Exception as e:
            logger.error(
                "AI qayta ishlashda xato ('%s'): %s",
                article.title[:40],
                e,
                exc_info=True,
            )
            failed_count += 1
            continue

        if not processed:
            logger.warning(
                "AI post yarata olmadi: '%s'. O'tkazib yuborildi.",
                article.title[:60],
            )
            # Takrorlanmasligi uchun bazaga yozamiz (is_sent=False)
            try:
                await db.save_article(
                    article_id=article.article_id,
                    title=article.title,
                    source_url=article.source_url,
                    is_sent=False,
                )
            except Exception as db_err:
                logger.error("Bazaga yozishda xato: %s", db_err)
            failed_count += 1
            continue

        # Telegram ga yuborish
        message_id = await _send_post_to_channel(
            bot=bot,
            channel_id=config.channel_id,
            post_text=processed.text,
            source_url=processed.source_url,
            delay_seconds=config.post_delay_seconds,
        )

        # Bazaga saqlash
        try:
            await db.save_article(
                article_id=article.article_id,
                title=article.title,
                source_url=article.source_url,
                telegram_message_id=message_id,
                is_sent=message_id is not None,
            )
        except Exception as db_err:
            logger.error("Bazaga yozishda xato: %s", db_err)

        if message_id:
            sent_count += 1
        else:
            failed_count += 1

    logger.info(
        "Sikl yakunlandi. Yuborildi: %d | Muvaffaqiyatsiz: %d",
        sent_count,
        failed_count,
    )
    logger.info("=" * 50)


def setup_scheduler(
    bot: Bot,
    db: Database,
    ai_processor: AIProcessor,
    config: Config,
) -> AsyncIOScheduler:
    """
    APScheduler ni sozlaydi va posting siklini vaqt bo'yicha rejalashtiradi.

    Returns:
        Sozlangan (lekin hali ishga tushirilmagan) scheduler.
    """
    scheduler = AsyncIOScheduler(timezone="Asia/Tashkent")

    async def scheduled_job() -> None:
        """Scheduler chaqiradigan wrapper funksiya."""
        try:
            await run_posting_cycle(
                bot=bot,
                db=db,
                ai_processor=ai_processor,
                config=config,
            )
        except Exception as e:
            logger.critical(
                "Scheduled job da kritik xato: %s", e, exc_info=True
            )

    scheduler.add_job(
        func=scheduled_job,
        trigger="interval",
        minutes=config.fetch_interval_minutes,
        id="auto_posting_job",
        name="Avto-posting sikli",
        misfire_grace_time=60,         # 60 soniya kechiksa ham ishlatadi
        coalesce=True,                  # Bir vaqtda bir nechta siklni oldini oladi
        max_instances=1,                # Parallel sikllarni bloklaydi
    )

    # Media faktlarni har kuni 18:00 da yuborish
    async def scheduled_media() -> None:
        try:
            await run_media_post(bot, config, ai_processor)
        except Exception as e:
            logger.error("Media fakt xatosi: %s", e)

    scheduler.add_job(
        func=scheduled_media,
        trigger="cron",
        hour=18,
        minute=0,
        id="media_post_job",
        name="Kunlik media fakt",
        misfire_grace_time=300,
        coalesce=True,
        max_instances=1,
    )

    # So'z o'yinlari har kuni 22:00 da yuborish
    async def scheduled_game() -> None:
        try:
            await run_daily_game(bot, config, ai_processor)
        except Exception as e:
            logger.error("Daily game xatosi: %s", e)

    scheduler.add_job(
        func=scheduled_game,
        trigger="cron",
        hour=22,
        minute=0,
        id="daily_game_job",
        name="Kunlik so'z o'yini",
        misfire_grace_time=300,
        coalesce=True,
        max_instances=1,
    )

    # Haftalik chellenj har shanba 23:00 da yuborish
    async def scheduled_challenge() -> None:
        try:
            await run_weekly_challenge(bot, config, ai_processor)
        except Exception as e:
            logger.error("Weekly challenge xatosi: %s", e)

    scheduler.add_job(
        func=scheduled_challenge,
        trigger="cron",
        day_of_week="sat",
        hour=23,
        minute=0,
        id="weekly_challenge_job",
        name="Haftalik chellenj",
        misfire_grace_time=300,
        coalesce=True,
        max_instances=1,
    )

    logger.info(
        "Scheduler sozlandi. Har %d daqiqada ishlaydi.",
        config.fetch_interval_minutes,
    )
    return scheduler
