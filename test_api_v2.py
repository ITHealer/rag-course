import requests
import json
import time

url = "http://localhost:8000/api/v1/ask-agentic"
data = {
    "query": "What are transformers in machine learning?",
    "user_id": "test_user"
}

# Wait a bit for the server to stabilize if it just reloaded
time.sleep(5)

try:
    print(f"Sending request to {url} (with 180s timeout)...")
    response = requests.post(url, json=data, timeout=180) 
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print("Success! Response received:")
        print(f"Answer: {result.get('answer', 'N/A')[:1000]}...")
        print(f"Guardrail Score: {result.get('guardrail_score')}")
        print(f"Sources: {len(result.get('sources', []))}")
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
except Exception as e:
    print(f"Request failed: {e}")
