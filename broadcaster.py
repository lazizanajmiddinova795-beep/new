import asyncio
import logging
from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter, TelegramAPIError

logger = logging.getLogger(__name__)

async def safe_send_message(
    bot: Bot, 
    chat_id: str | int, 
    text: str, 
    parse_mode: str | None = None,
    reply_markup=None,
    disable_web_page_preview: bool = False
) -> bool:
    """
    Xavfsiz xabar yuborish. Agar Telegram API 'Too Many Requests' (429) xatosini qaytarsa,
    ko'rsatilgan vaqt (TelegramRetryAfter) davomida kutadi va qayta urinadi.
    """
    max_retries = 3
    for attempt in range(max_retries):
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
                disable_web_page_preview=disable_web_page_preview
            )
            return True
        except TelegramRetryAfter as e:
            logger.warning("Rate limitga tushdik! %s soniya kutamiz... (Kanal: %s)", e.retry_after, chat_id)
            await asyncio.sleep(e.retry_after)
        except TelegramAPIError as e:
            logger.error("Xabar yuborishda xato (Kanal: %s): %s", chat_id, e)
            # Kritik xatolarda qayta urinmaymiz (masalan kanal topilmadi, block qilingan va h.k.)
            break
        except Exception as e:
            logger.error("Kutilmagan xato (Kanal: %s): %s", chat_id, e)
            break
            
    return False

async def safe_send_photo(
    bot: Bot,
    chat_id: str | int,
    photo: str,
    caption: str | None = None,
    parse_mode: str | None = None,
    reply_markup=None
) -> bool:
    max_retries = 3
    for attempt in range(max_retries):
        try:
            await bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=caption,
                parse_mode=parse_mode,
                reply_markup=reply_markup
            )
            return True
        except TelegramRetryAfter as e:
            logger.warning("Rate limitga tushdik (Rasm)! %s soniya kutamiz... (Kanal: %s)", e.retry_after, chat_id)
            await asyncio.sleep(e.retry_after)
        except TelegramAPIError as e:
            logger.error("Rasm yuborishda xato (Kanal: %s): %s", chat_id, e)
            break
        except Exception as e:
            logger.error("Kutilmagan xato rasm yuborishda (Kanal: %s): %s", chat_id, e)
            break
            
    return False

async def safe_send_video(
    bot: Bot,
    chat_id: str | int,
    video: str,
    caption: str | None = None,
    parse_mode: str | None = None,
    reply_markup=None
) -> bool:
    max_retries = 3
    for attempt in range(max_retries):
        try:
            await bot.send_video(
                chat_id=chat_id,
                video=video,
                caption=caption,
                parse_mode=parse_mode,
                reply_markup=reply_markup
            )
            return True
        except TelegramRetryAfter as e:
            logger.warning("Rate limitga tushdik (Video)! %s soniya kutamiz... (Kanal: %s)", e.retry_after, chat_id)
            await asyncio.sleep(e.retry_after)
        except TelegramAPIError as e:
            logger.error("Video yuborishda xato (Kanal: %s): %s", chat_id, e)
            break
        except Exception as e:
            logger.error("Kutilmagan xato video yuborishda (Kanal: %s): %s", chat_id, e)
            break
            
    return False
