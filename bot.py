import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()  # Load token from .env file

TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Define intents - required in the latest version of discord.py
intents = discord.Intents.default()
intents.typing = False  # Disable unneeded intents to improve performance
intents.presences = False
intents.messages = True  # Allow bot to read messages if necessary for certain commands

bot = commands.Bot(command_prefix="/", intents=intents)  # Pass the intents here

@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user}")

@bot.command()
async def hello(ctx):
    await ctx.send("Hello! This is a basic bot setup.")

bot.run(TOKEN)


