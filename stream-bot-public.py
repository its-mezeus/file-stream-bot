#!/usr/bin/env python3
"""
File To Link Bot - HTTP Downloads
Streams files from Telegram via HTTP
By Zeus ⚡
"""

import os
import asyncio
from dotenv import load_dotenv
load_dotenv()
from pathlib import Path
from datetime import datetime
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

# Config - Load from environment variables
API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
BOT_TOKEN = os.getenv('BOT_TOKEN', '')
SESSION_STRING = os.getenv('SESSION_STRING', '')
LOG_CHANNEL = int(os.getenv('LOG_CHANNEL', '0'))
PUBLIC_URL = os.getenv('PUBLIC_URL', 'http://localhost:8080')
PORT = int(os.getenv('PORT', 8080))
DOWNLOAD_DIR = Path(__file__).parent / 'downloads'

# Admin User IDs (comma-separated in env var)
ADMIN_IDS = [int(x) for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip().isdigit()]

# Validate required config
if not all([API_ID, API_HASH, BOT_TOKEN, SESSION_STRING, LOG_CHANNEL, ADMIN_IDS]):
    raise ValueError("Missing required environment variables! Check .env file or environment settings.")

# ==================== DATABASE ====================
try:
    from database import StreamBotDB
    db = StreamBotDB()
    USE_DATABASE = True
    print("✅ MongoDB connected!")
except Exception as e:
    print(f"⚠️ MongoDB not available: {e}")
    print("⚠️ Running WITHOUT database - data won't persist!")
    db = None
    USE_DATABASE = False

# Force Join Channels (add your channel usernames or IDs)
FORCE_CHANNELS = []  # Will be managed via commands

# Banned Users
BANNED_USERS = set()  # Will be managed via commands

# Maintenance Mode
maintenance = {
    'enabled': False,
    'resume_time': None  # datetime when bot auto-resumes, None = indefinite
}

# Link Expiry Settings (in seconds)
EXPIRY_OPTIONS = {
    '12h': 43200,
    '24h': 86400,
    '48h': 172800,
    '72h': 259200,
    '7d': 604800,
    'permanent': 0  # 0 = never expires
}
DEFAULT_EXPIRY = 86400  # 24 hours default
link_expiry = {'default': DEFAULT_EXPIRY}  # Will be loaded from DB

# Statistics
stats = {
    'total_users': set(),
    'total_files': 0,
    'total_downloads': 0,
    'files_today': 0,
    'links_today': 0,
    'downloads_today': 0,
    'bytes_today': 0,
    'start_date': datetime.now()
}

DOWNLOAD_DIR.mkdir(exist_ok=True)

# File mapping: hash -> {file_id, name, size, chat_id, message_id}
file_map = {}
user_cooldowns = {}  # user_id -> last file timestamp
pending_files = {}  # user_id -> message object (file waiting for force join)

