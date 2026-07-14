import requests
proxies = {'http': 'socks5://127.0.0.1:9150', 'https': 'socks5://127.0.0.1:9150'}
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.0.0 Safari/537.36',
    'accept-language': 'en-US,en',
    'accept': 'text/html,application/xhtml+xml,application/xml'
}
try:
    r = requests.get('https://scholar.google.com/scholar?q=urban+AND+%22green+space%22', proxies=proxies, headers=headers, timeout=10)
    print("gs_res_ccl in text:", "gs_res_ccl" in r.text)
    print("gs_top in text:", "gs_top" in r.text)
    print("gs_ab_rt in text:", "gs_ab_rt" in r.text)
    print("gs_nori in text:", "gs_nori" in r.text) # "Did not match any articles" container
except Exception as e:
    print("Failed:", e)
