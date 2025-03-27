from fastapi import FastAPI, Request

app = FastAPI()

@app.post("/interactions")
async def interactions(request: Request):
    data = await request.json()
    if data.get("type") == 1:  # PING check from Discord
        return {"type": 1}
    return {"type": 4, "data": {"content": "Pong!"}}

