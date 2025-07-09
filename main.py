import os
import re
import time
import shutil
import logging
import traceback
from pathlib import Path
from slugify import slugify
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

from yt_dlp import YoutubeDL
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.error import RetryAfter

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Logging Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GetUrMusicBot")

# Configs
executor = ThreadPoolExecutor()
DOWNLOAD_DIR = Path("downloads")
YOUTUBE_REGEX = r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+"
user_last_command = {}
command_cooldown = 10  # seconds

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎵 Welcome to GetUrMusicBot Pro V3!
Send a YouTube link or type a song name.
Use /help or /cancel anytime.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💡 Usage Guide:
- Send a YouTube link to download MP3
"
        "- Type a song name to search
"
        "- Use /cancel to stop
"
        "- Audio will include title & artist when available")

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Cancelled current action. You can start again anytime.")

def check_ffmpeg():
    if not shutil.which("ffmpeg"):
        raise EnvironmentError("❌ FFmpeg not installed. Please contact admin.")

def clean_old_downloads():
    if not DOWNLOAD_DIR.exists():
        return
    now = time.time()
    for f in DOWNLOAD_DIR.glob("*.mp3"):
        if now - f.stat().st_mtime > 1800:  # 30 mins
            f.unlink(missing_ok=True)

def search_youtube(query):
    check_ffmpeg()
    ydl_opts = {'quiet': True, 'skip_download': True}
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"ytsearch5:{query}", download=False)
        return [entry for entry in info.get('entries', []) if entry]

def download_audio(url, safe_title=None):
    check_ffmpeg()
    unique_stamp = str(int(time.time()))
    safe_folder = DOWNLOAD_DIR / f"{safe_title or 'track'}-{unique_stamp}"
    safe_folder.mkdir(parents=True, exist_ok=True)

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{safe_folder}/%(title)s.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True,
    }

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        if info.get("is_live"):
            raise Exception("⚠️ Livestreams not supported.")
        title = slugify(info.get("title", "audio"))
        audio_path = next(safe_folder.glob("*.mp3"), None)
        return audio_path, info

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.message.text.strip()
        user_id = update.effective_user.id

        now = datetime.utcnow()
        if (now - user_last_command.get(user_id, now - timedelta(seconds=20))).total_seconds() < command_cooldown:
            await update.message.reply_text("⏳ Please wait before trying again.")
            return
        user_last_command[user_id] = now

        if re.match(YOUTUBE_REGEX, query):
            await update.message.reply_text("⏬ Downloading from YouTube...")
            try:
                DOWNLOAD_DIR.mkdir(exist_ok=True)
                clean_old_downloads()
                mp3_path, info = await context.application.run_in_executor(executor, download_audio, query)
                if not mp3_path or not mp3_path.exists():
                    raise Exception("Download failed. Try another link.")

                if mp3_path.stat().st_size > 48 * 1024 * 1024:
                    await update.message.reply_text("⚠️ File too large for Telegram. Try a shorter video.")
                    mp3_path.unlink(missing_ok=True)
                    return

                with mp3_path.open('rb') as f:
                    await update.message.reply_audio(
                        audio=InputFile(f),
                        title=info.get("title", "Unknown Title"),
                        performer=info.get("uploader", "Unknown Artist")
                    )
            except Exception as e:
                logger.error(traceback.format_exc())
                await update.message.reply_text(f"❌ Error:
{traceback.format_exc()}")
            finally:
                try:
                    if mp3_path and mp3_path.exists():
                        mp3_path.unlink(missing_ok=True)
                        mp3_path.parent.rmdir()
                except Exception:
                    pass
        else:
            if len(query) < 3:
                await update.message.reply_text("❗ Please enter a longer search.")
                return

            await update.message.reply_text(f"🔍 Searching: {query}")
            results = await context.application.run_in_executor(executor, search_youtube, query)
            if not results:
                await update.message.reply_text("❌ No results found.")
                return

            context.user_data['search_results'] = results
            buttons = [
                [InlineKeyboardButton(f"{i+1}. {r['title'][:40]}", callback_data=str(i))]
                for i, r in enumerate(results)
            ]
            await update.message.reply_text("Choose a video to convert:", reply_markup=InlineKeyboardMarkup(buttons))

    except RetryAfter as e:
        await update.message.reply_text(f"🚫 Too many requests. Try again in {e.retry_after} sec.")
    except Exception as e:
        logger.error(traceback.format_exc())
        await update.message.reply_text(f"❌ Error:
{traceback.format_exc()}")

async def handle_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        index = int(query.data)
        results = context.user_data.get('search_results', [])
        if not results or index >= len(results):
            await query.edit_message_text("⚠️ Session expired or invalid choice.")
            return

        video = results[index]
        url = video.get("webpage_url")
        title = video.get("title", "Selected Track")

        if not url:
            await query.edit_message_text("⚠️ This video cannot be downloaded.")
            return

        await query.edit_message_text(f"🎧 Selected: {title}
⏬ Converting to MP3...")

        DOWNLOAD_DIR.mkdir(exist_ok=True)
        clean_old_downloads()
        mp3_path, info = await context.application.run_in_executor(executor, download_audio, url, slugify(title))

        if not mp3_path or not mp3_path.exists():
            raise Exception("Download failed.")

        if mp3_path.stat().st_size > 48 * 1024 * 1024:
            await query.message.reply_text("⚠️ File too large to send.")
            mp3_path.unlink(missing_ok=True)
            return

        with mp3_path.open('rb') as f:
            await query.message.reply_audio(
                audio=InputFile(f),
                title=info.get("title", "Audio"),
                performer=info.get("uploader", "Unknown Artist")
            )
    except Exception as e:
        logger.error(traceback.format_exc())
        await query.message.reply_text(f"❌ Error during conversion:
{traceback.format_exc()}")
    finally:
        try:
            if mp3_path and mp3_path.exists():
                mp3_path.unlink(missing_ok=True)
                mp3_path.parent.rmdir()
        except Exception:
            pass

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("cancel", cancel_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_selection))
    print("🚀 GetUrMusicBot Pro V3 (Debugger 2.0 Fixes Applied) is running...")
    app.run_polling()
