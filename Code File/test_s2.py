import requests
import json

doi = "10.1080/24749508.2025.2451450"
url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}?fields=abstract"
resp = requests.get(url)
if resp.status_code == 200:
    print(resp.json())
else:
    print(f"Failed: {resp.status_code} {resp.text}")
