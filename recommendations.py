# recommendations.py — Haftalik tavsiyalar moduli

import logging
from aiogram import Bot
from aiogram.enums import ParseMode
from ai_processor import AIProcessor
from config import Config

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Siz insonlar uchun foydali manbalarni kashf qilishga yordam beradigan ekspertsiz.
Vazifangiz har yakshanba kuni 1 ta ajoyib resursni (kitob, hujjatli film, yoki foydali veb-sayt / AI vositasi) tavsiya qilish.

QOIDALAR:
1. O'zbek tilida, qiziqarli va motivatsion ohangda yozing.
2. 4-5 jumla bo'lsin. Nima uchun bu narsa foydali ekanligini alohida ta'kidlang.
3. Sarlavha emoji bilan va **bold** bo'lsin.
4. Resursning nomini ham **bold** qilib ajratib ko'rsating.
5. Hech qanday HTML ishlatmang, faqat Markdown.
"""

USER_PROMPT = "Bugun dam olish kuni. O'quvchilarga o'z ustida ishlash yoki dunyoqarashini kengaytirish uchun yordam beradigan 1 ta ajoyib kitob, kino, hujjatli film yoki juda foydali AI vositasi/veb-sayt tavsiya qiling."

async def run_weekly_recommendation(bot: Bot, config: Config, ai_processor: AIProcessor) -> None:
    """Har Yakshanba soat 10:00 da foydali tavsiya yuborish funksiyasi."""
    logger.info("Weekly recommendation sikli boshlandi...")
    
    rec_text = await ai_processor.generate_custom_text(SYSTEM_PROMPT, USER_PROMPT)
    if not rec_text:
        logger.error("Tavsiya uchun AI matn yarata olmadi.")
        return

    final_text = f"📚 **Hafta Tavsiyasi!**\n\n{rec_text}\n\n#tavsiya #foydali #rivojlanish"

    try:
        message = await bot.send_message(
            chat_id=config.channel_id,
            text=final_text,
            parse_mode=ParseMode.MARKDOWN
        )
        logger.info("Tavsiya muvaffaqiyatli yuborildi! Message ID: %d", message.message_id)
    except Exception as e:
        logger.error("Tavsiya yuborishda xato: %s", e)
        try:
            plain_text = final_text.replace("**", "").replace("*", "")
            await bot.send_message(
                chat_id=config.channel_id,
                text=plain_text
            )
        except Exception as retry_err:
            logger.error("Plain text bilan jo'natishda ham xato: %s", retry_err)
