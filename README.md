# 🔗 File Stream Bot

A powerful Telegram bot that converts files to direct download links with streaming support up to 2GB.

## ✨ Features

- 📁 **File Streaming** - Stream files up to 2GB
- 🔗 **Direct Links** - Generate instant download links
- 🔒 **Force Join** - Require users to join channels
- 🚫 **Ban System** - Ban/unban users
- 📊 **Statistics** - Track usage and downloads
- 📢 **Broadcast** - Send announcements to all users
- ⚙️ **Admin Panel** - Manage bot via commands
- 🎨 **Beautiful UI** - HTML formatted messages with buttons

## 🚀 Deployment

### Requirements

- Python 3.8+
- Telegram API credentials
- Telegram Bot Token
- Pyrogram session string

### Installation

1. Clone repository:
```bash
git clone <your-repo-url>
cd file-stream-bot
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment:
```bash
cp .env.example .env
nano .env
```

4. Fill in your credentials in `.env`

5. Run bot:
```bash
python3 stream-bot-public.py
```

## ⚙️ Configuration

Create a `.env` file with these variables:

```env
API_ID=your_api_id
API_HASH=your_api_hash
BOT_TOKEN=your_bot_token
SESSION_STRING=your_session_string
LOG_CHANNEL=-1001234567890
PUBLIC_URL=https://your-domain.com
PORT=8080
ADMIN_IDS=123456789,987654321
```

### Getting Credentials

**API_ID & API_HASH:**
- Go to https://my.telegram.org
- Login and create an app
- Copy API ID and API Hash

**BOT_TOKEN:**
- Talk to [@BotFather](https://t.me/BotFather)
- Create new bot
- Copy the token

**SESSION_STRING:**
- Run `python3 generate_session.py`
- Follow the prompts
- Copy the session string

**LOG_CHANNEL:**
- Create a private channel
- Add bot as admin
- Get channel ID (use @username_to_id_bot)

## 📝 Admin Commands

- `/addchannel @channel` - Add force join channel
- `/removechannel @channel` - Remove channel
- `/listchannels` - List all channels
- `/ban user_id` - Ban a user
- `/unban user_id` - Unban a user
- `/banlist` - Show banned users
- `/stats` - View statistics
- `/broadcast <message>` - Broadcast to all users

## 👥 User Commands

- `/start` - Start the bot
- `/stats` - View bot statistics
- Send any file - Get download link

## 🌐 Deployment Options

### Render

1. Push to GitHub
2. Create new Web Service on Render
3. Connect repository
4. Add environment variables
5. Deploy!

### Railway

1. Push to GitHub
2. Create new project on Railway
3. Add environment variables
4. Deploy!

### VPS

1. Clone repository
2. Install requirements
3. Create `.env` file
4. Run with `python3 stream-bot-public.py`
5. Use screen/tmux to keep running

## 🔐 Security

- Never commit `.env` file
- Keep credentials secret
- Use strong admin passwords
- Regularly update dependencies

## 📦 Requirements

```
pyrogram
tgcrypto
aiohttp
```

## 🤝 Support

For issues or questions, contact: @zeus_is_here

## ⚡ Credits

Created by Zeus

## 📄 License

Free to use and modify
