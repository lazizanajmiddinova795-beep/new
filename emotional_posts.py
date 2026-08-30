# emotional_posts.py — Ertalabki motivatsion va emotional postlar moduli

import logging
from aiogram import Bot
from aiogram.enums import ParseMode
from ai_processor import AIProcessor
from config import Config

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

async def run_emotional_post(bot: Bot, config: Config, ai_processor: AIProcessor) -> None:
    """Har kuni soat 09:00 da motivatsion post yaratish va yuborish funksiyasi."""
    logger.info("Emotional post sikli boshlandi...")
    
    post_text = await ai_processor.generate_custom_text(SYSTEM_PROMPT, USER_PROMPT)
    if not post_text:
        logger.error("Emotional post uchun AI matn yarata olmadi.")
        return

    final_text = f"{post_text}\n\n#motivatsiya #tong #kayfiyat"

    try:
        message = await bot.send_message(
            chat_id=config.channel_id,
            text=final_text,
            parse_mode=ParseMode.MARKDOWN
        )
        logger.info("Emotional post muvaffaqiyatli yuborildi! Message ID: %d", message.message_id)
    except Exception as e:
        logger.error("Emotional post yuborishda xato: %s", e)
        try:
            plain_text = final_text.replace("**", "").replace("*", "")
            await bot.send_message(
                chat_id=config.channel_id,
                text=plain_text
            )
        except Exception as retry_err:
            logger.error("Plain text bilan jo'natishda ham xato: %s", retry_err)
