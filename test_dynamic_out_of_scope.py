import requests
import json
import time

url = "http://localhost:8000/api/v1/ask-agentic"
data = {
    "query": "Who are you and what do you do?",
    "user_id": "test_user"
}

try:
    print(f"Sending request to {url}...")
    response = requests.post(url, json=data, timeout=60)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print("Success! Response received:")
        print(f"Answer: {result.get('answer')}")
        print(f"Reasoning Steps: {result.get('reasoning_steps')}")
        print(f"Guardrail Score: {result.get('guardrail_score')}")
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
except Exception as e:
    print(f"Request failed: {e}")
