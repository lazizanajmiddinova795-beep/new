import asyncio
import logging
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import Database, QuizSession
from ai_processor import AIProcessor

logger = logging.getLogger(__name__)
router = Router()

db: Database = None
ai: AIProcessor = None
bot_instance: Bot = None

def set_game_dependencies(database: Database, ai_processor: AIProcessor, bot: Bot):
    global db, ai, bot_instance
    db = database
    ai = ai_processor
    bot_instance = bot

SYSTEM_PROMPT = """Siz qiziqarli viktorina va mantiqiy savollar tuzuvchi ekspertsiz.
QOIDALAR:
1. Savol va uning 4 ta varianti bo'lsin.
2. Har bir savol O'zbek tilida qiziqarli qilib yozilsin.
3. Chiqish formati faqat JSON bo'lishi shart! (Hech qanday qo'shimcha matnlarsiz).
4. JSON strukturasi:
{
  "question": "Savol matni va emojilar",
  "options": {
    "A": "Birinchi variant",
    "B": "Ikkinchi variant",
    "C": "Uchinchi variant",
    "D": "To'rtinchi variant"
  },
  "correct": "A" (yoki B, C, D)
}
"""

@router.message(Command("start_game"))
async def cmd_start_game(message: Message):
    """Admin o'yinni boshlaydi."""
    channels = await db.get_user_channels(message.from_user.id)
    if not channels:
        await message.answer("Sizda ro'yxatdan o'tgan kanallar yo'q.")
        return

    # Faqat birinchi kanalida o'yinni boshlaymiz
    target_channel = channels[0].channel_id
    
    await message.answer(f"O'yin {target_channel} kanalida boshlanmoqda! 5 ta savol tayyorlanadi...")
    
    # Orqa fonda o'yinni yurgizish
    asyncio.create_task(run_quiz_cycle(target_channel, total_questions=5))


async def run_quiz_cycle(channel_id: str, total_questions: int = 5):
    """5 ta savolni ketma-ket (masalan, har 30 soniyada) kanalga yuborish."""
    import json
    
    # Yangi sessiya yaratish
    session = await db.create_quiz_session(channel_id, total_questions)
    
    for i in range(1, total_questions + 1):
        # AI dan savol so'rash
        prompt = f"Qiyinlik darajasi o'rtacha bo'lgan {i}-savolni yarating."
        ai_response = await ai.generate_custom_text(SYSTEM_PROMPT, prompt)
        
        try:
            # Markdown code blocklarni tozalash (agar AI qo'shgan bo'lsa)
            clean_json = ai_response.replace("```json", "").replace("```", "").strip()
            data = json.loads(clean_json)
            
            question = data.get("question", "Noma'lum savol")
            options = data.get("options", {})
            correct = data.get("correct", "A")
            
            # Bazani yangilash (joriy savol)
            await db.update_quiz_session(session.id, current_question_index=i, correct_option=correct, is_active=True)
            
            # Kanalga xabar jo'natish
            text = f"🧩 **Savol {i}/{total_questions}**\n\n{question}\n\n"
            for k, v in options.items():
                text += f"**{k})** {v}\n"
                
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="A", callback_data=f"quiz_{session.id}_{i}_A"),
                    InlineKeyboardButton(text="B", callback_data=f"quiz_{session.id}_{i}_B"),
                    InlineKeyboardButton(text="C", callback_data=f"quiz_{session.id}_{i}_C"),
                    InlineKeyboardButton(text="D", callback_data=f"quiz_{session.id}_{i}_D")
                ]
            ])
            
            await bot_instance.send_message(
                chat_id=channel_id,
                text=text,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
            
            # Keyingi savolgacha kutish (masalan 20 soniya, real loyihada ko'proq bo'lishi mumkin)
            await asyncio.sleep(20)
            
        except Exception as e:
            logger.error("Savol generatsiyasida xato: %s", e)
            await bot_instance.send_message(chat_id=channel_id, text="Savol tayyorlashda xatolik yuz berdi. O'yin davom etadi...")
            await asyncio.sleep(10)
            
    # O'yin tugadi. Sessiyani nofaol qilish va reytingni chiqarish.
    await db.update_quiz_session(session.id, current_question_index=total_questions, correct_option="", is_active=False)
    await send_leaderboard(channel_id, session.id)


async def send_leaderboard(channel_id: str, session_id: int):
    """Reytingni kanalga yuborish."""
    leaderboard = await db.get_quiz_leaderboard(session_id)
    
    if not leaderboard:
        await bot_instance.send_message(chat_id=channel_id, text="🏆 **Bugungi O'yin Natijalari**\n\nHech kim savollarga to'g'ri javob topa olmadi yoki ishtirok etmadi 😢")
        return
        
    medals = ["🥇", "🥈", "🥉", "🏅", "🏅", "🏅", "🏅", "🏅", "🏅", "🏅"]
    text = "🏆 **Bugungi O'yin Natijalari va Reytingi**\n\n"
    
    for idx, (username, score) in enumerate(leaderboard):
        medal = medals[idx] if idx < len(medals) else "🎗"
        text += f"{idx + 1}. {medal} {username} — {score}/5 ball\n"
        
    await bot_instance.send_message(chat_id=channel_id, text=text, parse_mode="Markdown")


@router.callback_query(F.data.startswith("quiz_"))
async def process_quiz_answer(callback: CallbackQuery):
    """Foydalanuvchi variantlardan birini bosganda ishlaydi."""
    # Data formati: quiz_{session_id}_{question_index}_{option}
    parts = callback.data.split("_")
    if len(parts) != 4:
        await callback.answer("Xato format.", show_alert=True)
        return
        
    _, session_id_str, q_index_str, user_option = parts
    session_id = int(session_id_str)
    q_index = int(q_index_str)
    
    # Sessiyani tekshirish
    async with db.get_session() as session_db:
        from sqlalchemy import select
        res = await session_db.execute(select(QuizSession).where(QuizSession.id == session_id))
        quiz_session = res.scalar_one_or_none()
        
        if not quiz_session:
            await callback.answer("Bu o'yin allaqachon tugagan yoki topilmadi.", show_alert=True)
            return
            
        if not quiz_session.is_active or quiz_session.current_question_index != q_index:
            await callback.answer("Bu savolning vaqti tugagan! Keyingi savolni kuting.", show_alert=True)
            return
            
        # Javobni tekshirish
        is_correct = (user_option == quiz_session.current_correct_option)
        
    # Bazaga yozish
    username = f"@{callback.from_user.username}" if callback.from_user.username else callback.from_user.first_name
    success = await db.record_quiz_answer(
        session_id=session_id,
        telegram_id=callback.from_user.id,
        username=username,
        question_index=q_index,
        is_correct=is_correct
    )
    
    if success:
        if is_correct:
            await callback.answer("✅ To'g'ri javob! +1 ball", show_alert=True)
        else:
            await callback.answer("❌ Noto'g'ri javob!", show_alert=True)
    else:
        await callback.answer("Siz bu savolga allaqachon javob bergansiz!", show_alert=True)
