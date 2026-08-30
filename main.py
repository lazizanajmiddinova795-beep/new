# main.py — Asosiy kirish nuqtasi
# Botni ishga tushiradi, barcha modullarni bog'laydi va
# to'g'ri tartibda yopilishni ta'minlaydi (graceful shutdown).

import asyncio
import logging
import signal
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram import F, types

from ai_processor import AIProcessor
from config import load_config
from database import Database
from scheduler import run_posting_cycle, setup_scheduler
from handlers.user_handlers import router as user_router, set_db as set_user_db



# -------------------------------------------------------
# Logging sozlamasi
# -------------------------------------------------------

def setup_logging(log_level: str = "INFO") -> None:
    """Logging ni konsol va fayl uchun sozlaydi."""
    Path("logs").mkdir(exist_ok=True)

    # Windows cmd/PowerShell da UTF-8 encoding muammosini hal qilish
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            try:
                stream.reconfigure(encoding='utf-8', errors='replace')
            except Exception:
                pass

    log_format = (
        "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s"
    )
    date_format = "%Y-%m-%d %H:%M:%S"

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level, logging.INFO))

    # Konsol handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(log_format, date_format))
    root_logger.addHandler(console_handler)

    # Fayl handler (aylanuvchi)
    try:
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(
            "logs/bot.log",
            maxBytes=5 * 1024 * 1024,   # 5 MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(logging.Formatter(log_format, date_format))
        root_logger.addHandler(file_handler)
    except Exception as e:
        logging.warning("Log fayl yaratib bo'lmadi: %s", e)

    # Uchinchi tomon kutubxonalar logini kamaytirish
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("feedparser").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("anthropic").setLevel(logging.WARNING)


logger = logging.getLogger(__name__)


# -------------------------------------------------------
# Asosiy asinxron funksiya
# -------------------------------------------------------

async def main() -> None:
    """
    Botni to'liq ishga tushiradi:
    1. Konfiguratsiyani yuklaydi
    2. Ma'lumotlar bazasini tayyorlaydi
    3. AI processorni ishga tushiradi
    4. Telegramga ulanadi
    5. Scheduler ni ishga tushiradi
    6. Darhol birinchi siklni bajaradi
    7. Polling ni boshlaydi
    """

    # --- Konfiguratsiya ---
    try:
        config = load_config()
    except (EnvironmentError, ValueError) as e:
        logging.critical("Konfiguratsiya xatosi: %s", e)
        sys.exit(1)

    setup_logging(config.log_level)

    logger.info("=== NLMINI_12 Auto-Posting Bot v1.0 ===")
    logger.info("AI Provider  : %s", config.ai_provider.upper())
    logger.info("Kanal        : %s", config.channel_id)
    logger.info("Interval     : %d daqiqa", config.fetch_interval_minutes)
    logger.info("Post limiti  : %d/sikl", config.max_posts_per_cycle)

    # --- Ma'lumotlar bazasi ---
    db = Database(config.database_url)
    try:
        await db.create_tables()
    except Exception as e:
        logger.critical("Baza yaratib bo'lmadi: %s", e, exc_info=True)
        sys.exit(1)

    # --- AI Processor ---
    try:
        ai_processor = AIProcessor(config)
    except (ImportError, ValueError) as e:
        logger.critical("AI Processor xatosi: %s", e)
        sys.exit(1)

    # --- Telegram Bot ---
    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )
    dp = Dispatcher()

    # --- Routerlarni ulash ---
    set_user_db(db)
    dp.include_router(user_router)

    @dp.callback_query(F.data == "challenge_join")
    async def on_challenge_join(callback: types.CallbackQuery):
        await callback.answer(
            text="Ajoyib! O'z ustingizda ishlashdan to'xtamang! 🔥\nOmad yor bo'lsin!",
            show_alert=True
        )


    # --- Scheduler ---
    scheduler = setup_scheduler(
        bot=bot,
        db=db,
        ai_processor=ai_processor,
        config=config,
    )

    # --- Graceful shutdown handler ---
    stop_event = asyncio.Event()

    def handle_signal(sig_name: str) -> None:
        logger.info("%s signali qabul qilindi. Bot to'xtatilmoqda...", sig_name)
        stop_event.set()

    # Windows da SIGTERM va SIGINT ni ushlash
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(
                sig, lambda s=sig: handle_signal(s.name)
            )
        except (NotImplementedError, RuntimeError):
            # Windows da signal handler qo'llab-quvvatlanmaydi
            pass

    # --- Botni tekshirish ---
    try:
        bot_info = await bot.get_me()
        logger.info(
            "Bot ulandi: @%s (ID: %d)", bot_info.username, bot_info.id
        )
    except Exception as e:
        logger.critical("Telegram ulanish xatosi: %s", e)
        await db.dispose()
        sys.exit(1)

    # --- Scheduler ishga tushirish ---
    scheduler.start()
    logger.info("Scheduler ishga tushdi.")

    # --- Darhol birinchi sikl ---
    logger.info("Birinchi posting sikli darhol boshlanmoqda...")
    try:
        await run_posting_cycle(
            bot=bot,
            db=db,
            ai_processor=ai_processor,
            config=config,
        )
    except Exception as e:
        logger.error("Birinchi siklda xato: %s", e, exc_info=True)

    # --- Polling boshlash ---
    logger.info("Bot polling boshlandi. To'xtatish uchun Ctrl+C bosing.")

    try:
        # Polling va stop_event ni parallel ishlatish
        polling_task = asyncio.create_task(
            dp.start_polling(bot, handle_signals=False)
        )
        stop_task = asyncio.create_task(stop_event.wait())

        done, pending = await asyncio.wait(
            [polling_task, stop_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        # Qolgan vazifalarni bekor qilish
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    except asyncio.CancelledError:
        logger.info("Polling bekor qilindi.")
    except Exception as e:
        logger.error("Polling da kutilmagan xato: %s", e, exc_info=True)
    finally:
        # --- To'g'ri yopilish ---
        logger.info("Yopilmoqda...")

        if scheduler.running:
            scheduler.shutdown(wait=False)
            logger.info("Scheduler to'xtatildi.")

        try:
            await bot.session.close()
        except Exception:
            pass

        await db.dispose()
        logger.info("Bot muvaffaqiyatli to'xtatildi. Xayr! 👋")


# -------------------------------------------------------
# Kirish nuqtasi
# -------------------------------------------------------

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[Bot foydalanuvchi tomonidan to'xtatildi]")
    except Exception as e:
        logging.critical("Kritik xato: %s", e, exc_info=True)
        sys.exit(1)
