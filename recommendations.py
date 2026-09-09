# recommendations.py — Haftalik tavsiyalar moduli

import logging
from aiogram import Bot
from aiogram.enums import ParseMode
from ai_processor import AIProcessor
from database import Database
from broadcaster import safe_send_message

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

async def run_weekly_recommendation(bot: Bot, db: Database, ai_processor: AIProcessor) -> None:
    """Har Yakshanba soat 10:00 da foydali tavsiya yuborish funksiyasi."""
    logger.info("Weekly recommendation sikli boshlandi...")

    active_channels = await db.get_active_channels()
    target_channels = [ch for ch in active_channels if ch.setting_recommendations]
    if not target_channels:
        logger.info("setting_recommendations yoqilgan faol kanallar yo'q.")
        return
    
    rec_text = await ai_processor.generate_custom_text(SYSTEM_PROMPT, USER_PROMPT)
    if not rec_text:
        logger.error("Tavsiya uchun AI matn yarata olmadi.")
        return

    final_text = f"📚 **Hafta Tavsiyasi!**\n\n{rec_text}\n\n#tavsiya #foydali #rivojlanish"

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
