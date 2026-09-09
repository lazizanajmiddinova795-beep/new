import asyncio
import logging
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import Database
from broadcaster import safe_send_message, safe_send_photo, safe_send_video

logger = logging.getLogger(__name__)
router = Router()

db: Database = None
bot_instance: Bot = None

def set_ad_dependencies(database: Database, bot: Bot):
    global db, bot_instance
    db = database
    bot_instance = bot

class AdStates(StatesGroup):
    waiting_for_ad_post = State()

@router.message(Command("send_ad"))
async def cmd_send_ad(message: Message, state: FSMContext):
    """Admin reklama yuborishni boshlaydi."""
    # Check if user has channels
    channels = await db.get_user_channels(message.from_user.id)
    if not channels:
        await message.answer("Sizda ro'yxatdan o'tgan kanallar yo'q. Ushbu buyruq faqat adminlar uchun.")
        return
        
    await message.answer(
        "Reklama postini yuboring. \n"
        "(Siz matn, rasm yoki video yuborishingiz mumkin. Agar tugma (inline keyboard) bo'lsa, uni ham bot avtomatik qabul qilib tarqatadi.)\n\n"
        "Bekor qilish uchun /cancel yozing."
    )
    await state.set_state(AdStates.waiting_for_ad_post)

@router.message(Command("cancel"), AdStates.waiting_for_ad_post)
async def cancel_ad(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Reklama yuborish bekor qilindi.")

@router.message(AdStates.waiting_for_ad_post)
async def process_ad_post(message: Message, state: FSMContext):
    """Reklama postini barcha kanallarga tarqatish."""
    await state.clear()
    
    active_channels = await db.get_active_channels()
    if not active_channels:
        await message.answer("Bazadan faol kanallar topilmadi!")
        return
        
    await message.answer(f"Reklama {len(active_channels)} ta kanalga tarqatilmoqda. Iltimos, kuting...")
    
    # Run broadcast in background
    asyncio.create_task(broadcast_ad(message, active_channels, message.from_user.id))

async def broadcast_ad(ad_message: Message, target_channels: list, admin_id: int):
    """Reklamani navbat bilan kanallarga yuborish va hisobot berish."""
    success_count = 0
    fail_count = 0
    
    for ch in target_channels:
        try:
            # message.copy_to xavfsiz va barcha turdagi xabarlarni qo'llab-quvvatlaydi
            # Lekin biz RateLimit ga tushmaslik uchun broadcaster ga moslashishimiz kerak.
            # Shuning uchun copy_to orqali jo'natamiz, lekin try/except bilan RateLimit ni ushlaymiz.
            # Ammo biz safe_send yozgandik, uni copy_to ga ham moslashimiz mumkin, yoki shu yerda retry logic yozamiz.
            
            from aiogram.exceptions import TelegramRetryAfter, TelegramAPIError
            
            max_retries = 3
            sent = False
            for attempt in range(max_retries):
                try:
                    await ad_message.copy_to(chat_id=ch.channel_id, reply_markup=ad_message.reply_markup)
                    sent = True
                    break
                except TelegramRetryAfter as e:
                    logger.warning("Ad broadcast Rate limit! %s soniya kutiladi...", e.retry_after)
                    await asyncio.sleep(e.retry_after)
                except TelegramAPIError as e:
                    logger.error("Reklama yuborishda xato (Kanal: %s): %s", ch.channel_id, e)
                    break
                except Exception as e:
                    logger.error("Kutilmagan xato (Kanal: %s): %s", ch.channel_id, e)
                    break
            
            if sent:
                success_count += 1
            else:
                fail_count += 1
                
            # Har bir xabardan so'ng ozgina kutish (spam protection)
            await asyncio.sleep(1)
            
        except Exception as e:
            logger.error("Kutilmagan broadcast xatosi: %s", e)
            fail_count += 1
            
    # Hisobot yuborish
    report = (
        f"📊 **Reklama Tarqatish Yakunlandi!**\n\n"
        f"✅ Muvaffaqiyatli: {success_count} ta kanal\n"
        f"❌ Xatolik: {fail_count} ta kanal\n\n"
        f"Jami: {len(target_channels)} ta kanal."
    )
    
    # Adminga xabar berish
    try:
        await bot_instance.send_message(chat_id=admin_id, text=report, parse_mode="Markdown")
    except Exception as e:
        logger.error("Adminga hisobot yuborib bo'lmadi: %s", e)
