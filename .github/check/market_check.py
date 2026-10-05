# 一時的な確認用スクリプト（マーケット枠の候補フィードと数値取得元をGitHub上で試す）
import datetime, json
import feedparser, requests
H = {"User-Agent": "Mozilla/5.0 (compatible; daily-news-bot/2.0)"}
FEEDS = {
    "日経 マーケット": "https://assets.wor.jp/rss/rdf/nikkei/markets.rdf",
    "日経 マーケット2": "https://assets.wor.jp/rss/rdf/nikkei/market.rdf",
    "ロイター 経済": "https://assets.wor.jp/rss/rdf/reuters/business.rdf",
    "ロイター 市場": "https://assets.wor.jp/rss/rdf/reuters/markets.rdf",
    "ブルームバーグ": "https://assets.wor.jp/rss/rdf/bloomberg/top.rdf",
    "ブルームバーグ 市場": "https://assets.wor.jp/rss/rdf/bloomberg/markets.rdf",
    "株探 ニュース": "https://kabutan.jp/rss/news",
    "株探 市況": "https://kabutan.jp/news/marketnews/rss",
    "みんかぶ": "https://minkabu.jp/news/rss",
    "Yahoo!ファイナンス": "https://news.yahoo.co.jp/rss/media/finance/all.xml",
    "ZAi": "https://diamond.jp/zai/list/feed/rss",
    "東洋経済 マーケット": "https://toyokeizai.net/list/feed/rss/category/market",
    "モーニングスター": "https://www.morningstar.co.jp/rss/news.xml",
    "fisco": "https://web.fisco.jp/platform/rss/news",
    "トレーダーズ": "https://www.traders.co.jp/rss/news.xml",
    "NHK 経済": "https://news.web.nhk/n-data/conf/na/rss/cat5.xml",
}
now = datetime.datetime.now(datetime.timezone.utc)
for n, u in FEEDS.items():
    try:
        r = requests.get(u, headers=H, timeout=15)
        es = feedparser.parse(r.content).entries
        ts = [e.get("published_parsed") or e.get("updated_parsed") for e in es]
        ts = [datetime.datetime(*t[:6], tzinfo=datetime.timezone.utc) for t in ts if t]
        fresh = sum(1 for t in ts if now - t < datetime.timedelta(hours=30))
        print(f"FEED {n}: http{r.status_code} {len(es)}件 新着{fresh} 最新{max(ts) if ts else None}")
        for e in es[:4]:
            print("   -", e.get("title", "")[:50])
    except Exception as e:
        print(f"FEED {n}: ERR {str(e)[:100]}")

for sym in ["^N225", "^DJI", "JPY=X", "^GSPC", "^IXIC", "^TNX"]:
    for host in ["query1", "query2"]:
        try:
            r = requests.get(f"https://{host}.finance.yahoo.com/v8/finance/chart/{sym}",
                             params={"range": "5d", "interval": "1d"}, headers=H, timeout=15)
            m = r.json()["chart"]["result"][0]["meta"]
            print(f"YAHOO {host} {sym}: http{r.status_code} price={m.get('regularMarketPrice')} prev={m.get('chartPreviousClose')} t={m.get('regularMarketTime')}")
        except Exception as e:
            print(f"YAHOO {host} {sym}: ERR {r.status_code if 'r' in dir() else ''} {str(e)[:80]}")
for sym in ["^nkx", "^dji", "usdjpy", "^spx"]:
    try:
        r = requests.get("https://stooq.com/q/l/", params={"s": sym, "f": "sd2t2ohlcv", "h": "", "e": "csv"}, headers=H, timeout=15)
        print(f"STOOQ {sym}: http{r.status_code} {r.text.strip()[:150]!r}")
    except Exception as e:
        print(f"STOOQ {sym}: ERR {str(e)[:80]}")
