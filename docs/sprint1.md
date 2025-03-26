# Sprint 1 Plan: Basic Bot Setup and FastAPI Integration

## **Sprint Goal:**  
Set up the foundational structure for the Discord bot and integrate FastAPI to handle Discord's slash commands and responses.

## **Sprint Duration:**  
1-2 weeks

---

## **Tasks and Subtasks:**

### **1. Discord Bot Setup**
- **Objective:** Create and configure a Discord bot and connect it to a test server.
- **Subtasks:**  
  - Register the bot on the [Discord Developer Portal](https://discord.com/developers/applications).  
  - Generate the bot token and store it securely (e.g., in an environment variable).  
  - Invite the bot to a test server using the OAuth2 URL generated from the Developer Portal.  
  - Implement basic event handlers in the bot (e.g., logging when the bot goes online).
  - Verify that the bot can respond to basic commands (e.g., `/hello`).

### **2. FastAPI Setup**
- **Objective:** Set up a FastAPI backend to handle Discord interactions.
- **Subtasks:**  
  - Install FastAPI and Uvicorn:
    ```bash
    pip install fastapi uvicorn
    ```
  - Create a basic FastAPI app with a test endpoint:
    ```python
    from fastapi import FastAPI

    app = FastAPI()

    @app.get("/")
    async def root():
        return {"message": "Hello, World!"}
    ```
  - Run the FastAPI app locally using Uvicorn:
    ```bash
    uvicorn main:app --reload
    ```
  - Verify that the FastAPI app is running by visiting `http://localhost:8000` in a browser.

### **3. ngrok Integration**
- **Objective:** Expose the local FastAPI server to the internet using ngrok for handling Discord webhooks.
- **Subtasks:**  
  - Install ngrok and authenticate it with your account (if needed):
    ```bash
    npm install -g ngrok
    ngrok config add-authtoken <your-auth-token>
    ```
  - Start ngrok to expose the FastAPI server:
    ```bash
    ngrok http 8000
    ```
  - Note the generated public URL (e.g., `https://abc123.ngrok.io`).

### **4. Slash Command Implementation**
- **Objective:** Implement a basic slash command (`/ping`) in FastAPI and connect it to the Discord bot.
- **Subtasks:**  
  - Set up a POST endpoint in FastAPI to handle Discord interactions:
    ```python
    from fastapi import FastAPI, Request

    app = FastAPI()

    @app.post("/interactions")
    async def interactions(request: Request):
        data = await request.json()
        if data.get("type") == 1:  # Discord's PING check
            return {"type": 1}
        return {"type": 4, "data": {"content": "Pong!"}}
    ```
  - Update the bot settings to use the ngrok public URL as the interaction endpoint.
    - Go to the Discord Developer Portal > Your Bot > Interactions > Set `https://abc123.ngrok.io/interactions` as the endpoint.
  - Verify that the bot responds to `/ping` with "Pong!" in your Discord server.

### **5. Testing and Verification**
- **Objective:** Ensure that the bot, FastAPI backend, and ngrok setup are working correctly.
- **Subtasks:**  
  - Test the `/ping` slash command and confirm the bot responds correctly.
  - Verify that the ngrok public URL is correctly forwarding requests to your local FastAPI app.
  - Check the logs in your FastAPI app to confirm it is receiving requests from Discord.

---

## **Sprint Deliverable:**
A functioning Discord bot that can respond to a basic `/ping` command, with FastAPI handling the backend logic and ngrok enabling real-time interaction via webhooks.

## **Next Steps:**
- Plan and implement recipe search functionality in Sprint 2.
- Refactor and optimize the FastAPI and bot code for scalability.
- Set up Kafka integration in later sprints.

