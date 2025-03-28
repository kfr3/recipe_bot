from fastapi import FastAPI, HTTPException, Request, Response, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import os
import asyncio
import multiprocessing
import logging
import json
from .recipe_client import search_recipes_by_ingredients, get_recipe_information
from .recipe_client import mock_search_recipes, mock_recipe_information  # Import mock functions
import nacl.signing
import nacl.exceptions
from dotenv import load_dotenv

# Import Kafka modules
from .kafka_config import initialize_kafka, close_kafka, send_message
from .kafka_config import RECIPE_REQUEST_TOPIC, FAVORITE_RECIPE_TOPIC
from .kafka_consumer import run_consumers

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
USE_MOCK_DATA = True

# Consumer process
consumer_process = None

@app.on_event("startup")
async def startup_event():
    """Initialize Kafka and start consumers when the app starts"""
    # Initialize Kafka producer
    kafka_available = await initialize_kafka()
    
    if kafka_available:
        # Start the consumers in a separate process
        global consumer_process
        consumer_process = multiprocessing.Process(target=run_consumers)
        consumer_process.start()
        logger.info("Kafka consumers started in separate process")
    else:
        logger.warning("Kafka is not available - running in fallback mode without Kafka")

@app.on_event("shutdown")
async def shutdown_event():
    """Close Kafka connections when the app shuts down"""
    # Close Kafka producer
    await close_kafka()
    
    # Terminate the consumer process
    if consumer_process:
        consumer_process.terminate()
        consumer_process.join()
        logger.info("Kafka consumers terminated")

@app.post("/api/discord-interactions")
async def discord_interactions(request: Request, background_tasks: BackgroundTasks):
    """Handle Discord interactions with better error handling and logging"""
    # Get the signature and timestamp from the headers
    signature = request.headers.get('X-Signature-Ed25519')
    timestamp = request.headers.get('X-Signature-Timestamp')
    
    logger.info(f"Received Discord interaction. Signature present: {bool(signature)}, Timestamp present: {bool(timestamp)}")
    
    # Get the request body as bytes
    body = await request.body()
    body_str = body.decode('utf-8', errors='replace')
    logger.info(f"Request body (truncated): {body_str[:100]}...")
    
    # Verify the request
    if not signature or not timestamp:
        logger.error("Missing signature or timestamp")
        raise HTTPException(status_code=401, detail="Invalid request signature")
    
    try:
        # In development with ngrok, you might want to skip signature verification
        # for testing. In production, always verify signatures.
        verify_signature = True
        
        if verify_signature:
            # Create a verify key using your Discord application's public key
            verify_key = nacl.signing.VerifyKey(bytes.fromhex(DISCORD_PUBLIC_KEY))
            
            # Verify the signature
            verify_key.verify(f"{timestamp}".encode() + body, bytes.fromhex(signature))
            logger.info("Signature verified successfully")
        else:
            logger.warning("Skipping signature verification (development mode)")
        
        # Parse the request body as JSON
        try:
            data = json.loads(body_str)
            logger.info(f"Interaction type: {data.get('type')}")
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            raise HTTPException(status_code=400, detail="Invalid JSON body")
        
        # Respond to Discord's ping
        if data.get("type") == 1:  # PING
            logger.info("Responding to PING with PONG")
            return {"type": 1}  # PONG
            
        # Handle slash commands
        if data.get("type") == 2:  # APPLICATION_COMMAND
            command_name = data.get("data", {}).get("name")
            logger.info(f"Handling command: {command_name}")
            
            # Handle the findrecipe command
            if command_name == "findrecipe":
                # Extract options (ingredients)
                options = data.get("data", {}).get("options", [])
                ingredients = ""
                for option in options:
                    if option.get("name") == "ingredients":
                        ingredients = option.get("value", "")
                
                user_id = data.get("member", {}).get("user", {}).get("id", "unknown")
                logger.info(f"Find recipe for user {user_id}, ingredients: {ingredients}")
                
                # Add to background tasks to process asynchronously
                # This ensures we respond to Discord quickly
                background_tasks.add_task(
                    process_recipe_request,
                    ingredients=ingredients,
                    user_id=user_id,
                    application_id=data.get("application_id"),
                    token=data.get("token")
                )
                
                # Immediate response to Discord
                logger.info("Sending deferred response")
                return {
                    "type": 5,  # DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE - "Bot is thinking..."
                }
        
        # Default response for other interaction types
        logger.warning(f"Unhandled interaction type: {data.get('type')}")
        return {
            "type": 4,
            "data": {
                "content": "Received your command, but I'm not sure how to handle it."
            }
        }
    
    except nacl.exceptions.BadSignatureError:
        logger.error("Bad signature error")
        raise HTTPException(status_code=401, detail="Invalid request signature")
    except Exception as e:
        logger.error(f"Error handling Discord interaction: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

# Function to process recipe request in background
async def process_recipe_request(ingredients: str, user_id: str, application_id: str, token: str):
    """Process a recipe request in the background with better error handling"""
    import requests
    
    logger.info(f"Background task: Processing recipe request for user {user_id}, ingredients: {ingredients}")
    
    try:
        # For faster debugging, use mock data
        # In production, set this to False
        use_mock = True
        
        if use_mock:
            from .recipe_client import mock_search_recipes, mock_recipe_information
            logger.info("Using mock data for quick response")
            recipes = await mock_search_recipes(ingredients)
            if recipes and len(recipes) > 0:
                recipe = recipes[0]
                detailed_recipe = await mock_recipe_information(recipe['id'])
            else:
                recipes = []
        else:
            # Real API call
            logger.info("Calling recipe search API")
            from .recipe_client import search_recipes_by_ingredients, get_recipe_information
            recipes = await search_recipes_by_ingredients(ingredients)
            
        if not recipes or len(recipes) == 0:
            # Send "no recipes found" response to Discord
            logger.info("No recipes found, sending response to Discord")
            send_follow_up_message(
                application_id, 
                token, 
                {"content": "No recipes found with those ingredients. Try different ingredients!"}
            )
            return
            
        recipe = recipes[0]
        if not use_mock:
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
        logger.info(f"Sending recipe response to Discord for {recipe['title']}")
        send_follow_up_message(application_id, token, response)
        
        # Also send to Kafka for analytics/logging
        await send_message(
            RECIPE_REQUEST_TOPIC, 
            {
                "user_id": user_id,
                "ingredients": ingredients,
                "recipe_id": recipe["id"],
                "action": "search_success"
            }, 
            key=user_id
        )
        
    except Exception as e:
        logger.error(f"Error processing recipe request: {e}", exc_info=True)
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
        if not app_id or not token:
            logger.error("Missing app_id or token for Discord response")
            return False
            
        url = f"https://discord.com/api/v10/webhooks/{app_id}/{token}"
        logger.info(f"Sending Discord message to URL: {url[:30]}...{url[-5:]}")
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, json=message_data, headers=headers)
        logger.info(f"Discord API response status: {response.status_code}")
        response.raise_for_status()
        logger.info("Successfully sent follow-up message to Discord")
        return True
    except Exception as e:
        logger.error(f"Error sending follow-up message to Discord: {e}", exc_info=True)
        return False

