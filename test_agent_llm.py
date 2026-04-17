import requests
import json
import os

url = "http://localhost:8000/api/v1/ask-agentic"
data = {
    "query": "What are transformers in machine learning?",
    "user_id": "test_user"
}

try:
    print(f"Sending request to {url}...")
    response = requests.post(url, json=data, timeout=120)  # Increased timeout for LLM
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print("Success! Response received:")
        print(f"Answer: {result.get('answer', 'N/A')[:500]}...")
        print(f"Score: {result.get('guardrail_score')}")
    else:
        print(f"Error: {response.text}")
except Exception as e:
    print(f"Failed to connect: {e}")
