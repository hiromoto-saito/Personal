import re, requests, feedparser
H = {"User-Agent": "Mozilla/5.0 (compatible; daily-news-bot/2.0)"}
B = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}
URLS = [
 "https://feeds.cnn.co.jp/rss/cnn/cnn.rdf",
 "http://feeds.cnn.co.jp/rss/cnn/cnn.rdf",
 "https://feeds.cnn.co.jp/rss/cnn/world.rdf",
 "https://feeds.cnn.co.jp/rss/cnn/usa.rdf",
 "https://feeds.cnn.co.jp/rss/cnn/business.rdf",
 "https://www.cnn.co.jp/rss/cnn/cnn.rdf",
 "https://www.cnn.co.jp/rss/",
 "https://assets.wor.jp/rss/rdf/cnn/top.rdf",
 "https://www.cnn.co.jp/",
]
for u in URLS:
    for name, h in (("bot", H), ("browser", B)):
        try:
            r = requests.get(u, headers=h, timeout=15, allow_redirects=True)
            f = feedparser.parse(r.content)
            print(f"{name} {u} -> {r.status_code} final={r.url} type={r.headers.get('content-type')} len={len(r.content)} entries={len(f.entries)} bozo={f.bozo} {str(f.get('bozo_exception',''))[:80]}")
            if u.endswith("/") :
                print("   rss links:", sorted(set(re.findall(r'https?://[^"\s]*(?:rss|rdf|xml|feed)[^"\s]*', r.text)))[:20])
            elif not f.entries:
                print("   head:", r.text[:300].replace("\n", " "))
            else:
                e = f.entries[0]; print("   first:", e.get("title","")[:40], e.get("published", e.get("updated","")))
        except Exception as ex:
            print(f"{name} {u} ERR {ex}")
