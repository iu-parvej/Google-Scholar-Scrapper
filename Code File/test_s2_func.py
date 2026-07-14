import requests

def get_full_abstract(doi):
    if doi == "N/A": return None
    try:
        url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}?fields=abstract"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            return resp.json().get('abstract')
    except Exception:
        pass
    return None

print(get_full_abstract("10.1080/24749508.2025.2451450"))
