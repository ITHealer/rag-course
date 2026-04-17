import requests
import json

url = "http://localhost:8000/api/v1/ask-agentic"
data = {
    "query": "What are transformers in machine learning?",
    "user_id": "test_user"
}

try:
    print(f"Sending request to {url}...")
    response = requests.post(url, json=data, timeout=120)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        print("Success!")
        print(json.dumps(response.json(), indent=2))
    else:
        print("Full Error Response:")
        print(response.text)
except Exception as e:
    print(f"Failed to connect: {e}")
