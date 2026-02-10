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
SAVE_FILE = "save_game.txt"

assistant_id = None
current_thread_id = None

async def setup_level_assistant():
    global assistant_id
    # We create a specialized assistant that ONLY cares about the level number.
    assistant = await client.create_assistant(
        name="Level Manager",
        system_prompt=(
            "You are a game save system. You track the player's Level. "
            "The player starts at Level 1. "
            "If the user says 'GET_LEVEL', respond with ONLY the current level number (e.g., '1'). "
            "If the user says 'LEVEL_UP', increment the level by 1 and respond with ONLY the new number. "
            "Do not say anything else. Just the number."
        )
    )
    assistant_id = assistant.assistant_id
    print(f"Level Assistant Created: {assistant_id}")

def load_saved_thread():
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, "r") as f:
            return f.read().strip()
    return None

def save_thread(tid):
    with open(SAVE_FILE, "w") as f:
        # --- FIX: Convert UUID to string before writing ---
        f.write(str(tid)) 

async def handler(websocket):
    print("Unity Level Tracker Connected")
    global current_thread_id

    # 1. Load existing game or start new
    if current_thread_id is None:
        saved_id = load_saved_thread()
        if saved_id:
            print(f"Resuming saved game thread: {saved_id}")
            current_thread_id = saved_id
        else:
            print("Starting new game save...")
            thread = await client.create_thread(assistant_id)
            current_thread_id = thread.thread_id
            save_thread(current_thread_id)
    
    try:
        async for message in websocket:
            print(f"Command received: {message}")

            # --- NEW: Handle Reset Logic ---
            if message == "RESET_LEVEL":
                print("RESET command received. Creating fresh game thread...")
                
                # 1. Create a brand new thread (This resets the AI memory to start)
                new_thread = await client.create_thread(assistant_id)
                current_thread_id = new_thread.thread_id
                
                # 2. Overwrite the save file
                save_thread(current_thread_id)
                
                # 3. Send "1" back to Unity immediately
                await websocket.send("1")
                await websocket.send("[END]")
                
                print("Game reset to Level 1.")
                continue # Skip the normal LLM processing for this loop

            # --- Normal Logic (GET_LEVEL / LEVEL_UP) ---
            response_stream = await client.add_message(
                thread_id=current_thread_id,
                content=message,
                llm_provider="openai",
                model_name="gpt-4o",
                stream=True
            )

            # Stream the number back to Unity
            full_response = ""
            async for chunk in response_stream:
                if chunk.get("type") == "content_streaming":
                    content = chunk.get("content", "")
                    if content:
                        full_response += content
                        await websocket.send(content)

            # Send End token
            await websocket.send("[END]")
            print(f"Current Level sent: {full_response}")

    except websockets.exceptions.ConnectionClosed:
        print("Unity disconnected")
    except Exception as e:
        print(f"Error: {e}")

async def main():
    await setup_level_assistant()
    # Port 2027 as requested
    async with websockets.serve(handler, "0.0.0.0", 2027):
        print("LEVEL SERVER READY (Listening on Port 2027)")
        await asyncio.Future()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Server stopped by user")