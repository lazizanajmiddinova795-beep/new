import asyncio
from aiogram import Bot
from config import load_config
from database import Database
from ai_processor import AIProcessor
from games import run_daily_game
from video_fetcher import run_daily_video
from media_fetcher import run_media_post

async def main():
    config = load_config()
    db = Database(config.database_url)
    await db.create_tables()
    ai = AIProcessor(config)
    bot = Bot(token=config.bot_token)
    
    print("Testing Daily Game...")
    await run_daily_game(bot, db, ai)
    
    print("Testing Daily Video...")
    await run_daily_video(bot, db, ai)
    
    print("Testing Media Post...")
    await run_media_post(bot, db, ai)
    
    await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
