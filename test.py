import requests

proxies = {
    'http': 'http://127.0.0.1:8000',
    'https': 'http://127.0.0.1:8000',
}

r = requests.get("https://api.myip.com", proxies=proxies, timeout=10)
print(r.text)
