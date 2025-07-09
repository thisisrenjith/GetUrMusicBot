import os
from yt_dlp import YoutubeDL
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

BOT_TOKEN = os.getenv("BOT_TOKEN")

search_results = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎵 Send a YouTube link or type the name of a song to search and download it as MP3.")

def search_youtube(query):
    ydl_opts = {'quiet': True, 'skip_download': True}
    with YoutubeDL(ydl_opts) as ydl:
        search_url = f"ytsearch5:{query}"
        info = ydl.extract_info(search_url, download=False)
        return info['entries']

def download_audio(youtube_url):
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': 'downloads/%(title)s.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True,
    }

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(youtube_url, download=True)
        title = ydl.prepare_filename(info)
        mp3_file = title.replace(".webm", ".mp3").replace(".m4a", ".mp3")
        return mp3_file

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    user_id = str(update.effective_user.id)

    if "youtube.com" in query or "youtu.be" in query:
        await update.message.reply_text("⏳ Downloading...")
        try:
            os.makedirs("downloads", exist_ok=True)
            mp3_path = download_audio(query)
            await update.message.reply_audio(audio=open(mp3_path, 'rb'))
            os.remove(mp3_path)
        except Exception as e:
            await update.message.reply_text(f"⚠️ Error: {str(e)}")
    else:
        await update.message.reply_text(f"🔍 Searching YouTube for: {query}")
        try:
            results = search_youtube(query)
            search_results[user_id] = results
            buttons = [
                [InlineKeyboardButton(f"{i+1}. {r['title'][:40]}", callback_data=str(i))]
                for i, r in enumerate(results)
            ]
            reply_markup = InlineKeyboardMarkup(buttons)
            await update.message.reply_text("Select a video to download:", reply_markup=reply_markup)
        except Exception as e:
            await update.message.reply_text(f"⚠️ Error while searching: {str(e)}")

async def handle_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    index = int(query.data)
    user_id = str(query.from_user.id)

    if user_id not in search_results:
        await query.edit_message_text("⚠️ Search session expired. Please try again.")
        return

    try:
        video = search_results[user_id][index]
        url = video['webpage_url']
        title = video['title']
        await query.edit_message_text(f"🎯 Selected: {title}
⏳ Downloading...")
        mp3_path = download_audio(url)
        await query.message.reply_audio(audio=open(mp3_path, 'rb'))
        os.remove(mp3_path)
    except Exception as e:
        await query.edit_message_text(f"⚠️ Error during download: {str(e)}")

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_selection))
    print("Bot is running...")
    app.run_polling()
