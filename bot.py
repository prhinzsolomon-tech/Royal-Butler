import os
import random
import sqlite3
import threading
import traceback
from datetime import datetime
from flask import Flask
from openai import OpenAI
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, CallbackQueryHandler, filters

print(">>> bot.py starting up...", flush=True)

# ============================================
# DATABASE (SQLite) — drafts + schedules
# ============================================
DB_PATH = "royalbutler.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS drafts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        content TEXT,
        source TEXT,
        created_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS schedules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        content TEXT,
        platforms TEXT,
        fire_at TEXT,
        status TEXT DEFAULT 'pending'
    )""")
    conn.commit()
    conn.close()
    print(">>> [db] initialized", flush=True)

def save_draft(user_id: int, content: str, source: str = "ai"):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO drafts (user_id, content, source, created_at) VALUES (?, ?, ?, ?)",
              (user_id, content, source, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

def list_drafts(user_id: int, limit: int = 10):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, content, source, created_at FROM drafts WHERE user_id = ? ORDER BY id DESC LIMIT ?",
              (user_id, limit))
    rows = c.fetchall()
    conn.close()
    return rows

# ============================================
# AI GENERATOR (OpenAI)
# ============================================
def generate_statuses(topic: str, mood: str = "neutral", count: int = 5) -> list:
    """Generate `count` status ideas using OpenAI."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return [f"[DEV MODE — no OpenAI key set] {topic} ({mood}) — would be a great status"]
    try:
        client = OpenAI(api_key=api_key)
        prompt = (
            f"Generate {count} short WhatsApp status ideas (1-2 sentences each) about: {topic}. "
            f"Mood: {mood}. Make them punchy, original, suitable for small business owners in Lagos. "
            f"Include a mix of styles: 1 promotional, 1 motivational, 1 question, 1 tip, 1 bold statement. "
            f"Number them 1-{count}. No hashtags unless relevant."
        )
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
        )
        text = resp.choices[0].message.content
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        return lines[:count]
    except Exception as e:
        print(f">>> [ai] error: {e}", flush=True)
        return [f"[AI error] {e}"]

# ============================================
# FLASK WEB SERVER (keeps Render free-tier alive)
# ============================================
app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "👑 Royalty's Butler Pro is alive!"

# ============================================
# TELEGRAM BOT HANDLERS
# ============================================
WELCOME = (
    "👑 *Royal Butler Pro*\n\n"
    "Your AI content engine for WhatsApp + social media.\n\n"
    "*What I can do:*\n"
    "/generate topic:coffee, mood:excited — AI writes 5 statuses\n"
    "/drafts — see your saved drafts\n"
    "/schedule — schedule a post (coming tomorrow)\n"
    "/today — see today's schedule\n"
    "/platforms — toggle platforms (WhatsApp / X)\n"
    "/help — all commands\n\n"
    "Try: `/generate topic:my bakery opening, mood:proud`"
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME, parse_mode="Markdown")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME, parse_mode="Markdown")

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
        "🎯 *Today's focus:*\n\n"
        "1. Build, don't scroll.\n"
        "2. Send the pitch.\n"
        "3. Show up at 3 AM tomorrow.\n\n"
        "— Royalty's Bot 🤖",
        parse_mode="Markdown"
    )

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👑 *Royal Butler Pro*\n\n"
        "Built by Royalty, powered by Mira + OpenAI.\n"
        "Built on iPhone 8. Because greatness doesn't wait for better tools."
    , parse_mode="Markdown")

async def generate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /generate topic:your topic, mood:mood"""
    args = " ".join(context.args) if context.args else ""
    topic = ""
    mood = "neutral"
    if "topic:" in args:
        try:
            after = args.split("topic:", 1)[1]
            if "mood:" in after:
                topic_part, mood_part = after.split("mood:", 1)
                topic = topic_part.strip().rstrip(",").strip()
                mood = mood_part.strip().rstrip(",").strip()
            else:
                topic = after.strip()
        except Exception:
            pass
    if not topic:
        await update.message.reply_text(
            "⚠️ *Usage:*\n"
            "`/generate topic:my new coffee shop, mood:excited`\n\n"
            "Mood options: excited, professional, funny, bold, proud, helpful, mysterious",
            parse_mode="Markdown"
        )
        return
    await update.message.reply_text(f"🤖 Generating 5 statuses on *{topic}* (mood: {mood})...", parse_mode="Markdown")
    ideas = generate_statuses(topic, mood, 5)
    # save them all as drafts
    for idea in ideas:
        save_draft(update.effective_user.id, idea, "ai")
    msg = "✨ *AI generated these for you:*\n\n"
    for i, idea in enumerate(ideas, 1):
        msg += f"{i}. {idea}\n\n"
    msg += "All saved to your /drafts. Use /schedule to send one to WhatsApp + X."
    await update.message.reply_text(msg, parse_mode="Markdown")

async def drafts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = list_drafts(update.effective_user.id, limit=10)
    if not rows:
        await update.message.reply_text("📭 No drafts yet. Try `/generate topic:your business, mood:excited`", parse_mode="Markdown")
        return
    msg = "📝 *Your drafts (latest 10):*\n\n"
    for r in rows:
        draft_id, content, source, created = r
        # strip leading "1. " if AI numbered them
        clean = content
        if len(clean) > 3 and clean[0].isdigit() and clean[1] == ".":
            clean = clean[2:].strip()
        msg += f"`#{draft_id}` [{source}] {clean}\n\n"
    msg += "\n_Next: /schedule to post one to WhatsApp + X._"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📅 *Schedule a post*\n\n"
        "Coming tomorrow (Day 2 of build).\n\n"
        "For now, generate + save drafts with /generate.",
        parse_mode="Markdown"
    )

async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📅 Today's schedule — coming Day 5.")

async def platforms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("✅ WhatsApp", callback_data="toggle_whatsapp"),
         InlineKeyboardButton("✅ X (Twitter)", callback_data="toggle_x")],
    ]
    await update.message.reply_text(
        "📡 *Active platforms (v1):*\n\n"
        "Tap to toggle on/off.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(text=f"🔧 Toggled: {query.data}\n\n(Platform toggles coming Day 4.)")

# ============================================
# RUN
# ============================================
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
        init_db()
        app = ApplicationBuilder().token(token).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", help_cmd))
        app.add_handler(CommandHandler("quote", quote))
        app.add_handler(CommandHandler("goal", goal))
        app.add_handler(CommandHandler("about", about))
        app.add_handler(CommandHandler("generate", generate))
        app.add_handler(CommandHandler("drafts", drafts))
        app.add_handler(CommandHandler("schedule", schedule))
        app.add_handler(CommandHandler("today", today))
        app.add_handler(CommandHandler("platforms", platforms))
        app.add_handler(CallbackQueryHandler(button_handler))
        print(">>> [bot thread] handlers registered, polling...", flush=True)
        app.run_polling()
    except Exception as e:
        print(f">>> [bot thread] CRASHED: {e}", flush=True)
        traceback.print_exc()

if __name__ == "__main__":
    web_thread = threading.Thread(target=run_web, daemon=True)
    web_thread.start()
    run_bot()