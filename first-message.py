# Install: pip install backboard-sdk
import asyncio
from backboard import BackboardClient

key = "<my key>"

async def main():
    # Initialize the Backboard client
    client = BackboardClient(api_key=key)

    # Create an assistant
    assistant = await client.create_assistant(
        name="My First Assistant",
        system_prompt="A helpful assistant"
    )

    # Create a thread
    thread = await client.create_thread(assistant.assistant_id)

    # Send a message and stream the response
    async for chunk in await client.add_message(
        thread_id=thread.thread_id,
        content="Tell me a short story about a robot learning to paint.",
        llm_provider="openai",
        model_name="gpt-4o",
        stream=True
    ):
        # Print each chunk of content as it arrives
        if chunk['type'] == 'content_streaming':
            print(chunk['content'], end='', flush=True)
        elif chunk['type'] == 'message_complete':
            break

if __name__ == "__main__":
    asyncio.run(main())