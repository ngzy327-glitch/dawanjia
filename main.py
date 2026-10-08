import asyncio
import os
import logging
import re
import urllib.request
import urllib.parse
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError

logging.basicConfig(level=logging.CRITICAL)
for name in logging.root.manager.loggerDict:
    logging.getLogger(name).setLevel(logging.CRITICAL)
logging.getLogger('telethon').setLevel(logging.CRITICAL)

# ========== 环境变量 ==========
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
SESSION_STRING = (os.environ.get("SESSION_STRING", "") or "").strip()
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
MY_CHAT_ID = int(os.environ.get("MY_CHAT_ID", 0))

TARGET_USERNAMES = [u.strip().lower().lstrip('@')
                    for u in os.environ.get("TARGET_USERNAMES", "").split(",")
                    if u.strip()]
# =============================

missing = []
if not API_ID: missing.append("API_ID")
if not API_HASH: missing.append("API_HASH")
if not SESSION_STRING: missing.append("SESSION_STRING")
if not BOT_TOKEN: missing.append("BOT_TOKEN")
if not MY_CHAT_ID: missing.append("MY_CHAT_ID")
if not TARGET_USERNAMES: missing.append("TARGET_USERNAMES")
if missing:
    print(f"❌ 缺少环境变量: {', '.join(missing)}")
    exit(1)

client = TelegramClient(
    StringSession(SESSION_STRING),
    API_ID, API_HASH,
    connection_retries=5,
    retry_delay=5,
    auto_reconnect=True,
    request_retries=3,
    flood_sleep_threshold=86400,
    sequential_updates=False,
)

# 全局缓存：用户名 -> 用户ID
USERNAME_TO_ID = {}
ID_TO_USERNAME = {}

def clean_text(text):
    if not text: return ""
    return re.sub(r'[\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff\u00a0]', '', text).strip()

async def send_tg(message):
    safe = urllib.parse.quote(message, encoding='utf-8')
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage?chat_id={MY_CHAT_ID}&text={safe}"
    req = urllib.request.Request(url, method='GET')
    try:
        def _send():
            with urllib.request.urlopen(req, timeout=10) as resp:
                pass
        await asyncio.to_thread(_send)
    except Exception as e:
        print(f"[推送失败] {e}")

@client.on(events.NewMessage(incoming=True))
async def handler(event):
    if not event.is_group:
        return

    if event.sender_id not in ID_TO_USERNAME:
        return

    try:
        sender = await event.get_sender()
    except Exception:
        return
    if sender is None:
        return

    username = ID_TO_USERNAME.get(event.sender_id, "未知")
    first_name = getattr(sender, 'first_name', '') or ''
    last_name = getattr(sender, 'last_name', '') or ''
    full_name = (first_name + ' ' + last_name).strip() or '未知用户'
    username_str = f"@{username}" if username else "无用户名"

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

    await send_tg(msg)

async def resolve_usernames():
    """启动时把用户名解析为 ID，只调用一次 API"""
    print(f"[预热] 解析 {len(TARGET_USERNAMES)} 个用户名...")
    for username in TARGET_USERNAMES:
        try:
            entity = await client.get_entity(username)
            USERNAME_TO_ID[username] = entity.id
            ID_TO_USERNAME[entity.id] = username
            print(f"  ✓ @{username} -> {entity.id}")
        except Exception as e:
            print(f"  ✗ @{username} 解析失败: {e}")

async def main():
    try:
        await client.start(phone=lambda: "")
        print(f'[启动] SESSION_STRING 长度: {len(SESSION_STRING)}')
        await resolve_usernames()
        print(f'[运行中] 监听 {len(ID_TO_USERNAME)} 个目标用户，推送到 {MY_CHAT_ID}')
        await client.run_until_disconnected()
    except FloodWaitError as e:
        print(f'[限流] 需等待 {e.seconds} 秒...')
        await asyncio.sleep(e.seconds)
        await main()
    except Exception as e:
        print(f'[崩溃] {type(e).__name__}: {e}')
        await asyncio.sleep(10)
        await main()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
