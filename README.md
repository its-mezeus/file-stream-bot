<p align="center">
  <img src="https://img.icons8.com/3d-fluency/94/lightning-bolt--v2.png" width="80"/>
</p>

<h1 align="center">⚡ File To Link Bot</h1>

<p align="center">
  <b>A powerful Telegram bot that converts any file into a direct download & streaming link — up to 2GB!</b>
</p>

<p align="center">
  <a href="https://t.me/Filetolinkzeus_bot"><img src="https://img.shields.io/badge/Try%20Now-Bot-blue?style=for-the-badge&logo=telegram&logoColor=white" alt="Bot"></a>
  <a href="https://t.me/botsproupdates"><img src="https://img.shields.io/badge/Updates-Channel-green?style=for-the-badge&logo=telegram&logoColor=white" alt="Channel"></a>
  <a href="https://t.me/ZEUS_IS_HERE2"><img src="https://img.shields.io/badge/Contact-Owner-red?style=for-the-badge&logo=telegram&logoColor=white" alt="Owner"></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.8+-3776AB?style=flat-square&logo=python&logoColor=white"/>
  <img src="https://img.shields.io/badge/Pyrogram-2.x-orange?style=flat-square"/>
  <img src="https://img.shields.io/badge/License-Free-brightgreen?style=flat-square"/>
  <img src="https://img.shields.io/badge/Maintained-Yes-success?style=flat-square"/>
  <img src="https://img.shields.io/github/stars/its-mezeus/file-stream-bot?style=flat-square&color=yellow"/>
</p>

---

## ✨ Features

<table>
<tr>
<td>

🚀 **Core**
- 📁 Stream files up to **2GB**
- 🔗 Instant direct download links
- ▶️ Online video player (watch in browser)
- 📱 MX Player & PLAYit integration
- ⏳ Auto-expire links after 24h

</td>
<td>

🛡️ **Admin**
- 🔒 Force join channels
- 🚫 Ban/Unban system
- 📢 Broadcast to all users
- 📩 Send message to specific user
- ⏸️ Maintenance mode with auto-resume

</td>
</tr>
<tr>
<td>

📊 **Analytics**
- 📈 Real-time statistics
- 📊 Daily stats report at midnight IST
- 👤 New user notifications
- 📝 Feedback system
- 💾 MongoDB persistence

</td>
<td>

🎨 **UI/UX**
- 🌐 Beautiful download landing page
- ⏱️ 15s countdown with progress bar
- 🎬 Built-in video player page
- 💰 Ad integration support
- 📱 Mobile responsive design

</td>
</tr>
</table>

---

## 🖼️ Preview

<details>
<summary><b>📱 Click to see Bot Interface</b></summary>
<br>

**Start Menu** — Clean welcome with admin panel button

**Link Generated** — File info + download + watch online buttons

**Download Page** — Branded landing page with countdown timer

**Video Player** — Stream any format directly in browser

</details>

---

## 🚀 Quick Deploy

### 📋 Prerequisites

