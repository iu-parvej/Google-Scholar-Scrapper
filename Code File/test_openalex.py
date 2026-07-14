import requests
import json

title = "Implications of climate variability and changing seasonal hydrology for subarctic riverbank erosion"
url = f"https://api.openalex.org/works?search={title}"
resp = requests.get(url)
if resp.status_code == 200:
    data = resp.json()
    if data.get('results'):
        item = data['results'][0]
        inv = item.get('abstract_inverted_index')
        if inv:
            # Reconstruct abstract
            max_idx = max([max(pos) for pos in inv.values()])
            words = [""] * (max_idx + 1)
            for word, positions in inv.items():
                for pos in positions:
                    words[pos] = word
            print(" ".join(words))
        else:
            print("No abstract in OpenAlex")
    else:
        print("No results in OpenAlex")
else:
    print("Failed")
