import urllib.request
try:
    with urllib.request.urlopen('http://127.0.0.1:5000/data') as response:
        print(len(response.read()))
except Exception as e:
    print(e)
