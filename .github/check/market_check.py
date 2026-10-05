# 一時的な確認用スクリプト（マーケット枠の候補フィードと数値取得元をGitHub上で試す）その2
import datetime, re
import feedparser, requests
H = {"User-Agent": "Mozilla/5.0 (compatible; daily-news-bot/2.0)"}
GN = "https://news.google.com/rss/search?hl=ja&gl=JP&ceid=JP:ja&q="
FEEDS = {
    "日経 マーケット": "https://assets.wor.jp/rss/rdf/nikkei/markets.rdf",
    "時事 経済(wor)": "https://assets.wor.jp/rss/rdf/jiji/economy.rdf",
    "産経 経済(wor)": "https://assets.wor.jp/rss/rdf/sankei/economy.rdf",
    "読売 経済(wor)": "https://assets.wor.jp/rss/rdf/yomiuri/economy.rdf",
    "Investing 株式": "https://jp.investing.com/rss/news_25.rss",
    "Investing 為替": "https://jp.investing.com/rss/news_1.rss",
    "Investing 経済指標": "https://jp.investing.com/rss/news_95.rss",
    "Investing 経済": "https://jp.investing.com/rss/news_14.rss",
    "GoogleNews 市況": GN + "%E6%97%A5%E7%B5%8C%E5%B9%B3%E5%9D%87+OR+%E3%83%89%E3%83%AB%E5%86%86+OR+%E7%B1%B3%E5%9B%BD%E6%A0%AA+when:1d",
    "GoogleNews 経済指標": GN + "%E9%9B%87%E7%94%A8%E7%B5%B1%E8%A8%88+OR+CPI+OR+GDP+OR+%E6%97%A5%E9%8A%80%E7%9F%AD%E8%A6%B3+OR+FOMC+when:1d",
    "ロイター(GoogleNews)": GN + "site:jp.reuters.com+%E5%B8%82%E5%A0%B4+when:1d",
    "Yahoo!ファイナンス news": "https://finance.yahoo.co.jp/rss/news",
    "Yahoo トピ経済": "https://news.yahoo.co.jp/rss/topics/business.xml",
    "minkabu FX": "https://fx.minkabu.jp/news/rss",
    "ZAi FX": "https://zai.diamond.jp/list/feed/rss/fxnews",
    "ITmedia ビジネス": "https://rss.itmedia.co.jp/rss/2.0/business.xml",
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
        for e in es[:5]:
            print("   -", e.get("title", "")[:60], "|", e.get("link", "")[:60])
    except Exception as e:
        print(f"FEED {n}: ERR {str(e)[:100]}")

try:
    r = requests.get("https://www.wor.jp/rss/", headers=H, timeout=15)
    print("WORINDEX", r.status_code, sorted(set(re.findall(r"assets\.wor\.jp/rss/rdf/[a-z0-9_]+/[a-z0-9_]+\.rdf", r.text)))[:300])
except Exception as e:
    print("WORINDEX ERR", e)

for sym in ["^N225", "^DJI", "JPY=X", "^TOPX", "998405.T", "1306.T"]:
    try:
        r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}",
                         params={"range": "5d", "interval": "1d"}, headers=H, timeout=15)
        res = r.json()["chart"]["result"][0]
        closes = res["indicators"]["quote"][0]["close"]
        print(f"YAHOO {sym}: ts={res.get('timestamp')} closes={closes} meta_price={res['meta'].get('regularMarketPrice')}")
    except Exception as e:
        print(f"YAHOO {sym}: ERR {str(e)[:80]}")
