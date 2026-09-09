# emotional_posts.py — Ertalabki motivatsion va emotional postlar moduli

import logging
from aiogram import Bot
from aiogram.enums import ParseMode
from ai_processor import AIProcessor
from database import Database
from broadcaster import safe_send_message

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Siz insonlarga ijobiy energiya, motivatsiya va iliqlik ulashuvchi psixolog va yozuvchisiz.
Vazifangiz har kuni ertalab kanal obunachilari uchun kunni yaxshi boshlashga yordam beradigan, ruhiyatni ko'taruvchi "emotional" (hissiyotli) va samimiy post yozish.

QOIDALAR:
1. Post O'zbek tilida, juda samimiy, insoniy va iliq ohangda bo'lsin.
2. 4-5 jumladan oshmasin.
3. Sarlavhada kuningiz xayrli bo'lsin ma'nosidagi so'zlar va emoji (masalan, 🌅, ☕️, 💛) qatnashsin va **bold** bo'lsin.
4. Hech qanday HTML tegi yoki havolalar ishlatmang, faqat Markdown.
5. Har bir post noyob va o'ylantiradigan chuqur ma'noga ega bo'lsin (masalan, vaqt qadri, o'ziga ishonch, yaxshilik qilish haqida).
"""

USER_PROMPT = "Bugungi tong uchun obunachilarga ijobiy kayfiyat, motivatsiya va iliqlik ulashadigan juda ta'sirli va chiroyli ertalabki post yozib bering."

async def run_emotional_post(bot: Bot, db: Database, ai_processor: AIProcessor) -> None:
    """Har kuni soat 09:00 da motivatsion post yaratish va yuborish funksiyasi."""
    logger.info("Emotional post sikli boshlandi...")

    active_channels = await db.get_active_channels()
    target_channels = [ch for ch in active_channels if ch.setting_emotional]
    if not target_channels:
        logger.info("setting_emotional yoqilgan faol kanallar yo'q.")
        return
    
    post_text = await ai_processor.generate_custom_text(SYSTEM_PROMPT, USER_PROMPT)
    if not post_text:
        logger.error("Emotional post uchun AI matn yarata olmadi.")
        return

    final_text = f"{post_text}\n\n#motivatsiya #tong #kayfiyat"

    for ch in target_channels:
        success = await safe_send_message(
            bot=bot,
                chat_id=ch.channel_id,
                text=final_text,
                parse_mode=ParseMode.MARKDOWN
        )
        if success:
            logger.info("Yuborildi: %s", ch.channel_id)
        else:
            logger.error("Yuborishda xato, oddiy matnda urinib ko'ramiz: %s", ch.channel_id)
            plain_text = final_text.replace("**", "").replace("*", "")
            await safe_send_message(
                bot=bot,
                chat_id=ch.channel_id,
                text=plain_text
            )