| Requirement | How to Get |
|---|---|
| **API_ID & API_HASH** | [my.telegram.org](https://my.telegram.org) → Create App |
| **BOT_TOKEN** | [@BotFather](https://t.me/BotFather) → `/newbot` |
| **SESSION_STRING** | Run `python3 quick_session.py` |
| **LOG_CHANNEL** | Create channel → Add bot as admin → Get ID |
| **MongoDB** | [mongodb.com](https://www.mongodb.com/atlas) → Free cluster |

### ⚡ One-Click Deploy

```bash
# Clone
git clone https://github.com/its-mezeus/file-stream-bot.git
cd file-stream-bot

# Install
pip install -r requirements.txt

# Configure
cp .env.example .env
nano .env  # Fill in your credentials

# Run
python3 stream-bot-public.py
```

### 🐳 Environment Variables

```env
API_ID=your_api_id
API_HASH=your_api_hash
BOT_TOKEN=your_bot_token
SESSION_STRING=your_session_string
LOG_CHANNEL=-100xxxxxxxxxx
DATABASE_URL=mongodb+srv://user:pass@cluster.mongodb.net/
PUBLIC_URL=https://your-domain.com
PORT=8080
ADMIN_IDS=123456789
```

---

## 🎮 Commands

<details>
<summary><b>👑 Admin Commands</b></summary>

| Command | Description |
|---|---|
| `/addchannel @name` | Add force join channel |
| `/removechannel @name` | Remove force join channel |
| `/listchannels` | List all force channels |
| `/clearall` | Remove all force channels |
| `/ban <user_id>` | Ban a user |
| `/unban <user_id>` | Unban a user |
| `/banlist` | Show banned users |
| `/broadcast <msg>` | Send to all users |
| `/sendto <id> <msg>` | Message specific user |
| `/stats` | Detailed statistics |
| `/off [minutes]` | Maintenance mode |
| `/on` | Resume from maintenance |
| `/restart` | Restart the bot |

</details>

<details>
<summary><b>👥 User Commands</b></summary>

| Command | Description |
|---|---|
| `/start` | Start the bot |
| `/stats` | View bot statistics |
| `/ping` | Check response time |
| `/feedback <msg>` | Send feedback to admin |
| **Send any file** | Get instant download link |

</details>

---

## 📊 Daily Stats

The bot automatically sends a daily report to the log channel at **12:00 AM IST** every night:

```
📊 Daily Stats — 27 Apr 2026

┏━━━━━━━━━━━━━━━━━━━━
┠ 📁 Files Processed: 142
┠ 🔗 Links Generated: 142
┠ 📥 Downloads: 89
┠ 💾 Total Size: 2.34 GB
┗━━━━━━━━━━━━━━━━━━━━

🤖 @Filetolinkzeus_bot
```

---

## 🏗️ Architecture

```
file-stream-bot/
├── stream-bot-public.py   # Main bot + web server
├── database.py            # MongoDB operations
├── templates/
│   └── download.html      # Download page template
├── requirements.txt
├── .env                   # Config (not committed)
└── README.md
```

**How it works:**
1. User sends a file to the bot
2. Bot forwards file to log channel for persistence
3. Generates a unique hash and creates download link
4. Web server streams file directly from Telegram on demand
5. Supports range requests (pause/resume/seek)

---

## 🌐 Deployment Options

<details>
<summary><b>🖥️ VPS (Recommended)</b></summary>

```bash
# Use screen/tmux to keep running
screen -S filebot
python3 stream-bot-public.py

# Detach: Ctrl+A, D
# Reattach: screen -r filebot
```

Use **Cloudflare Tunnel** for HTTPS without port forwarding:
```bash
cloudflared tunnel --url http://localhost:8080
```

</details>

<details>
<summary><b>🚂 Railway</b></summary>

1. Fork this repo
2. Create new project on [Railway](https://railway.app)
3. Connect your GitHub repo
4. Add environment variables
5. Deploy!

</details>

<details>
<summary><b>🎨 Render</b></summary>

1. Fork this repo
2. Create Web Service on [Render](https://render.com)
3. Connect repo → Add env vars → Deploy

</details>

---

## 🔐 Security

- ⚠️ Never commit `.env` — it's in `.gitignore`
- 🔑 Keep `SESSION_STRING` and `BOT_TOKEN` secret
- 🛡️ Only trusted users should be `ADMIN_IDS`
- 🔄 Links auto-expire after 24 hours
- 🚫 Built-in ban system for abuse prevention

---

## 🤝 Support & Credits

<p align="center">
  <a href="https://t.me/botsproupdates"><img src="https://img.shields.io/badge/Updates-Channel-blue?style=for-the-badge&logo=telegram" alt="Channel"></a>
  <a href="https://t.me/ZEUS_IS_HERE2"><img src="https://img.shields.io/badge/Developer-Zeus%20⚡-gold?style=for-the-badge" alt="Developer"></a>
</p>

<p align="center">
  <b>Made with ❤️ by Zeus ⚡</b><br>
  <i>Star ⭐ this repo if you found it useful!</i>
</p>

---

<p align="center">
  <img src="https://img.shields.io/badge/Telegram-Bot-blue?logo=telegram&logoColor=white"/>
  <img src="https://img.shields.io/badge/Powered%20By-Pyrogram-orange"/>
  <img src="https://img.shields.io/badge/Database-MongoDB-green?logo=mongodb&logoColor=white"/>
</p>
