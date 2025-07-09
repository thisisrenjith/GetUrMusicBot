# GetUrMusic Bot 🎵

GetUrMusic is a Telegram bot that lets you download any YouTube music video as an MP3 by either:

- Sending a **YouTube link** directly
- Typing a **song name** and selecting from the top 5 matching results

## 🚀 Features

- 🎧 Convert YouTube to MP3
- 🔍 Smart search with result selection
- ⚡ Fast downloads using yt-dlp
- 🛠️ Deployable on Render with `.render.yaml`

## 🔧 Setup (Locally or on Render)

### 1. Requirements

- Python 3.8+
- FFmpeg
- yt-dlp
- python-telegram-bot==20.3

### 2. Environment Variable

Set your Telegram bot token using:
```
BOT_TOKEN=your_token_here
```

### 3. Run Locally

```bash
pip install -r requirements.txt
python main.py
```

### 4. Deploy on Render

- Push this repo to GitHub
- Connect Render and create a new **Web Service**
- Render auto-detects `.render.yaml` and sets up everything

## 📂 Project Structure

```
.
├── main.py              # Telegram bot logic
├── requirements.txt     # Python dependencies
├── .render.yaml         # Render deployment config
└── README.md            # You're reading it!
```

---

Built with ❤️ by [@thisisrenjith](https://github.com/thisisrenjith)
