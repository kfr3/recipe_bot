import os
import aiohttp
import asyncio
import json
from fastapi import FastAPI, HTTPException
from openai import AsyncOpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI()

# Get OpenAI API key with better error handling
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    print("WARNING: OPENAI_API_KEY not found in environment variables!")

# Initialize AsyncOpenAI client
try:
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
except Exception as e:
    print(f"Error initializing OpenAI client: {e}")
    client = None

async def search_recipes_by_ingredients(ingredients: str, limit: int = 5):
    """Search for recipes based on provided ingredients using OpenAI"""
    
    if not client or not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured properly")
    
    try:
        # Create a prompt for OpenAI
        prompt = f"""Generate {limit} unique recipe ideas using these ingredients: {ingredients}. 
        For each recipe, provide:
        1. A title
        2. A list of all ingredients with measurements (including the ones provided plus any additions)
        3. A list of ingredients that weren't in the original list (as "missedIngredients")
        4. A count of how many provided ingredients are used (as "usedIngredientCount")
        5. A URL for an image that would represent this dish (as "image")
        6. A unique ID for each recipe (a simple number between 10000 and 99999)

        Format the response as a JSON array of recipe objects with this structure:
        [
          {{
            "id": 12345,
            "title": "Recipe Name",
            "image": "https://example.com/image.jpg",
            "usedIngredientCount": 3,
            "missedIngredients": [
              {{ "name": "ingredient1" }},
              {{ "name": "ingredient2" }}
            ]
          }}
        ]
        """

        # Call OpenAI API asynchronously
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that generates recipe ideas based on ingredients."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        # Extract and parse the JSON response
        recipes_json = json.loads(response.choices[0].message.content)
        
        # If OpenAI returns a different structure, map it to match Spoonacular's format
        if isinstance(recipes_json, dict) and "recipes" in recipes_json:
            recipes = recipes_json["recipes"]
        else:
            recipes = recipes_json
            
        return recipes
        
    except Exception as e:
        print(f"OpenAI API Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"API Error: {str(e)}")

async def get_recipe_information(recipe_id: int):
    """Get detailed information for a specific recipe using OpenAI"""
    
    if not client or not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured properly")
    
    try:
        prompt = f"""Create detailed information for a recipe with ID {recipe_id}.
        Include a complete set of step-by-step instructions and a full ingredient list with measurements.
        
        Format the response as a JSON object with this structure:
        {{
          "id": {recipe_id},
          "title": "Recipe Name",
          "instructions": "Step-by-step instructions for preparing the dish...",
          "extendedIngredients": [
            {{
              "original": "1 cup of ingredient"
            }}
          ],
          "summary": "Brief description of the dish"
        }}
        """
        
        # Call OpenAI API asynchronously
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo-0125",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that provides detailed recipe information."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        # Extract and parse the JSON response
        recipe_info = json.loads(response.choices[0].message.content)
        return recipe_info
        
    except Exception as e:
        print(f"OpenAI API Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"API Error: {str(e)}")

# Simple mock response for testing - use this when you need a fast response
async def mock_search_recipes(ingredients: str, limit: int = 5):
    """Mock function that returns recipe data instantly for testing"""
    return [
        {
            "id": 12345,
            "title": "Quick Test Recipe",
            "image": "https://via.placeholder.com/150",
            "usedIngredientCount": 3,
            "missedIngredients": [
                {"name": "salt"},
                {"name": "pepper"}
            ]
        }
    ]

async def mock_recipe_information(recipe_id: int):
    """Mock function that returns recipe details instantly for testing"""
    return {
        "id": recipe_id,
        "title": "Quick Test Recipe",
        "instructions": "This is a test recipe for debugging purposes. Steps would go here.",
        "extendedIngredients": [
            {"original": "Test ingredient 1"},
            {"original": "Test ingredient 2"}
        ],
        "summary": "A test recipe"
    }