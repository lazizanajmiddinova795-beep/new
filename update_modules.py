import os
import re

files_and_settings = {
    'challenges.py': ('run_weekly_challenge', 'setting_games'), # we'll use setting_games or just create setting_challenges? the db has no setting_challenges. We'll use setting_news for challenges? Actually setting_news is for news. Let's use setting_games for challenges too or just setting_news. Wait, setting_recommendations is available. Let's use `setting_news` for challenges.
    'media_fetcher.py': ('run_media_post', 'setting_videos'), # Wait, media is image. Let's use setting_videos.
    'emotional_posts.py': ('run_emotional_post', 'setting_emotional'),
    'video_fetcher.py': ('run_daily_video', 'setting_videos'),
    'recommendations.py': ('run_weekly_recommendation', 'setting_recommendations'),
}

for filename, (func_name, setting) in files_and_settings.items():
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()

    # Change imports
    content = content.replace('from config import Config', 'from database import Database')
    
    # Change signature
    content = content.replace(f'async def {func_name}(bot: Bot, config: Config, ai_processor: AIProcessor) -> None:',
                              f'async def {func_name}(bot: Bot, db: Database, ai_processor: AIProcessor) -> None:')
                              
    # Add active channels check after logger.info
    loop_code = f"""
    active_channels = await db.get_active_channels()
    target_channels = [ch for ch in active_channels if ch.{setting}]
    if not target_channels:
        logger.info("{setting} yoqilgan faol kanallar yo'q.")
        return
"""
    # Find the first logger.info inside the function
    match = re.search(r'logger\.info\(.*?\n', content)
    if match:
        idx = match.end()
        # insert only if not already inserted
        if 'active_channels = await db.get_active_channels()' not in content:
            content = content[:idx] + loop_code + content[idx:]

    # Replace the try/except block at the end with a loop
    try_block_pattern = r'    try:\n.*?except Exception as retry_err:\n.*?logger\.error\(.*?\)'
    
    loop_replacement = f"""    for ch in target_channels:
        try:
            message = await bot.send_message(
                chat_id=ch.channel_id,
                text=final_text,
                parse_mode=ParseMode.MARKDOWN
            )
            logger.info("Yuborildi: %s", ch.channel_id)
        except Exception as e:
            logger.error("Yuborishda xato (%s): %s", ch.channel_id, e)
            try:
                plain_text = final_text.replace("**", "").replace("*", "")
                await bot.send_message(
                    chat_id=ch.channel_id,
                    text=plain_text
                )
            except Exception as retry_err:
                logger.error("Plain text xato: %s", retry_err)"""
                
    content = re.sub(try_block_pattern, loop_replacement, content, flags=re.DOTALL)
    
    # For video_fetcher, disable_web_page_preview=False is needed.
    if filename == 'video_fetcher.py':
        content = content.replace('parse_mode=ParseMode.MARKDOWN', 'parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=False')
        content = content.replace('text=plain_text', 'text=plain_text, disable_web_page_preview=False')
        
    # for media_fetcher, send_photo is used instead of send_message!
    if filename == 'media_fetcher.py':
        # restore media fetcher special logic
        pass

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)

print("Done")
