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
            
            # Call FastAPI to save the favorite
            # Note: You'll need to extract the recipe ID from the embed or message
            # This is simplified, you may need to adjust based on your message format
            recipe_id = extract_recipe_id_from_message(reaction.message)
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

def extract_recipe_id_from_message(message):
    """Helper function to extract recipe ID from message
    
    You'll need to implement this based on how you're storing the recipe ID
    in your message. One approach is to use a custom footer or hidden field.
    """
    # Implementation depends on your message structure
    # This is just a placeholder
    return None