# handlers/user_handlers.py

import logging
from aiogram import Router, F, types
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from database import Database

logger = logging.getLogger(__name__)
router = Router()

# Global bazaga havola (main.py dan set qilinadi)
db: Database = None

def set_db(database: Database):
    global db
    db = database

@router.message(CommandStart())
async def cmd_start(message: Message):
    """Foydalanuvchi botni boshlaganda."""
    user = await db.get_or_create_user(message.from_user.id, message.from_user.username)
    text = (
        f"Salom, {message.from_user.first_name}! 👋\n\n"
        "Men Avto-Posting botiman. Men orqali kanalingizga qiziqarli yangiliklar, "
        "videolar va o'yinlarni avtomatik joylab borishingiz mumkin.\n\n"
        "Kanal qo'shish uchun: /add_channel\n"
        "Kanallaringizni ko'rish: /my_channels"
    )
    await message.answer(text)

@router.message(Command("add_channel"))
async def cmd_add_channel(message: Message):
    text = (
        "➕ **Kanal qo'shish bo'yicha yo'riqnoma:**\n\n"
        "1. Meni (@{}) o'z kanalingizga **Administrator** sifatida qo'shing (Post yozish huquqi bilan).\n"
        "2. Kanalingizga kiring va istalgan postni (yoki yangi yozib) menga **Forward** (Uzatish) qiling.\n\n"
        "Shundan so'ng kanalingiz ro'yxatga olinadi!"
    ).format((await message.bot.get_me()).username)
    await message.answer(text, parse_mode="Markdown")

@router.message(F.forward_origin)
async def handle_forwarded_message(message: Message):
    """Kanalni ro'yxatdan o'tkazish uchun forwarded xabarni ushlash."""
    origin = message.forward_origin
    if origin.type == "channel":
        channel_id = str(origin.chat.id)
        channel_title = origin.chat.title
        
        # Admin huquqini tekshirish
        try:
            member = await message.bot.get_chat_member(chat_id=channel_id, user_id=(await message.bot.get_me()).id)
            if member.status not in ("administrator", "creator"):
                await message.answer("Men bu kanalda administrator emasman! Iltimos, admin huquqini bering.")
                return
            if not member.can_post_messages:
                await message.answer("Menda post yozish (Post messages) huquqi yo'q! Iltimos, ruxsat bering.")
                return
        except Exception as e:
            logger.error("Kanal adminligini tekshirishda xato: %s", e)
            await message.answer("Kanalni tekshirib bo'lmadi. Meni admin qilganingizga ishonch hosil qiling.")
            return

        success = await db.add_channel(message.from_user.id, channel_id, channel_title)
        if success:
            await message.answer(f"✅ **{channel_title}** kanali muvaffaqiyatli ulandi!\n\nSozlamalarni ko'rish uchun: /my_channels", parse_mode="Markdown")
        else:
            await message.answer("Kechirasiz, bazada xatolik yuz berdi yoki siz ro'yxatdan o'tmagansiz (/start ni bosing).")
    else:
        await message.answer("Iltimos, xabarni aynan **kanaldan** forward qiling (guruh yoki shaxsiy chatdan emas).")

@router.message(Command("my_channels"))
async def cmd_my_channels(message: Message):
    """Foydalanuvchi kanallari va sozlamalarini chiqarish."""
    channels = await db.get_user_channels(message.from_user.id)
    if not channels:
        await message.answer("Sizda hali ulangan kanallar yo'q. /add_channel orqali qo'shing.")
        return

    for ch in channels:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"{'✅' if ch.setting_news else '❌'} Yangiliklar",
                        callback_data=f"toggle_{ch.channel_id}_setting_news"
                    ),
                    InlineKeyboardButton(
                        text=f"{'✅' if ch.setting_games else '❌'} O'yinlar",
                        callback_data=f"toggle_{ch.channel_id}_setting_games"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=f"{'✅' if ch.setting_videos else '❌'} Videolar",
                        callback_data=f"toggle_{ch.channel_id}_setting_videos"
                    ),
                    InlineKeyboardButton(
                        text=f"{'✅' if ch.setting_emotional else '❌'} Motivatsiya",
                        callback_data=f"toggle_{ch.channel_id}_setting_emotional"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=f"{'✅' if ch.setting_recommendations else '❌'} Tavsiyalar",
                        callback_data=f"toggle_{ch.channel_id}_setting_recommendations"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=f"{'🟢 Faol' if ch.is_active else '🔴 To`xtatilgan'} (Kanal Holati)",
                        callback_data=f"toggle_{ch.channel_id}_is_active"
                    )
                ]
            ]
        )
        await message.answer(f"📢 **{ch.channel_name}** sozlamalari:", reply_markup=keyboard, parse_mode="Markdown")

@router.callback_query(F.data.startswith("toggle_"))
async def process_toggle_callback(callback: CallbackQuery):
    # data formati: toggle_-100123456789_setting_news
    parts = callback.data.split("_")
    # toggle, id, setting_name
    if len(parts) >= 3:
        channel_id = parts[1]
        setting_name = "_".join(parts[2:]) # e.g. setting_news
        
        channels = await db.get_user_channels(callback.from_user.id)
        channel = next((c for c in channels if c.channel_id == channel_id), None)
        
        if channel:
            current_value = getattr(channel, setting_name)
            new_value = not current_value
            await db.update_channel_setting(channel_id, setting_name, new_value)
            
            # Yangi qiymatni obyektga ham qo'llaymiz
            setattr(channel, setting_name, new_value)
            
            # Tugmalarni yangilaymiz
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=f"{'✅' if channel.setting_news else '❌'} Yangiliklar",
                            callback_data=f"toggle_{channel.channel_id}_setting_news"
                        ),
                        InlineKeyboardButton(
                            text=f"{'✅' if channel.setting_games else '❌'} O'yinlar",
                            callback_data=f"toggle_{channel.channel_id}_setting_games"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text=f"{'✅' if channel.setting_videos else '❌'} Videolar",
                            callback_data=f"toggle_{channel.channel_id}_setting_videos"
                        ),
                        InlineKeyboardButton(
                            text=f"{'✅' if channel.setting_emotional else '❌'} Motivatsiya",
                            callback_data=f"toggle_{channel.channel_id}_setting_emotional"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text=f"{'✅' if channel.setting_recommendations else '❌'} Tavsiyalar",
                            callback_data=f"toggle_{channel.channel_id}_setting_recommendations"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text=f"{'🟢 Faol' if channel.is_active else '🔴 To`xtatilgan'} (Kanal Holati)",
                            callback_data=f"toggle_{channel.channel_id}_is_active"
                        )
                    ]
                ]
            )
            await callback.message.edit_reply_markup(reply_markup=keyboard)
            await callback.answer("Sozlama o'zgartirildi!")
        else:
            await callback.answer("Kanal topilmadi yoki huquqingiz yo'q.", show_alert=True)
    else:
        await callback.answer("Xato ma'lumot formati.")

@router.callback_query(F.data == "game_ans")
async def game_answer_callback(callback: CallbackQuery):
    await callback.answer(
        "✅ Javobingiz qabul qilindi!\n\n💡 To'g'ri javobni bilish uchun post tagidagi qoraytirilgan (spoiler) so'z ustiga bosing.", 
        show_alert=True
    )