@app.post("/api/findrecipe")
async def find_recipe(request: RecipeRequest):
    """Find recipes based on provided ingredients"""
    try:
        # Send the request to Kafka for analytics
        await send_message(
            RECIPE_REQUEST_TOPIC,
            {
                "ingredients": request.ingredients,
                "user_id": request.user_id,
                "source": "api"
            },
            key=request.user_id
        )
        
        # For now, still call the API directly for the response
        if USE_MOCK_DATA:
            recipes = await mock_search_recipes(request.ingredients)
        else:
            recipes = await search_recipes_by_ingredients(request.ingredients)
        return recipes
    except Exception as e:
        logger.error(f"Error in findrecipe API: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/recipe/{recipe_id}")
async def get_recipe(recipe_id: int):
    """Get detailed information for a specific recipe"""
    try:
        # This doesn't go through Kafka since it's a simple lookup
        if USE_MOCK_DATA:
            recipe = await mock_recipe_information(recipe_id)
        else:
            recipe = await get_recipe_information(recipe_id)
        return recipe
    except Exception as e:
        logger.error(f"Error getting recipe details: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# In-memory storage for favorite recipes
favorite_recipes = {}

@app.post("/api/favorites/add")
async def add_favorite(recipe_data: Dict[str, Any], user_id: str):
    """Save a recipe to user's favorites"""
    try:
        if user_id not in favorite_recipes:
            favorite_recipes[user_id] = []
        
        # Check if recipe already exists in favorites
        if not any(recipe["id"] == recipe_data["id"] for recipe in favorite_recipes[user_id]):
            favorite_recipes[user_id].append(recipe_data)
        
        # Send favorite event to Kafka
        await send_message(
            FAVORITE_RECIPE_TOPIC,
            {
                "user_id": user_id,
                "recipe_id": recipe_data["id"],
                "recipe_title": recipe_data.get("title", "Unknown Recipe"),
                "action": "add"
            },
            key=user_id
        )
        
        return {"status": "success", "message": "Recipe added to favorites"}
    except Exception as e:
        logger.error(f"Error adding favorite: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/favorites/{user_id}")
async def get_favorites(user_id: str):
    """Get a user's favorite recipes"""
    try:
        if user_id not in favorite_recipes:
            return []
        return favorite_recipes[user_id]
    except Exception as e:
        logger.error(f"Error getting favorites: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# Health check endpoint
@app.get("/health")
async def health_check():
    """Simple health check endpoint"""
    return {"status": "healthy", "message": "API is running", "kafka_enabled": True}