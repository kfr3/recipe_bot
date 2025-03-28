import os
import discord
from discord import app_commands
from discord.ext import commands
import requests
import json
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Bot setup
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
BOT_PREFIX = "!"
FASTAPI_URL = "http://localhost:8000"  # Your FastAPI server URL

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
bot = commands.Bot(command_prefix=BOT_PREFIX, intents=intents)

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

# Define the slash command
@bot.tree.command(name="findrecipe", description="Find recipes based on ingredients")
async def find_recipe(interaction: discord.Interaction, ingredients: str):
    # Defer the response immediately to prevent timeout
    await interaction.response.defer(thinking=True)
    print(f"Received request for ingredients: {ingredients}")
    
    try:
        # Call FastAPI backend
        # With Kafka, we don't need to wait for the response
        # The API will send the request to Kafka and respond when it's ready
        response = requests.post(
            f"{FASTAPI_URL}/api/discord-interactions",
            json={
                "type": 2,  # APPLICATION_COMMAND
                "data": {
                    "name": "findrecipe",
                    "options": [
                        {
                            "name": "ingredients",
                            "value": ingredients
                        }
                    ]
                },
                "member": {
                    "user": {
                        "id": str(interaction.user.id)
                    }
                },
                "application_id": bot.user.id,
                "token": interaction.token
            },
            headers={
                "X-Signature-Ed25519": "dummy-signature",  # These won't be verified here
                "X-Signature-Timestamp": "dummy-timestamp"  # They're for documentation
            }
        )
        
        # The response is handled by Kafka consumers in the background
        # We just need to wait for the webhook response from FastAPI
        await interaction.followup.send("Looking for recipes... Please wait.")
        
    except Exception as e:
        print(f"Error in find_recipe command: {e}")
        await interaction.followup.send(f"Error finding recipes: {str(e)}")

@bot.event
async def on_reaction_add(reaction, user):
    # Ignore bot's own reactions
    if user.id == bot.user.id:
        return
    
    # Check if the reaction is 👍 on a recipe message
    if str(reaction.emoji) == "👍" and reaction.message.author.id == bot.user.id:
        try:
            # Extract recipe data from the embed
            embed = reaction.message.embeds[0]
            recipe_title = embed.title
            
            # Extract recipe ID from footer
            footer_text = embed.footer.text
            recipe_id = None
            if "Recipe ID:" in footer_text:
                recipe_id = footer_text.split("Recipe ID:")[1].split("|")[0].strip()
            
            if recipe_id:
                response = requests.get(f"{FASTAPI_URL}/api/recipe/{recipe_id}")
                recipe_data = response.json()
                
                requests.post(
                    f"{FASTAPI_URL}/api/favorites/add",
                    json=recipe_data,
                    params={"user_id": str(user.id)}
                )
                
                # Notify the user
                await user.send(f"Added '{recipe_title}' to your favorites!")
        except Exception as e:
            print(f"Error saving favorite: {e}")

# Only run the bot when this file is executed directly
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)