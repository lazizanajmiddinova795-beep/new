# games.py — So'z o'yinlari va viktorinalar moduli

import logging
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from ai_processor import AIProcessor
from database import Database
from broadcaster import safe_send_message

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Siz qiziqarli mantiqiy topishmoqlar va viktorinalar tuzuvchi ekspertsiz.
Vazifangiz har kuni obunachilar uchun mantiqiy, qiziqarli va "normal" odamlar ham topa oladigan bitta o'yin yaratish.

QOIDALAR:
1. Siz FAQAT VA FAQAT sof JSON formatida javob qaytarishingiz shart. Boshqa hech qanday izoh qo'shmang.
2. Savol (question) matni O'zbek tilida bo'lsin va umumiy uzunligi 250 belgidan (harfdan) oshmasin.
3. To'rtta qisqa variant (options) bering.
4. To'g'ri javobning indeksini (correct_option_id) 0 dan 3 gacha bo'lgan raqam bilan ko'rsating.
5. To'g'ri javob nega to'g'ri ekanligini qisqa tushuntirib bering (explanation). Maksimum 150 belgi.

JSON FORMATI:
{
  "question": "Mantiqiy savolni bu yerga yozing...",
  "options": ["A variant", "B variant", "C variant", "D variant"],
  "correct_option_id": 1,
  "explanation": "Chunki..."
}
"""

USER_PROMPT = "Bugun uchun juda qiziqarli mantiqiy topishmoq tuzib bering. Faqat JSON qaytaring."

async def run_daily_game(bot: Bot, db: Database, ai_processor: AIProcessor) -> None:
    """Har kuni soat 22:00 da o'yin yaratish va yuborish funksiyasi."""
    logger.info("Daily game sikli boshlandi...")
    
    active_channels = await db.get_active_channels()
    target_channels = [ch for ch in active_channels if ch.setting_games]
    if not target_channels:
        logger.info("O'yinlar yoqilgan faol kanallar yo'q.")
        return

    json_text = await ai_processor.generate_custom_text(SYSTEM_PROMPT, USER_PROMPT)
    if not json_text:
        logger.error("O'yin uchun AI matn (JSON) yarata olmadi.")
        return

    import json
    import re
    
    try:
        # Markdown kod bloki (```json ... ```) bilan kelsa tozalash
        json_text = re.sub(r'```(?:json)?\n?(.*?)\n?```', r'\1', json_text, flags=re.DOTALL).strip()
        data = json.loads(json_text)
        
        question = data.get("question", "Qiziqarli mantiqiy savol:")
        options = data.get("options", ["A", "B", "C", "D"])
        correct_option_id = data.get("correct_option_id", 0)
        explanation = data.get("explanation", "To'g'ri javob!")
        
        # Telegram API cheklovlari
        if len(question) > 300:
            question = question[:295] + "..."
        if len(explanation) > 200:
            explanation = explanation[:195] + "..."
        
        for i in range(len(options)):
            if len(options[i]) > 100:
                options[i] = options[i][:95] + "..."
                
    except Exception as e:
        logger.error("JSON parse xatosi: %s | Text: %s", e, json_text)
        return

    for ch in target_channels:
        try:
            await bot.send_poll(
                chat_id=ch.channel_id,
                question=question,
                options=options,
                type="quiz",
                correct_option_id=correct_option_id,
                explanation=explanation,
                is_anonymous=True
            )
            logger.info("Native Quiz yuborildi: %s", ch.channel_id)
        except Exception as e:
            logger.error("Native Quiz yuborishda xato: %s | Kanal: %s", e, ch.channel_id)
