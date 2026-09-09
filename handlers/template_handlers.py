import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)
router = Router()

def get_template_keyboard() -> InlineKeyboardMarkup:
    """Shablon turlari uchun inline klaviatura."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📰 Yangilik / E'lon", callback_data="tpl_news")],
            [InlineKeyboardButton(text="🎮 Viktorina / O'yin", callback_data="tpl_game")],
            [InlineKeyboardButton(text="📢 Reklama / Hamkorlik", callback_data="tpl_ad")],
            [InlineKeyboardButton(text="✨ Motivatsiya / Kun Fakti", callback_data="tpl_motivation")],
        ]
    )

@router.message(Command("template"))
async def cmd_template(message: Message):
    """Admin uchun tayyor shablonlar menyusi."""
    await message.answer(
        "📝 **Tayyor Post Shablonlari**\n\n"
        "Qanday turdagi post tayyorlamoqchisiz? Quyidagilardan birini tanlang:",
        reply_markup=get_template_keyboard()
    )

@router.callback_query(F.data.startswith("tpl_"))
async def process_template_callback(callback: CallbackQuery):
    """Tanlangan shablon turiga qarab tayyor matnni yuborish."""
    action = callback.data
    
    templates = {
        "tpl_news": (
            "📰 **[Asosiy Sarlavha Yozing]**\n\n"
            "Bugun [Sana/Vaqt] holatiga ko'ra, [Joy/Kompaniya] da muhim voqea yuz berdi. "
            "Bunga ko'ra, endilikda [Asosiy yangilik mazmuni 2-3 gapda].\n\n"
            "📌 **Nega bu muhim?**\n"
            "— [Birinchi sabab]\n"
            "— [Ikkinchi sabab]\n\n"
            "🔗 Manba: [Havola o'rnating]\n"
            "#yangilik #kun_mavzusi"
        ),
        "tpl_game": (
            "🎮 **KUN VIKTORINASI** 🧠\n\n"
            "Bugungi bilimingizni sinab ko'ramiz! Qani aytingchi:\n\n"
            "**[Qiziqarli savolni bu yerga yozing]**\n\n"
            "🅰️ [Birinchi variant]\n"
            "🅱️ [Ikkinchi variant]\n"
            "🅲️ [Uchinchi variant]\n"
            "🅳️ [To'rtinchi variant]\n\n"
            "👇 To'g'ri javobni pastdagi izohlarda yozib qoldiring! "
            "Birinchi bo'lib to'g'ri topgan obunachimizga +10 ball beriladi!"
        ),
        "tpl_ad": (
            "📢 **DIQQAT, FOYDALI TAVSIYA!**\n\n"
            "Siz ham [Muammo/Ehtiyojni yozing] qiynalyapsizmi? Unda bizda ajoyib yechim bor!\n\n"
            "🚀 **[Mahsulot/Kompaniya nomi]** sizga yordam beradi:\n"
            "✅ [1-Foydali xususiyat]\n"
            "✅ [2-Foydali xususiyat]\n"
            "✅ [3-Foydali xususiyat]\n\n"
            "🎁 Maxsus chegirma: Bizning kanal a'zolari uchun **[Chegirma foizi]%** chegirma mavjud!\n\n"
            "👇 Hoziroq quyidagi havolaga kiring va buyurtma bering:\n"
            "🔗 [Havolani shu yerga qo'ying]"
        ),
        "tpl_motivation": (
            "✨ **Xayrli tong, qadrli obunachilar!** ☀️\n\n"
            "Bugungi kuningiz a'lo kayfiyat va katta yutuqlar bilan o'tishini tilaymiz. "
            "Unutmang:\n\n"
            "_\"[Ilhomlantiruvchi iqtibos yoki maqolni shu yerga yozing]\"_\n\n"
            "📊 **Bugungi rejalaringiz qanday?** O'z maqsadlaringizni izohlarda yozib qoldiring, "
            "birgalikda erishamiz! 👇\n\n"
            "#motivatsiya #xayrlitong #maqsad"
        )
    }
    
    text = templates.get(action, "Kechirasiz, shablon topilmadi.")
    
    await callback.message.edit_text(
        f"✅ **Siz tanlagan shablon:**\n\n"
        f"Quyidagi matnni nusxalab, ichidagi qavslar `[...]` o'rnini to'ldiring va kanalga yuboring:\n\n"
        f"```text\n{text}\n```",
        parse_mode="Markdown"
    )
    await callback.answer()
