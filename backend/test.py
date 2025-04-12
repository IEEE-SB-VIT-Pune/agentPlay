import aiohttp
import asyncio
import json

async def call_process_route(query, video_id, addition_mode=True):
    """
    Makes an async POST request to the /process endpoint.
    
    Args:
        query (str): The user query to process
        video_id (str): The ID of the video
        addition_mode (bool, optional): Mode parameter. Defaults to True.
        
    Returns:
        dict: The JSON response from the server
    """
    url = "http://127.0.0.1:5001/process"  # Replace with your actual server URL
    
    # Prepare the payload
    payload = {
        "query": query,
        "video_id": video_id,
        "addition_mode": addition_mode
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as response:
            if response.status == 200:
                return await response.json()
            else:
                print(f"Error: {response.status}")
                return await response.text()

# Example usage
async def main():
    query = "What is the main topic discussed in the video?"
    video_id = "HeUVMcERvlM"
    
    result = await call_process_route(query, video_id)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    asyncio.run(main())