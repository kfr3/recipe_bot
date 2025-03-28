import asyncio
import json
import requests
import logging
from .kafka_config import create_consumer, send_message
from .kafka_config import RECIPE_REQUEST_TOPIC, RECIPE_RESPONSE_TOPIC
from .recipe_client import search_recipes_by_ingredients, get_recipe_information, mock_search_recipes, mock_recipe_information

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Set to True to use mock data for faster testing and debugging
USE_MOCK_DATA = True

async def recipe_request_consumer():
    """Consumer for recipe requests"""
    consumer = await create_consumer(RECIPE_REQUEST_TOPIC, "recipe-processor-group")
    if not consumer:
        logger.error("Failed to create recipe request consumer")
        return
    
    logger.info(f"Starting recipe request consumer on topic {RECIPE_REQUEST_TOPIC}")
    
    try:
        async for msg in consumer:
            logger.info(f"Received recipe request: {msg.value}")
            # Process the recipe request
            try:
                # Extract data from the message
                ingredients = msg.value.get("ingredients", "")
                user_id = msg.value.get("user_id", "unknown")
                interaction_token = msg.value.get("token")
                application_id = msg.value.get("application_id")
                
                logger.info(f"Processing request for user {user_id} with ingredients: {ingredients}")
                
                # Use mock data for quicker responses during testing
                if USE_MOCK_DATA:
                    logger.info("Using mock data for faster response")
                    recipes = await mock_search_recipes(ingredients)
                    if recipes and len(recipes) > 0:
                        recipe = recipes[0]
                        detailed_recipe = await mock_recipe_information(recipe['id'])
                    else:
                        recipes = []
                else:
                    # Real API call
                    logger.info("Calling recipe search API")
                    recipes = await search_recipes_by_ingredients(ingredients)
                    
                if not recipes or len(recipes) == 0:
                    # No recipes found
                    logger.info("No recipes found")
                    response_data = {
                        "status": "no_recipes",
                        "message": "No recipes found with those ingredients. Try different ingredients!",
                        "token": interaction_token,
                        "application_id": application_id,
                        "user_id": user_id
                    }
                    
                    # Send directly to Discord (bypass Kafka for faster response)
                    logger.info("Sending 'no recipes' response directly to Discord")
                    discord_payload = {
                        "content": "No recipes found with those ingredients. Try different ingredients!"
                    }
                    send_discord_response(application_id, interaction_token, discord_payload)
                else:
                    # Get detailed information for the first recipe
                    recipe = recipes[0]
                    logger.info(f"Found recipe: {recipe['title']}")
                    
                    if USE_MOCK_DATA:
                        detailed_recipe = await mock_recipe_information(recipe['id'])
                    else:
                        detailed_recipe = await get_recipe_information(recipe['id'])
                    
                    # Format instructions
                    instructions = detailed_recipe.get("instructions", "No instructions available.")
                    if len(instructions) > 1800:  # Discord has a 2000 char limit
                        instructions = instructions[:1800] + "..."
                    
                    # Handle missing ingredients
                    missing_ingredients = recipe.get("missedIngredients", [])
                    missing_ingredient_text = "None"
                    if missing_ingredients:
                        # Handle both formats
                        if isinstance(missing_ingredients[0], dict) and "name" in missing_ingredients[0]:
                            missing_ingredient_text = ", ".join([ing["name"] for ing in missing_ingredients])
                        elif isinstance(missing_ingredients, list) and all(isinstance(item, str) for item in missing_ingredients):
                            missing_ingredient_text = ", ".join(missing_ingredients)
                    
                    # Send directly to Discord (bypass Kafka for faster response)
                    logger.info("Sending response directly to Discord")
                    discord_payload = {
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
                    send_discord_response(application_id, interaction_token, discord_payload)
                    
                    # Also send to Kafka for logging/analytics
                    response_data = {
                        "status": "success",
                        "recipe": {
                            "id": recipe["id"],
                            "title": recipe["title"],
                            "image": recipe.get("image", ""),
                            "usedIngredientCount": recipe.get("usedIngredientCount", 0),
                            "missedIngredients": missing_ingredient_text,
                            "instructions": instructions
                        },
                        "token": interaction_token,
                        "application_id": application_id,
                        "user_id": user_id
                    }
                    await send_message(RECIPE_RESPONSE_TOPIC, response_data, key=user_id)
                
            except Exception as e:
                logger.error(f"Error processing recipe request: {e}", exc_info=True)
                # Send error message directly to Discord
                try:
                    error_message = {
                        "content": f"Error finding recipes: {str(e)}"
                    }
                    send_discord_response(
                        msg.value.get("application_id"), 
                        msg.value.get("token"), 
                        error_message
                    )
                except Exception as discord_error:
                    logger.error(f"Error sending error message to Discord: {discord_error}", exc_info=True)
    
    except Exception as e:
        logger.error(f"Consumer error: {e}", exc_info=True)
    finally:
        await consumer.stop()

def send_discord_response(app_id, token, message_data):
    """Send a follow-up message to Discord"""
    if not app_id or not token:
        logger.error("Missing app_id or token for Discord response")
        return
        
    try:
        url = f"https://discord.com/api/v10/webhooks/{app_id}/{token}"
        logger.info(f"Sending Discord message to URL: {url}")
        headers = {"Content-Type": "application/json"}
        response = requests.post(url, json=message_data, headers=headers)
        response_text = response.text
        logger.info(f"Discord API response status: {response.status_code}, response: {response_text[:100]}")
        response.raise_for_status()
        logger.info("Successfully sent follow-up message to Discord")
        return True
    except Exception as e:
        logger.error(f"Error sending follow-up message to Discord: {e}", exc_info=True)
        return False

# Main function to start all consumers
async def start_consumers():
    """Start all Kafka consumers"""
    # For now, just run the recipe request consumer since we're bypassing
    # the response consumer for speed
    await recipe_request_consumer()

# Function to run in a separate process
def run_consumers():
    """Run the consumers in a separate process"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        logger.info("Starting Kafka consumers")
        loop.run_until_complete(start_consumers())
    except KeyboardInterrupt:
        logger.info("Shutting down consumers")
    finally:
        loop.close()