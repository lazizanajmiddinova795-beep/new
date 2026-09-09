import asyncio
from database import Database

async def main():
    db = Database("sqlite+aiosqlite:///./data/news_bot.db")
    await db.create_tables()
    user = await db.get_or_create_user(telegram_id=123456789, username="laziza_admin")
    await db.add_channel(telegram_id=123456789, channel_id="@NLMINI_12", channel_name="NLMINI_12")
    print("Muvaffaqiyatli!")

if __name__ == "__main__":
    asyncio.run(main())
