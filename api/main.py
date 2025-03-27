from fastapi import FastAPI, HTTPException, Request, Response, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import os
import asyncio
from .recipe_client import search_recipes_by_ingredients, get_recipe_information
from .recipe_client import mock_search_recipes, mock_recipe_information  # Import mock functions
import nacl.signing
import nacl.exceptions
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

app = FastAPI()

# Define the request model
class RecipeRequest(BaseModel):
    ingredients: str
    user_id: str

# Discord public key from the Developer Portal
DISCORD_PUBLIC_KEY = os.getenv("DISCORD_PUBLIC_KEY")

# Set this to True to use mock data for faster testing
USE_MOCK_DATA = False

@app.post("/api/discord-interactions")
async def discord_interactions(request: Request, background_tasks: BackgroundTasks):
    # Get the signature and timestamp from the headers
    signature = request.headers.get('X-Signature-Ed25519')
    timestamp = request.headers.get('X-Signature-Timestamp')
    
    # Get the request body as bytes
    body = await request.body()
    
    # Verify the request
    if not signature or not timestamp:
        raise HTTPException(status_code=401, detail="Invalid request signature")
    
    try:
        # Create a verify key using your Discord application's public key
        verify_key = nacl.signing.VerifyKey(bytes.fromhex(DISCORD_PUBLIC_KEY))
        
        # Verify the signature
        verify_key.verify(f"{timestamp}".encode() + body, bytes.fromhex(signature))
        
        # Parse the request body as JSON
        data = await request.json()
        
        # Respond to Discord's ping
        if data.get("type") == 1:  # PING
            return {"type": 1}  # PONG
            
        # Handle slash commands
        if data.get("type") == 2:  # APPLICATION_COMMAND
            command_name = data.get("data", {}).get("name")
            
            # Handle the findrecipe command
            if command_name == "findrecipe":
                # Extract options (ingredients)
                options = data.get("data", {}).get("options", [])
                ingredients = ""
                for option in options:
                    if option.get("name") == "ingredients":
                        ingredients = option.get("value", "")
                
                user_id = data.get("member", {}).get("user", {}).get("id", "unknown")
                
                # We need to respond quickly to Discord
                # Return a loading message immediately, then process in background
                background_tasks.add_task(
                    process_recipe_request, 
                    ingredients=ingredients, 
                    user_id=user_id,
                    application_id=data.get("application_id"),
                    token=data.get("token")
                )
                
                # Immediate response to Discord
                return {
                    "type": 5,  # DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE - "Bot is thinking..."
                }
        
        # Default response for other interaction types
        return {
            "type": 4,
            "data": {
                "content": "Received your command, but I'm not sure how to handle it."
            }
        }
    
    except nacl.exceptions.BadSignatureError:
        raise HTTPException(status_code=401, detail="Invalid request signature")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

# Function to process recipe request in background
async def process_recipe_request(ingredients: str, user_id: str, application_id: str, token: str):
    import requests
    
    try:
        # Choose between mock data or real API
        if USE_MOCK_DATA:
            recipes = await mock_search_recipes(ingredients)
            recipe = recipes[0]
            detailed_recipe = await mock_recipe_information(recipe['id'])
        else:
            # Real API call
            recipes = await search_recipes_by_ingredients(ingredients)
            if not recipes or len(recipes) == 0:
                # Send "no recipes found" response to Discord
                send_follow_up_message(
                    application_id, 
                    token, 
                    {"content": "No recipes found with those ingredients. Try different ingredients!"}
                )
                return
                
            recipe = recipes[0]
            detailed_recipe = await get_recipe_information(recipe['id'])
        
        # Format instructions
        instructions = detailed_recipe.get("instructions", "No instructions available.")
        if len(instructions) > 1800:  # Discord has a 2000 char limit
            instructions = instructions[:1800] + "..."
        
        # Handle missing ingredients
        missing_ingredients = recipe.get("missedIngredients", [])
        missing_ingredient_text = "None"
        if missing_ingredients:
            # Handle both formats OpenAI might return
            if isinstance(missing_ingredients[0], dict) and "name" in missing_ingredients[0]:
                missing_ingredient_text = ", ".join([ing["name"] for ing in missing_ingredients])
            elif isinstance(missing_ingredients, list) and all(isinstance(item, str) for item in missing_ingredients):
                missing_ingredient_text = ", ".join(missing_ingredients)
        
        # Create the response
        response = {
            "embeds": [
                {
                    "title": recipe["title"],
                    "description": f"Uses {recipe.get('usedIngredientCount', 0)} of your ingredients",
                    "color": 3066993,  # Green color
                    "thumbnail": {"url": recipe.get("image", "")},
                    "fields": [
                        {
                            "name": "Missing Ingredients",
                            "value": missing_ingredient_text,
                            "inline": False
                        },
                        {
                            "name": "Instructions",
                            "value": instructions,
                            "inline": False
                        }
                    ],
                    "footer": {
                        "text": f"Recipe ID: {recipe['id']} | React with 👍 to save this recipe to your favorites"
                    }
                }
            ]
        }
        
        # Send the follow-up message to Discord
        send_follow_up_message(application_id, token, response)
        
    except Exception as e:
        print(f"Error processing recipe request: {e}")
        # Send error message to Discord
        send_follow_up_message(
            application_id, 
            token, 
            {"content": f"Error finding recipes: {str(e)}"}
        )

def send_follow_up_message(app_id, token, message_data):
    """Send a follow-up message to Discord"""
    import requests
    
    try:
        url = f"https://discord.com/api/v10/webhooks/{app_id}/{token}"
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, json=message_data, headers=headers)
        response.raise_for_status()
        print("Successfully sent follow-up message to Discord")
    except Exception as e:
        print(f"Error sending follow-up message to Discord: {e}")

# In-memory storage for favorite recipes
favorite_recipes = {}

@app.post("/api/findrecipe")
async def find_recipe(request: RecipeRequest):
    """Find recipes based on provided ingredients"""
    try:
        # Choose between mock data or real API
        if USE_MOCK_DATA:
            recipes = await mock_search_recipes(request.ingredients)
        else:
            # Real API call
            recipes = await search_recipes_by_ingredients(request.ingredients)
        return recipes
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/recipe/{recipe_id}")
async def get_recipe(recipe_id: int):
    """Get detailed information for a specific recipe"""
    try:
        # Choose between mock data or real API
        if USE_MOCK_DATA:
            recipe = await mock_recipe_information(recipe_id)
        else:
            # Real API call
            recipe = await get_recipe_information(recipe_id)
        return recipe
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/favorites/add")
async def add_favorite(recipe_data: Dict[str, Any], user_id: str):
    """Save a recipe to user's favorites"""
    if user_id not in favorite_recipes:
        favorite_recipes[user_id] = []
    
    # Check if recipe already exists in favorites
    if not any(recipe["id"] == recipe_data["id"] for recipe in favorite_recipes[user_id]):
        favorite_recipes[user_id].append(recipe_data)
    
    return {"status": "success", "message": "Recipe added to favorites"}

@app.get("/api/favorites/{user_id}")
async def get_favorites(user_id: str):
    """Get a user's favorite recipes"""
    if user_id not in favorite_recipes:
        return []
    return favorite_recipes[user_id]

# Health check endpoint
@app.get("/health")
async def health_check():
    """Simple health check endpoint"""
    return {"status": "healthy", "message": "API is running"}