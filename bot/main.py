import os
import discord
from discord import app_commands
from discord.ext import commands
import requests
import json
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
    await interaction.response.defer(thinking=True)
    
    try:
        # Call FastAPI backend
        response = requests.post(
            f"{FASTAPI_URL}/api/findrecipe",
            json={"ingredients": ingredients, "user_id": str(interaction.user.id)}
        )
        response.raise_for_status()
        recipes = response.json()
        
        if not recipes:
            await interaction.followup.send("No recipes found with those ingredients. Try different ingredients!")
            return
        
        # Format and send the first recipe
        recipe = recipes[0]  # Get the first recipe
        
        embed = discord.Embed(
            title=recipe["title"],
            description=f"Uses {recipe['usedIngredientCount']} of your ingredients",
            color=discord.Color.green()
        )
        
        if "image" in recipe:
            embed.set_thumbnail(url=recipe["image"])
        
        embed.add_field(name="Missing Ingredients", value=", ".join([ing["name"] for ing in recipe.get("missedIngredients", [])]), inline=False)
        
        # Get detailed recipe information
        detailed_recipe = requests.get(
            f"{FASTAPI_URL}/api/recipe/{recipe['id']}"
        ).json()
        
        if "instructions" in detailed_recipe:
            # Truncate instructions if too long
            instructions = detailed_recipe["instructions"]
            if len(instructions) > 1024:
                instructions = instructions[:1021] + "..."
            embed.add_field(name="Instructions", value=instructions, inline=False)
        
        # Add recipe ID to footer for later reference
        embed.set_footer(text=f"Recipe ID: {recipe['id']} | React with 👍 to save this recipe to your favorites")
        
        message = await interaction.followup.send(embed=embed)
        await message.add_reaction("👍")
        
    except Exception as e:
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