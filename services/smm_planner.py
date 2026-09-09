import logging
from aiogram import Bot
from ai_processor import AIProcessor
from database import Database
from broadcaster import safe_send_message

logger = logging.getLogger(__name__)

async def run_morning_smm(bot: Bot, db: Database, ai_processor: AIProcessor):
    """Ertalabki SMM posti (Motivatsiya + Ob-havo)."""
    logger.info("Ertalabki SMM sikli boshlandi.")
    active_channels = await db.get_active_channels()
    if not active_channels:
        return

    prompt = (
        "Ertalabki motivatsion salomlashuv va kunlik ob-havo haqida qisqacha post yozing. "
        "Faktlar va vizual tasvirlardan foydalaning. "
        "Eng muhimi: obunachilarni izoh qoldirishga undovchi ochiq savol bilan tugating."
    )
    sys_prompt = "Siz tajribali, energiya ulashuvchi SMM menejersiz. O'zbek tilida, chiroyli Markdown formatda yozasiz."
    
    text = await ai_processor.generate_custom_text(sys_prompt, prompt)
    if not text:
        logger.error("AI ertalabki SMM post yarata olmadi.")
        return
        
    for ch in active_channels:
        await safe_send_message(bot, ch.channel_id, text)


async def run_evening_smm(bot: Bot, db: Database, ai_processor: AIProcessor):
    """Kechki SMM posti (Yakunlovchi mulohaza)."""
    logger.info("Kechki SMM sikli boshlandi.")
    active_channels = await db.get_active_channels()
    if not active_channels:
        return

    prompt = (
        "Kechki yakuniy mulohaza, bugungi kun sarhisobi haqida post yozing. "
        "Sokin, tinchlantiruvchi atmosferada bo'lsin. "
        "Obunachilardan bugungi kunda nimalarga erishganini yoki qanday o'tganini izohda yozishlarini so'rang."
    )
    sys_prompt = "Siz tajribali, mulohazakor SMM menejersiz. O'zbek tilida, chiroyli Markdown formatda yozasiz."
    
    text = await ai_processor.generate_custom_text(sys_prompt, prompt)
    if not text:
        logger.error("AI kechki SMM post yarata olmadi.")
        return
        
    for ch in active_channels:
        await safe_send_message(bot, ch.channel_id, text)