# Bots
bot = Client("streambot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, max_concurrent_transmissions=10)
userbot = Client("stream_user", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING, max_concurrent_transmissions=10)

print("🤖 File To Link Bot")
print("⚡ HTTP Downloads via Cloudflare")
print(f"🌐 {PUBLIC_URL}")


async def check_user_joined(client, user_id):
    """Check if user joined all force channels"""
    not_joined = []
    
    for channel in FORCE_CHANNELS:
        try:
            member = await client.get_chat_member(channel, user_id)
            if member.status in ["left", "kicked"]:
                not_joined.append(channel)
        except:
            not_joined.append(channel)
    
    return not_joined


@bot.on_message(filters.command("addchannel") & filters.user(ADMIN_IDS))
async def add_channel(client, message):
    """Add force join channel - Admin only"""
    try:
        if len(message.command) < 2:
            await message.reply("❌ <b>Usage:</b> <code>/addchannel @channelname</code>", parse_mode=enums.ParseMode.HTML)
            return
        
        channel = message.command[1]
        if not channel.startswith("@"):
            channel = "@" + channel
        
        # Check if channel exists
        try:
            chat = await client.get_chat(channel)
        except:
            await message.reply(f"❌ <b>Channel not found:</b> <code>{channel}</code>", parse_mode=enums.ParseMode.HTML)
            return
        
        if channel in FORCE_CHANNELS:
            await message.reply(f"⚠️ <b>Channel already added:</b> <code>{channel}</code>", parse_mode=enums.ParseMode.HTML)
            return
        
        FORCE_CHANNELS.append(channel)
        
        # Save to database
        if USE_DATABASE and db:
            db.add_force_channel(chat.id, channel, chat.title, message.from_user.id)
        
        text = f"""✅ <b>Channel Added!</b>

📢 <b>Channel:</b> <code>{channel}</code>
📝 <b>Name:</b> {chat.title}

<b>Total Channels:</b> {len(FORCE_CHANNELS)}

━━━━━━━━━━━━
💾 <i>Saved to database</i>"""
        
        await message.reply(text, parse_mode=enums.ParseMode.HTML)
        
    except Exception as e:
        await message.reply(f"❌ <b>Error:</b> {str(e)}", parse_mode=enums.ParseMode.HTML)


@bot.on_message(filters.command("removechannel") & filters.user(ADMIN_IDS))
async def remove_channel(client, message):
    """Remove force join channel - Admin only"""
    try:
        if len(message.command) < 2:
            await message.reply("❌ <b>Usage:</b> <code>/removechannel @channelname</code>", parse_mode=enums.ParseMode.HTML)
            return
        
        channel = message.command[1]
        if not channel.startswith("@"):
            channel = "@" + channel
        
        if channel not in FORCE_CHANNELS:
            await message.reply(f"⚠️ <b>Channel not in list:</b> <code>{channel}</code>", parse_mode=enums.ParseMode.HTML)
            return
        
        FORCE_CHANNELS.remove(channel)
        
        # Remove from database
        if USE_DATABASE and db:
            try:
                chat = await client.get_chat(channel)
                db.remove_force_channel(chat.id)
            except:
                pass
        
        text = f"""✅ <b>Channel Removed!</b>

📢 <b>Channel:</b> <code>{channel}</code>

<b>Remaining Channels:</b> {len(FORCE_CHANNELS)}

━━━━━━━━━━━━
💾 <i>Removed from database</i>"""
        
        await message.reply(text, parse_mode=enums.ParseMode.HTML)
        
    except Exception as e:
        await message.reply(f"❌ <b>Error:</b> {str(e)}", parse_mode=enums.ParseMode.HTML)


@bot.on_message(filters.command("listchannels") & filters.user(ADMIN_IDS))
async def list_channels(client, message):
    """List all force join channels - Admin only"""
    if not FORCE_CHANNELS:
        await message.reply("📋 <b>No force join channels configured</b>\n\nUse /addchannel to add one!", parse_mode=enums.ParseMode.HTML)
        return
    
    text = f"📋 <b>FORCE JOIN CHANNELS</b>\n\n<b>Total:</b> {len(FORCE_CHANNELS)}\n\n"
    
    for i, channel in enumerate(FORCE_CHANNELS, 1):
        text += f"{i}. <code>{channel}</code>\n"
    
    text += "\n━━━━━━━━━━━━\n"
    text += "➕ /addchannel @name\n"
    text += "➖ /removechannel @name\n"
    text += "🗑️ /clearall"
    
    await message.reply(text, parse_mode=enums.ParseMode.HTML)


@bot.on_message(filters.command("clearall") & filters.user(ADMIN_IDS))
async def clear_all(client, message):
    """Clear all force join channels - Admin only"""
    if not FORCE_CHANNELS:
        await message.reply("⚠️ <b>No channels to clear</b>", parse_mode=enums.ParseMode.HTML)
        return
    
    count = len(FORCE_CHANNELS)
    
    # Clear from database
    if USE_DATABASE and db:
        for channel in FORCE_CHANNELS:
            try:
                chat = await client.get_chat(channel)
                db.remove_force_channel(chat.id)
            except:
                pass
    
    FORCE_CHANNELS.clear()
    
    await message.reply(f"✅ <b>Cleared {count} channel(s)</b>\n\n<i>Force join disabled until you add new channels</i>\n💾 <i>Database updated</i>", parse_mode=enums.ParseMode.HTML)


@bot.on_message(filters.command("ban") & filters.user(ADMIN_IDS))
async def ban_user(client, message):
    """Ban user - Admin only"""
    try:
        if len(message.command) < 2:
            await message.reply("❌ <b>Usage:</b> <code>/ban user_id</code> or reply to user's message", parse_mode=enums.ParseMode.HTML)
            return
        
        # Check if replying to a message
        if message.reply_to_message:
            user_id = message.reply_to_message.from_user.id
            user_name = message.reply_to_message.from_user.first_name
        else:
            user_id = int(message.command[1])
            try:
                user = await client.get_users(user_id)
                user_name = user.first_name
            except:
                user_name = "Unknown"
        
        if user_id in ADMIN_IDS:
            await message.reply("❌ <b>Cannot ban admin!</b>", parse_mode=enums.ParseMode.HTML)
            return
        
        if user_id in BANNED_USERS:
            await message.reply(f"⚠️ <b>User already banned:</b> {user_name} (<code>{user_id}</code>)", parse_mode=enums.ParseMode.HTML)
            return
        
        BANNED_USERS.add(user_id)
        
        # Save to database
        if USE_DATABASE and db:
            db.ban_user(user_id, admin_id=message.from_user.id)
        
        text = f"""🚫 <b>USER BANNED!</b>

👤 <b>Name:</b> {user_name}
🆔 <b>ID:</b> <code>{user_id}</code>

<b>Total Banned:</b> {len(BANNED_USERS)}

━━━━━━━━━━━━
💾 <i>Saved to database</i>
Use /unban {user_id} to unban"""
        
        await message.reply(text, parse_mode=enums.ParseMode.HTML)
        
    except Exception as e:
        await message.reply(f"❌ <b>Error:</b> {str(e)}", parse_mode=enums.ParseMode.HTML)


@bot.on_message(filters.command("unban") & filters.user(ADMIN_IDS))
async def unban_user(client, message):
    """Unban user - Admin only"""
    try:
        if len(message.command) < 2:
            await message.reply("❌ <b>Usage:</b> <code>/unban user_id</code>", parse_mode=enums.ParseMode.HTML)
            return
        
        user_id = int(message.command[1])
        
        if user_id not in BANNED_USERS:
            await message.reply(f"⚠️ <b>User not banned:</b> <code>{user_id}</code>", parse_mode=enums.ParseMode.HTML)
            return
        
        BANNED_USERS.remove(user_id)
        
        # Update database
        if USE_DATABASE and db:
            db.unban_user(user_id)
        
        try:
            user = await client.get_users(user_id)
            user_name = user.first_name
        except:
            user_name = "Unknown"
        
        text = f"""✅ <b>USER UNBANNED!</b>

👤 <b>Name:</b> {user_name}
🆔 <b>ID:</b> <code>{user_id}</code>

<b>Remaining Banned:</b> {len(BANNED_USERS)}

━━━━━━━━━━━━
💾 <i>Database updated</i>"""
        
        await message.reply(text, parse_mode=enums.ParseMode.HTML)
        
    except Exception as e:
        await message.reply(f"❌ <b>Error:</b> {str(e)}", parse_mode=enums.ParseMode.HTML)


@bot.on_message(filters.command("banlist") & filters.user(ADMIN_IDS))
async def ban_list(client, message):
    """Show banned users - Admin only"""
    if not BANNED_USERS:
        await message.reply("📋 <b>No banned users</b>\n\nUse /ban to ban someone!", parse_mode=enums.ParseMode.HTML)
        return
    
    text = f"🚫 <b>BANNED USERS</b>\n\n<b>Total:</b> {len(BANNED_USERS)}\n\n"
    
    for i, user_id in enumerate(BANNED_USERS, 1):
        try:
            user = await client.get_users(user_id)
            name = user.first_name
        except:
            name = "Unknown"
        
        text += f"{i}. {name} - <code>{user_id}</code>\n"
    
    text += "\n━━━━━━━━━━━━\n"
    text += "🚫 /ban user_id\n"
    text += "✅ /unban user_id"
    
    await message.reply(text, parse_mode=enums.ParseMode.HTML)


@bot.on_message(filters.command("sendto") & filters.user(ADMIN_IDS))
async def send_to_user(client, message):
    """Send a message to a specific user by ID - Admin only"""
    if len(message.command) < 2:
        await message.reply(
            "❌ <b>Usage:</b>\n\n"
            "<code>/sendto user_id Your message here</code>\n"
            "Or reply to a message with <code>/sendto user_id</code>",
            parse_mode=enums.ParseMode.HTML
        )
        return

    try:
        target_id = int(message.command[1])
    except ValueError:
        await message.reply("❌ <b>Invalid user ID!</b>", parse_mode=enums.ParseMode.HTML)
        return

    # Get message content
    if len(message.command) >= 3:
        # Text from command
        msg_text = message.text.split(None, 2)[2]
        formatted = (
            f"📩 <b><i>Message from Admin</i></b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<b><i>{msg_text}</i></b>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ @Filetolinkzeus_bot"
        )
        try:
            await client.send_message(target_id, formatted, parse_mode=enums.ParseMode.HTML)
            try:
                user = await client.get_users(target_id)
                name = user.first_name
            except:
                name = "Unknown"
            await message.reply(f"✅ <b>Message sent to {name} (<code>{target_id}</code>)</b>", parse_mode=enums.ParseMode.HTML)
        except Exception as e:
            if "blocked" in str(e).lower():
                await message.reply(f"❌ <b>User blocked the bot!</b>", parse_mode=enums.ParseMode.HTML)
            else:
                await message.reply(f"❌ <b>Failed:</b> {str(e)[:100]}", parse_mode=enums.ParseMode.HTML)

    elif message.reply_to_message:
        # Forward replied message with formatting
        reply = message.reply_to_message
        try:
            reply_text = reply.text or reply.caption or ""
            if reply_text:
                # Send as formatted text
                formatted = (
                    f"📩 <b><i>Message from Admin</i></b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"<b><i>{reply_text}</i></b>\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"⚡ @Filetolinkzeus_bot"
                )
                # If it has media, send media with formatted caption
                if reply.photo or reply.video or reply.document or reply.audio:
                    await reply.copy(target_id, caption=formatted, parse_mode=enums.ParseMode.HTML)
                else:
                    await client.send_message(target_id, formatted, parse_mode=enums.ParseMode.HTML)
            else:
                # No text, just forward media as-is
                await reply.copy(target_id)

            try:
                user = await client.get_users(target_id)
                name = user.first_name
            except:
                name = "Unknown"
            await message.reply(f"✅ <b>Message sent to {name} (<code>{target_id}</code>)</b>", parse_mode=enums.ParseMode.HTML)
        except Exception as e:
            if "blocked" in str(e).lower():
                await message.reply(f"❌ <b>User blocked the bot!</b>", parse_mode=enums.ParseMode.HTML)
            else:
                await message.reply(f"❌ <b>Failed:</b> {str(e)[:100]}", parse_mode=enums.ParseMode.HTML)
    else:
        await message.reply(
            "❌ <b>No message to send!</b>\n\n"
            "<code>/sendto user_id Your message</code>\n"
            "Or reply to a message with <code>/sendto user_id</code>",
            parse_mode=enums.ParseMode.HTML
        )


@bot.on_message(filters.command("setexpiry") & filters.user(ADMIN_IDS))
async def set_expiry(client, message):
    """Set default link expiry time - Admin only"""
    try:
        if len(message.command) < 2:
            current = link_expiry['default']
            if current == 0:
                current_display = "♾️ Permanent"
            elif current >= 86400:
                current_display = f"{current // 86400}d"
            else:
                current_display = f"{current // 3600}h"
            
            text = f"""⏰ <b>LINK EXPIRY SETTINGS</b>

📌 <b>Current Default:</b> {current_display}

<b>Usage:</b> <code>/setexpiry &lt;time&gt;</code>

<b>Options:</b>
• <code>/setexpiry 12h</code> — 12 hours
• <code>/setexpiry 24h</code> — 24 hours
• <code>/setexpiry 48h</code> — 48 hours
• <code>/setexpiry 72h</code> — 72 hours
• <code>/setexpiry 7d</code> — 7 days
• <code>/setexpiry permanent</code> — Never expire

━━━━━━━━━━━━
⚡ <i>Changes apply to new links only</i>"""
            await message.reply(text, parse_mode=enums.ParseMode.HTML)
            return
        
        option = message.command[1].lower()
        
        if option not in EXPIRY_OPTIONS:
            await message.reply(
                "❌ <b>Invalid option!</b>\n\nUse: <code>12h, 24h, 48h, 72h, 7d, permanent</code>",
                parse_mode=enums.ParseMode.HTML
            )
            return
        
        link_expiry['default'] = EXPIRY_OPTIONS[option]
        
        # Save to database
        if USE_DATABASE and db:
            db.db['settings'].update_one(
                {'key': 'link_expiry'},
                {'$set': {'key': 'link_expiry', 'value': EXPIRY_OPTIONS[option]}},
                upsert=True
            )
        
        display = "♾️ Permanent (never expire)" if option == 'permanent' else option
        
        text = f"""✅ <b>EXPIRY UPDATED!</b>

⏰ <b>New Default:</b> {display}

<i>All new links will use this expiry time.</i>
<i>Existing links are not affected.</i>

━━━━━━━━━━━━
💾 <i>Saved to database</i>"""
        
        await message.reply(text, parse_mode=enums.ParseMode.HTML)
        
    except Exception as e:
        await message.reply(f"❌ <b>Error:</b> {str(e)}", parse_mode=enums.ParseMode.HTML)


@bot.on_message(filters.command("feedback"))
async def feedback(client, message):
    """Collect feedback from users and forward to admins"""
    user = message.from_user

    # Get feedback text from command args or replied message
    if len(message.command) >= 2:
        feedback_text = message.text.split(None, 1)[1]
    elif message.reply_to_message:
        feedback_text = message.reply_to_message.text or message.reply_to_message.caption or ""
    else:
        await message.reply(
            "📝 <b>Send your feedback:</b>\n\n"
            "<code>/feedback Your message here</code>\n"
            "Or reply to a message with <code>/feedback</code>\n\n"
            "<i>Your feedback will be sent to the admin. Thank you!</i>",
            parse_mode=enums.ParseMode.HTML
        )
        return

    if not feedback_text.strip():
        await message.reply("⚠️ <b>Empty feedback!</b> Please write something.", parse_mode=enums.ParseMode.HTML)
        return

    # Forward to all admins
    feedback_msg = f"""📬 <b>NEW FEEDBACK!</b>
━━━━━━━━━━━━━━━━━━━━━━━━━

👤 <b>From:</b> <a href="tg://user?id={user.id}">{user.first_name}</a>
🆔 <b>ID:</b> <code>{user.id}</code>"""

    if user.username:
        feedback_msg += f"\n🔗 <b>Username:</b> @{user.username}"

    feedback_msg += f"""

💬 <b>Message:</b>
<i>{feedback_text}</i>

━━━━━━━━━━━━━━━━━━━━━━━━━
⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC"""

    sent = False
    for admin_id in ADMIN_IDS:
        try:
            await client.send_message(admin_id, feedback_msg, parse_mode=enums.ParseMode.HTML)
            sent = True
        except:
            pass

    # Also send to log channel
    try:
        await client.send_message(LOG_CHANNEL, feedback_msg, parse_mode=enums.ParseMode.HTML)
    except:
        pass

    if sent:
        await message.reply(
            "✅ <b>Feedback sent!</b>\n\n<i>Thank you for your feedback. The admin will review it.</i>",
            parse_mode=enums.ParseMode.HTML
        )
    else:
        await message.reply(
            "❌ <b>Failed to send feedback.</b>\n\n<i>Please try again later.</i>",
            parse_mode=enums.ParseMode.HTML
        )


@bot.on_message(filters.command("ping"))
async def ping(client, message):
    """Check bot response time"""
    import time
    start = time.time()
    msg = await message.reply_text("🏓 Pong!")
    end = time.time()
    ms = round((end - start) * 1000)
    await msg.edit_text(f"🏓 <b>Pong!</b>\n⚡ Response time: <code>{ms}ms</code>", parse_mode=enums.ParseMode.HTML)


@bot.on_message(filters.command("stats"))
async def show_stats(client, message):
    """Show bot statistics"""
    # Admin gets detailed stats, users get basic stats
    is_admin = message.from_user.id in ADMIN_IDS
    
    uptime = datetime.now() - stats['start_date']
    days = uptime.days
    hours = uptime.seconds // 3600
    
    if is_admin:
        text = f"""📊 <b>BOT STATISTICS</b>

👥 <b>Total Users:</b> {len(stats['total_users'])}
📁 <b>Total Files:</b> {stats['total_files']}
📥 <b>Total Downloads:</b> {stats['total_downloads']}
📅 <b>Files Today:</b> {stats['files_today']}

🚫 <b>Banned Users:</b> {len(BANNED_USERS)}
📢 <b>Force Join Channels:</b> {len(FORCE_CHANNELS)}

⏰ <b>Uptime:</b> {days}d {hours}h

━━━━━━━━━━━━
⚡ <i>Admin View</i>"""
    else:
        text = f"""📊 <b>BOT STATISTICS</b>

👥 <b>Total Users:</b> {len(stats['total_users'])}
📁 <b>Total Files:</b> {stats['total_files']}
📥 <b>Downloads:</b> {stats['total_downloads']}

⏰ <b>Running Since:</b> {days} days

━━━━━━━━━━━━
⚡ <i>@Filetolinkzeus_bot</i>"""
    
    await message.reply(text, parse_mode=enums.ParseMode.HTML)


@bot.on_message(filters.command("broadcast") & filters.user(ADMIN_IDS))
async def broadcast_message(client, message):
    """Broadcast message to all users - Admin only"""
    try:
        if len(message.command) < 2 and not message.reply_to_message:
            await message.reply(
                "❌ <b>Usage:</b>\n\n"
                "<code>/broadcast Your message here</code>\n\n"
                "Or reply to a message with <code>/broadcast</code>",
                parse_mode=enums.ParseMode.HTML
            )
            return
        
        # Get broadcast message
        if message.reply_to_message:
            broadcast_text = message.reply_to_message.text or message.reply_to_message.caption
        else:
            broadcast_text = message.text.split(None, 1)[1]
        
        if not broadcast_text:
            await message.reply("❌ <b>No message to broadcast!</b>", parse_mode=enums.ParseMode.HTML)
            return
        
        # Confirm broadcast
        confirm_msg = await message.reply(
            f"📢 <b>Broadcasting to {len(stats['total_users'])} users...</b>\n\n"
            "<i>This may take a few minutes...</i>",
            parse_mode=enums.ParseMode.HTML
        )
        
        # Broadcast to all users
        success = 0
        failed = 0
        blocked = 0
        
        for user_id in stats['total_users']:
            try:
                await client.send_message(
                    user_id,
                    f"📢 <b>ANNOUNCEMENT</b>\n━━━━━━━━━━━━\n\n<b><i>{broadcast_text}</i></b>\n\n━━━━━━━━━━━━\n⚡ @Filetolinkzeus_bot",
                    parse_mode=enums.ParseMode.HTML
                )
                success += 1
                await asyncio.sleep(0.05)  # Avoid flood
            except Exception as e:
                if "blocked" in str(e).lower():
                    blocked += 1
                else:
                    failed += 1
        
        # Results
        result_text = f"""✅ <b>BROADCAST COMPLETED!</b>

📊 <b>Results:</b>
✅ Success: {success}
❌ Failed: {failed}
🚫 Blocked: {blocked}

<b>Total:</b> {len(stats['total_users'])} users

━━━━━━━━━━━━
⏱️ <i>Completed</i>"""
        
        await confirm_msg.edit(result_text, parse_mode=enums.ParseMode.HTML)
        
    except Exception as e:
        await message.reply(f"❌ <b>Error:</b> {str(e)}", parse_mode=enums.ParseMode.HTML)


@bot.on_message(filters.command("restart") & filters.user(ADMIN_IDS))
async def restart_bot(client, message):
    """Restart the bot - Admin only"""
    await message.reply("🔄 <b>Restarting bot...</b>\n\n⏳ Please wait a few seconds.", parse_mode=enums.ParseMode.HTML)
    import sys, signal
    # Stop the web server first so port 8888 is freed
    try:
        await client.stop()
    except:
        pass
    # Small delay to let port close
    await asyncio.sleep(2)
    os.execv(sys.executable, [sys.executable] + sys.argv)

@bot.on_message(filters.command("off") & filters.user(ADMIN_IDS))
async def bot_off(client, message):
    """Temporarily disable bot - Admin only"""
    try:
        if len(message.command) > 1 and message.command[1].isdigit():
            minutes = int(message.command[1])
            from datetime import timedelta
            maintenance['enabled'] = True
            maintenance['resume_time'] = datetime.now() + timedelta(minutes=minutes)
            
            text = f"""⏸️ <b>BOT PAUSED!</b>

⏰ <b>Duration:</b> {minutes} minutes
🔄 <b>Auto-resume at:</b> {maintenance['resume_time'].strftime('%H:%M:%S')} UTC

━━━━━━━━━━━━
🔧 <i>Users will see maintenance message</i>"""
            
            log_text = f"""⏸️ <b>BOT PAUSED!</b>

🤖 <b>Bot:</b> @{(await client.get_me()).username}
⏰ <b>Duration:</b> {minutes} minutes
👤 <b>By:</b> <a href="tg://user?id={message.from_user.id}">{message.from_user.first_name}</a>

⏰ <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC

━━━━━━━━━━━━
🔧 <i>Bot is in maintenance mode</i>"""
            
        else:
            maintenance['enabled'] = True
            maintenance['resume_time'] = None
            
            text = f"""⏸️ <b>BOT PAUSED!</b>

⏰ <b>Duration:</b> Indefinite
🔄 <b>Resume:</b> Use /on to resume

━━━━━━━━━━━━
🔧 <i>Users will see maintenance message</i>"""
            
            log_text = f"""⏸️ <b>BOT PAUSED!</b>

🤖 <b>Bot:</b> @{(await client.get_me()).username}
⏰ <b>Duration:</b> Indefinite
👤 <b>By:</b> <a href="tg://user?id={message.from_user.id}">{message.from_user.first_name}</a>

⏰ <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC

━━━━━━━━━━━━
🔧 <i>Bot is in maintenance mode</i>"""
        
        await message.reply(text, parse_mode=enums.ParseMode.HTML)
        await client.send_message(LOG_CHANNEL, log_text, parse_mode=enums.ParseMode.HTML)
        
    except Exception as e:
        await message.reply(f"❌ <b>Error:</b> {str(e)}", parse_mode=enums.ParseMode.HTML)


@bot.on_message(filters.command("on") & filters.user(ADMIN_IDS))
async def bot_on(client, message):
    """Re-enable bot - Admin only"""
    try:
        if not maintenance['enabled']:
            await message.reply("⚠️ <b>Bot is already online!</b>", parse_mode=enums.ParseMode.HTML)
            return
        
        maintenance['enabled'] = False
        maintenance['resume_time'] = None
        
        text = f"""▶️ <b>BOT RESUMED!</b>

✅ Bot is back online!

━━━━━━━━━━━━
⚡ <i>All systems operational</i>"""
        
        log_text = f"""▶️ <b>BOT RESUMED!</b>

🤖 <b>Bot:</b> @{(await client.get_me()).username}
👤 <b>By:</b> <a href="tg://user?id={message.from_user.id}">{message.from_user.first_name}</a>

⏰ <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC

━━━━━━━━━━━━
⚡ <i>File To Link Bot is Online!</i>"""
        
        await message.reply(text, parse_mode=enums.ParseMode.HTML)
        await client.send_message(LOG_CHANNEL, log_text, parse_mode=enums.ParseMode.HTML)
        
    except Exception as e:
        await message.reply(f"❌ <b>Error:</b> {str(e)}", parse_mode=enums.ParseMode.HTML)


def is_maintenance_active():
    """Check if maintenance mode is active (handles auto-resume)"""
    if not maintenance['enabled']:
        return False
    
    # Check if timer expired
    if maintenance['resume_time'] and datetime.now() >= maintenance['resume_time']:
        maintenance['enabled'] = False
        maintenance['resume_time'] = None
        return False
    
    return True


def get_maintenance_message():
    """Get maintenance message for users"""
    if maintenance['resume_time']:
        remaining = maintenance['resume_time'] - datetime.now()
        minutes_left = max(1, int(remaining.total_seconds() / 60))
        
        return f"""🔧 <b>Bot Under Maintenance!</b>

The bot is temporarily offline for maintenance.

⏰ <b>Back in:</b> ~{minutes_left} minutes

Please try again later.

━━━━━━━━━━━━
⚡ @Filetolinkzeus_bot"""
    else:
        return f"""🔧 <b>Bot Under Maintenance!</b>

The bot is temporarily offline for maintenance.

Please try again later.

━━━━━━━━━━━━
⚡ @Filetolinkzeus_bot"""


@bot.on_message(filters.command("start"))
async def start(client, message):
    """Start command"""
    name = message.from_user.first_name
    user_id = message.from_user.id
    
    # Track user & notify if new
    is_new_user = user_id not in stats['total_users']
    stats['total_users'].add(user_id)
    
    # Save to database
    if USE_DATABASE and db:
        db.add_user(user_id, message.from_user.username, name)
        db.update_user_activity(user_id)
    
    # Send new user notification to log channel
    if is_new_user:
        user = message.from_user
        new_user_text = f"""👤 <b>NEW USER STARTED BOT!</b>

<b>Name:</b> <a href="tg://user?id={user.id}">{user.first_name}</a>"""
        if user.last_name:
            new_user_text += f"\n<b>Last Name:</b> {user.last_name}"
        if user.username:
            new_user_text += f"\n<b>Username:</b> @{user.username}"
        new_user_text += f"""
🆔 <b>ID:</b> <code>{user.id}</code>

👥 <b>Total Users:</b> {len(stats['total_users'])}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC

━━━━━━━━━━━━
🆕 <i>New user joined!</i>"""
        try:
            await client.send_message(LOG_CHANNEL, new_user_text, parse_mode=enums.ParseMode.HTML)
        except:
            pass
    
    # Check maintenance mode (admins bypass)
    if is_maintenance_active() and user_id not in ADMIN_IDS:
        await message.reply(get_maintenance_message(), parse_mode=enums.ParseMode.HTML)
        return
    
    # Check if banned
    if user_id in BANNED_USERS:
        await message.reply("🚫 <b>YOU ARE BANNED!</b>\n\n<i>Contact owner for support</i>", parse_mode=enums.ParseMode.HTML)
        return
    
    # Show welcome (no force join on /start)
    bot_me = await client.get_me()
    
    text = f"""🌟 <b>Welcome To File To Link Bot</b> 🌟

Hey <a href="tg://user?id={user_id}">{name}</a>! 👋

Send me any file and get instant download link!

📎 <i>All file types supported</i>
⚡ <i>Instant link generation</i>
🌐 <i>Direct browser downloads</i>
💪 <i>Fast and Furious</i>

━━━━━━━━━━━━
⚡ <i>By Zeus</i>"""
    
    # Show admin button if user is admin
    if user_id in ADMIN_IDS:
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("👤 Owner", url="https://t.me/ZEUS_IS_HERE2"),
                InlineKeyboardButton("❓ Help", callback_data="help")
            ],
            [
                InlineKeyboardButton("☕ Donate", callback_data="donate")
            ],
            [
                InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel")
            ]
        ])
    else:
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("👤 Owner", url="https://t.me/ZEUS_IS_HERE2"),
                InlineKeyboardButton("❓ Help", callback_data="help")
            ],
            [
                InlineKeyboardButton("☕ Donate", callback_data="donate")
            ]
        ])
    
    await message.reply(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)


