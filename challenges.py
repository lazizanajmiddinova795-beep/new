# challenges.py — Haftalik chellenjlar moduli

import logging
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from ai_processor import AIProcessor
from config import Config

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Siz insonlarni o'z-o'zini rivojlantirishga undovchi motivatsion ekspertsiz.
Vazifangiz har shanba kuni obunachilar uchun 1 haftalik foydali chellenj (musobaqa/maqsad) o'ylab topish.
Masalan: "1 hafta har kuni 15 daqiqa kitob o'qish", "Raqamli detoks", "Yangi 10 ta so'z yodlash".

QOIDALAR:
1. O'zbek tilida yozing, motivatsion va jo'shqin ruhda bo'lsin.
2. Chellenj shartlarini aniq va qisqa (3-4 qator) qilib tushuntiring.
3. Sarlavha emoji bilan boshlanib, **bold** formatda yozilsin.
4. Hech qanday HTML tegi ishlatmang, faqat Markdown.
5. Hech qanday havola qo'shmang.
"""

USER_PROMPT = "Kelgusi hafta uchun obunachilar hayotini yaxshilaydigan, foydali va qiziqarli bitta haftalik chellenj o'ylab toping."

def _make_challenge_keyboard(channel_id: str) -> InlineKeyboardMarkup:
    """Chellenj postiga inline tugmalar qo'shadi."""
    # Izohlar uchun kanal havolasini yaratishga harakat qilamiz, yoki callback_data ishlatamiz.
    # Agar channel_id @ bilan boshlansa:
    url = f"https://t.me/{channel_id.replace('@', '')}" if channel_id.startswith('@') else "https://t.me/NLMINI_12"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔥 Qatnashaman!", callback_data="challenge_join"),
                InlineKeyboardButton(text="✍️ Fikr bildirish", url=url)
            ]
        ]
    )

async def run_weekly_challenge(bot: Bot, config: Config, ai_processor: AIProcessor) -> None:
    """Har shanba soat 23:00 da chellenj yaratish va yuborish funksiyasi."""
    logger.info("Weekly challenge sikli boshlandi...")
    
    challenge_text = await ai_processor.generate_custom_text(SYSTEM_PROMPT, USER_PROMPT)
    if not challenge_text:
        logger.error("Chellenj uchun AI matn yarata olmadi.")
        return

    final_text = f"🎯 **Haftalik Chellenj!**\n\n{challenge_text}\n\n#chellenj #motivatsiya #maqsad"
    keyboard = _make_challenge_keyboard(config.channel_id)

    try:
        message = await bot.send_message(
            chat_id=config.channel_id,
            text=final_text,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        logger.info("Chellenj muvaffaqiyatli yuborildi! Message ID: %d", message.message_id)
    except Exception as e:
        logger.error("Chellenj yuborishda xato: %s", e)
        try:
            plain_text = final_text.replace("**", "").replace("*", "")
            await bot.send_message(
                chat_id=config.channel_id,
                text=plain_text,
                reply_markup=keyboard
            )
        except Exception as retry_err:
            logger.error("Plain text bilan jo'natishda ham xato: %s", retry_err)
