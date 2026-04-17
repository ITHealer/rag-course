import requests
import json

url = "http://10.10.0.7:11445/api/generate"
data = {
    "model": "gpt-oss:20b",
    "prompt": "Hello, who are you?",
    "stream": False
}

try:
    print(f"Testing generation on {url} with model gpt-oss:20b...")
    response = requests.post(url, json=data, timeout=30)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        print("Response received:")
        print(response.json().get("response"))
    else:
        print(f"Error: {response.status_code} - {response.text}")
except Exception as e:
    print(f"Failed to connect: {e}")
