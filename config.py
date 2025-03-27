import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Discord configuration
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
DISCORD_APP_ID = os.getenv('DISCORD_APP_ID')
DISCORD_PUBLIC_KEY = os.getenv('DISCORD_PUBLIC_KEY')

# Server configuration
API_HOST = os.getenv('API_HOST', '0.0.0.0')
API_PORT = int(os.getenv('API_PORT', '8000'))

# Ensure all required environment variables are set
def validate_config():
    """Validate that all required environment variables are set."""
    required_vars = [
        'DISCORD_BOT_TOKEN',
        'DISCORD_APP_ID',
        'DISCORD_PUBLIC_KEY',
    ]
    
    missing_vars = [var for var in required_vars if not globals().get(var)]
    
    if missing_vars:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing_vars)}"
        )