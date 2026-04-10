import discord
import os
import json
from dotenv import load_dotenv
from discord.ext import commands, tasks
from datetime import datetime, timedelta

# ===== LOAD ENV =====
load_dotenv()
TOKEN = os.getenv("TOKEN")

# ===== CONFIG =====
TARGET = 127
DATA_FILE = "progress.json"
ROLE_NAME = "Arabic Learner"
CHANNEL_NAME = "arabic-updates"
MAX_DAILY = 10  # anti-cheat
START_DATE = datetime(2026, 3, 30).date()  # change if your Day 1 is different

# ===== BOT SETUP =====
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!!', intents=intents)

# ===== DATA HANDLING =====
def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def get_today():
    return datetime.utcnow().date()

def get_yesterday():
    return get_today() - timedelta(days=1)

def format_date(date_obj):
    return str(date_obj)

def get_day_number():
    return (get_today() - START_DATE).days + 1

# ===== PROGRESS BAR =====
def progress_bar(percent):
    filled = int(percent // 5)
    return "█" * filled + "░" * (20 - filled)

# ===== EVENTS =====
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    daily_post.start()

# ===== COMMANDS =====

@bot.command()
async def hello(ctx):
    await ctx.send("Hello bro, I'm alive.")

# UPDATE TODAY
@bot.command()
async def updateProgress(ctx, member: discord.Member, value: float):
    today = str(get_today())
    data = load_data()

    # Role check
    if ROLE_NAME not in [role.name for role in member.roles]:
        return await ctx.send("User is not an Arabic Learner.")

    # Self update restriction
    if ctx.author != member and not ctx.author.guild_permissions.administrator:
        return await ctx.send("You can only update your own progress.")

    if value > MAX_DAILY and not ctx.author.guild_permissions.administrator:
        return await ctx.send("Value too high. Stop cheating.")

    if today not in data:
        data[today] = {}

    # Prevent multiple updates
    if str(member.id) in data[today] and not ctx.author.guild_permissions.administrator:
        return await ctx.send("You already updated today.")

    data[today][str(member.id)] = value
    save_data(data)

    await ctx.send(f"{member.mention} progress updated to {value}")

# UPDATE YESTERDAY
@bot.command()
async def updateYesterday(ctx, member: discord.Member, value: float):
    yesterday = str(get_yesterday())
    data = load_data()

    if yesterday not in data:
        return await ctx.send("No data for yesterday.")

    if ctx.author != member and not ctx.author.guild_permissions.administrator:
        return await ctx.send("Not allowed.")

    data[yesterday][str(member.id)] = value
    save_data(data)

    await ctx.send(f"{member.mention} yesterday's progress updated.")

# Shows Progress Immediately
@bot.command()
async def showProgress(ctx, date: str = None):
    data = load_data()

    # Default = today
    if date is None:
        date = str(get_today())

    if date not in data:
        return await ctx.send("No data for this date.")

    entries = []

    for user_id, value in data[date].items():
        member = ctx.guild.get_member(int(user_id))
        if not member:
            continue

        # Role filter
        if ROLE_NAME not in [role.name for role in member.roles]:
            continue

        percent = (value / TARGET) * 100
        entries.append((member, value, percent))

    if not entries:
        return await ctx.send("No valid entries found.")

    # Sort highest → lowest
    entries.sort(key=lambda x: x[2], reverse=True)

    day_number = get_day_number()

    message = f"**Progress Report**\nDay {day_number}, Date: {date}\n\n"

    for member, value, percent in entries:
        bar = progress_bar(percent)
        message += f"{member.mention} : {value}/{TARGET} ({percent:.2f}%)\n{bar}\n\n"

    await ctx.send(message)

# ===== REPORT GENERATION =====

async def generate_report(guild):
    data = load_data()
    yesterday = str(get_yesterday())

    if yesterday not in data:
        return "No data for yesterday."

    entries = []

    for user_id, value in data[yesterday].items():
        member = guild.get_member(int(user_id))
        if not member:
            continue

        percent = (value / TARGET) * 100
        entries.append((member, value, percent))

    # Sort highest → lowest
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

    # 7 AM PKT = 2 AM UTC
    if now.hour == 2 and now.minute == 0:
        for guild in bot.guilds:
            channel = discord.utils.get(guild.text_channels, name=CHANNEL_NAME)
            if channel:
                report = await generate_report(guild)
                await channel.send(report)

# ===== RUN =====
bot.run(TOKEN)