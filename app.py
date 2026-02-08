import os
import asyncio
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from backboard import BackboardClient

# Load API Key
load_dotenv()
API_KEY = os.getenv("BACKBOARD_API_KEY")

app = Flask(__name__)

# --- GLOBAL SHARED STATE ---
# This is the "World Memory" that affects everyone
WORLD_STATE = {
    "anger_level": 0,        # 0-100%
    "last_crime": "None",    # e.g., "Player_42 punched the merchant"
    "banned_users": []       # List of IDs who pushed it to 100%
}

ASSISTANT_ID = None
USER_THREADS = {} 

async def setup_assistant():
    """
    Creates the 'Dungeon Master' with specific instructions to use the Global State.
    """
    global ASSISTANT_ID
    # Temporary client for setup
    client = BackboardClient(api_key=API_KEY)
    
    print(">> INITIALIZING DUNGEON MASTER...")
    try:
        assistant = await client.create_assistant(
            name="Dungeon Master",
            system_prompt="""
            You are the 'System' of a dark RPG world.
            
            [CRITICAL CONTEXT RULES]
            1. You will receive [SYSTEM DATA] with every message. READ IT.
            2. If 'Last Crime' is not 'None', you MUST mention that player's name and what they did.
               (Example: "I am in a foul mood because Player_92 just punched me.")
            3. If 'Global Anger' is > 50, you are hostile to EVERYONE, even innocent players.
            4. If 'Global Anger' is 100, refuse to help anyone.
            
            [ACTION TAGS]
            - If the user insults/attacks you, output: [ACTION: CRIME]
            - If the user pays/apologizes, output: [ACTION: ATONE]
            
            Do not explain the tags. Just use them naturally at the end of the response.
            """
        )
        ASSISTANT_ID = assistant.assistant_id
        print(f"✅ Dungeon Master Online. ID: {ASSISTANT_ID}")
    except Exception as e:
        print(f"❌ SETUP ERROR: {e}")

async def run_chat_logic(user_id, user_message):
    global ASSISTANT_ID, WORLD_STATE
    
    # 0. Check Ban List
    if user_id in WORLD_STATE["banned_users"]:
        return "SYSTEM MESSAGE: You have been banned from the server. The Grudge is eternal."

    # Create a fresh client for this request (Prevents event loop crashes)
    client = BackboardClient(api_key=API_KEY)
    
    # 1. Get Thread
    if user_id not in USER_THREADS:
        # Link new thread to our Dungeon Master
        thread = await client.create_thread(ASSISTANT_ID)
        USER_THREADS[user_id] = thread.thread_id
        
    thread_id = USER_THREADS[user_id]
    
    # 2. INJECT GLOBAL CONTEXT
    # We hide the world state inside the user's message so the AI sees it.
    context_header = f"""
    [SYSTEM DATA]
    Global Anger Level: {WORLD_STATE['anger_level']}/100
    Last Crime Committed by: {WORLD_STATE['last_crime']}
    [/SYSTEM DATA]
    
    User says: 
    """
    full_prompt = context_header + user_message

    # 3. Get Response (Streaming pattern)
    full_response = ""
    stream_generator = await client.add_message(
        thread_id=thread_id,
        content=full_prompt,
        llm_provider="openai",
        model_name="gpt-4o",
        stream=True
    )

    async for chunk in stream_generator:
        if chunk['type'] == 'content_streaming':
            full_response += chunk['content']
            
    # 4. PARSE ACTION TAGS (Update Global State)
    if "[ACTION: CRIME]" in full_response:
        WORLD_STATE["anger_level"] = min(100, WORLD_STATE["anger_level"] + 20)
        WORLD_STATE["last_crime"] = f"{user_id} (Just now)"
        # Clean up the tag so user doesn't see it
        full_response = full_response.replace("[ACTION: CRIME]", " *(The System glares at you)*")
        
    elif "[ACTION: ATONE]" in full_response:
        WORLD_STATE["anger_level"] = max(0, WORLD_STATE["anger_level"] - 10)
        full_response = full_response.replace("[ACTION: ATONE]", " *(The atmosphere lightens slightly)*")

    # 5. Ban Hammer Logic
    if WORLD_STATE["anger_level"] >= 100:
        if user_id not in WORLD_STATE["banned_users"]:
            WORLD_STATE["banned_users"].append(user_id)
        full_response += "\n\n[SYSTEM ALERT]: WORLD ANGER CRITICAL. YOU HAVE BEEN BANNED."

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
        return jsonify({"reply": "System initializing..."})

    try:
        reply = asyncio.run(run_chat_logic(user_id, user_input))
        return jsonify({
            "reply": reply, 
            "anger": WORLD_STATE["anger_level"]
        })
    except Exception as e:
        print(f"CHAT ERROR: {e}")
        return jsonify({"reply": "System Error."})

# polling endpoint for the frontend
@app.route('/status', methods=['GET'])
def get_status():
    return jsonify({
        "anger": WORLD_STATE["anger_level"],
        "last_crime": WORLD_STATE["last_crime"],
        "banned_count": len(WORLD_STATE["banned_users"])
    })

if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(setup_assistant())
    app.run(host='0.0.0.0', port=5000, debug=True)