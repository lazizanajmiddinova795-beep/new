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
from broadcaster import safe_send_message

from games import run_daily_game
from challenges import run_weekly_challenge
from media_fetcher import run_media_post
from emotional_posts import run_emotional_post
from video_fetcher import run_daily_video
from recommendations import run_weekly_recommendation
from services.smm_planner import run_morning_smm, run_evening_smm
from services.ad_manager import check_and_delete_ads
from datetime import datetime, timezone


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
        success = await safe_send_message(
            bot=bot,
            chat_id=channel_id,
            text=post_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
            disable_web_page_preview=False
        )
        if success:
            logger.info("Post muvaffaqiyatli yuborildi! (Kanal: %s)", channel_id)
            await asyncio.sleep(delay_seconds)  # Rate limit
            return 1 # (yuborildi)
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
                success = await safe_send_message(
                    bot=bot,
                    chat_id=channel_id,
                    text=plain_text,
                    reply_markup=keyboard,
                    disable_web_page_preview=False,
                )
                if success:
                    await asyncio.sleep(delay_seconds)
                    return 1
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

    # Faol kanallarni olish
    active_channels = await db.get_active_channels()
    news_channels = [ch for ch in active_channels if ch.setting_news]
    
    if not news_channels:
        logger.info("Yangiliklar uqish yoqilgan faol kanallar yo'q.")
        return

    # --- 1. RSS manbalardan maqolalar yig'ish ---
    try:
        articles = await fetch_all_feeds(config.rss_feeds)
    except Exception as e:
        logger.error("RSS yig'ishda kritik xato: %s", e, exc_info=True)
        return

    if not articles:
        logger.info("Hech qanday maqola topilmadi. Sikl yakunlandi.")
        return

    # Eng so'nggi max_posts_per_cycle ta maqolani olamiz
    articles_to_process = articles[: config.max_posts_per_cycle]
    
    for article in articles_to_process:
        # Tekshiramiz: Ushbu maqola hamma news_channels ga yuborilganmi?
        channels_to_send = []
        for ch in news_channels:
            is_pub = await db.is_article_published(article.article_id, ch.channel_id)
            if not is_pub:
                channels_to_send.append(ch)
                
        if not channels_to_send:
            continue # Hamma kanalga yuborilgan

        # Agar yuborilmagan kanallar bo'lsa, AI dan o'tkazamiz
        logger.info("Qayta ishlanmoqda: '%s'", article.title[:60])
        try:
            processed = await ai_processor.process_article(article)
        except Exception as e:
            logger.error("AI qayta ishlashda xato: %s", e, exc_info=True)
            continue

        if not processed:
            # AI muvaffaqiyatsiz bo'lsa, xatoni yozamiz
            for ch in channels_to_send:
                await db.save_article(article.article_id, ch.channel_id, article.title, article.source_url, None, False)
            continue

        # Har bir kanalga yuboramiz
        for ch in channels_to_send:
            # VIP tekshiruvi
            is_vip = ch.user and ch.user.is_vip and (not ch.user.vip_until or ch.user.vip_until >= datetime.now(timezone.utc))
            
            if is_vip:
                post_text = processed.text
            else:
                half = len(processed.text) // 2
                post_text = processed.text[:half] + "\n\n🔒 **... Ushbu postning to'liq versiyasini o'qish uchun botga kirib VIP obuna xarid qiling!**"

            message_id = await _send_post_to_channel(
                bot=bot,
                channel_id=ch.channel_id,
                post_text=post_text,
                source_url=processed.source_url,
                delay_seconds=config.post_delay_seconds,
            )
            
            await db.save_article(
                article_id=article.article_id,
                channel_id=ch.channel_id,
                title=article.title,
                source_url=article.source_url,
                telegram_message_id=message_id,
                is_sent=message_id is not None,
            )

    logger.info("Sikl yakunlandi.")
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
            await run_media_post(bot, db, ai_processor)
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
            await run_daily_game(bot, db, ai_processor)
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
            await run_weekly_challenge(bot, db, ai_processor)
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

    # Ertalabki emotional post har kuni 09:00 da
    async def scheduled_emotional() -> None:
        try:
            await run_emotional_post(bot, db, ai_processor)
        except Exception as e:
            logger.error("Emotional post xatosi: %s", e)

    scheduler.add_job(
        func=scheduled_emotional,
        trigger="cron",
        hour=9,
        minute=0,
        id="emotional_post_job",
        name="Ertalabki emotional post",
        misfire_grace_time=300,
        coalesce=True,
        max_instances=1,
    )

    # Kunlik video-fakt har kuni 14:00 da
    async def scheduled_video() -> None:
        try:
            await run_daily_video(bot, db, ai_processor)
        except Exception as e:
            logger.error("Video-fakt xatosi: %s", e)

    scheduler.add_job(
        func=scheduled_video,
        trigger="cron",
        hour=14,
        minute=0,
        id="daily_video_job",
        name="Kunlik video fakt",
        misfire_grace_time=300,
        coalesce=True,
        max_instances=1,
    )

    # Haftalik tavsiya har yakshanba 10:00 da
    async def scheduled_recommendation() -> None:
        try:
            await run_weekly_recommendation(bot, db, ai_processor)
        except Exception as e:
            logger.error("Haftalik tavsiya xatosi: %s", e)

    scheduler.add_job(
        func=scheduled_recommendation,
        trigger="cron",
        day_of_week="sun",
        hour=10,
        minute=0,
        id="weekly_recommendation_job",
        name="Haftalik tavsiya",
        misfire_grace_time=300,
        coalesce=True,
        max_instances=1,
    )

    # SMM Planner: Ertalab 08:00
    async def scheduled_morning_smm() -> None:
        try:
            await run_morning_smm(bot, db, ai_processor)
        except Exception as e:
            logger.error("Morning SMM xatosi: %s", e)

    scheduler.add_job(
        func=scheduled_morning_smm,
        trigger="cron",
        hour=8,
        minute=0,
        id="morning_smm_job",
        name="Ertalabki SMM",
        misfire_grace_time=300,
        coalesce=True,
        max_instances=1,
    )

    # SMM Planner: Kechqurun 21:00
    async def scheduled_evening_smm() -> None:
        try:
            await run_evening_smm(bot, db, ai_processor)
        except Exception as e:
            logger.error("Evening SMM xatosi: %s", e)

    scheduler.add_job(
        func=scheduled_evening_smm,
        trigger="cron",
        hour=21,
        minute=0,
        id="evening_smm_job",
        name="Kechki SMM",
        misfire_grace_time=300,
        coalesce=True,
        max_instances=1,
    )

    # Ad Manager: Har 1 soatda reklamalarni tekshirish (Auto-Delete)
    async def scheduled_ad_manager() -> None:
        try:
            await check_and_delete_ads(bot, db)
        except Exception as e:
            logger.error("Ad Manager xatosi: %s", e)

    scheduler.add_job(
        func=scheduled_ad_manager,
        trigger="interval",
        minutes=60,
        id="ad_manager_job",
        name="Reklama Auto-Delete",
        misfire_grace_time=300,
        coalesce=True,
        max_instances=1,
    )


    logger.info(
        "Scheduler sozlandi. Har %d daqiqada ishlaydi.",
        config.fetch_interval_minutes,
    )
    return scheduler
