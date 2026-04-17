import requests
import json

url = "http://10.10.0.7:11445/api/tags"

try:
    print(f"Checking models on {url}...")
    response = requests.get(url, timeout=10)
    if response.status_code == 200:
        models = [m['name'] for m in response.json().get('models', [])]
        print(f"Available models: {models}")
        if "llama3.2:1b" in models or "llama3.2:1b" in [m.split(":")[0] for m in models]:
             print("llama3.2:1b is found!")
        else:
             print("llama3.2:1b NOT FOUND!")
    else:
        print(f"Error: {response.status_code} - {response.text}")
except Exception as e:
    print(f"Failed to connect to remote Ollama: {e}")
