import asyncio, websockets, json

async def t():
    uri = "ws://127.0.0.1:8000/ws/match/"
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({"type": "join_queue", "user_id": 1, "party_size": 2}))
        print(await ws.recv())

asyncio.run(t())