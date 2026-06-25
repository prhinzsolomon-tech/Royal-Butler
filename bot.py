
```
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

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
        "Discipline is choosing what you want most over what you want now. — Abraham Lincoln",
        "The best time to plant a tree was 20 years ago. The second best time is now.",
        "You don't have to be great to start, but you have to start to be great.",
        "Small daily improvements are the key to staggering long-term results.",
        "Royalty doesn't rush. He builds."
    ]
    import random
    await update.message.reply_text("💡 " + random.choice(quotes))

async def goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎯 Today's focus:\n\n"
        "1. Build, don't scroll.\n"
        "2. Send the pitch.\n"
        "3. No gambling.\n"
        "4. Show up at 3 AM tomorrow too.\n\n"
        "— Royalty's Bot 🤖"
    )

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👑 Royalty's First Bot\n\n"
        "Built by Royalty, powered by Mira.\n"
        "Built on iPhone 8. Because greatness doesn't wait for better tools."
    )

if __name__ == "__main__":
    token = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("quote", quote))
    app.add_handler(CommandHandler("goal", goal))
    app.add_handler(CommandHandler("about", about))
    app.print_bot_info()
    app.run_polling()
```