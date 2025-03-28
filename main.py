from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
import uvicorn
import hmac
import hashlib
import json
import time

import config
from config import validate_config

# Initialize FastAPI app
app = FastAPI(title="Discord Bot API")

# Verify Discord signature
async def verify_signature(request: Request):
    # Get Discord signature and timestamp
    signature = request.headers.get('X-Signature-Ed25519')
    timestamp = request.headers.get('X-Signature-Timestamp')
    
    if not signature or not timestamp:
        raise HTTPException(status_code=401, detail="Missing signature or timestamp")
    
    # Get raw request body
    body = await request.body()
    
    # Verify signature
    message = timestamp.encode() + body
    
    try:
        # Convert hex strings to bytes
        signature_bytes = bytes.fromhex(signature)
        public_key_bytes = bytes.fromhex(config.DISCORD_PUBLIC_KEY)
        
        # Use nacl's verify_key to verify the signature
        import nacl.signing
        verify_key = nacl.signing.VerifyKey(public_key_bytes)
        verify_key.verify(message, signature_bytes)
        
        return await request.json()
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid signature: {str(e)}")

@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "message": "Discord bot API is running"}

@app.post("/interactions")
async def interactions(data: dict = Depends(verify_signature)):
    """Handle Discord interactions."""
    
    # Log the incoming data for debugging
    print(f"Received interaction: {data}")
    
    # Interaction type 1: PING (used by Discord to verify the endpoint)
    if data.get("type") == 1:
        print("Responding to PING with PONG")
        return JSONResponse(content={"type": 1})  # Type 1: PONG response
    
    # Interaction type 2: APPLICATION_COMMAND (slash commands)
    elif data.get("type") == 2:
        command_name = data.get("data", {}).get("name", "")
        
        if command_name == "ping":
            return JSONResponse(content={
                "type": 4,  # Type 4: Channel message with source
                "data": {
                    "content": "Pong! Bot is working correctly."
                }
            })
        
        # Default response for unknown commands
        return JSONResponse(content={
            "type": 4,
            "data": {
                "content": f"Command '{command_name}' received but not implemented yet."
            }
        })
    
    # Default response for other interaction types
    return JSONResponse(content={
        "type": 4,
        "data": {
            "content": "Interaction received but not supported."
        }
    })

def start_api():
    """Start the FastAPI server."""
    # Validate configuration
    validate_config()
    
    # Start the server
    uvicorn.run(
        "main:app",
        host=config.API_HOST,
        port=config.API_PORT,
        reload=True
    )

if __name__ == "__main__":
    start_api()