import re, requests
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}
for sym in ["^TOPX", "998405.T", "^TPX", "1306.T"]:
    try:
        r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}", params={"range": "5d", "interval": "1d"}, headers=H, timeout=15)
        print("YAHOO", sym, r.status_code, r.text[:200].replace("\n", " "))
    except Exception as e: print("YAHOO", sym, "ERR", e)
URLS = {
 "yjfinance": "https://finance.yahoo.co.jp/quote/998405.T",
 "google": "https://www.google.com/finance/quote/TOPIX:INDEXTOKYO",
 "nikkei": "https://www.nikkei.com/markets/worldidx/chart/topix/",
 "kabutan": "https://kabutan.jp/stock/?code=0010",
 "minkabu": "https://minkabu.jp/stock/KSISU1000",
 "investing": "https://jp.investing.com/indices/topix",
 "stooq": "https://stooq.com/q/l/?s=^tpx&f=sd2t2ohlcv&h&e=csv",
}
for n, u in URLS.items():
    try:
        r = requests.get(u, headers=H, timeout=15)
        t = r.text
        nums = re.findall(r"[23],\d{3}\.\d{2}", t)[:8]
        print("PAGE", n, r.status_code, len(t), nums)
        if n == "yjfinance":
            for k in ["previousPrice", "changePrice", "changePriceRate", "\"price\""]:
                i = t.find(k); print("   ", k, t[i:i+80] if i >= 0 else None)
        if n == "google":
            i = t.find('data-last-price'); print("   ", t[i:i+120] if i >= 0 else None)
            i = t.find('Previous close'); print("   ", re.sub(r"<[^>]+>", " ", t[i:i+300]) if i >= 0 else None)
    except Exception as e: print("PAGE", n, "ERR", e)