@bot.on_callback_query()
async def callbacks(client, query):
    """Callbacks"""
    
    if query.data == "check_joined":
        # Check if user joined
        if FORCE_CHANNELS:
            not_joined = await check_user_joined(client, query.from_user.id)
            
            if not_joined:
                await query.answer("❌ Please join all channels first!", show_alert=True)
                return
        
        # User joined - check if they have a pending file
        user_id = query.from_user.id
        pending_msg = pending_files.pop(user_id, None)
        
        if pending_msg:
            # Process the pending file
            await query.answer("✅ Verified! Generating your link...", show_alert=True)
            await query.message.delete()
            await handle_file(client, pending_msg)
        else:
            # No pending file - just confirm
            await query.answer("✅ Access granted! Now send me a file.", show_alert=True)
            await query.message.delete()
        return
    
    await query.answer()
    
    if query.data == "admin_panel":
        # Admin panel - show commands
        if query.from_user.id not in ADMIN_IDS:
            await query.answer("❌ Admin only!", show_alert=True)
            return
        
        total_channels = len(FORCE_CHANNELS)
        total_banned = len(BANNED_USERS)
        
        text = f"""⚙️ <b>ADMIN PANEL</b>

<b>Force Join:</b> {'✅ Enabled' if FORCE_CHANNELS else '❌ Disabled'}
<b>Channels:</b> {total_channels}
<b>Banned Users:</b> {total_banned}
<b>Total Users:</b> {len(stats['total_users'])}
<b>Total Files:</b> {stats['total_files']}

━━━━━━━━━━━━

<b>📢 FORCE JOIN:</b>
<code>/addchannel @name</code>
<code>/removechannel @name</code>
<code>/listchannels</code>
<code>/clearall</code>

<b>🚫 BAN SYSTEM:</b>
<code>/ban user_id</code> or reply
<code>/unban user_id</code>
<code>/banlist</code>

<b>📊 STATS & BROADCAST:</b>
<code>/stats</code> - View statistics
<code>/broadcast message</code> - Send to all
<code>/sendto user_id message</code> - Send to user

<b>🔧 TOOLS:</b>
<code>/ping</code> - Check bot response time
<code>/feedback message</code> - User feedback

<b>⏸️ MAINTENANCE:</b>
<code>/off</code> - Pause bot
<code>/off 30</code> - Pause for 30 minutes
<code>/on</code> - Resume bot
<code>/restart</code> - Restart bot
<code>/setexpiry 24h</code> - Set link expiry

━━━━━━━━━━━━
⚡ <i>Send commands in chat</i>"""
        
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 Main Menu", callback_data="start")]
        ])
        
        await query.message.edit(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        return
    
    if query.data == "start":
        # Show main menu
        bot_me = await client.get_me()
        name = query.from_user.first_name
        user_id = query.from_user.id
        
        text = f"""🌟 <b>Welcome To File To Link Bot</b> 🌟

Hey <a href="tg://user?id={user_id}">{name}</a>! 👋

Send me any file and get instant download link!

📎 <i>All file types supported</i>
⚡ <i>Instant link generation</i>
🌐 <i>Direct browser downloads</i>
💪 <i>Fast and Furious</i>

━━━━━━━━━━━━
⚡ <i>By Zeus</i>"""
        
        # Show admin button if user is admin
        if user_id in ADMIN_IDS:
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("👤 Owner", url="https://t.me/ZEUS_IS_HERE2"), InlineKeyboardButton("❓ Help", callback_data="help")],
                [InlineKeyboardButton("☕ Donate", callback_data="donate")],
                [InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel")]
            ])
        else:
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("👤 Owner", url="https://t.me/ZEUS_IS_HERE2"), InlineKeyboardButton("❓ Help", callback_data="help")],
                [InlineKeyboardButton("☕ Donate", callback_data="donate")]
            ])
        
        await query.message.edit(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        return
    
    if query.data == "donate":
        await query.message.edit(
            """☕ <b>Support Zeus!</b>

Thank you for considering a donation! ❤️

Your support helps keep this bot running 24/7 and motivates me to add new features ⚡

💰 <b>How to donate:</b>

📲 <b>UPI (India):</b> <code>muhammed50@fam</code>
🌍 <b>Not in India?</b> DM me @ZEUS_IS_HERE2

Every contribution, big or small, means the world to me! 🙏

━━━━━━━━━━━━
⚡ <i>By Zeus</i>""",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Contact @ZEUS_IS_HERE2", url="https://t.me/ZEUS_IS_HERE2")],
                [InlineKeyboardButton("🔙 Back", callback_data="back_to_start")]
            ]),
            parse_mode=enums.ParseMode.HTML
        )
        return

    if query.data == "back_to_start":
        name = query.from_user.first_name
        user_id = query.from_user.id
        text = f"""🌟 <b>Welcome To File To Link Bot</b> 🌟

Hey <a href="tg://user?id={user_id}">{name}</a>! 👋

Send me any file and get instant download link!

📎 <i>All file types supported</i>
⚡ <i>Instant link generation</i>
🌐 <i>Direct browser downloads</i>
💪 <i>Fast and Furious</i>

━━━━━━━━━━━━
⚡ <i>By Zeus</i>"""
        if user_id in ADMIN_IDS:
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("👤 Owner", url="https://t.me/ZEUS_IS_HERE2"), InlineKeyboardButton("❓ Help", callback_data="help")],
                [InlineKeyboardButton("☕ Donate", callback_data="donate")],
                [InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel")]
            ])
        else:
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("👤 Owner", url="https://t.me/ZEUS_IS_HERE2"), InlineKeyboardButton("❓ Help", callback_data="help")],
                [InlineKeyboardButton("☕ Donate", callback_data="donate")]
            ])
        await query.message.edit(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        return

    if query.data == "help":
        await query.message.edit(
            """🆘 <b>HOW TO USE</b>

<b>📤 Step 1:</b> Send Your File
Send any type of file to this bot

<b>⚡ Step 2:</b> Get Instant Link
Bot generates download link instantly

<b>📥 Step 3:</b> Share & Download
Share link anywhere, download from browser!

━━━━━━━━━━━━

<b>✨ FEATURES:</b>

⚡ <b>Lightning Fast</b>
Instant link generation - no waiting!

🌐 <b>Direct Downloads</b>
Download directly in Chrome/any browser

💪 <b>Fast And Furious</b>

🔒 <b>Secure & Private</b>
Your files are safe with us

📱 <b>All File Types</b>
Videos, Photos, Documents, Audio, etc.

🚀 <b>No Registration</b>
Just send and get link!

━━━━━━━━━━━━

<b>📞 Support:</b> @zeus_is_here
<b>⚡ Powered by:</b> Zeus""",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="start")]]),
            parse_mode=enums.ParseMode.HTML
        )


    # Change expiry callback — show options
    if query.data.startswith("expiry_"):
        file_hash = query.data[7:]
        if file_hash not in file_map:
            await query.answer("❌ Link not found!", show_alert=True)
            return
        
        info = file_map[file_hash]
        # Only link owner or admin can change expiry
        if query.from_user.id != info.get('user_id') and query.from_user.id not in ADMIN_IDS:
            await query.answer("❌ Only the link owner can change expiry!", show_alert=True)
            return
        
        current = info.get('expiry', 86400)
        if current == 0:
            current_display = "♾️ Permanent"
        elif current >= 86400:
            current_display = f"{current // 86400} day(s)"
        else:
            current_display = f"{current // 3600} hour(s)"
        
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("12h", callback_data=f"setexp_{file_hash}_12h"),
                InlineKeyboardButton("24h", callback_data=f"setexp_{file_hash}_24h"),
                InlineKeyboardButton("48h", callback_data=f"setexp_{file_hash}_48h"),
            ],
            [
                InlineKeyboardButton("72h", callback_data=f"setexp_{file_hash}_72h"),
                InlineKeyboardButton("7 Days", callback_data=f"setexp_{file_hash}_7d"),
                InlineKeyboardButton("♾️ Permanent", callback_data=f"setexp_{file_hash}_permanent"),
            ],
            [InlineKeyboardButton("🔙 Back", callback_data=f"expback_{file_hash}")]
        ])
        
        await query.message.edit(
            f"⏰ <b>Change Link Expiry</b>\n\n"
            f"📄 <b>{info['name']}</b>\n\n"
            f"📌 <b>Current:</b> {current_display}\n\n"
            f"Select new expiry time:",
            reply_markup=kb,
            parse_mode=enums.ParseMode.HTML
        )
        return
    
    # Set expiry for specific link
    if query.data.startswith("setexp_"):
        parts = query.data.split("_", 2)  # setexp, hash, option
        if len(parts) < 3:
            await query.answer("❌ Invalid!", show_alert=True)
            return
        
        file_hash = parts[1]
        option = parts[2]
        
        if file_hash not in file_map:
            await query.answer("❌ Link not found!", show_alert=True)
            return
        
        info = file_map[file_hash]
        if query.from_user.id != info.get('user_id') and query.from_user.id not in ADMIN_IDS:
            await query.answer("❌ Only the link owner can change expiry!", show_alert=True)
            return
        
        if option not in EXPIRY_OPTIONS:
            await query.answer("❌ Invalid option!", show_alert=True)
            return
        
        new_expiry = EXPIRY_OPTIONS[option]
        file_map[file_hash]['expiry'] = new_expiry
        
        # Sync to database
        if USE_DATABASE and db:
            db.update_file_expiry(file_hash, new_expiry)
        
        if new_expiry == 0:
            display = "♾️ Permanent (never expire)"
        elif new_expiry >= 86400:
            display = f"{new_expiry // 86400} day(s)"
        else:
            display = f"{new_expiry // 3600} hour(s)"
        
        await query.answer(f"✅ Expiry set to {display}", show_alert=True)
        
        # Rebuild the original link message
        name = info['name']
        size = info['size']
        if size >= 1024 * 1024:
            size_display = f"{size / (1024 * 1024):.2f} MB"
        else:
            size_display = f"{size / 1024:.2f} KB"
        
        dl_link = f"{PUBLIC_URL}/download/{file_hash}"
        watch_link = dl_link.replace('/download/', '/watch/')
        video_exts = ('.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv', '.m4v', '.3gp')
        
        text = f"""✅ <b>Link Ready!</b>

📄 <b>Name:</b> <code>{name}</code>
📊 <b>Size:</b> <code>{size_display}</code>

🔗 <b>Download Link:</b>
<code>{dl_link}</code>

⏰ <i>Link expires in {display}</i>
━━━━━━━━━━━━
⚡ <i>By Zeus</i>"""
        
        if name.lower().endswith(video_exts):
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("📥 Download", url=dl_link), InlineKeyboardButton("▶️ Watch Online", url=watch_link)],
                [InlineKeyboardButton("⏰ Change Expiry", callback_data=f"expiry_{file_hash}"), InlineKeyboardButton("🗑️ Revoke", callback_data=f"revoke_{file_hash}")]
            ])
        else:
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("📥 Download", url=dl_link)],
                [InlineKeyboardButton("⏰ Change Expiry", callback_data=f"expiry_{file_hash}"), InlineKeyboardButton("🗑️ Revoke", callback_data=f"revoke_{file_hash}")]
            ])
        
        await query.message.edit(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        return
    
    # Back from expiry menu
    if query.data.startswith("expback_"):
        file_hash = query.data[8:]
        if file_hash not in file_map:
            await query.answer("❌ Link not found!", show_alert=True)
            return
        
        info = file_map[file_hash]
        name = info['name']
        size = info['size']
        current_expiry = info.get('expiry', 86400)
        
        if size >= 1024 * 1024:
            size_display = f"{size / (1024 * 1024):.2f} MB"
        else:
            size_display = f"{size / 1024:.2f} KB"
        
        if current_expiry == 0:
            expiry_display = "♾️ Permanent"
        elif current_expiry >= 86400:
            expiry_display = f"{current_expiry // 86400} day(s)"
        else:
            expiry_display = f"{current_expiry // 3600} hour(s)"
        
        dl_link = f"{PUBLIC_URL}/download/{file_hash}"
        watch_link = dl_link.replace('/download/', '/watch/')
        video_exts = ('.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv', '.m4v', '.3gp')
        
        text = f"""✅ <b>Link Ready!</b>

📄 <b>Name:</b> <code>{name}</code>
📊 <b>Size:</b> <code>{size_display}</code>

🔗 <b>Download Link:</b>
<code>{dl_link}</code>

⏰ <i>Link expires in {expiry_display}</i>
━━━━━━━━━━━━
⚡ <i>By Zeus</i>"""
        
        if name.lower().endswith(video_exts):
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("📥 Download", url=dl_link), InlineKeyboardButton("▶️ Watch Online", url=watch_link)],
                [InlineKeyboardButton("⏰ Change Expiry", callback_data=f"expiry_{file_hash}"), InlineKeyboardButton("🗑️ Revoke", callback_data=f"revoke_{file_hash}")]
            ])
        else:
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("📥 Download", url=dl_link)],
                [InlineKeyboardButton("⏰ Change Expiry", callback_data=f"expiry_{file_hash}"), InlineKeyboardButton("🗑️ Revoke", callback_data=f"revoke_{file_hash}")]
            ])
        
        await query.message.edit(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        return

    # Revoke link callback
    if query.data.startswith("revoke_"):
        file_hash = query.data[7:]
        if file_hash in file_map:
            name = file_map[file_hash].get('name', 'Unknown')
            del file_map[file_hash]
            # Also delete from DB
            if USE_DATABASE:
                try:
                    db.files.delete_one({'file_hash': file_hash})
                except:
                    pass
            await query.message.edit(
                f"🗑️ <b>Link Revoked!</b>\n\n"
                f"📄 <b>{name}</b>\n\n"
                f"❌ Download link has been permanently deleted.\n\n"
                f"━━━━━━━━━━━━\n"
                f"⚡ <i>By Zeus</i>",
                parse_mode=enums.ParseMode.HTML
            )
            await query.answer("✅ Link revoked!", show_alert=True)
            
            # Log to channel
            if LOG_CHANNEL:
                user = query.from_user
                log_text = (
                    f"🗑️ <b>Link Revoked</b>\n\n"
                    f"👤 <b>User:</b> <a href='tg://user?id={user.id}'>{user.first_name}</a> [<code>{user.id}</code>]\n"
                    f"📄 <b>File:</b> {name}\n"
                    f"🔗 <b>Hash:</b> <code>{file_hash}</code>"
                )
                try:
                    await bot.send_message(LOG_CHANNEL, log_text, parse_mode=enums.ParseMode.HTML)
                except:
                    pass
        else:
            await query.answer("❌ Link already revoked or not found!", show_alert=True)
        return


_processed_media_groups = {}  # media_group_id -> True

@bot.on_message(filters.document | filters.video | filters.audio | filters.photo)
async def handle_file(client, message):
    """Handle files"""
    try:
        # Skip duplicate files from media groups (only process first file)
        if message.media_group_id:
            if message.media_group_id in _processed_media_groups:
                return
            _processed_media_groups[message.media_group_id] = True
            if len(_processed_media_groups) > 100:
                keys = list(_processed_media_groups.keys())
                for k in keys[:-50]:
                    _processed_media_groups.pop(k, None)

        # Cooldown check (15s between files, admins bypass)
        user_id = message.from_user.id
        if user_id not in ADMIN_IDS:
            import time as _time
            now = _time.time()
            last = user_cooldowns.get(user_id, 0)
            remaining = 15 - (now - last)
            if remaining > 0:
                await message.reply(f"⏳ <b>Please wait {int(remaining)}s</b> before sending the next file.", parse_mode=enums.ParseMode.HTML)
                return
        
        # Check maintenance mode (admins bypass)
        if is_maintenance_active() and message.from_user.id not in ADMIN_IDS:
            await message.reply(get_maintenance_message(), parse_mode=enums.ParseMode.HTML)
            return
        
        # Check if banned
        if message.from_user.id in BANNED_USERS:
            await message.reply("🚫 <b>YOU ARE BANNED!</b>\n\n<i>Contact owner for support</i>", parse_mode=enums.ParseMode.HTML)
            return
        
        # Check force join
        if FORCE_CHANNELS:
            not_joined = await check_user_joined(client, message.from_user.id)
            
            if not_joined:
                buttons = []
                for i, channel in enumerate(not_joined, 1):
                    channel_name = channel.replace("@", "")
                    try:
                        chat = await client.get_chat(channel_name)
                        display_name = chat.title or f"@{channel_name}"
                    except:
                        display_name = f"@{channel_name}"
                    buttons.append([InlineKeyboardButton(f"📢 Join {display_name}", url=f"https://t.me/{channel_name}")])
                
                buttons.append([InlineKeyboardButton("✅ I've Joined — Verify Me", callback_data="check_joined")])
                
                # Store the file message so we can process it after verification
                pending_files[message.from_user.id] = message
                
                name = message.from_user.first_name or "User"
                text = f"""🔐 <b>Join to continue</b>

Hey <b>{name}</b>, join our channel(s) to use this bot ⚡"""
                
                await message.reply(
                    text,
                    reply_markup=InlineKeyboardMarkup(buttons),
                    parse_mode=enums.ParseMode.HTML
                )
                return
        
        msg = await message.reply("⚡ <b>Processing...</b>", parse_mode=enums.ParseMode.HTML)
        
        # Track user
        stats['total_users'].add(message.from_user.id)
        
        # Save to database
        if USE_DATABASE and db:
            db.add_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
            db.update_user_activity(message.from_user.id)
            db.increment_user_files(message.from_user.id)
        
        # Get file info
        duration = 0  # seconds
        if message.document:
            file = message.document
            name = file.file_name
            size = file.file_size
        elif message.video:
            file = message.video
            name = file.file_name or f"video_{int(datetime.now().timestamp())}.mp4"
            size = file.file_size
            duration = file.duration or 0
        elif message.audio:
            file = message.audio
            name = file.file_name or f"audio_{int(datetime.now().timestamp())}.mp3"
            size = file.file_size
            duration = file.duration or 0
        elif message.photo:
            file = message.photo
            name = f"photo_{int(datetime.now().timestamp())}.jpg"
            size = file.file_size
        else:
            await msg.edit("❌ Unsupported!")
            return
        
        # Forward to channel (using bot, not userbot)
        fwd = await bot.copy_message(LOG_CHANNEL, message.chat.id, message.id)
        print(f"Forwarded: {fwd.id}")
        
        # Update stats
        stats['total_files'] += 1
        stats['files_today'] += 1
        stats['links_today'] += 1
        stats['bytes_today'] += size
        
        # Generate hash
        import hashlib
        file_hash = hashlib.md5(f"{file.file_id}{datetime.now()}".encode()).hexdigest()[:16]
        
        # Generate link
        dl_link = f"{PUBLIC_URL}/download/{file_hash}"
        
        # Send user details + link to log channel
        user = message.from_user
        user_info = f"""👤 <b>USER DETAILS</b>

<b>Name:</b> <a href="tg://user?id={user.id}">{user.first_name}</a>
<b>User ID:</b> <code>{user.id}</code>"""
        
        if user.username:
            user_info += f"\n<b>Username:</b> @{user.username}"
        
        if user.last_name:
            user_info += f"\n<b>Last Name:</b> {user.last_name}"
        
        user_info += f"""

📄 <b>File:</b> <code>{name}</code>
📊 <b>Size:</b> <code>{size / (1024 * 1024):.2f} MB</code>

🔗 <b>Link:</b> <code>{dl_link}</code>

━━━━━━━━━━━━
⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC"""
        
        await bot.send_message(
            LOG_CHANNEL,
            user_info,
            parse_mode=enums.ParseMode.HTML,
            reply_to_message_id=fwd.id
        )
        
        # Store
        import time as _time
        file_map[file_hash] = {
            'chat_id': LOG_CHANNEL,
            'message_id': fwd.id,
            'name': name,
            'size': size,
            'duration': duration,
            'created_at': _time.time(),
            'user_id': message.from_user.id,
            'expiry': link_expiry['default']  # 0 = permanent
        }
        
        # Save to database for persistence across restarts
        if USE_DATABASE and db:
            db.save_file(file_hash, file_map[file_hash])
        
        # Set cooldown
        import time as _time
        user_cooldowns[message.from_user.id] = _time.time()
        
        # Size display
        if size >= 1024 * 1024:
            size_display = f"{size / (1024 * 1024):.2f} MB"
        else:
            size_display = f"{size / 1024:.2f} KB"
        
        # Expiry display
        current_expiry = link_expiry['default']
        if current_expiry == 0:
            expiry_display = "♾️ Permanent"
        elif current_expiry >= 86400:
            expiry_display = f"{current_expiry // 86400} day(s)"
        else:
            expiry_display = f"{current_expiry // 3600} hour(s)"
        
        text = f"""✅ <b>Link Ready!</b>

📄 <b>Name:</b> <code>{name}</code>
📊 <b>Size:</b> <code>{size_display}</code>

🔗 <b>Download Link:</b>
<code>{dl_link}</code>

⏰ <i>Link expires in {expiry_display}</i>
━━━━━━━━━━━━
⚡ <i>By Zeus</i>"""
        
        # Check if video file — add Watch Online button
        video_exts = ('.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv', '.m4v', '.3gp')
        watch_link = dl_link.replace('/download/', '/watch/')
        is_admin = message.from_user.id in ADMIN_IDS
        if name.lower().endswith(video_exts):
            if is_admin:
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📥 Download", url=dl_link), InlineKeyboardButton("▶️ Watch Online", url=watch_link)],
                    [InlineKeyboardButton("⏰ Change Expiry", callback_data=f"expiry_{file_hash}"), InlineKeyboardButton("🗑️ Revoke", callback_data=f"revoke_{file_hash}")]
                ])
            else:
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📥 Download", url=dl_link), InlineKeyboardButton("▶️ Watch Online", url=watch_link)],
                    [InlineKeyboardButton("🗑️ Revoke Link", callback_data=f"revoke_{file_hash}")]
                ])
        else:
            if is_admin:
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📥 Download", url=dl_link)],
                    [InlineKeyboardButton("⏰ Change Expiry", callback_data=f"expiry_{file_hash}"), InlineKeyboardButton("🗑️ Revoke", callback_data=f"revoke_{file_hash}")]
                ])
            else:
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📥 Download", url=dl_link)],
                    [InlineKeyboardButton("🗑️ Revoke Link", callback_data=f"revoke_{file_hash}")]
                ])
        
        await msg.edit(text, reply_markup=kb, parse_mode=enums.ParseMode.HTML)
        print(f"✅ {name} ({size_display})")
        
    except Exception as e:
        print(f"Error: {e}")
        await msg.edit(f"❌ <b>Error!</b>\n\n{str(e)[:100]}", parse_mode=enums.ParseMode.HTML)


