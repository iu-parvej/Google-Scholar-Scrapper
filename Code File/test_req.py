import json
import urllib.request

url = 'http://127.0.0.1:5000/start-scrape'
data = {'query': 'test erosion', 'max_results': '3'}
req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers={'Content-Type': 'application/json'})
try:
    with urllib.request.urlopen(req) as response:
        print(response.read().decode())
except Exception as e:
    print(e)
