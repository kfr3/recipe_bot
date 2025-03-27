from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import os
from .recipe_client import search_recipes_by_ingredients, get_recipe_information
import nacl.signing
import nacl.exceptions
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI()

# Define the request model - IMPORTANT: This needs to be defined BEFORE using it
class RecipeRequest(BaseModel):
    ingredients: str
    user_id: str

# Your Discord public key from the Developer Portal
DISCORD_PUBLIC_KEY = os.getenv("DISCORD_PUBLIC_KEY")

@app.post("/api/discord-interactions")
async def discord_interactions(request: Request):
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
                
                # Call the recipe search function
                try:
                    # Use ingredients directly instead of RecipeRequest
                    recipes = await search_recipes_by_ingredients(ingredients)
                    
                    if not recipes:
                        return {
                            "type": 4,  # CHANNEL_MESSAGE_WITH_SOURCE
                            "data": {
                                "content": "No recipes found with those ingredients. Try different ingredients!"
                            }
                        }
                    
                    # Format the response
                    recipe = recipes[0]  # Get the first recipe
                    
                    # Get detailed recipe info
                    detailed_recipe = await get_recipe_information(recipe['id'])
                    
                    # Format instructions
                    instructions = detailed_recipe.get("instructions", "No instructions available.")
                    if len(instructions) > 1800:  # Discord has a 2000 char limit
                        instructions = instructions[:1800] + "..."
                    
                    # Create the response
                    response = {
                        "type": 4,  # CHANNEL_MESSAGE_WITH_SOURCE
                        "data": {
                            "embeds": [
                                {
                                    "title": recipe["title"],
                                    "description": f"Uses {recipe.get('usedIngredientCount', 0)} of your ingredients",
                                    "color": 3066993,  # Green color
                                    "thumbnail": {"url": recipe.get("image", "")},
                                    "fields": [
                                        {
                                            "name": "Missing Ingredients",
                                            "value": ", ".join([ing["name"] for ing in recipe.get("missedIngredients", [])]) or "None",
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
                    }
                    
                    return response
                    
                except Exception as e:
                    return {
                        "type": 4,  # CHANNEL_MESSAGE_WITH_SOURCE
                        "data": {
                            "content": f"Error finding recipes: {str(e)}"
                        }
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

# In-memory storage for favorite recipes (will be replaced with Kafka in Sprint 3)
favorite_recipes = {}

@app.post("/api/findrecipe")
async def find_recipe(request: RecipeRequest):
    """Find recipes based on provided ingredients"""
    try:
        # Call the Spoonacular API
        recipes = await search_recipes_by_ingredients(request.ingredients)
        return recipes
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/recipe/{recipe_id}")
async def get_recipe(recipe_id: int):
    """Get detailed information for a specific recipe"""
    try:
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