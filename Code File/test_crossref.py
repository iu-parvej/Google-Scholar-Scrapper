import requests
import json
import re

doi = "10.1080/24749508.2025.2451450"
resp = requests.get(f"https://api.crossref.org/works/{doi}")
if resp.status_code == 200:
    item = resp.json().get("message", {})
    abstract = item.get("abstract", "")
    print("RAW ABSTRACT:")
    print(abstract)
    print("\nCLEAN ABSTRACT:")
    print(re.sub(r'<[^>]+>', '', abstract).strip())
else:
    print("Failed")
