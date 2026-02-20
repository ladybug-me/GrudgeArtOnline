# pip install flask backboard-sdk

import asyncio
from flask import Flask, request, jsonify
from backboard import BackboardClient

app = Flask(__name__)

API_KEY = <key>

async def ask_ai(message):
    client = BackboardClient(api_key=API_KEY)

    assistant = await client.create_assistant(
        name="Unity NPC",
        system_prompt="You are an NPC inside a video game. Reply briefly."
    )

    thread = await client.create_thread(assistant.assistant_id)

    final_text = ""

    async for chunk in await client.add_message(
        thread_id=thread.thread_id,
        content=message,
        llm_provider="openai",
        model_name="gpt-4o",
        stream=True
    ):
        if chunk["type"] == "content_streaming":
            final_text += chunk["content"]
        elif chunk["type"] == "message_complete":
            break

    return final_text


@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    player_msg = data["message"]

    response = asyncio.run(ask_ai(player_msg))
    return jsonify({"reply": response})


if __name__ == "__main__":
    app.run(port=5000)
