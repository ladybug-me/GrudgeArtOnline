import os
import asyncio
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from backboard import BackboardClient

# Load API Key
load_dotenv()
API_KEY = os.getenv("BACKBOARD_API_KEY")

app = Flask(__name__)

# --- GLOBAL MEMORY ---
# We store these globally so they persist while the server is running
ASSISTANT_ID = None
USER_THREADS = {} # Maps user_id -> thread_id

async def setup_assistant():
    """
    Creates the 'Dungeon Master' assistant once on startup.
    """
    global ASSISTANT_ID
    print(">> CONNECTING TO BACKBOARD...")
    
    # We create a temporary client just for setup
    client = BackboardClient(api_key=API_KEY)
    
    try:
        # Pattern from your working snippet: Only Name + Prompt
        assistant = await client.create_assistant(
            name="Dungeon Master",
            system_prompt="""
            You are the 'System' from a dark fantasy RPG. 
            CRITICAL: You have persistent memory of this thread.
            1. If the user died in a previous session, MOCK them.
            2. If the user was rude to an NPC, that NPC refuses help.
            3. Be brief, snarky, and dramatic.
            """
        )
        # Note: Using .assistant_id based on your snippet
        ASSISTANT_ID = assistant.assistant_id
        print(f"✅ Dungeon Master Online. ID: {ASSISTANT_ID}")
    except Exception as e:
        print(f"❌ SETUP ERROR: {e}")

async def run_chat_logic(user_id, user_message):
    """
    Handles the conversation using the exact pattern that worked for you.
    """
    global ASSISTANT_ID
    
    # Create a fresh client for this request (Prevents event loop crashes in Flask)
    client = BackboardClient(api_key=API_KEY)
    
    # 1. Get or Create Thread
    if user_id not in USER_THREADS:
        # Pattern: create_thread(assistant_id)
        thread = await client.create_thread(ASSISTANT_ID)
        USER_THREADS[user_id] = thread.thread_id
        print(f"New Thread for {user_id}: {thread.thread_id}")
        
    thread_id = USER_THREADS[user_id]
    
    # 2. Add Message & Stream Response
    # We collect all chunks into a single string to send back to the frontend
    full_response = ""
    
    # Pattern: Passing provider/model HERE, not in assistant creation
    stream_generator = await client.add_message(
        thread_id=thread_id,
        content=user_message,
        llm_provider="openai",
        model_name="gpt-4o",
        stream=True
    )

    async for chunk in stream_generator:
        if chunk['type'] == 'content_streaming':
            full_response += chunk['content']
            
    return full_response

# --- FLASK ROUTES ---

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_input = data.get('message')
    user_id = data.get('user_id', 'Guest')

    if not ASSISTANT_ID:
        return jsonify({"reply": "System initializing... Please wait."})

    try:
        # We use asyncio.run to execute the async logic safely
        reply = asyncio.run(run_chat_logic(user_id, user_input))
        return jsonify({"reply": reply})
    except Exception as e:
        print(f"CHAT ERROR: {e}")
        return jsonify({"reply": "The System is silent. (Check terminal logs)"})

if __name__ == '__main__':
    # Run the setup once before starting the web server
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(setup_assistant())
    
    app.run(host='0.0.0.0', port=5000, debug=True)