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
    c.execute("""CREATE TABLE IF NOT EXISTS user_state (
        user_id INTEGER PRIMARY KEY,
        state TEXT,
        data TEXT
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

def set_state(user_id: int, state: str, data: str = ""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO user_state (user_id, state, data) VALUES (?, ?, ?)",
              (user_id, state, data))
    conn.commit()
    conn.close()

def get_state(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT state, data FROM user_state WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row if row else (None, None)

def clear_state(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM user_state WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

# ============================================
# AI GENERATOR (OpenAI)
# ============================================
def generate_statuses(topic: str, mood: str = "neutral", count: int = 5) -> list:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return [f"[DEV MODE — no OpenAI key] {topic} ({mood}) — would be a great status"] * count
    try:
        client = OpenAI(api_key=api_key)
        prompt = (
            f"Generate {count} short WhatsApp status ideas (1-2 sentences each) about: {topic}. "
            f"Mood: {mood}. Make them punchy, original, suitable for small business owners in Lagos. "
            f"Mix styles: 1 promotional, 1 motivational, 1 question, 1 tip, 1 bold statement. "
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
# FLASK WEB SERVER
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
    "/generate — AI writes 5 statuses (interactive ✨)\n"
    "/drafts — see your saved drafts\n"
    "/schedule — schedule a post\n"
    "/today — see today's schedule\n"
    "/platforms — toggle platforms\n"
    "/help — all commands"
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
        "3. Show up at 3 AM tomorrow.",
        parse_mode="Markdown"
    )

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👑 *Royal Butler Pro*\n\n"
        "Built by Royalty, powered by Mira + OpenAI.\n"
        "Built on iPhone 8. Because greatness doesn't wait for better tools.",
        parse_mode="Markdown"
    )

# ============ INTERACTIVE GENERATE FLOW ============
async def generate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 1: ask for topic."""
    user_id = update.effective_user.id
    set_state(user_id, "awaiting_topic")
    # mood quick-pick buttons (sent alongside the prompt)
    await update.message.reply_text(
        "🤖 *AI Status Generator*\n\n"
        "*Step 1 of 2:* What's your status about?\n\n"
        "Type your topic below — e.g. `my new bakery opening`, `client retention`, `monday motivation`.\n\n"
        "💡 _Or pick a quick category first:_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏪 My Business", callback_data="topic_business"),
             InlineKeyboardButton("💪 Motivation", callback_data="topic_motivation")],
            [InlineKeyboardButton("💡 Tips / Value", callback_data="topic_tips"),
             InlineKeyboardButton("🎉 Promo / Offer", callback_data="topic_promo")],
            [InlineKeyboardButton("❓ Question / Engage", callback_data="topic_question"),
             InlineKeyboardButton("🔥 Bold Statement", callback_data="topic_bold")],
        ])
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    data = query.data

    # ----- Topic quick-pick -----
    if data.startswith("topic_"):
        topic_map = {
            "topic_business": "my small business in Lagos, what makes it special and why customers should care",
            "topic_motivation": "monday motivation and entrepreneurial mindset for hustlers building something",
            "topic_tips": "a useful tip or piece of value for small business owners or entrepreneurs",
            "topic_promo": "a special promotion, offer, or call-to-action for my customers",
            "topic_question": "an engaging question to spark conversation with my audience",
            "topic_bold": "a bold, attention-grabbing statement about business, hustle, or ambition",
        }
        topic = topic_map[data]
        set_state(user_id, "awaiting_mood", topic)
        await query.edit_message_text(
            f"✅ Topic: *{topic}*\n\n"
            f"*Step 2 of 2:* Pick a mood:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔥 Excited", callback_data="mood_excited"),
                 InlineKeyboardButton("💼 Professional", callback_data="mood_professional")],
                [InlineKeyboardButton("😄 Funny", callback_data="mood_funny"),
                 InlineKeyboardButton("💪 Bold", callback_data="mood_bold")],
                [InlineKeyboardButton("🤝 Helpful", callback_data="mood_helpful"),
                 InlineKeyboardButton("🤫 Mysterious", callback_data="mood_mysterious")],
            ])
        )
        return

    # ----- Mood quick-pick → run generation -----
    if data.startswith("mood_"):
        state, topic = get_state(user_id)
        if not topic:
            await query.edit_message_text("⚠️ Session expired. Run /generate again.")
            return
        mood = data.replace("mood_", "")
        clear_state(user_id)
        await query.edit_message_text(f"🤖 Generating 5 statuses...\n\nTopic: *{topic}*\nMood: *{mood}*", parse_mode="Markdown")
        ideas = generate_statuses(topic, mood, 5)
        for idea in ideas:
            save_draft(user_id, idea, "ai")
        msg = "✨ *AI generated these for you:*\n\n"
        for i, idea in enumerate(ideas, 1):
            clean = idea
            if len(clean) > 3 and clean[0].isdigit() and clean[1] == ".":
                clean = clean[2:].strip()
            msg += f"{i}. {clean}\n\n"
        msg += "All saved to /drafts. Use /schedule to post one."
        await query.message.reply_text(msg, parse_mode="Markdown")
        return

    # ----- Platforms toggle -----
    if data.startswith("toggle_"):
        platform = data.replace("toggle_", "").upper()
        await query.edit_message_text(f"🔧 Toggled: {platform}\n\n(Real toggles coming Day 4.)")
        return

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Catch free-text input when user is in a state."""
    user_id = update.effective_user.id
    state, data = get_state(user_id)
    if not state:
        return  # not in a flow, ignore

    text = update.message.text.strip()

    if state == "awaiting_topic":
        set_state(user_id, "awaiting_mood", text)
        await update.message.reply_text(
            f"✅ Topic: *{text}*\n\n*Step 2 of 2:* Pick a mood:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔥 Excited", callback_data="mood_excited"),
                 InlineKeyboardButton("💼 Professional", callback_data="mood_professional")],
                [InlineKeyboardButton("😄 Funny", callback_data="mood_funny"),
                 InlineKeyboardButton("💪 Bold", callback_data="mood_bold")],
                [InlineKeyboardButton("🤝 Helpful", callback_data="mood_helpful"),
                 InlineKeyboardButton("🤫 Mysterious", callback_data="mood_mysterious")],
            ])
        )

    elif state == "awaiting_mood":
        # user typed a mood instead of clicking a button
        topic = data
        clear_state(user_id)
        await update.message.reply_text(f"🤖 Generating 5 statuses...\n\nTopic: *{topic}*\nMood: *{text}*", parse_mode="Markdown")
        ideas = generate_statuses(topic, text, 5)
        for idea in ideas:
            save_draft(user_id, idea, "ai")
        msg = "✨ *AI generated these for you:*\n\n"
        for i, idea in enumerate(ideas, 1):
            clean = idea
            if len(clean) > 3 and clean[0].isdigit() and clean[1] == ".":
                clean = clean[2:].strip()
            msg += f"{i}. {clean}\n\n"
        msg += "All saved to /drafts. Use /schedule to post one."
        await update.message.reply_text(msg, parse_mode="Markdown")

# ============ OTHER COMMANDS ============
async def drafts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = list_drafts(update.effective_user.id, limit=10)
    if not rows:
        await update.message.reply_text("📭 No drafts yet. Try `/generate` to get started.", parse_mode="Markdown")
        return
    msg = "📝 *Your drafts (latest 10):*\n\n"
    for r in rows:
        draft_id, content, source, created = r
        clean = content
        if len(clean) > 3 and clean[0].isdigit() and clean[1] == ".":
            clean = clean[2:].strip()
        msg += f"`#{draft_id}` [{source}] {clean}\n\n"
    msg += "\n_Next: /schedule to post one to WhatsApp + X._"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📅 *Schedule a post*\n\nComing tomorrow (Day 2).", parse_mode="Markdown")

async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📅 Today's schedule — coming Day 5.")

async def platforms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("✅ WhatsApp", callback_data="toggle_whatsapp"),
         InlineKeyboardButton("✅ X (Twitter)", callback_data="toggle_x")],
    ]
    await update.message.reply_text(
        "📡 *Active platforms (v1):*\n\nTap to toggle on/off.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

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
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        print(">>> [bot thread] handlers registered, polling...", flush=True)
        app.run_polling()
    except Exception as e:
        print(f">>> [bot thread] CRASHED: {e}", flush=True)
        traceback.print_exc()

if __name__ == "__main__":
    web_thread = threading.Thread(target=run_web, daemon=True)
    web_thread.start()
    run_bot()