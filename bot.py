import discord
import os
import sqlite3
from dotenv import load_dotenv
from discord.ext import commands, tasks
from datetime import datetime, timedelta

# ===== LOAD ENV =====
load_dotenv()
TOKEN = os.getenv("TOKEN")

# ===== CONFIG =====
TARGET = 127
ROLE_NAME = "Arabic Learner"
CHANNEL_NAME = "arabic-updates"
MAX_DAILY = 10
START_DATE = datetime(2026, 3, 30).date()

# ===== SQLITE SETUP =====
DB_FILE = "progress.db"

conn = sqlite3.connect(DB_FILE)
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

# ===== BOT SETUP =====
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!!', intents=intents)

# ===== HELPERS =====
def get_today():
    return datetime.utcnow().date()

def get_yesterday():
    return get_today() - timedelta(days=1)

def get_day_number():
    return (get_today() - START_DATE).days + 1

def progress_bar(percent):
    filled = int(percent // 5)
    return "█" * filled + "░" * (20 - filled)

# ===== EVENTS =====
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    daily_post.start()

# ===== COMMANDS =====

@bot.command()
async def hello(ctx):
    await ctx.send("Hello bro, I'm alive.")

# ===== UPDATE TODAY =====
@bot.command()
async def updateProgress(ctx, member: discord.Member, value: float):
    today = str(get_today())

    if ROLE_NAME not in [role.name for role in member.roles]:
        return await ctx.send("User is not an Arabic Learner.")

    if ctx.author != member and not ctx.author.guild_permissions.administrator:
        return await ctx.send("You can only update your own progress.")

    if value > MAX_DAILY and not ctx.author.guild_permissions.administrator:
        return await ctx.send("Value too high. Stop cheating.")

    cursor.execute("""
    INSERT OR REPLACE INTO progress (date, user_id, value)
    VALUES (?, ?, ?)
    """, (today, str(member.id), value))

    conn.commit()

    await ctx.send(f"{member.mention} progress updated to {value}")

# ===== UPDATE YESTERDAY =====
@bot.command()
async def updateYesterday(ctx, member: discord.Member, value: float):
    yesterday = str(get_yesterday())

    if ROLE_NAME not in [role.name for role in member.roles]:
        return await ctx.send("User is not an Arabic Learner.")

    if ctx.author != member and not ctx.author.guild_permissions.administrator:
        return await ctx.send("Not allowed.")

    cursor.execute("""
    INSERT OR REPLACE INTO progress (date, user_id, value)
    VALUES (?, ?, ?)
    """, (yesterday, str(member.id), value))

    conn.commit()

    await ctx.send(f"{member.mention} yesterday's progress updated.")

# ===== SHOW PROGRESS =====
@bot.command()
async def showProgress(ctx, date: str = None):
    if date is None:
        date = str(get_today())

    cursor.execute("""
    SELECT user_id, value FROM progress WHERE date = ?
    """, (date,))

    rows = cursor.fetchall()

    entries = []

    for user_id, value in rows:
        member = ctx.guild.get_member(int(user_id))
        if not member:
            continue

        if ROLE_NAME not in [role.name for role in member.roles]:
            continue

        percent = (value / TARGET) * 100
        entries.append((member, value, percent))

    if not entries:
        return await ctx.send("No data for this date.")

    entries.sort(key=lambda x: x[2], reverse=True)

    day_number = get_day_number()

    message = f"**Progress Report**\nDay {day_number}, Date: {date}\n\n"

    for member, value, percent in entries:
        bar = progress_bar(percent)
        message += f"{member.mention} : {value}/{TARGET} ({percent:.2f}%)\n{bar}\n\n"

    await ctx.send(message)

# ===== REPORT GENERATION =====
async def generate_report(guild):
    yesterday = str(get_yesterday())

    cursor.execute("""
    SELECT user_id, value FROM progress WHERE date = ?
    """, (yesterday,))

    rows = cursor.fetchall()

    if not rows:
        return "No data for yesterday."

    entries = []

    for user_id, value in rows:
        member = guild.get_member(int(user_id))
        if not member:
            continue

        percent = (value / TARGET) * 100
        entries.append((member, value, percent))

    entries.sort(key=lambda x: x[2], reverse=True)

    day_number = get_day_number()

    message = f"**Day {day_number} Progress**\n"
    message += f"Date: {yesterday}\n\n"

    for member, value, percent in entries:
        bar = progress_bar(percent)
        message += f"{member.mention} : {value}/{TARGET} ({percent:.2f}%)\n{bar}\n\n"

    return message

# ===== DAILY AUTO POST =====
@tasks.loop(minutes=1)
async def daily_post():
    now = datetime.utcnow()

    # 8 AM PKT = 3 AM UTC
    if now.hour == 3 and now.minute == 0:
        for guild in bot.guilds:
            channel = discord.utils.get(guild.text_channels, name=CHANNEL_NAME)
            if channel:
                report = await generate_report(guild)
                await channel.send(report)

# ===== RUN =====
bot.run(TOKEN)