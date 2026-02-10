import asyncio
import websockets
import os
from dotenv import load_dotenv
from backboard import BackboardClient

# load .env
load_dotenv()

API_KEY = os.getenv("BACKBOARD_API_KEY")

if not API_KEY:
    raise Exception("BACKBOARD_API_KEY not found in .env")

client = BackboardClient(api_key=API_KEY)

# We only need one Assistant for the whole server
assistant_id = None

async def setup_global_assistant():
    global assistant_id
    
    # Check if we already created it or create a new one
    assistant = await client.create_assistant(
        name="Unity Enemy",
        system_prompt="You are an angry anime boss. You speak in short, threatening bursts."
    )
    assistant_id = assistant.assistant_id
    print(f"Global Assistant Created: {assistant_id}")


async def handler(websocket):
    print("New Unity Client Connected")

    # 1. Create a FRESH thread for this specific connection/game session
    # This ensures restarting the game resets the conversation memory.
    try:
        thread = await client.create_thread(assistant_id)
        thread_id = thread.thread_id
        print(f"Created Thread {thread_id} for this client")

        # 2. Keep the loop open to receive multiple messages
        async for message in websocket:
            print(f"Received from Client: {message}")

            # Send prompt to AI
            response_stream = await client.add_message(
                thread_id=thread_id,
                content=message,
                llm_provider="openai",
                model_name="gpt-4o",
                stream=True
            )

            # Stream the response chunks back to Unity
            async for chunk in response_stream:
                if chunk.get("type") == "content_streaming":
                    content = chunk.get("content", "")
                    if content:
                        await websocket.send(content)

            # 3. CRITICAL: Send [END] after EACH prompt response is finished
            # This allows Unity to know the specific response is complete.
            await websocket.send("[END]")
            print("Finished sending response.")

    except websockets.exceptions.ConnectionClosed:
        print("Client disconnected")
    except Exception as e:
        print(f"Error in handler: {e}")


async def main():
    # Setup the assistant once when server starts
    await setup_global_assistant()

    # Serve the handler
    async with websockets.serve(handler, "0.0.0.0", 8765):
        print("AI STREAM SERVER READY (Listening on Port 8765)")
        # Keep the server running forever
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Server stopped by user")