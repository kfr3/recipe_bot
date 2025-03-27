import requests
import json
import time
import config
from config import validate_config

def register_commands():
    """Register slash commands with Discord."""
    # Validate configuration
    validate_config()
    
    # Define the commands to register
    commands = [
        {
            "name": "ping",
            "description": "Check if the bot is working",
            "type": 1  # CHAT_INPUT
        }
    ]
    
    # Discord API endpoint for registering global commands
    url = f"https://discord.com/api/v10/applications/{config.DISCORD_APP_ID}/commands"
    
    # Set up headers with authorization
    headers = {
        "Authorization": f"Bot {config.DISCORD_BOT_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Register each command
    for command in commands:
        response = requests.post(url, headers=headers, json=command)
        
        if response.status_code in (200, 201):
            print(f"Successfully registered command: {command['name']}")
        else:
            print(f"Failed to register command {command['name']}: {response.status_code}")
            try:
                print(f"Error: {response.json()}")
            except:
                print(f"Response: {response.text}")

def main():
    """Main function to set up the Discord bot."""
    print("Registering Discord commands...")
    register_commands()
    print("Commands registered. You can now start the FastAPI server using 'python main.py'")
    print("Then, expose it using ngrok with 'ngrok http 8000'")
    print("Finally, update your Discord application's interactions endpoint URL in the Developer Portal")

if __name__ == "__main__":
    main()