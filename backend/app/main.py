from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Allow CORS for local testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/channel-id")
async def get_channel_id(request: Request):
    data = await request.json()
    channel_id = data.get("channelId")
    print(f"Received Channel ID: {channel_id}")   # <-- 👈 Prints to terminal
    return {"status": "Channel ID received", "channelId": channel_id}
