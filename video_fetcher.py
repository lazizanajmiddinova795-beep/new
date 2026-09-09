# video_fetcher.py — Kunlik qiziqarli videolar va faktlar moduli

import logging
import random
from aiogram import Bot
from aiogram.enums import ParseMode
from ai_processor import AIProcessor
from database import Database
from broadcaster import safe_send_message

logger = logging.getLogger(__name__)

# Tasdiqlangan va qiziqarli video havolalari (YouTube Shorts yoki ochiq manbalar)
# AI ushbu mavzularda fakt yozadi va havola postga qo'shiladi.
VIDEO_SOURCES = [
    {"url": "https://www.youtube.com/shorts/3ZzRXXz0Qkw", "topic": "Kvant kompyuterlari qanday ishlaydi"},
    {"url": "https://www.youtube.com/shorts/ZqM6WJv4N6Q", "topic": "Qora tuynuklar siri"},
    {"url": "https://www.youtube.com/shorts/V4QcZpE3DGs", "topic": "Sun'iy intellekt kelajagi"},
    {"url": "https://www.youtube.com/shorts/5jR1XN8V2Qk", "topic": "Kosmosning cheki bormi?"},
    {"url": "https://www.youtube.com/shorts/8b1qY7M7J00", "topic": "Odam miyasi va neyron tarmoqlar"},
    {"url": "https://www.youtube.com/shorts/4b9V4X3C210", "topic": "Marsga sayohat va SpaceX"},
    {"url": "https://www.youtube.com/shorts/7A3Y9T5V6aM", "topic": "Dengiz tubidagi hayratlanarli jonzotlar"},
    {"url": "https://www.youtube.com/shorts/9f8R7Z1T6b0", "topic": "Vaqt bo'ylab sayohat qilish mumkinmi?"}
]

SYSTEM_PROMPT = """Siz ilm-fan va texnologiya bo'yicha qiziqarli faktlar ulashuvchi O'zbek tili ekspertisiz.
Sizga bir mavzu beriladi. Siz shu mavzuga doir odamlarni hayratda qoldiradigan bitta qisqa fakt (3-4 jumla) yozishingiz kerak.

QOIDALAR:
1. Matn O'zbek tilida, ilmiy, lekin ommabop va tushunarli bo'lsin.
2. Sarlavha qiziqarli emoji bilan boshlanib, **bold** formatda yozilsin.
3. Hech qanday HTML tegi ishlatmang, faqat Markdown.
4. Odamlar o'qiganda "Shunaqasi ham bo'ladimi?!" deyishi kerak.
"""

async def run_daily_video(bot: Bot, db: Database, ai_processor: AIProcessor) -> None:
    """Har kuni soat 14:00 da qiziqarli video-fakt yuborish funksiyasi."""
    logger.info("Video fetcher sikli boshlandi...")

    active_channels = await db.get_active_channels()
    target_channels = [ch for ch in active_channels if ch.setting_videos]
    if not target_channels:
        logger.info("setting_videos yoqilgan faol kanallar yo'q.")
        return
    
    # Tasodifiy video manbasini tanlash
    selected_video = random.choice(VIDEO_SOURCES)
    topic = selected_video["topic"]
    video_url = selected_video["url"]
    
    user_prompt = f"Mavzu: {topic}. Shu mavzu atrofida juda qiziqarli, hayratlanarli fakt yozib bering."
    
    fact_text = await ai_processor.generate_custom_text(SYSTEM_PROMPT, user_prompt)
    if not fact_text:
        logger.error("Video fakt uchun AI matn yarata olmadi.")
        return

    # Matn va videoni birlashtirish
    topic_tag = topic.replace(' ', '').replace("'", "")
    final_text = f"🎬 **Kunlik Video-Fakt**\n\n{fact_text}\n\n📹 **Videoni ko'rish:** [Shu yerga bosing]({video_url})\n\n#videofakt #qiziqarli #{topic_tag}"

    for ch in target_channels:
        success = await safe_send_message(
            bot=bot,
                chat_id=ch.channel_id,
                text=final_text,
                parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=False
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
