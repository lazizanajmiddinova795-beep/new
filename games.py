# games.py — So'z o'yinlari va viktorinalar moduli

import logging
from aiogram import Bot
from aiogram.enums import ParseMode
from ai_processor import AIProcessor
from config import Config

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

async def run_daily_game(bot: Bot, config: Config, ai_processor: AIProcessor) -> None:
    """Har kuni soat 22:00 da o'yin yaratish va yuborish funksiyasi."""
    logger.info("Daily game sikli boshlandi...")
    
    game_text = await ai_processor.generate_custom_text(SYSTEM_PROMPT, USER_PROMPT)
    if not game_text:
        logger.error("O'yin uchun AI matn yarata olmadi.")
        return

    final_text = f"🎮 **Kechki Mantiq O'yini!**\n\n{game_text}\n\n#oyin #mantiq #quiz"

    try:
        # Markdown parsing xatoliklarini kamaytirish uchun xavfsiz jo'natamiz
        message = await bot.send_message(
            chat_id=config.channel_id,
            text=final_text,
            parse_mode=ParseMode.MARKDOWN
        )
        logger.info("O'yin muvaffaqiyatli yuborildi! Message ID: %d", message.message_id)
    except Exception as e:
        logger.error("O'yin yuborishda xato: %s", e)
        # Agar Markdown xatosi bo'lsa, plain text bilan qayta urinib ko'rish
        try:
            plain_text = final_text.replace("**", "").replace("*", "")
            await bot.send_message(
                chat_id=config.channel_id,
                text=plain_text
            )
        except Exception as retry_err:
            logger.error("Plain text bilan jo'natishda ham xato: %s", retry_err)
