import os

import requests


API_KEY = os.environ.get("ROBOFLOW_API_KEY", "")

if not API_KEY:
    raise SystemExit("Set ROBOFLOW_API_KEY before running this helper.")

r = requests.get("https://api.roboflow.com/?api_key=" + API_KEY, timeout=30)
data = r.json()

print("Workspace:", data.get("workspace", "not found"))
print("Full response:", data)