# Web server
routes = web.RouteTableDef()

HOME_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⚡ File To Link Bot — Fast & Secure File Sharing</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: #07070d;
            color: #fff;
            overflow-x: hidden;
        }}
        /* Hero */
        .hero {{
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
            padding: 40px 20px;
            position: relative;
            overflow: hidden;
        }}
        .hero::before {{
            content: '';
            position: absolute;
            top: -30%;
            left: 50%;
            transform: translateX(-50%);
            width: 800px;
            height: 800px;
            background: radial-gradient(circle, rgba(255, 215, 0, 0.12) 0%, rgba(255, 154, 0, 0.05) 40%, transparent 70%);
            pointer-events: none;
        }}
        .hero-badge {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(255, 215, 0, 0.08);
            border: 1px solid rgba(255, 215, 0, 0.15);
            border-radius: 50px;
            padding: 6px 16px;
            font-size: 12px;
            color: #ffd700;
            font-weight: 600;
            letter-spacing: 0.5px;
            margin-bottom: 32px;
        }}
        .hero-badge .dot {{
            width: 6px; height: 6px;
            background: #22c55e;
            border-radius: 50%;
            box-shadow: 0 0 8px rgba(34, 197, 94, 0.6);
            animation: pulse 2s infinite;
        }}
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.4; }}
        }}
        .hero-icon {{
            width: 80px; height: 80px;
            background: linear-gradient(135deg, #ffd700, #ff9a00);
            border-radius: 22px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 40px;
            margin-bottom: 28px;
            box-shadow: 0 8px 40px rgba(255, 215, 0, 0.2);
        }}
        .hero h1 {{
            font-size: clamp(32px, 6vw, 56px);
            font-weight: 900;
            line-height: 1.1;
            margin-bottom: 16px;
            letter-spacing: -1px;
        }}
        .hero h1 .accent {{ color: #ffd700; }}
        .hero p {{
            font-size: 17px;
            color: rgba(255, 255, 255, 0.5);
            max-width: 520px;
            line-height: 1.7;
            margin-bottom: 36px;
        }}
        .hero-buttons {{ display: flex; gap: 12px; flex-wrap: wrap; justify-content: center; }}
        .btn-primary {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: linear-gradient(135deg, #ffd700, #ff9a00);
            color: #0a0a0f;
            text-decoration: none;
            padding: 14px 32px;
            border-radius: 14px;
            font-size: 15px;
            font-weight: 700;
            transition: all 0.3s ease;
            box-shadow: 0 4px 20px rgba(255, 215, 0, 0.2);
        }}
        .btn-primary:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 30px rgba(255, 215, 0, 0.35);
        }}
        .btn-secondary {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: rgba(255, 255, 255, 0.06);
            border: 1px solid rgba(255, 255, 255, 0.1);
            color: #fff;
            text-decoration: none;
            padding: 14px 32px;
            border-radius: 14px;
            font-size: 15px;
            font-weight: 600;
            transition: all 0.3s ease;
        }}
        .btn-secondary:hover {{
            background: rgba(255, 255, 255, 0.1);
            transform: translateY(-2px);
        }}
        /* Stats */
        .stats {{
            display: flex;
            gap: 40px;
            margin-top: 60px;
            flex-wrap: wrap;
            justify-content: center;
        }}
        .stat {{ text-align: center; }}
        .stat-value {{ font-size: 28px; font-weight: 800; color: #ffd700; }}
        .stat-label {{ font-size: 12px; color: rgba(255,255,255,0.35); text-transform: uppercase; letter-spacing: 1.5px; margin-top: 4px; font-weight: 500; }}
        /* Features */
        .features {{
            padding: 80px 20px;
            max-width: 1000px;
            margin: 0 auto;
        }}
        .features-title {{
            text-align: center;
            font-size: 28px;
            font-weight: 800;
            margin-bottom: 48px;
        }}
        .features-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 16px;
        }}
        .feature-card {{
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 18px;
            padding: 28px;
            transition: all 0.3s ease;
        }}
        .feature-card:hover {{
            border-color: rgba(255, 215, 0, 0.15);
            background: rgba(255, 255, 255, 0.05);
            transform: translateY(-2px);
        }}
        .feature-icon {{
            width: 44px; height: 44px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 22px;
            margin-bottom: 16px;
        }}
        .feature-card h3 {{ font-size: 16px; font-weight: 700; margin-bottom: 8px; }}
        .feature-card p {{ font-size: 13px; color: rgba(255,255,255,0.45); line-height: 1.6; }}
        /* How it works */
        .how {{
            padding: 60px 20px 80px;
            max-width: 700px;
            margin: 0 auto;
            text-align: center;
        }}
        .how-title {{ font-size: 28px; font-weight: 800; margin-bottom: 40px; }}
        .steps {{ display: flex; flex-direction: column; gap: 20px; text-align: left; }}
        .step {{
            display: flex;
            align-items: flex-start;
            gap: 16px;
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 14px;
            padding: 20px;
        }}
        .step-num {{
            width: 36px; height: 36px;
            background: linear-gradient(135deg, #ffd700, #ff9a00);
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 16px;
            font-weight: 800;
            color: #0a0a0f;
            flex-shrink: 0;
        }}
        .step h4 {{ font-size: 15px; font-weight: 700; margin-bottom: 4px; }}
        .step p {{ font-size: 13px; color: rgba(255,255,255,0.45); }}
        /* Footer */
        .footer {{
            text-align: center;
            padding: 40px 20px;
            border-top: 1px solid rgba(255, 255, 255, 0.04);
        }}
        .footer-text {{ color: rgba(255,255,255,0.2); font-size: 12px; }}
        .footer-text a {{ color: rgba(255, 215, 0, 0.5); text-decoration: none; }}
        .footer-text a:hover {{ color: #ffd700; }}
        /* Animations */
        @keyframes fadeInUp {{
            from {{ opacity: 0; transform: translateY(30px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        .hero-icon {{ animation: fadeInUp 0.6s ease; }}
        .hero h1 {{ animation: fadeInUp 0.6s ease 0.1s both; }}
        .hero p {{ animation: fadeInUp 0.6s ease 0.2s both; }}
        .hero-buttons {{ animation: fadeInUp 0.6s ease 0.3s both; }}
        .stats {{ animation: fadeInUp 0.6s ease 0.4s both; }}
    </style>
</head>
<body>
    <div class="hero">
        <div class="hero-badge"><span class="dot"></span> Bot Online — {total_users} Users Served</div>
        <div class="hero-icon">⚡</div>
        <h1>File To Link <span class="accent">Bot</span></h1>
        <p>Send any file to our Telegram bot and get instant download & streaming links. Fast, secure, and free.</p>
        <div class="hero-buttons">
            <a href="https://t.me/Filetolinkzeus_bot" class="btn-primary">🤖 Start Bot</a>
            <a href="https://t.me/ZEUS_IS_HERE2" class="btn-secondary">👤 Contact Zeus</a>
            <a href="https://t.me/ZEUS_IS_HERE2" class="btn-secondary" style="background:rgba(255,154,0,0.08);border-color:rgba(255,154,0,0.2);color:#ff9a00;">☕ Donate</a>
        </div>
        <div class="stats">
            <div class="stat">
                <div class="stat-value">{total_users}</div>
                <div class="stat-label">Users</div>
            </div>
            <div class="stat">
                <div class="stat-value">{total_files}</div>
                <div class="stat-label">Links Generated</div>
            </div>
        </div>
    </div>

    <div class="features">
        <div class="features-title">Why Choose Us?</div>
        <div class="features-grid">
            <div class="feature-card">
                <div class="feature-icon" style="background:rgba(255,215,0,0.1);border:1px solid rgba(255,215,0,0.15);">⚡</div>
                <h3>Ultra Fast Speeds</h3>
                <p>Optimized for high-speed downloads and streaming. No more waiting for Telegram to buffer large files.</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon" style="background:rgba(0,212,255,0.1);border:1px solid rgba(0,212,255,0.15);">🎬</div>
                <h3>Direct Streaming</h3>
                <p>Watch videos instantly in your browser or external players like VLC, MX Player, KMPlayer & PLAYit.</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon" style="background:rgba(167,139,250,0.1);border:1px solid rgba(167,139,250,0.15);">📦</div>
                <h3>No File Size Limits</h3>
                <p>Whether it's a 10MB document or a 4GB video, we handle it effortlessly. Any file Telegram supports.</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon" style="background:rgba(34,197,94,0.1);border:1px solid rgba(34,197,94,0.15);">🔒</div>
                <h3>Secure & Private</h3>
                <p>We don't log your files or share them. Links are unique and hard to guess, keeping your content safe.</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon" style="background:rgba(255,100,100,0.1);border:1px solid rgba(255,100,100,0.15);">⏱️</div>
                <h3>Auto-Expiry Links</h3>
                <p>All generated links automatically expire for security. Configurable from 12 hours to permanent.</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon" style="background:rgba(255,154,0,0.1);border:1px solid rgba(255,154,0,0.15);">🚀</div>
                <h3>One-Click Use</h3>
                <p>No complicated commands. Just send a file to the bot and get your links instantly in seconds.</p>
            </div>
        </div>
    </div>

    <div class="how">
        <div class="how-title">How It Works</div>
        <div class="steps">
            <div class="step">
                <div class="step-num">1</div>
                <div>
                    <h4>Send Your File</h4>
                    <p>Open <a href="https://t.me/Filetolinkzeus_bot" style="color:#ffd700;text-decoration:none;">@Filetolinkzeus_bot</a> on Telegram and send any file — video, document, audio, photo.</p>
                </div>
            </div>
            <div class="step">
                <div class="step-num">2</div>
                <div>
                    <h4>Get Instant Links</h4>
                    <p>The bot generates a download link and a streaming link (for videos) within seconds.</p>
                </div>
            </div>
            <div class="step">
                <div class="step-num">3</div>
                <div>
                    <h4>Share & Enjoy</h4>
                    <p>Share the link anywhere. Recipients can download directly in their browser — no Telegram needed.</p>
                </div>
            </div>
        </div>
    </div>

    <div class="footer">
        <div class="footer-text">
            Powered by <a href="https://t.me/Filetolinkzeus_bot">@Filetolinkzeus_bot</a> — By <a href="https://t.me/ZEUS_IS_HERE2">Zeus</a> ⚡
        </div>
    </div>
</body>
</html>"""

async def log_visitor(req, page="Homepage"):
    """Log visitor details to LOG_CHANNEL"""
    if not LOG_CHANNEL:
        return
    try:
        ip = req.headers.get('CF-Connecting-IP') or req.headers.get('X-Forwarded-For', '').split(',')[0].strip() or req.remote
        country = req.headers.get('CF-IPCountry', 'Unknown')
        ua = req.headers.get('User-Agent', 'Unknown')
        # Shorten user agent
        if len(ua) > 80:
            ua = ua[:80] + '...'
        referer = req.headers.get('Referer', 'Direct')
        path = req.path
        
        log_text = (
            f"🌐 <b>Site Visitor</b>\n\n"
            f"📄 <b>Page:</b> {page}\n"
            f"🔗 <b>Path:</b> <code>{path}</code>\n"
            f"🌍 <b>IP:</b> <code>{ip}</code>\n"
            f"🏳️ <b>Country:</b> {country}\n"
            f"📱 <b>Device:</b> <code>{ua}</code>\n"
            f"↩️ <b>Referer:</b> {referer}"
        )
        await bot.send_message(LOG_CHANNEL, log_text, parse_mode=enums.ParseMode.HTML)
    except:
        pass

@routes.get('/')
async def home(req):
    await log_visitor(req, "🏠 Homepage")
    html = HOME_PAGE.format(
        total_users=len(stats['total_users']),
        total_files=stats['total_files']
    )
    return web.Response(text=html, content_type='text/html')

def get_file_icon(filename):
    """Get emoji icon based on file extension"""
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    icons = {
        'mp4': '🎬', 'mkv': '🎬', 'avi': '🎬', 'mov': '🎬', 'wmv': '🎬', 'flv': '🎬', 'webm': '🎬',
        'mp3': '🎵', 'flac': '🎵', 'wav': '🎵', 'aac': '🎵', 'ogg': '🎵', 'm4a': '🎵',
        'jpg': '🖼️', 'jpeg': '🖼️', 'png': '🖼️', 'gif': '🖼️', 'webp': '🖼️', 'bmp': '🖼️',
        'pdf': '📄', 'doc': '📝', 'docx': '📝', 'txt': '📝', 'rtf': '📝',
        'zip': '📦', 'rar': '📦', '7z': '📦', 'tar': '📦', 'gz': '📦',
        'apk': '📱', 'exe': '💻', 'dmg': '💻', 'iso': '💿',
        'srt': '💬', 'ass': '💬', 'sub': '💬',
    }
    return icons.get(ext, '📁')

import string as _string

def _load_template(name):
    tpl_path = os.path.join(os.path.dirname(__file__), 'templates', name)
    with open(tpl_path, 'r') as f:
        return _string.Template(f.read())

DOWNLOAD_TPL = _load_template('download.html')

def get_file_type(filename):
    """Get file type label based on extension"""
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    types = {
        'mp4': 'VIDEO', 'mkv': 'VIDEO', 'avi': 'VIDEO', 'mov': 'VIDEO', 'wmv': 'VIDEO', 'flv': 'VIDEO', 'webm': 'VIDEO',
        'mp3': 'AUDIO', 'flac': 'AUDIO', 'wav': 'AUDIO', 'aac': 'AUDIO', 'ogg': 'AUDIO', 'm4a': 'AUDIO',
        'jpg': 'IMAGE', 'jpeg': 'IMAGE', 'png': 'IMAGE', 'gif': 'IMAGE', 'webp': 'IMAGE', 'bmp': 'IMAGE',
        'pdf': 'PDF', 'doc': 'DOCUMENT', 'docx': 'DOCUMENT', 'txt': 'TEXT', 'rtf': 'DOCUMENT',
        'zip': 'ARCHIVE', 'rar': 'ARCHIVE', '7z': 'ARCHIVE', 'tar': 'ARCHIVE', 'gz': 'ARCHIVE',
        'apk': 'APP', 'exe': 'APP', 'dmg': 'APP', 'iso': 'DISC',
        'srt': 'SUBTITLE', 'ass': 'SUBTITLE', 'sub': 'SUBTITLE',
    }
    return types.get(ext, 'FILE')

DOWNLOAD_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⚡ File To Link Bot - Download</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .container {{
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(20px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 20px;
            padding: 40px;
            max-width: 480px;
            width: 100%;
            text-align: center;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
        }}
        .logo {{ font-size: 48px; margin-bottom: 10px; }}
        .brand {{ color: #fff; font-size: 22px; font-weight: 700; margin-bottom: 5px; }}
        .tagline {{ color: rgba(255, 255, 255, 0.5); font-size: 13px; margin-bottom: 30px; }}
        .file-card {{
            background: rgba(255, 255, 255, 0.08);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 14px;
            padding: 24px;
            margin-bottom: 24px;
        }}
        .file-icon {{ font-size: 40px; margin-bottom: 12px; }}
        .file-name {{ color: #fff; font-size: 16px; font-weight: 600; word-break: break-all; margin-bottom: 16px; }}
        .file-details {{ display: flex; justify-content: center; gap: 24px; margin-bottom: 4px; }}
        .detail {{ text-align: center; }}
        .detail-label {{ color: rgba(255, 255, 255, 0.4); font-size: 11px; text-transform: uppercase; letter-spacing: 1px; }}
        .detail-value {{ color: #fff; font-size: 15px; font-weight: 600; margin-top: 4px; }}
        .countdown {{ color: rgba(255, 255, 255, 0.6); font-size: 14px; margin-bottom: 16px; }}
        .countdown span {{ color: #ffd700; font-weight: 700; font-size: 18px; }}
        .download-btn {{
            display: inline-block;
            background: linear-gradient(135deg, #ffd700, #ffaa00);
            color: #1a1a2e;
            text-decoration: none;
            padding: 14px 48px;
            border-radius: 50px;
            font-size: 16px;
            font-weight: 700;
            letter-spacing: 0.5px;
            transition: all 0.3s ease;
            border: none;
            cursor: pointer;
            width: 100%;
        }}
        .download-btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 30px rgba(255, 215, 0, 0.3);
        }}
        .download-btn.disabled {{
            background: rgba(255, 255, 255, 0.15);
            color: rgba(255, 255, 255, 0.4);
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
            pointer-events: none;
        }}
        .footer {{ margin-top: 24px; color: rgba(255, 255, 255, 0.3); font-size: 12px; }}
        .footer a {{ color: #ffd700; text-decoration: none; }}
        .progress-bar {{ width: 100%; height: 4px; background: rgba(255, 255, 255, 0.1); border-radius: 2px; margin-bottom: 20px; overflow: hidden; }}
        .progress-fill {{ height: 100%; background: linear-gradient(90deg, #ffd700, #ffaa00); border-radius: 2px; width: 0%; transition: width 1s linear; }}
        .stats-row {{ display: flex; justify-content: center; gap: 8px; margin-top: 16px; }}
        .stat-badge {{
            background: rgba(255, 255, 255, 0.06);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 20px;
            padding: 4px 12px;
            color: rgba(255, 255, 255, 0.5);
            font-size: 11px;
        }}
        .watch-btn {{
            display: inline-block;
            background: linear-gradient(135deg, #00d4ff, #0099cc);
            color: #fff;
            text-decoration: none;
            padding: 14px 48px;
            border-radius: 50px;
            font-size: 16px;
            font-weight: 700;
            letter-spacing: 0.5px;
            transition: all 0.3s ease;
            border: none;
            cursor: pointer;
            width: 100%;
            margin-top: 12px;
        }}
        .watch-btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 30px rgba(0, 212, 255, 0.3);
        }}
        .not-found {{ color: rgba(255,255,255,0.7); font-size: 18px; margin: 40px 0; }}
    </style>
</head>
<body>
    <nav style="position:fixed;top:0;left:0;right:0;display:flex;align-items:center;justify-content:space-between;padding:12px 20px;background:rgba(10,10,15,0.85);backdrop-filter:blur(20px);border-bottom:1px solid rgba(255,255,255,0.06);z-index:999;">
        <a href="/" style="display:flex;align-items:center;gap:10px;text-decoration:none;">
            <div style="width:34px;height:34px;background:linear-gradient(135deg,#ffd700,#ff9a00);border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:17px;box-shadow:0 2px 10px rgba(255,215,0,0.2);">⚡</div>
            <span style="color:#fff;font-size:15px;font-weight:700;letter-spacing:-0.3px;">File To Link</span>
        </a>
        <a href="/" style="display:flex;align-items:center;justify-content:center;width:34px;height:34px;background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.08);border-radius:9px;text-decoration:none;transition:all 0.2s;" onmouseover="this.style.background='rgba(255,255,255,0.12)'" onmouseout="this.style.background='rgba(255,255,255,0.06)'">
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.6)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
        </a>
    </nav>
    <div class="container" style="margin-top:70px;">
        <div class="logo">⚡</div>
        <div class="brand">File To Link Bot</div>
        <div class="tagline">Fast & Secure File Sharing</div>
        <div class="file-card">
            <div class="file-icon">{file_icon}</div>
            <div class="file-name">{file_name}</div>
            <div class="file-details">
                <div class="detail">
                    <div class="detail-label">Size</div>
                    <div class="detail-value">{file_size}</div>
                </div>
                <div class="detail">
                    <div class="detail-label">Type</div>
                    <div class="detail-value">{file_type}</div>
                </div>
                <div class="detail">
                    <div class="detail-label">Downloads</div>
                    <div class="detail-value">{download_count}</div>
                </div>
            </div>
        </div>
        <div class="countdown" id="countdown">
            Starting download in <span id="timer">5</span> seconds...
        </div>
        <div class="progress-bar">
            <div class="progress-fill" id="progress"></div>
        </div>
        <a href="{download_url}" id="downloadBtn" class="download-btn disabled">
            ⏳ Please wait...
        </a>
        {watch_button}
        <div class="stats-row">
            <span class="stat-badge">🔒 Secure</span>
            <span class="stat-badge">⚡ Fast</span>
            <span class="stat-badge">🌐 Direct</span>
        </div>
        <a href="https://t.me/ZEUS_IS_HERE2" target="_blank" style="display:block;text-align:center;margin-top:16px;padding:12px;border-radius:12px;background:rgba(255,154,0,0.1);border:1px solid rgba(255,154,0,0.2);color:#ff9a00;text-decoration:none;font-weight:600;font-size:13px;">☕ Buy Me a Coffee</a>
        <div class="footer">
            Powered by <a href="https://t.me/Filetolinkzeus_bot">@Filetolinkzeus_bot</a> — By Zeus ⚡
        </div>
    </div>
    <script>
        let seconds = 10;
        const timer = document.getElementById('timer');
        const btn = document.getElementById('downloadBtn');
        const progress = document.getElementById('progress');
        const countdown = document.getElementById('countdown');
        const interval = setInterval(() => {{
            seconds--;
            timer.textContent = seconds;
            progress.style.width = ((10 - seconds) / 10 * 100) + '%';
            if (seconds <= 0) {{
                clearInterval(interval);
                countdown.innerHTML = '✅ Ready to download!';
                btn.classList.remove('disabled');
                btn.textContent = '📥 DOWNLOAD NOW';
                btn.style.pointerEvents = 'auto';
                btn.addEventListener('click', function(e) {{
                    e.preventDefault();
                    window.location.href = btn.href;
                }});
                progress.style.width = '100%';
            }}
        }}, 1000);
    </script>
</body>
</html>"""

NOT_FOUND_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>⚡ File Not Found</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .container {{
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(20px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 20px;
            padding: 40px;
            max-width: 480px;
            width: 100%;
            text-align: center;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
        }}
        .logo {{ font-size: 48px; margin-bottom: 10px; }}
        .brand {{ color: #fff; font-size: 22px; font-weight: 700; margin-bottom: 5px; }}
        .tagline {{ color: rgba(255, 255, 255, 0.5); font-size: 13px; margin-bottom: 30px; }}
        .not-found {{ color: rgba(255,255,255,0.7); font-size: 18px; margin: 40px 0; }}
        .home-btn {{
            display: inline-block;
            background: linear-gradient(135deg, #ffd700, #ffaa00);
            color: #1a1a2e;
            text-decoration: none;
            padding: 12px 36px;
            border-radius: 50px;
            font-size: 14px;
            font-weight: 700;
        }}
        .footer {{ margin-top: 24px; color: rgba(255, 255, 255, 0.3); font-size: 12px; }}
        .footer a {{ color: #ffd700; text-decoration: none; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">⚡</div>
        <div class="brand">File To Link Bot</div>
        <div class="tagline">Fast & Secure File Sharing</div>
        <div class="not-found">❌ File not found or link expired</div>
        <a href="https://t.me/Filetolinkzeus_bot" class="home-btn">🤖 Go to Bot</a>
        <div class="footer">
            Powered by <a href="https://t.me/Filetolinkzeus_bot">@Filetolinkzeus_bot</a> — By Zeus ⚡
        </div>
    </div>

</body>
</html>"""

@routes.get('/download/{file_hash}')
async def download_page(req):
    """Show branded download page"""
    file_hash = req.match_info['file_hash']
    
    if file_hash not in file_map:
        return web.Response(text=NOT_FOUND_PAGE, content_type='text/html', status=404)
    
    info = file_map[file_hash]
    name = info['name']
    size = info['size']
    
    # Size display
    if size >= 1024 * 1024 * 1024:
        size_display = f"{size / (1024 * 1024 * 1024):.2f} GB"
    elif size >= 1024 * 1024:
        size_display = f"{size / (1024 * 1024):.2f} MB"
    else:
        size_display = f"{size / 1024:.2f} KB"
    
    # Download count
    dl_count = info.get('downloads', 0)
    
    # Check if file is a video for watch button
    video_exts = ('.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv', '.m4v', '.3gp')
    is_video = name.lower().endswith(video_exts)
    watch_button = f'<a href="/watch/{file_hash}" class="btn btn-watch">▶️ Watch Online</a>' if is_video else ''
    
    html = DOWNLOAD_TPL.safe_substitute(
        file_icon=get_file_icon(name),
        file_name=name,
        file_size=size_display,
        file_type=get_file_type(name),
        download_count=dl_count,
        download_url=f"/stream/{file_hash}",
        watch_button=watch_button
    )
    
    return web.Response(text=html, content_type='text/html')

@routes.get('/transcode/{file_hash}')
async def transcode_stream(req):
    """Transcode video to MP4 (H264+AAC) on-the-fly for browser playback"""
    import subprocess
    
    file_hash = req.match_info['file_hash']
    if file_hash not in file_map:
        return web.Response(text="404", status=404)
    
    info = file_map[file_hash]
    
    try:
        stream_client = userbot if userbot.is_connected else bot
        msg = await stream_client.get_messages(info['chat_id'], info['message_id'])
        
        response = web.StreamResponse(
            status=200,
            headers={
                'Content-Type': 'video/mp4',
                'Transfer-Encoding': 'chunked',
                'Cache-Control': 'no-cache',
                'Accept-Ranges': 'none',
            }
        )
        await response.prepare(req)
        
        # Start ffmpeg process: read from stdin, output fragmented MP4 to stdout
        ffmpeg = await asyncio.create_subprocess_exec(
            'ffmpeg', '-i', 'pipe:0',
            '-c:v', 'copy',        # Keep video codec (no re-encoding)
            '-c:a', 'aac',         # Transcode audio to AAC (browser compatible)
            '-b:a', '192k',
            '-movflags', 'frag_keyframe+empty_moov+default_base_moof',
            '-f', 'mp4',
            '-y', 'pipe:1',
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL
        )
        
        print(f"🔄 Transcoding {info['name']}...")
        
        # Feed Telegram stream into ffmpeg stdin
        async def feed_ffmpeg():
            try:
                async for chunk in stream_client.stream_media(msg):
                    ffmpeg.stdin.write(chunk)
                    await ffmpeg.stdin.drain()
                ffmpeg.stdin.close()
            except Exception as e:
                print(f"Feed error: {e}")
                try:
                    ffmpeg.stdin.close()
                except:
                    pass
        
        # Start feeding in background
        feed_task = asyncio.create_task(feed_ffmpeg())
        
        # Read ffmpeg output and send to client
        try:
            while True:
                chunk = await ffmpeg.stdout.read(65536)  # 64KB chunks
                if not chunk:
                    break
                await response.write(chunk)
        except ConnectionResetError:
            print(f"⚠️ Client disconnected during transcode: {info['name']}")
        finally:
            feed_task.cancel()
            try:
                ffmpeg.kill()
            except:
                pass
        
        await response.write_eof()
        print(f"✅ Transcoded {info['name']}")
        return response
        
    except Exception as e:
        print(f"Transcode error: {e}")
        return web.Response(text=f"Error: {e}", status=500)

@routes.get('/watch/{file_hash}')
async def watch_page(req):
    """Online video player page"""
    file_hash = req.match_info['file_hash']
    
    if file_hash not in file_map:
        return web.Response(text=NOT_FOUND_PAGE, content_type='text/html', status=404)
    
    info = file_map[file_hash]
    name = info['name']
    size = info['size']
    duration = info.get('duration', 0)
    
    if size >= 1024 * 1024 * 1024:
        size_display = f"{size / (1024 * 1024 * 1024):.2f} GB"
    elif size >= 1024 * 1024:
        size_display = f"{size / (1024 * 1024):.2f} MB"
    else:
        size_display = f"{size / 1024:.2f} KB"
    
    # Duration display
    if duration > 0:
        hours = duration // 3600
        mins = (duration % 3600) // 60
        secs = duration % 60
        if hours > 0:
            duration_display = f"{hours}h {mins}m {secs}s"
        else:
            duration_display = f"{mins}m {secs}s"
    else:
        duration_display = "Unknown"
    
    # Detect mime type for video
    ext = name.rsplit('.', 1)[-1].lower() if '.' in name else ''
    mime_map = {
        'mp4': 'video/mp4', 'mkv': 'video/x-matroska', 'avi': 'video/x-msvideo',
        'mov': 'video/quicktime', 'webm': 'video/webm', 'flv': 'video/x-flv',
        'wmv': 'video/x-ms-wmv', 'm4v': 'video/mp4', '3gp': 'video/3gpp'
    }
    video_mime = mime_map.get(ext, 'video/mp4')
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>▶️ {name} — Stream Online</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 20px;
        }}
        .player-container {{
            background: rgba(0, 0, 0, 0.6);
            backdrop-filter: blur(20px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 20px;
            padding: 20px;
            max-width: 900px;
            width: 100%;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
            margin-top: 10px;
        }}
        .video-wrapper {{
            position: relative;
            width: 100%;
            border-radius: 12px;
            overflow: hidden;
            background: #000;
            aspect-ratio: 16/9;
        }}
        video {{
            width: 100%;
            height: 100%;
            border-radius: 12px;
            background: #000;
        }}
        .video-info {{
            padding: 16px 4px 4px;
        }}
        .video-title {{
            color: #fff;
            font-size: 16px;
            font-weight: 600;
            word-break: break-all;
            margin-bottom: 8px;
        }}
        .video-meta {{
            display: flex;
            gap: 16px;
            color: rgba(255, 255, 255, 0.5);
            font-size: 13px;
        }}
        .video-meta span {{
            display: flex;
            align-items: center;
            gap: 4px;
        }}
        .btn-row {{
            display: flex;
            gap: 10px;
            margin-top: 16px;
        }}
        .dl-btn {{
            flex: 1;
            display: inline-block;
            background: linear-gradient(135deg, #ffd700, #ffaa00);
            color: #1a1a2e;
            text-decoration: none;
            padding: 12px 20px;
            border-radius: 50px;
            font-size: 14px;
            font-weight: 700;
            text-align: center;
            transition: all 0.3s ease;
        }}
        .dl-btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 30px rgba(255, 215, 0, 0.3);
        }}
        .back-btn {{
            flex: 1;
            display: inline-block;
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            color: #fff;
            text-decoration: none;
            padding: 12px 20px;
            border-radius: 50px;
            font-size: 14px;
            font-weight: 700;
            text-align: center;
            transition: all 0.3s ease;
        }}
        .back-btn:hover {{
            background: rgba(255, 255, 255, 0.2);
        }}
        .footer {{
            margin-top: 20px;
            color: rgba(255, 255, 255, 0.3);
            font-size: 12px;
            text-align: center;
        }}
        .footer a {{ color: #ffd700; text-decoration: none; }}
        .tip {{
            background: rgba(255, 215, 0, 0.1);
            border: 1px solid rgba(255, 215, 0, 0.2);
            border-radius: 10px;
            padding: 10px 14px;
            margin-top: 12px;
            color: rgba(255, 255, 255, 0.6);
            font-size: 12px;
        }}
        .tip b {{ color: #ffd700; }}
    </style>
</head>
<body>
    <nav style="position:fixed;top:0;left:0;right:0;display:flex;align-items:center;justify-content:space-between;padding:12px 20px;background:rgba(10,10,15,0.85);backdrop-filter:blur(20px);border-bottom:1px solid rgba(255,255,255,0.06);z-index:999;">
        <a href="/" style="display:flex;align-items:center;gap:10px;text-decoration:none;">
            <div style="width:34px;height:34px;background:linear-gradient(135deg,#ffd700,#ff9a00);border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:17px;box-shadow:0 2px 10px rgba(255,215,0,0.2);">⚡</div>
            <span style="color:#fff;font-size:15px;font-weight:700;letter-spacing:-0.3px;">File To Link</span>
        </a>
        <a href="/" style="display:flex;align-items:center;justify-content:center;width:34px;height:34px;background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.08);border-radius:9px;text-decoration:none;transition:all 0.2s;" onmouseover="this.style.background='rgba(255,255,255,0.12)'" onmouseout="this.style.background='rgba(255,255,255,0.06)'">
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.6)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
        </a>
    </nav>
    <div class="player-container" style="margin-top:70px;">
        <div class="video-wrapper" id="videoWrapper">
            <video id="player" controls autoplay playsinline preload="auto"></video>
        </div>
        <div class="video-info">
            <div class="video-title">🎬 {name}</div>
            <div class="video-meta">
                <span>📦 {size_display}</span>
                <span>🎞️ {ext.upper()}</span>
                <span>⏱️ {duration_display}</span>
            </div>
            <div id="status-bar" class="tip" style="display:none;"></div>
            <div class="btn-row">
                <a href="/download/{file_hash}" class="dl-btn">📥 Download</a>
            </div>
            <div style="margin-top:20px;">
                <div style="color:rgba(255,255,255,0.4);font-size:11px;text-transform:uppercase;letter-spacing:2px;font-weight:600;margin-bottom:12px;">External Players</div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
                    <a href="#" onclick="openVLC();return false;" style="display:flex;flex-direction:column;align-items:center;gap:8px;padding:16px 10px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:14px;text-decoration:none;transition:all 0.2s;" onmouseover="this.style.background='rgba(255,255,255,0.08)'" onmouseout="this.style.background='rgba(255,255,255,0.04)'">
                        <img src="https://i.postimg.cc/15TQ4y7B/vlc.png" width="40" height="40" style="border-radius:10px;">
                        <span style="color:#fff;font-size:13px;font-weight:600;">VLC Player</span>
                    </a>
                    <a href="#" onclick="openMX();return false;" style="display:flex;flex-direction:column;align-items:center;gap:8px;padding:16px 10px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:14px;text-decoration:none;transition:all 0.2s;" onmouseover="this.style.background='rgba(255,255,255,0.08)'" onmouseout="this.style.background='rgba(255,255,255,0.04)'">
                        <img src="https://i.postimg.cc/sx4Msv4T/mx.png" width="40" height="40" style="border-radius:10px;">
                        <span style="color:#fff;font-size:13px;font-weight:600;">MX Player</span>
                    </a>
                    <a href="#" onclick="openKM();return false;" style="display:flex;flex-direction:column;align-items:center;gap:8px;padding:16px 10px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:14px;text-decoration:none;transition:all 0.2s;" onmouseover="this.style.background='rgba(255,255,255,0.08)'" onmouseout="this.style.background='rgba(255,255,255,0.04)'">
                        <img src="https://i.postimg.cc/wT9tFQ9Z/km.png" width="40" height="40" style="border-radius:10px;">
                        <span style="color:#fff;font-size:13px;font-weight:600;">KMPlayer</span>
                    </a>
                    <a href="#" onclick="openPlayit();return false;" style="display:flex;flex-direction:column;align-items:center;gap:8px;padding:16px 10px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:14px;text-decoration:none;transition:all 0.2s;" onmouseover="this.style.background='rgba(255,255,255,0.08)'" onmouseout="this.style.background='rgba(255,255,255,0.04)'">
                        <img src="https://i.postimg.cc/RVGWYJFF/playit.png" width="40" height="40" style="border-radius:10px;">
                        <span style="color:#fff;font-size:13px;font-weight:600;">PLAYit</span>
                    </a>
                </div>
            </div>
            <div class="tip" style="margin-top:12px;">
                ⚠️ For audio track or subtitle selection, use external players such as <b>VLC</b>.
            </div>
        </div>
    </div>
    <script>
        const video = document.getElementById('player');
        const directUrl = '/stream/{file_hash}';
        const transcodeUrl = '/transcode/{file_hash}';
        const ext = '{ext}'.toLowerCase();
        const statusBar = document.getElementById('status-bar');
        const fullStreamUrl = window.location.origin + '/stream/{file_hash}?play=1';
        const videoTitle = '{name}';
        
        function openVLC() {{
            // VLC Android intent
            const intentUrl = 'intent:' + fullStreamUrl + '#Intent;package=org.videolan.vlc;type=video/*;S.title=' + encodeURIComponent(videoTitle) + ';S.browser_fallback_url=' + encodeURIComponent('https://play.google.com/store/apps/details?id=org.videolan.vlc') + ';end';
            var iframe = document.createElement('iframe');
            iframe.style.display = 'none';
            iframe.src = intentUrl;
            document.body.appendChild(iframe);
            setTimeout(function() {{ document.body.removeChild(iframe); }}, 3000);
        }}
        
        function openKM() {{
            // KMPlayer Android intent
            const intentUrl = 'intent:' + fullStreamUrl + '#Intent;package=com.kmplayer;type=video/*;S.title=' + encodeURIComponent(videoTitle) + ';S.browser_fallback_url=' + encodeURIComponent('https://play.google.com/store/apps/details?id=com.kmplayer') + ';end';
            var iframe = document.createElement('iframe');
            iframe.style.display = 'none';
            iframe.src = intentUrl;
            document.body.appendChild(iframe);
            setTimeout(function() {{ document.body.removeChild(iframe); }}, 3000);
        }}
        
        function openMX() {{
            // MX Player Android intent with S.browser_fallback_url
            const intentUrl = 'intent:' + fullStreamUrl + '#Intent;package=com.mxtech.videoplayer.ad;type=video/*;S.title=' + encodeURIComponent(videoTitle) + ';S.browser_fallback_url=' + encodeURIComponent('https://play.google.com/store/apps/details?id=com.mxtech.videoplayer.ad') + ';end';
            
            // Also try MX Player Pro
            const intentUrlPro = 'intent:' + fullStreamUrl + '#Intent;package=com.mxtech.videoplayer.pro;type=video/*;S.title=' + encodeURIComponent(videoTitle) + ';S.browser_fallback_url=' + encodeURIComponent('https://play.google.com/store/apps/details?id=com.mxtech.videoplayer.ad') + ';end';
            
            // Create hidden iframe to trigger intent (more reliable than window.location)
            var iframe = document.createElement('iframe');
            iframe.style.display = 'none';
            iframe.src = intentUrl;
            document.body.appendChild(iframe);
            
            // Cleanup after 3s
            setTimeout(function() {{ document.body.removeChild(iframe); }}, 3000);
        }}
        
        function openPlayit() {{
            // PLAYit Android intent
            const intentUrl = 'intent:' + fullStreamUrl + '#Intent;package=com.playit.videoplayer;type=video/*;S.title=' + encodeURIComponent(videoTitle) + ';S.browser_fallback_url=' + encodeURIComponent('https://play.google.com/store/apps/details?id=com.playit.videoplayer') + ';end';
            
            var iframe = document.createElement('iframe');
            iframe.style.display = 'none';
            iframe.src = intentUrl;
            document.body.appendChild(iframe);
            
            setTimeout(function() {{ document.body.removeChild(iframe); }}, 3000);
        }}
        
        function showStatus(msg) {{
            statusBar.style.display = 'block';
            statusBar.innerHTML = msg;
        }}
        
        // All formats — try direct stream first (with video content type + range support = seekable)
        showStatus('⏳ <b>Loading video...</b>');
        video.src = directUrl + '?play=1';
        video.load();
        
        video.addEventListener('playing', function() {{
            statusBar.style.display = 'none';
        }});
        
        video.addEventListener('canplay', function() {{
            statusBar.style.display = 'none';
        }});
        
        // If direct fails (codec issue), try transcoded version
        video.addEventListener('error', function() {{
            if (video.src.indexOf('transcode') === -1) {{
                showStatus('🔄 <b>Converting for playback...</b> This may take a moment');
                video.src = transcodeUrl;
                video.load();
                video.play();
            }}
        }});
        
        // If nothing works after 20s, show help
        let playStarted = false;
        video.addEventListener('playing', function() {{ playStarted = true; }});
        setTimeout(function() {{
            if (!playStarted) {{
                showStatus('⚠️ <b>Not playing?</b> Try <a href="' + directUrl + '" style="color:#ffd700">downloading</a> and playing with VLC/MX Player.');
            }}
        }}, 20000);
    </script>
    <div class="footer">
        Powered by <a href="https://t.me/Filetolinkzeus_bot">@Filetolinkzeus_bot</a> — By Zeus ⚡
    </div>
</body>
</html>"""
    return web.Response(text=html, content_type='text/html')

@routes.get('/stream/{file_hash}')
async def stream_file(req):
    """Stream actual file from Telegram with range request support for pause/resume"""
    from urllib.parse import quote
    
    file_hash = req.match_info['file_hash']
    
    if file_hash not in file_map:
        return web.Response(text="404 - File not found", status=404)
    
    info = file_map[file_hash]
    file_size = info['size']
    CHUNK_SIZE = 1024 * 1024  # 1MB (Pyrogram chunk size)
    
    try:
        # Use userbot for streaming (higher concurrency limits than bot account)
        stream_client = userbot if userbot.is_connected else bot
        msg = await stream_client.get_messages(info['chat_id'], info['message_id'])
        
        # Sanitize filename for Content-Disposition
        safe_name = info["name"].encode('ascii', 'ignore').decode('ascii') or "download"
        utf8_name = info["name"]
        disposition = f'attachment; filename="{safe_name}"; filename*=UTF-8\'\'{quote(utf8_name)}'
        
        # Detect content type — use video mime for streaming, octet-stream for downloads
        ext = info["name"].rsplit('.', 1)[-1].lower() if '.' in info["name"] else ''
        video_mimes = {
            'mp4': 'video/mp4', 'mkv': 'video/x-matroska', 'avi': 'video/x-msvideo',
            'mov': 'video/quicktime', 'webm': 'video/webm', 'flv': 'video/x-flv',
            'wmv': 'video/x-ms-wmv', 'm4v': 'video/mp4', '3gp': 'video/3gpp'
        }
        referer = req.headers.get('Referer', '')
        is_stream = '/watch/' in referer or req.query.get('play') == '1'
        content_type = video_mimes.get(ext, 'application/octet-stream') if is_stream else 'application/octet-stream'
        
        # Log download start (only first request, not range continuations or streams)
        range_hdr = req.headers.get('Range', '')
        is_first_request = not range_hdr or range_hdr == 'bytes=0-'
        if is_first_request and not is_stream and LOG_CHANNEL:
            try:
                ip = req.headers.get('CF-Connecting-IP') or req.headers.get('X-Forwarded-For', '').split(',')[0].strip() or req.remote
                country = req.headers.get('CF-IPCountry', 'Unknown')
                ua = req.headers.get('User-Agent', 'Unknown')
                if len(ua) > 80:
                    ua = ua[:80] + '...'
                if file_size >= 1024 * 1024 * 1024:
                    sz = f"{file_size / (1024**3):.2f} GB"
                elif file_size >= 1024 * 1024:
                    sz = f"{file_size / (1024**2):.2f} MB"
                else:
                    sz = f"{file_size / 1024:.2f} KB"
                dl_log = (
                    f"📥 <b>Download Started</b>\n\n"
                    f"📄 <b>File:</b> {info['name']}\n"
                    f"💾 <b>Size:</b> {sz}\n"
                    f"🌍 <b>IP:</b> <code>{ip}</code>\n"
                    f"🏳️ <b>Country:</b> {country}\n"
                    f"📱 <b>Device:</b> <code>{ua}</code>"
                )
                await bot.send_message(LOG_CHANNEL, dl_log, parse_mode=enums.ParseMode.HTML)
            except:
                pass
        if is_stream:
            disposition = f'inline; filename="{safe_name}"'
        
        # Parse Range header for pause/resume support
        range_header = req.headers.get('Range', '')
        start = 0
        end = file_size - 1
        
        if range_header and range_header.startswith('bytes='):
            range_val = range_header.replace('bytes=', '')
            parts = range_val.split('-')
            if parts[0]:
                start = int(parts[0])
            if parts[1]:
                end = int(parts[1])
            
            # Validate range
            if start >= file_size or start > end:
                return web.Response(
                    status=416,
                    headers={'Content-Range': f'bytes */{file_size}'}
                )
            
            content_length = end - start + 1
            
            response = web.StreamResponse(
                status=206,
                headers={
                    'Content-Type': content_type,
                    'Content-Disposition': disposition,
                    'Content-Length': str(content_length),
                    'Content-Range': f'bytes {start}-{end}/{file_size}',
                    'Accept-Ranges': 'bytes',
                    'Cache-Control': 'no-cache',
                    'X-Content-Type-Options': 'nosniff',
                }
            )
        else:
            # Full download
            response = web.StreamResponse(
                status=200,
                headers={
                    'Content-Type': content_type,
                    'Content-Disposition': disposition,
                    'Content-Length': str(file_size),
                    'Accept-Ranges': 'bytes',
                    'Cache-Control': 'no-cache',
                    'X-Content-Type-Options': 'nosniff',
                }
            )
        
        await response.prepare(req)
        
        # Calculate chunk offset and how many bytes to skip in first chunk
        chunk_offset = start // CHUNK_SIZE
        skip_bytes = start % CHUNK_SIZE
        bytes_sent = 0
        bytes_to_send = end - start + 1
        
        if start > 0:
            print(f"Resuming {info['name']} from {start / (1024*1024):.1f}MB...")
        else:
            print(f"Streaming {info['name']}...")
        
        async for chunk in stream_client.stream_media(msg, offset=chunk_offset):
            if bytes_sent >= bytes_to_send:
                break
            
            data = chunk
            
            # Skip bytes in first chunk if resuming mid-chunk
            if skip_bytes > 0:
                data = data[skip_bytes:]
                skip_bytes = 0
            
            # Trim last chunk if needed
            remaining = bytes_to_send - bytes_sent
            if len(data) > remaining:
                data = data[:remaining]
            
            await response.write(data)
            bytes_sent += len(data)
        
        await response.write_eof()
        print(f"✅ Streamed {info['name']} ({bytes_sent / (1024*1024):.1f}MB)")
        
        # Track download (only for full downloads)
        if start == 0:
            stats['total_downloads'] += 1
            stats['downloads_today'] += 1
            info['downloads'] = info.get('downloads', 0) + 1
            # Sync download count to DB
            if USE_DATABASE and db:
                try:
                    db.update_file_downloads(file_hash, info['downloads'])
                except:
                    pass
        
        return response
        
    except ConnectionResetError:
        print(f"⚠️ Client disconnected: {info['name']}")
        return response
    except Exception as e:
        print(f"Stream error: {e}")
        return web.Response(text=f"Error: {e}", status=500)


async def start_web():
    """Start web server"""
    app = web.Application()
    app.add_routes(routes)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    print(f"✅ Web server: {PUBLIC_URL}")


async def main():
    """Main"""
    # Load data from database on startup
    if USE_DATABASE and db:
        print("📊 Loading data from MongoDB...")
        
        # Load force channels
        channels = db.get_force_channels()
        FORCE_CHANNELS.clear()
        for ch in channels:
            username = ch.get('channel_username')
            if username:
                FORCE_CHANNELS.append(username)
        print(f"✅ Loaded {len(FORCE_CHANNELS)} force join channels")
        
        # Load banned users
        banned = db.get_banned_users()
        BANNED_USERS.clear()
        for user_data in banned:
            BANNED_USERS.add(user_data['user_id'])
        print(f"✅ Loaded {len(BANNED_USERS)} banned users")
        
        # Load link expiry setting
        try:
            expiry_setting = db.db['settings'].find_one({'key': 'link_expiry'})
            if expiry_setting:
                link_expiry['default'] = expiry_setting['value']
                exp_val = link_expiry['default']
                if exp_val == 0:
                    print("✅ Link expiry: Permanent")
                elif exp_val >= 86400:
                    print(f"✅ Link expiry: {exp_val // 86400}d")
                else:
                    print(f"✅ Link expiry: {exp_val // 3600}h")
        except:
            pass
        
        # Load all users into stats
        all_users = db.get_all_users(limit=10000)
        stats['total_users'].clear()
        for user in all_users:
            stats['total_users'].add(user['user_id'])
        
        db_stats = db.get_stats()
        stats['total_files'] = db_stats.get('total_files', 0)
        
        # Load file mappings — links survive restarts!
        saved_files = db.get_all_files()
        file_map.update(saved_files)
        print(f"✅ Loaded {len(all_users)} users, {stats['total_files']} files from DB")
        print(f"✅ Restored {len(saved_files)} active file links from DB")
    
    await start_web()
    
    await bot.start()
    await userbot.start()
    
    bot_me = await bot.get_me()
    user_me = await userbot.get_me()
    
    print(f"✅ Bot: @{bot_me.username}")
    print(f"✅ Userbot: {user_me.first_name}")
    print("✅ Ready!")
    
    # Send START message to log channel
    start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    start_msg = f"""✅ <b>BOT STARTED!</b>

🤖 <b>Bot:</b> @{bot_me.username}
👤 <b>Userbot:</b> {user_me.first_name}
🌐 <b>URL:</b> {PUBLIC_URL}

⏰ <b>Time:</b> {start_time} UTC

━━━━━━━━━━━━
⚡ <i>File To Link Bot is Online!</i>"""
    
    await bot.send_message(LOG_CHANNEL, start_msg, parse_mode=enums.ParseMode.HTML)
    
    # Start link expiry cleanup task (runs every 5 minutes)
    async def cleanup_expired_links():
        import time as _time
        while True:
            await asyncio.sleep(300)  # Check every 5 minutes
            now = _time.time()
            expired = []
            for fhash, info in list(file_map.items()):
                created = info.get('created_at', 0)
                expiry = info.get('expiry', 86400)
                # Skip permanent links (expiry = 0)
                if expiry == 0:
                    continue
                if created > 0 and (now - created) >= expiry:
                    expired.append(fhash)
            
            for fhash in expired:
                info = file_map.pop(fhash, None)
                # Remove from database too
                if USE_DATABASE and db:
                    try:
                        db.delete_file(fhash)
                    except:
                        pass
                if info:
                    name = info.get('name', 'Unknown')
                    uid = info.get('user_id')
                    expiry_val = info.get('expiry', 86400)
                    if expiry_val >= 86400:
                        exp_display = f"{expiry_val // 86400} day(s)"
                    else:
                        exp_display = f"{expiry_val // 3600} hour(s)"
                    print(f"🗑️ Expired: {name}")
                    # Notify user
                    if uid:
                        try:
                            await bot.send_message(
                                uid,
                                f"⏰ <b>Link Expired!</b>\n\n"
                                f"📄 <b>{name}</b>\n\n"
                                f"❌ Your download link has expired after {exp_display}.\n"
                                f"Send the file again to generate a new link.",
                                parse_mode=enums.ParseMode.HTML
                            )
                        except:
                            pass
    
    asyncio.get_event_loop().create_task(cleanup_expired_links())

    # Daily stats task — sends report at 12:00 AM IST (18:30 UTC) and resets counters
    async def daily_stats_report():
        from datetime import timedelta
        IST = timedelta(hours=5, minutes=30)
        while True:
            # Calculate seconds until next 12:00 AM IST (18:30 UTC)
            now_utc = datetime.utcnow()
            now_ist = now_utc + IST
            # Next midnight IST
            tomorrow_ist = (now_ist + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            next_midnight_utc = tomorrow_ist - IST
            wait_seconds = (next_midnight_utc - now_utc).total_seconds()
            if wait_seconds <= 0:
                wait_seconds += 86400  # fallback: wait a full day
            print(f"📊 Daily stats scheduled in {wait_seconds/3600:.1f}h")
            await asyncio.sleep(wait_seconds)

            # Format bytes
            b = stats['bytes_today']
            if b >= 1024 * 1024 * 1024:
                size_str = f"{b / (1024**3):.2f} GB"
            elif b >= 1024 * 1024:
                size_str = f"{b / (1024**2):.2f} MB"
            elif b >= 1024:
                size_str = f"{b / 1024:.2f} KB"
            else:
                size_str = f"{b} B"

            today_str = (datetime.utcnow() + IST - timedelta(seconds=1)).strftime('%d %b %Y')
            report = f"""📊 <b>Daily Stats — {today_str}</b>

┏━━━━━━━━━━━━━━━━━━━━
┠ 📁 <b>Files Processed:</b> {stats['files_today']}
┠ 🔗 <b>Links Generated:</b> {stats['links_today']}
┠ 📥 <b>Downloads:</b> {stats['downloads_today']}
┠ 💾 <b>Total Size:</b> {size_str}
┗━━━━━━━━━━━━━━━━━━━━

🤖 @{bot_me.username}"""

            try:
                await bot.send_message(LOG_CHANNEL, report, parse_mode=enums.ParseMode.HTML)
                print(f"📊 Daily stats sent for {today_str}")
            except Exception as e:
                print(f"❌ Failed to send daily stats: {e}")

            # Reset daily counters
            stats['files_today'] = 0
            stats['links_today'] = 0
            stats['downloads_today'] = 0
            stats['bytes_today'] = 0

    asyncio.get_event_loop().create_task(daily_stats_report())

    from pyrogram import idle
    await idle()
    
    # Send STOP message to log channel (when bot is shutting down)
    stop_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    stop_msg = f"""❌ <b>BOT STOPPED!</b>

🤖 <b>Bot:</b> @{bot_me.username}

⏰ <b>Time:</b> {stop_time} UTC

━━━━━━━━━━━━
🔴 <i>File To Link Bot is Offline!</i>"""
    
    try:
        await bot.send_message(LOG_CHANNEL, stop_msg, parse_mode=enums.ParseMode.HTML)
    except:
        pass
    
    await bot.stop()
    await userbot.stop()


if __name__ == "__main__":
    import asyncio
    asyncio.get_event_loop().run_until_complete(main())
