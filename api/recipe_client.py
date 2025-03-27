import os
import requests
from fastapi import FastAPI, HTTPException

app = FastAPI()

SPOONACULAR_API_KEY = os.getenv("SPOONACULAR_API_KEY")
SPOONACULAR_BASE_URL = "https://api.spoonacular.com"

async def search_recipes_by_ingredients(ingredients: str, limit: int = 5):
    """Search for recipes based on provided ingredients"""
    
    endpoint = f"{SPOONACULAR_BASE_URL}/recipes/findByIngredients"
    
    params = {
        "apiKey": SPOONACULAR_API_KEY,
        "ingredients": ingredients,
        "number": limit,
        "ranking": 1,  # Maximize used ingredients
        "ignorePantry": False  # Include common ingredients
    }
    
    try:
        response = requests.get(endpoint, params=params)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"API Error: {str(e)}")

async def get_recipe_information(recipe_id: int):
    """Get detailed information for a specific recipe"""
    
    endpoint = f"{SPOONACULAR_BASE_URL}/recipes/{recipe_id}/information"
    
    params = {
        "apiKey": SPOONACULAR_API_KEY,
        "includeNutrition": False
    }
    
    try:
        response = requests.get(endpoint, params=params)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"API Error: {str(e)}")