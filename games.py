# games.py — So'z o'yinlari va viktorinalar moduli

import logging
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from ai_processor import AIProcessor
from database import Database
from broadcaster import safe_send_message

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Siz qiziqarli so'z o'yinlari, mantiqiy topishmoqlar va viktorinalar tuzuvchi ekspertsiz.
Vazifangiz har kuni obunachilar uchun mantiqiy, qiziqarli va "normal" odamlar ham topa oladigan bitta topishmoq yoki so'z o'yini yaratish.

QOIDALAR:
1. O'yin 3 ta tilda yozilishi shart: O'zbekcha (asosiy), Inglizcha va Ruscha.
2. Har bir til uchun bitta blok qiling: savol va uning variantlari (yoki ishoralari).
3. Postning eng pastida hamma tillar uchun umumiy javobni SPOILER tagida yashiring, ya'ni javobni || mana shunday || qavslar ichida yozing.
4. Qiziqarli emojilar ishlating. Format chiroyli va Markdown ga mos bo'lsin.
5. Hech qanday HTML ishlatmang, faqat Telegram Markdown (bold, italic va spoiler ||javob||).
"""

USER_PROMPT = "Bugun uchun juda qiziqarli mantiqiy topishmoq yoki so'z o'yini tuzib bering. Uchta tilda bo'lsin. Javobni eng pastda spoiler qilib yozing."

async def run_daily_game(bot: Bot, db: Database, ai_processor: AIProcessor) -> None:
    """Har kuni soat 22:00 da o'yin yaratish va yuborish funksiyasi."""
    logger.info("Daily game sikli boshlandi...")
    
    active_channels = await db.get_active_channels()
    target_channels = [ch for ch in active_channels if ch.setting_games]
    if not target_channels:
        logger.info("O'yinlar yoqilgan faol kanallar yo'q.")
        return

    game_text = await ai_processor.generate_custom_text(SYSTEM_PROMPT, USER_PROMPT)
    if not game_text:
        logger.error("O'yin uchun AI matn yarata olmadi.")
        return

    final_text = f"🎮 **Kechki Mantiq O'yini!**\n\n{game_text}\n\n#oyin #mantiq #quiz"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="A", callback_data="game_ans"),
            InlineKeyboardButton(text="B", callback_data="game_ans"),
            InlineKeyboardButton(text="C", callback_data="game_ans"),
            InlineKeyboardButton(text="D", callback_data="game_ans")
        ]
    ])

    for ch in target_channels:
        success = await safe_send_message(
            bot=bot,
            chat_id=ch.channel_id,
            text=final_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
        if success:
            logger.info("O'yin yuborildi: %s", ch.channel_id)
        else:
            logger.error("O'yin yuborishda xato, oddiy matnda urinib ko'ramiz: %s", ch.channel_id)
            plain_text = final_text.replace("**", "").replace("*", "")
            await safe_send_message(
                bot=bot,
                chat_id=ch.channel_id,
                text=plain_text,
                reply_markup=keyboard
            )
