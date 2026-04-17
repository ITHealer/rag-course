import httpx
import asyncio
import json

async def test_httpx():
    url = "http://10.10.0.7:11445/api/generate"
    data = {
        "model": "gpt-oss:20b",
        "prompt": "Hello, who are you?",
        "stream": False
    }

    try:
        print(f"Testing generation with HTTPX on {url}...")
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=data)
            print(f"Status Code: {response.status_code}")
            if response.status_code == 200:
                print("Response received:")
                print(response.json().get("response"))
            else:
                print(f"Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_httpx())
