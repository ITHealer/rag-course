import requests
import json

url = "http://10.10.0.7:11445/api/tags"

try:
    print(f"Checking models on {url}...")
    response = requests.get(url, timeout=10)
    if response.status_code == 200:
        models = [m['name'] for m in response.json().get('models', [])]
        print(f"Available models: {models}")
        target = "gpt-oss:20b"
        if target in models or target in [m.split(":")[0] for m in models]:
             print(f"{target} is found!")
        else:
             print(f"{target} NOT FOUND!")
    else:
        print(f"Error: {response.status_code} - {response.text}")
except Exception as e:
    print(f"Failed to connect to remote Ollama: {e}")
