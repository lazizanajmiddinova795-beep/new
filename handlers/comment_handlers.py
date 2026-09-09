import logging
import random
from aiogram import Router, F
from aiogram.types import Message, ReactionTypeEmoji
from ai_processor import AIProcessor

logger = logging.getLogger(__name__)
router = Router()
ai_proc: AIProcessor = None

def set_comment_dependencies(ai_processor: AIProcessor):
    global ai_proc
    ai_proc = ai_processor

@router.message(F.chat.type.in_({"supergroup", "group"}))
async def handle_group_message(message: Message):
    """Guruhdagi/Muhokamadagi xabarlarni ushlash."""
    if not message.text:
        return

    # 1. Agar xabar to'g'ridan-to'g'ri kanaldan kelgan post bo'lsa (avtomatik forward qilingan)
    if message.is_automatic_forward or (message.sender_chat and message.sender_chat.type == "channel"):
        try:
            reactions = ["👍", "🔥", "👏", "❤", "🎉", "🤩"]
            reaction = random.choice(reactions)
            await message.bot.set_message_reaction(
                chat_id=message.chat.id,
                message_id=message.message_id,
                reaction=[ReactionTypeEmoji(type="emoji", emoji=reaction)]
            )
            logger.info("Yangi postga reaksiya qoldirildi: %s", reaction)
        except Exception as e:
            logger.warning("Reaksiya qoldirishda xato: %s", e)
        return

    # 2. AI Chatbot muhokamada javob berishi
    # Agar foydalanuvchi xabarida "?" qatnashsa yozamiz
    if "?" in message.text or (message.reply_to_message and message.reply_to_message.from_user.id == message.bot.id):
        try:
            sys_prompt = (
                "Siz ushbu guruhning faol va do'stona SMM menejerisiz. "
                "Odamlarning fikrlariga va savollariga qisqa (1-2 gap) qiziqarli javob bering."
            )
            ai_reply = await ai_proc.generate_custom_text(sys_prompt, message.text)
            if ai_reply:
                await message.reply(ai_reply)
        except Exception as e:
            logger.error("AI comment javobida xato: %s", e)
