import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    LabeledPrice,
    PreCheckoutQuery,
    ContentType,
)
from database import Database

logger = logging.getLogger(__name__)
router = Router()
db: Database = None
PROVIDER_TOKEN = "TEST_PROVIDER_TOKEN"  # Bu yerni keyinroq .env dan olamiz

def set_vip_db(database: Database):
    global db
    db = database

@router.message(Command("vip"))
async def cmd_vip(message: Message):
    """VIP obuna xarid qilish."""
    # Narx (10 000 so'm) = 1000000 tiyin
    prices = [LabeledPrice(label="VIP Obuna (1 oy)", amount=1000000)]
    
    await message.answer_invoice(
        title="🌟 VIP Obuna (SMM Tizim)",
        description="Premium kanallardagi barcha ma'lumotlarni o'qish uchun 1 oylik VIP obuna xarid qiling.",
        payload="vip_1_month",
        provider_token=PROVIDER_TOKEN,
        currency="UZS",
        prices=prices,
        start_parameter="vip-subscription",
        need_name=False,
        need_phone_number=False,
        need_email=False,
        need_shipping_address=False,
        is_flexible=False
    )

@router.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    """To'lovni tasdiqlash (pre-checkout)."""
    await pre_checkout_query.answer(ok=True)

@router.message(F.successful_payment)
async def process_successful_payment(message: Message):
    """To'lov muvaffaqiyatli amalga oshirildi."""
    if message.successful_payment.invoice_payload == "vip_1_month":
        # 30 kunlik VIP berish
        await db.set_user_vip(message.from_user.id, 30)
        
        await message.answer(
            "🎉 **Tabriklaymiz! Siz VIP obuna xarid qildingiz!**\n\n"
            "Endi barcha kanallardagi ma'lumotlarni to'liq o'qiy olasiz."
        )
        logger.info("Foydalanuvchi %s VIP sotib oldi.", message.from_user.id)
