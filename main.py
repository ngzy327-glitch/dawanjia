import asyncio
import os
import logging
import re
import urllib.request
import urllib.parse
from telethon import TelegramClient, events
from telethon.sessions import StringSession

logging.basicConfig(level=logging.CRITICAL)
for name in logging.root.manager.loggerDict:
    logging.getLogger(name).setLevel(logging.CRITICAL)
logging.getLogger('telethon').setLevel(logging.CRITICAL)

# ========== 环境变量 ==========
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
TARGET_GROUP_ID = int(os.environ.get("TARGET_GROUP_ID", 0))

TARGET_USERNAMES = [u.strip().lower().lstrip('@')
                    for u in os.environ.get("TARGET_USERNAMES", "").split(",")
                    if u.strip()]
# =============================

if not all([API_ID, API_HASH, SESSION_STRING, BOT_TOKEN, TARGET_GROUP_ID]):
    print("❌ 缺少环境变量")
    exit(1)

client = TelegramClient(
    StringSession(SESSION_STRING),
    API_ID, API_HASH,
    connection_retries=99, retry_delay=0,
    auto_reconnect=True, request_retries=5,
    flood_sleep_threshold=86400, sequential_updates=False,
)

def clean_text(text):
    if not text: return ""
    return re.sub(r'[\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff\u00a0]', '', text).strip()

async def send_to_group(message):
    safe = urllib.parse.quote(message, encoding='utf-8')
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage?chat_id={TARGET_GROUP_ID}&text={safe}"
    req = urllib.request.Request(url, method='GET')
    try:
        def _send():
            with urllib.request.urlopen(req, timeout=10) as resp:
                pass
        await asyncio.to_thread(_send)
    except Exception as e:
        print(f"[播报失败] {e}")

@client.on(events.NewMessage(incoming=True))
async def handler(event):
    if not event.is_group:
        return

    try:
        sender = await event.get_sender()
    except Exception:
        return

    if sender is None:
        return

    sender_username = (getattr(sender, 'username', None) or '').lower()
    if sender_username not in TARGET_USERNAMES:
        return

    first_name = getattr(sender, 'first_name', '') or ''
    last_name = getattr(sender, 'last_name', '') or ''
    full_name = (first_name + ' ' + last_name).strip() or '未知用户'
    username_str = f"@{sender_username}" if sender_username else "无用户名"

    try:
        chat = await event.get_chat()
        chat_title = getattr(chat, 'title', '未知群组')
        raw_id = str(event.chat_id).replace('-100', '')
        msg_link = f"https://t.me/c/{raw_id}/{event.message.id}"
    except Exception:
        chat_title = '未知群组'
        msg_link = '无法获取链接'

    content = clean_text(event.raw_text) or '[非文本消息]'

    msg = (
        f"👤 发送者：{full_name}\n"
        f"🔗 用户名：{username_str}\n"
        f"📍 群组：{chat_title}\n"
        f"💬 内容：\n{content}\n"
        f"🔗 链接：{msg_link}"
    )

    await send_to_group(msg)

async def main():
    await client.start()
    print(f'[运行中] 监听所有群，目标用户：{TARGET_USERNAMES}')
    print(f'[播报目标] 群 {TARGET_GROUP_ID}')
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
