import feedparser, requests
from urllib.parse import quote
H = {"User-Agent": "Mozilla/5.0 (compatible; daily-news-bot/2.0)"}
QS = [
 "site:jp.reuters.com intitle:株式市場 OR intitle:外為市場 OR intitle:債券市場 when:1d",
 "site:jp.reuters.com allintitle:市場 when:1d",
 "site:jp.reuters.com intitle:市場 when:1d",
 "site:jp.reuters.com 東京株式市場 when:2d",
 "site:jp.reuters.com \"＝今週の\" when:3d",
]
for q in QS:
    u = "https://news.google.com/rss/search?hl=ja&gl=JP&ceid=JP:ja&q=" + quote(q, safe=":/")
    es = feedparser.parse(requests.get(u, headers=H, timeout=15).content).entries
    print("Q", q, len(es))
    for e in es[:10]: print("   -", e.title[:70])
