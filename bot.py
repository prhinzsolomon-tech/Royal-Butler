import os
import random
import asyncio
import threading
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

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

def run_bot():
    token = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("quote", quote))
    app.add_handler(CommandHandler("goal", goal))
    app.add_handler(CommandHandler("about", about))
    app.run_polling()

if __name__ == "__main__":
    # Start the Telegram bot in a separate thread
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    # Run the web server in the main thread (Render needs this)
    port = int(os.getenv("PORT", 10000))
    app_web.run(host="0.0.0.0", port=port)