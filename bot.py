import os
import random
import threading
import traceback
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

print(">>> bot.py starting up...", flush=True)

app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "👑 Royalty's Bot is alive!"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔥 Yo Royalty! Your bot is live.\n\n"
        "Try:\n"
        "/quote — motivation\n"
        "/goal — daily focus\n"
        "/about — who built me"
    )

async def quote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    quotes = [
        "Discipline is choosing what you want most over what you want now.",
        "The best time to plant a tree was 20 years ago. The second best time is now.",
        "You don't have to be great to start, but you have to start to be great.",
        "Royalty doesn't rush. He builds."
    ]
    await update.message.reply_text("💡 " + random.choice(quotes))

async def goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎯 Today's focus:\n\n"
        "1. Build, don't scroll.\n"
        "2. Send the pitch.\n"
        "3. Show up at 3 AM tomorrow.\n\n"
        "— Royalty's Bot 🤖"
    )

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👑 Royalty's First Bot\n\n"
        "Built by Royalty, powered by Mira.\n"
        "Built on iPhone 8. Because greatness doesn't wait for better tools."
    )

def run_web():
    try:
        port = int(os.getenv("PORT", 10000))
        print(f">>> [web thread] starting Flask on port {port}...", flush=True)
        app_web.run(host="0.0.0.0", port=port, use_reloader=False)
    except Exception as e:
        print(f">>> [web thread] error: {e}", flush=True)
        traceback.print_exc()

def run_bot():
    try:
        print(">>> [bot thread] starting...", flush=True)
        token = os.getenv("BOT_TOKEN")
        if not token:
            print(">>> [bot thread] ERROR: BOT_TOKEN is missing!", flush=True)
            return
        print(f">>> [bot thread] token found (length: {len(token)})", flush=True)
        app = ApplicationBuilder().token(token).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("quote", quote))
        app.add_handler(CommandHandler("goal", goal))
        app.add_handler(CommandHandler("about", about))
        print(">>> [bot thread] handlers registered, polling...", flush=True)
        app.run_polling()
    except Exception as e:
        print(f">>> [bot thread] CRASHED: {e}", flush=True)
        traceback.print_exc()

if __name__ == "__main__":
    # Start Flask in a thread so it doesn't block
    web_thread = threading.Thread(target=run_web, daemon=True)
    web_thread.start()
    # Run the bot in the main process (has its own event loop)
    run_bot()