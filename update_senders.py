import os
import re

files_to_update = ['challenges.py', 'emotional_posts.py', 'recommendations.py', 'video_fetcher.py']

for filename in files_to_update:
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()

    # Add import
    if 'from broadcaster import safe_send_message' not in content:
        content = content.replace('from database import Database', 'from database import Database\nfrom broadcaster import safe_send_message')

    # Replace the loop try/except block
    try_block_pattern = r'    for ch in target_channels:\n        try:\n            message = await bot\.send_message\(\n(.*?)\n            \)\n            logger\.info\("Yuborildi: %s", ch\.channel_id\)\n        except Exception as e:\n.*?logger\.error\("Plain text xato: %s", retry_err\)'
    
    def repl(m):
        inner = m.group(1)
        # inner has chat_id=ch.channel_id, etc
        return f"""    for ch in target_channels:
        success = await safe_send_message(
            bot=bot,
{inner}
        )
        if success:
            logger.info("Yuborildi: %s", ch.channel_id)
        else:
            logger.error("Yuborishda xato, oddiy matnda urinib ko'ramiz: %s", ch.channel_id)
            plain_text = final_text.replace("**", "").replace("*", "")
            await safe_send_message(
                bot=bot,
                chat_id=ch.channel_id,
                text=plain_text
            )"""

    content = re.sub(try_block_pattern, repl, content, flags=re.DOTALL)
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)

print("Updates applied to remaining files.")
