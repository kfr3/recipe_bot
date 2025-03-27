from fastapi import FastAPI, Request
import discord 
import os

app = FastAPI()
client = discord.Client(intents=discord.Intents.default())

@app.post("/interactions")
async def interactions(request: Request):
    data = await request.json()

    # Check if it's a PING event (sent by Discord to verify the endpoint)
    if data.get("type") == 1:
        return {"type": 1}  # Respond to PING event

    # Handle the /ping command
    if data["data"]["name"] == "ping":
        return {"type": 4, "data": {"content": "Pong!"}}

    return {"type": 4, "data": {"content": "Unknown command"}}
