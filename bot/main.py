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
        # Call FastAPI backend with a separate async function to avoid blocking
        async def fetch_recipes():
            try:
                # Set a timeout for the request
                response = requests.post(
                    f"{FASTAPI_URL}/api/findrecipe",
                    json={"ingredients": ingredients, "user_id": str(interaction.user.id)},
                    timeout=30  # Increase timeout to allow for OpenAI processing
                )
                response.raise_for_status()
                return response.json()
            except requests.exceptions.Timeout:
                print("Request to FastAPI timed out")
                return None
            except Exception as e:
                print(f"Error in fetch_recipes: {e}")
                return None
        
        # Run the fetch in a non-blocking way
        recipes = await asyncio.to_thread(fetch_recipes)
        
        if not recipes:
            await interaction.followup.send("The recipe search timed out or no recipes were found. Please try again with different ingredients.")
            return
        
        # Format and send the first recipe
        recipe = recipes[0]  # Get the first recipe
        
        # Get detailed recipe information with a separate async function
        async def fetch_recipe_details():
            try:
                detailed_response = requests.get(
                    f"{FASTAPI_URL}/api/recipe/{recipe['id']}",
                    timeout=30
                )
                detailed_response.raise_for_status()
                return detailed_response.json()
            except Exception as e:
                print(f"Error fetching recipe details: {e}")
                return None
        
        # Run the details fetch in a non-blocking way
        detailed_recipe = await asyncio.to_thread(fetch_recipe_details)
        
        embed = discord.Embed(
            title=recipe["title"],
            description=f"Uses {recipe.get('usedIngredientCount', 0)} of your ingredients",
            color=discord.Color.green()
        )
        
        if "image" in recipe:
            embed.set_thumbnail(url=recipe["image"])
        
        # Handle missing ingredients - could be in different formats
        missing_ingredients = recipe.get("missedIngredients", [])
        missing_ingredient_text = "None"
        
        if missing_ingredients:
            # Handle both potential formats
            if isinstance(missing_ingredients[0], dict) and "name" in missing_ingredients[0]:
                missing_ingredient_text = ", ".join([ing["name"] for ing in missing_ingredients])
            elif isinstance(missing_ingredients, list) and all(isinstance(item, str) for item in missing_ingredients):
                missing_ingredient_text = ", ".join(missing_ingredients)
        
        embed.add_field(name="Missing Ingredients", value=missing_ingredient_text, inline=False)
        
        if detailed_recipe and "instructions" in detailed_recipe:
            # Truncate instructions if too long
            instructions = detailed_recipe["instructions"]
            if len(instructions) > 1024:
                instructions = instructions[:1021] + "..."
            embed.add_field(name="Instructions", value=instructions, inline=False)
        else:
            embed.add_field(name="Instructions", value="Instructions not available", inline=False)
        
        # Add recipe ID to footer for later reference
        embed.set_footer(text=f"Recipe ID: {recipe['id']} | React with 👍 to save this recipe to your favorites")
        
        # Send the follow-up message with the embed
        message = await interaction.followup.send(embed=embed)
        
        # Add the reaction
        await message.add_reaction("👍")
        
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