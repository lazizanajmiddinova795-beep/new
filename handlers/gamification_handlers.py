import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from database import Database

logger = logging.getLogger(__name__)
router = Router()
db: Database = None

def set_gamification_db(database: Database):
    global db
    db = database

@router.message(Command("check_in"))
async def cmd_check_in(message: Message):
    """Kunlik faollikni tasdiqlash (Daily Streak)."""
    # Avval foydalanuvchini bazaga qo'shamiz (get_or_create)
    user = await db.get_or_create_user(message.from_user.id, message.from_user.username)
    streak = await db.update_user_streak(user.telegram_id)
    
    await message.answer(
        f"🔥 **Zo'r!** Siz bugun ham faolsiz.\n\n"
        f"📈 Sizning joriy uzluksiz kunlaringiz (streak): **{streak} kun**\n"
        f"💰 Hisobingizga 10 ball qo'shildi!"
    )

@router.message(Command("leaderboard"))
async def cmd_leaderboard(message: Message):
    """Eng faol 10 ta a'zo reytingi."""
    top_users = await db.get_global_leaderboard()
    if not top_users:
        await message.answer("Reyting hozircha bo'sh.")
        return
        
    text = "🏆 **Eng faol foydalanuvchilar (Top-10):**\n\n"
    for i, user in enumerate(top_users, 1):
        name = user.username or f"Foydalanuvchi {user.telegram_id}"
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text += f"{medal} @{name} — {user.points} ball (🔥 {user.streak_days} kun streak)\n"
        
    await message.answer(text)
