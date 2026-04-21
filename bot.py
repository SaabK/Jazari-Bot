import discord
import os
import sqlite3
from dotenv import load_dotenv
from discord.ext import commands, tasks
from datetime import datetime, timedelta

# =========================
# LOAD ENV
# =========================
load_dotenv()
TOKEN = os.getenv("TOKEN")

# =========================
# CONFIG
# =========================
TARGET = 127
ROLE_NAME = "Arabic Learner"
CHANNEL_NAME = "arabic-updates"
MAX_DAILY = 10
START_DATE = datetime(2026, 3, 30).date()

# =========================
# SQLITE SETUP
# =========================
DB_FILE = "progress.db"

conn = sqlite3.connect(DB_FILE, check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS progress (
    date TEXT,
    user_id TEXT,
    value REAL,
    PRIMARY KEY (date, user_id)
)
""")

conn.commit()

# =========================
# BOT SETUP
# =========================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!!", intents=intents)

# =========================
# HELPERS
# =========================
def format_date(date_obj):
    return date_obj.strftime("%d-%m-%Y")

def get_today():
    return datetime.utcnow().date()

def get_yesterday():
    return get_today() - timedelta(days=1)

def get_day_number(date_obj):
    return (date_obj - START_DATE).days + 1

def progress_bar(percent):
    filled = int(percent // 5)
    return "█" * filled + "░" * (20 - filled)

# =========================
# READY EVENT
# =========================
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    daily_post.start()

# =====================================================
# UPDATE COMMAND
# =====================================================
@bot.command()
async def update(ctx, *args):

    member = ctx.author
    date = format_date(get_today())
    value = None

    # CASE 1: !!update 4.5
    if len(args) == 1:
        try:
            value = float(args[0])
        except:
            return await ctx.send("Invalid number format.")

    # CASE 2: !!update today/yesterday 4.5
    elif len(args) == 2:
        key = args[0].lower()

        try:
            value = float(args[1])
        except:
            return await ctx.send("Invalid number format.")

        if key == "yesterday":
            date = format_date(get_yesterday())
        elif key == "today":
            date = format_date(get_today())
        else:
            return await ctx.send("Use: today or yesterday")

    # CASE 3: ADMIN update others
    elif len(args) == 3:
        if not ctx.author.guild_permissions.administrator:
            return await ctx.send("Admin only.")

        if len(ctx.message.mentions) == 0:
            return await ctx.send("Mention a user.")

        member = ctx.message.mentions[0]
        key = args[1].lower()

        try:
            value = float(args[2])
        except:
            return await ctx.send("Invalid number format.")

        if key == "yesterday":
            date = format_date(get_yesterday())
        elif key == "today":
            date = format_date(get_today())
        else:
            return await ctx.send("Use: today or yesterday")

    else:
        return await ctx.send("Invalid usage.")

    # ROLE CHECK
    if ROLE_NAME not in [role.name for role in member.roles]:
        return await ctx.send("User is not an Arabic Learner.")

    # ANTI-CHEAT
    if value > MAX_DAILY and not ctx.author.guild_permissions.administrator:
        return await ctx.send("Value too high.")

    # SAVE
    cursor.execute("""
    INSERT OR REPLACE INTO progress (date, user_id, value)
    VALUES (?, ?, ?)
    """, (date, str(member.id), value))

    conn.commit()

    await ctx.send(f"{member.mention} updated for {date} → {value}")

# =====================================================
# SHOW PROGRESS
# =====================================================
@bot.command()
async def showProgress(ctx, date: str = None):

    if date is None:
        date_obj = get_today()
        date = format_date(date_obj)
    else:
        try:
            date_obj = datetime.strptime(date, "%d-%m-%Y").date()
        except:
            return await ctx.send("Use DD-MM-YYYY format.")

    entries = []

    for member in ctx.guild.members:
        if ROLE_NAME not in [role.name for role in member.roles]:
            continue

        cursor.execute("""
        SELECT value FROM progress WHERE date = ? AND user_id = ?
        """, (date, str(member.id)))

        row = cursor.fetchone()

        value = row[0] if row else 0
        percent = (value / TARGET) * 100

        entries.append((member, value, percent))

    if not entries:
        return await ctx.send("No data.")

    entries.sort(key=lambda x: x[2], reverse=True)

    message = f"**Progress Report**\nDay {get_day_number(date_obj)}, Date: {date}\n\n"

    for member, value, percent in entries:
        bar = progress_bar(percent)
        message += f"{member.mention} : {value}/{TARGET} ({percent:.2f}%)\n{bar}\n\n"

    await ctx.send(message)

# =====================================================
# GENERATE REPORT (YESTERDAY)
# =====================================================
async def generate_report(guild):

    yesterday_date = get_yesterday()
    yesterday = format_date(yesterday_date)

    entries = []

    for member in guild.members:
        if ROLE_NAME not in [role.name for role in member.roles]:
            continue

        cursor.execute("""
        SELECT value FROM progress WHERE date = ? AND user_id = ?
        """, (yesterday, str(member.id)))

        row = cursor.fetchone()

        value = row[0] if row else 0
        percent = (value / TARGET) * 100

        entries.append((member, value, percent))

    if not entries:
        return "No data."

    entries.sort(key=lambda x: x[2], reverse=True)

    message = f"**Day {get_day_number(yesterday_date)} Progress**\n"
    message += f"Date: {yesterday}\n\n"

    for member, value, percent in entries:
        bar = progress_bar(percent)
        message += f"{member.mention} : {value}/{TARGET} ({percent:.2f}%)\n{bar}\n\n"

    return message

# =====================================================
# DAILY POST
# =====================================================
@tasks.loop(minutes=1)
async def daily_post():
    now = datetime.utcnow()

    if now.hour == 5 and now.minute == 0:
        for guild in bot.guilds:
            channel = discord.utils.get(guild.text_channels, name=CHANNEL_NAME)
            if channel:
                report = await generate_report(guild)
                await channel.send(report)

# =========================
# RUN
# =========================
bot.run(TOKEN)