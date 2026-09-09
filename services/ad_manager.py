import logging
import asyncio
from aiogram import Bot
from database import Database

logger = logging.getLogger(__name__)

async def check_and_delete_ads(bot: Bot, db: Database):
    """Vaqti o'tgan reklamalarni barcha kanallardan o'chirish."""
    logger.info("Reklamalarni tekshirish (Auto-Delete) boshlandi.")
    try:
        pending_ads = await db.get_pending_ads_to_delete()
        if not pending_ads:
            return
            
        for ad in pending_ads:
            try:
                # chat_id (kanal) va message_id (reklama)
                await bot.delete_message(chat_id=ad.channel_id, message_id=ad.message_id)
                await db.mark_ad_deleted(ad.id)
                logger.info("Reklama o'chirildi: %s (MSG: %d)", ad.channel_id, ad.message_id)
            except Exception as e:
                logger.error("Reklama o'chirishda xato (ID: %d): %s", ad.id, e)
                # Agar topilmasa yoki o'chirib yuborilgan bo'lsa ham bazada deleted qilib belgilaymiz
                if "message to delete not found" in str(e).lower():
                    await db.mark_ad_deleted(ad.id)
            
            await asyncio.sleep(0.5)
            
    except Exception as e:
        logger.error("Ad-Manager auto-delete xatosi: %s", e)
