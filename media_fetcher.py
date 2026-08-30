# media_fetcher.py — Ko'p formatli kontent yuborish moduli

import logging
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.types import URLInputFile
from ai_processor import AIProcessor
from database import Database

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Siz qiziqarli texnologiya va ilm-fan faktlarini ulashuvchi O'zbek tili ekspertisiz.
QOIDALAR:
1. Matn O'zbek tilida, tushunarli va qiziqarli bo'lsin.
2. Fakt 3-4 jumladan oshmasin.
3. Sarlavha qiziqarli emoji bilan boshlanib, **bold** formatda yozilsin.
4. Hech qanday havola yoki qo'shimcha teglarsiz toza Markdown formatda yozing.
5. Post yakunida doim bitta foydali maslahat yoki xulosa bering.
"""

USER_PROMPT = "Texnologiya, sun'iy intellekt, kosmos yoki zamonaviy ilm-fan haqida hozirgacha ko'pchilik bilmagan juda qiziqarli, hayratlanarli fakt yarating."

async def run_media_post(bot: Bot, db: Database, ai_processor: AIProcessor) -> None:
    """Kunlik yoki vaqti-vaqti bilan qiziqarli fakt va rasm yuborish funksiyasi."""
    logger.info("Media fact post sikli boshlandi...")

    active_channels = await db.get_active_channels()
    target_channels = [ch for ch in active_channels if ch.setting_videos]
    if not target_channels:
        logger.info("setting_videos yoqilgan faol kanallar yo'q.")
        return
    
    # 1. AI orqali qiziqarli fakt yaratish
    fact_text = await ai_processor.generate_custom_text(SYSTEM_PROMPT, USER_PROMPT)
    if not fact_text:
        logger.error("Media fakt uchun AI matn yarata olmadi.")
        return

    # 2. Rasm olish (LoremFlickr texnologiya rasmi)
    image_url = "https://loremflickr.com/800/600/technology,science"
    
    # Xeshteglarni qo'shish
    final_text = f"{fact_text}\n\n#fakt #texnologiya #ilmfan"

    # 3. Telegramga yuborish
    try:
        photo = URLInputFile(image_url)
        message = await bot.send_photo(
            chat_id=config.channel_id,
            photo=photo,
            caption=final_text,
            parse_mode=ParseMode.MARKDOWN
        )
        logger.info("Media post muvaffaqiyatli yuborildi! Message ID: %d", message.message_id)
    except Exception as e:
        logger.error("Media post yuborishda xato: %s", e)
