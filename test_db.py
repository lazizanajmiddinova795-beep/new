import asyncio
from database import Database

async def test():
    db = Database('sqlite+aiosqlite:///./data/news_bot.db')
    sess = await db.create_quiz_session('test_channel')
    print(f'SESSION ID: {sess.id}')
    await db.dispose()

asyncio.run(test())
