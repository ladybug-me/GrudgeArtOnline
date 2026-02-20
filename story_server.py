# pip install flask backboard-sdk

import asyncio
from flask import Flask, jsonify
from backboard import BackboardClient

app = Flask(__name__)

API_KEY = <key>

async def generate_story():
    client = BackboardClient(api_key=API_KEY)

    assistant = await client.create_assistant(
        name="Unity Assistant",
        system_prompt="A helpful assistant"
    )

    thread = await client.create_thread(assistant.assistant_id)

    final_text = ""

    async for chunk in await client.add_message(
        thread_id=thread.thread_id,
        content="Tell me a short story about a robot learning to paint.",
        llm_provider="openai",
        model_name="gpt-4o",
        stream=True
    ):
        if chunk["type"] == "content_streaming":
            final_text += chunk["content"]
        elif chunk["type"] == "message_complete":
            break

    return final_text


@app.route("/story")
def get_story():
    text = asyncio.run(generate_story())
    return jsonify({"text": text})


if __name__ == "__main__":
    app.run(port=5000)
