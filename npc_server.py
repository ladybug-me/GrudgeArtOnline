# pip install backboard-sdk flask
import asyncio
from flask import Flask, request, jsonify
from backboard import BackboardClient

app = Flask(__name__)
client = BackboardClient(api_key=<key>)

assistant_id = None
thread_id = None

async def setup():
    global assistant_id, thread_id

    assistant = await client.create_assistant(
        name="NPC",
        system_prompt="You are a character inside a sci-fi FPS game. You remember the player across sessions."
    )
    assistant_id = assistant.assistant_id

    thread = await client.create_thread(assistant_id=assistant_id)
    thread_id = thread.thread_id

asyncio.run(setup())

@app.route("/talk", methods=["POST"])
def talk():
    data = request.json
    player_msg = data["message"]

    async def run():
        await client.create_message(thread_id=thread_id, role="user", content=player_msg)
        await client.run_thread(thread_id=thread_id)
        msgs = await client.list_messages(thread_id=thread_id)
        return msgs[-1].content

    reply = asyncio.run(run())
    return jsonify({"reply": reply})

app.run(port=5000)
