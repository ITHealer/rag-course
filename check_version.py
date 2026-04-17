import requests

url = "http://10.10.0.7:11445/api/version"

try:
    response = requests.get(url, timeout=10)
    print(f"Ollama Version: {response.json().get('version')}")
except Exception as e:
    print(f"Failed to get version: {e}")
