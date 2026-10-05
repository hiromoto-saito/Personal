"""
毎朝Discordにニュースを送信するボット（完全無料版）
- RSSフィードからテクノロジー・経済・マーケット・政治・国際ニュースを取得
- 冒頭に主要な株価指数・為替の直近値と前日比を表示（Yahoo!ファイナンスの公開データ）
- 配信済み記事を sent_history.json に記録し、翌日以降の重複配信を防ぐ
- 公開から一定時間以上経った古い記事は送らない
- Discord Webhookで送信（AI要約なし・日本語メディアのみ）

環境変数:
  DISCORD_WEBHOOK_URL  送信先のWebhook URL（DRY_RUN時は不要）
  DRY_RUN=1            Discordに送らず標準出力に表示する（動作確認用）
"""

import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import feedparser
import requests

# ─── 設定 ────────────────────────────────────────────────────────────────────

DRY_RUN = os.environ.get("DRY_RUN") == "1"
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

JST = timezone(timedelta(hours=9))

# この時間より前に公開された記事は送らない（毎日1回実行なので少し余裕を持たせる）
FRESH_HOURS = 30
# 配信履歴を何日分残すか（これより古い履歴は自動で削除）
HISTORY_DAYS = 14
HISTORY_FILE = Path(__file__).with_name("sent_history.json")

# カテゴリごとに「フィード一覧」と「最大件数」を設定する
RSS_FEEDS = {
    "🏛️ 政治": {
        "max": 6,
        "feeds": [
            ("NHK 政治", "https://news.web.nhk/n-data/conf/na/rss/cat4.xml"),
            ("産経 政治", "https://assets.wor.jp/rss/rdf/sankei/politics.rdf"),
            ("読売 政治", "https://assets.wor.jp/rss/rdf/yomiuri/politics.rdf"),
            ("Yahoo!ニュース 国内", "https://news.yahoo.co.jp/rss/topics/domestic.xml"),
        ],
    },
    "💰 経済": {
        "max": 8,
        "feeds": [
            ("NHK 経済", "https://news.web.nhk/n-data/conf/na/rss/cat5.xml"),
            ("日経 経済", "https://assets.wor.jp/rss/rdf/nikkei/economy.rdf"),
            ("Yahoo!ニュース 経済", "https://news.yahoo.co.jp/rss/topics/business.xml"),
            ("東洋経済オンライン", "https://toyokeizai.net/list/feed/rss"),
            ("ダイヤモンド・オンライン", "https://diamond.jp/list/feed/rss/dol"),
        ],
    },
    "📈 マーケット": {
        "max": 6,
        "feeds": [
            ("日経 マーケット", "https://assets.wor.jp/rss/rdf/nikkei/markets.rdf"),
            # ロイターは公式RSSが無いため、Googleニュースで市況関連の記事を検索して取る
            ("ロイター", "https://news.google.com/rss/search?hl=ja&gl=JP&ceid=JP:ja&q="
             "site:jp.reuters.com%20%28%E6%A0%AA%E5%BC%8F%E5%B8%82%E5%A0%B4%20OR%20%E5%A4%96%E7%82%BA%E5%B8%82%E5%A0%B4%20OR%20%E5%82%B5%E5%88%B8%E5%B8%82%E5%A0%B4%20OR%20%E6%97%A5%E7%B5%8C%E5%B9%B3%E5%9D%87%20OR%20NY%E6%A0%AA%20OR%20%E7%B1%B3%E5%9B%BD%E6%A0%AA%20OR%20%E3%83%89%E3%83%AB/%E5%86%86%29%20when:1d"),
            ("Investing.com 経済指標", "https://jp.investing.com/rss/news_95.rss"),
            ("Investing.com 市況", "https://jp.investing.com/rss/news_1.rss"),
        ],
    },
    "🌍 国際": {
        "max": 8,
        "feeds": [
            ("NHK 国際", "https://news.web.nhk/n-data/conf/na/rss/cat6.xml"),
            ("BBCニュース 日本語", "https://feeds.bbci.co.uk/japanese/rss.xml"),
            ("産経 国際", "https://assets.wor.jp/rss/rdf/sankei/world.rdf"),
            ("CNN Japan", "https://feeds.cnn.co.jp/rss/cnn/cnn.rdf"),
            ("Yahoo!ニュース 国際", "https://news.yahoo.co.jp/rss/topics/world.xml"),
        ],
    },
    "🤖 テクノロジー・IT": {
        "max": 6,
        "feeds": [
            ("ITmedia NEWS", "https://rss.itmedia.co.jp/rss/2.0/news_bursts.xml"),
            ("日経クロステック", "https://xtech.nikkei.com/rss/index.rdf"),
            ("Publickey", "https://www.publickey1.jp/atom.xml"),
            ("ITmedia セキュリティ", "https://rss.itmedia.co.jp/rss/2.0/news_security.xml"),
            ("GIGAZINE", "https://gigazine.net/news/rss_2.0/"),
            ("Gizmodo Japan", "https://www.gizmodo.jp/index.xml"),
        ],
    },
}

# 冒頭に表示する指標（表示名, Yahoo!ファイナンスのシンボル, 小数点以下の桁数, 変化を%で出すか）
MARKET_INDICATORS = [
    ("日経平均", "^N225", 0, True),
    ("NYダウ", "^DJI", 0, True),
    ("S&P500", "^GSPC", 0, True),
    ("ナスダック", "^IXIC", 0, True),
    ("ドル円", "JPY=X", 2, False),
    ("米10年債利回り", "^TNX", 3, False),
]
MARKET_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; daily-news-bot/2.0)"}
WEEKDAYS_JA = "月火水木金土日"
DISCORD_LIMIT = 1900  # Discordの上限2000文字に余裕を持たせる


# ─── 配信履歴 ──────────────────────────────────────────────────────────────────

def normalize_link(url: str) -> str:
    """クエリやフラグメントを除いたURLを返す（同じ記事の表記ゆれ対策）"""
    parts = urlsplit(url.strip())
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path.rstrip("/"), "", ""))


def load_history(now: datetime) -> dict[str, str]:
    """{キー: 配信日時ISO} を読み込み、古い履歴は捨てる"""
    if not HISTORY_FILE.exists():
        return {}
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"[WARN] 履歴ファイルを読めませんでした（空として扱います）: {e}")
        return {}
    cutoff = now - timedelta(days=HISTORY_DAYS)
    return {k: v for k, v in data.items() if datetime.fromisoformat(v) >= cutoff}


def save_history(history: dict[str, str]) -> None:
    HISTORY_FILE.write_text(
        json.dumps(history, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def history_keys(article: dict) -> list[str]:
    return [f"url:{article['key']}", f"title:{article['title']}"]


# ─── ニュース取得 ──────────────────────────────────────────────────────────────

def entry_published(entry) -> datetime | None:
    for field in ("published_parsed", "updated_parsed"):
        t = entry.get(field)
        if t:
            return datetime(*t[:6], tzinfo=timezone.utc)
    return None


def fetch_feed(source: str, url: str) -> list[dict]:
    """1つのフィードを取得して記事のリストを返す（新しい順）"""
    resp = requests.get(url, headers=REQUEST_HEADERS, timeout=15)
    resp.raise_for_status()
    feed = feedparser.parse(resp.content)
    if not feed.entries:
        raise ValueError("記事が0件でした（URLの変更やフィード形式の問題の可能性）")

    articles = []
    for entry in feed.entries:
        title = " ".join(entry.get("title", "").split())
        link = entry.get("link", "")
        if "news.google.com" in link:  # 末尾の「 - 媒体名」を除く
            title = title.rsplit(" - ", 1)[0]
        if not title or not link:
            continue
        articles.append({
            "title": title,
            "link": link,
            "key": normalize_link(link),
            "source": source,
            "published": entry_published(entry),
        })
    articles.sort(key=lambda a: a["published"] or datetime.min.replace(tzinfo=timezone.utc),
                  reverse=True)
    return articles


def pick_articles(feeds: list[tuple[str, str]], max_articles: int, now: datetime,
                  history: dict[str, str], taken: set[str]) -> tuple[list[dict], list[str]]:
    """
    各フィードから新しい未配信記事を集め、フィードを順番に巡って1件ずつ選ぶ。
    取得に失敗したフィードがあっても、他のフィードで枠を埋める。
    """
    fresh_cutoff = now - timedelta(hours=FRESH_HOURS)
    candidates, failed = [], []

    for source, url in feeds:
        try:
            articles = fetch_feed(source, url)
        except Exception as e:
            print(f"[WARN] フィード取得失敗: {url} -> {e}")
            failed.append(source)
            continue
        usable = [
            a for a in articles
            if (a["published"] is None or a["published"] >= fresh_cutoff)
            and not any(k in history or k in taken for k in history_keys(a))
        ]
        print(f"[INFO]   {source}: {len(articles)}件中 {len(usable)}件が新着")
        candidates.append(usable)

    picked = []
    while len(picked) < max_articles and any(candidates):
        for queue in candidates:
            if not queue or len(picked) >= max_articles:
                continue
            a = queue.pop(0)
            keys = history_keys(a)
            if any(k in taken for k in keys):  # 別フィードで同じ記事を選択済み
                continue
            taken.update(keys)
            picked.append(a)
    return picked, failed


# ─── マーケット指標 ─────────────────────────────────────────────────────────────

def fetch_indicator(symbol: str) -> tuple[float, float]:
    """直近値と、その1つ前の営業日の終値を返す"""
    resp = requests.get(MARKET_CHART_URL.format(symbol=symbol),
                        params={"range": "5d", "interval": "1d"},
                        headers=REQUEST_HEADERS, timeout=15)
    resp.raise_for_status()
    result = resp.json()["chart"]["result"][0]
    closes = [c for c in result["indicators"]["quote"][0]["close"] if c is not None]
    if len(closes) < 2:
        raise ValueError("終値が足りません")
    return closes[-1], closes[-2]


def market_lines() -> tuple[list[str], bool]:
    """指標ごとの表示行と、取得に失敗した指標があったかを返す"""
    lines, failed = [], False
    for name, symbol, digits, as_percent in MARKET_INDICATORS:
        try:
            last, prev = fetch_indicator(symbol)
        except Exception as e:
            print(f"[WARN] 指標取得失敗: {symbol} -> {e}")
            failed = True
            continue
        diff = last - prev
        arrow = "🔺" if diff > 0 else "🔻" if diff < 0 else "➖"
        change = f"{diff / prev * 100:+.2f}%" if as_percent else f"{diff:+,.{digits}f}"
        lines.append(f"・{name}　**{last:,.{digits}f}**　{arrow}{change}")
    return lines, failed


# ─── Discord送信 ───────────────────────────────────────────────────────────────

def post_to_discord(content: str) -> None:
    if DRY_RUN:
        print(content + "\n")
        return
    for attempt in range(3):
        resp = requests.post(DISCORD_WEBHOOK_URL, json={"content": content}, timeout=10)
        if resp.status_code == 429:  # レート制限：指定秒数待って再送
            wait = float(resp.json().get("retry_after", 1))
            print(f"[WARN] Discordのレート制限。{wait}秒待って再送します")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        time.sleep(0.5)
        return
    raise RuntimeError("Discordへの送信に3回失敗しました")


def send_lines(lines: list[str]) -> None:
    """行の途中で切れないように、上限文字数ごとにまとめて送る"""
    buf = ""
    for line in lines:
        if buf and len(buf) + len(line) + 1 > DISCORD_LIMIT:
            post_to_discord(buf)
            buf = ""
        buf = f"{buf}\n{line}" if buf else line
    if buf:
        post_to_discord(buf)


def format_article(a: dict) -> str:
    # タイトルは普通の文字で表示し、末尾に出典名つきの小さなリンクを付ける
    # （<> で囲むとDiscordのリンクプレビューが出ない）
    return f"・{a['title']}　[🔗{a['source']}](<{a['link']}>)"


# ─── メイン ───────────────────────────────────────────────────────────────────

def main():
    if not DRY_RUN and not DISCORD_WEBHOOK_URL:
        raise SystemExit("DISCORD_WEBHOOK_URL が設定されていません")

    now = datetime.now(JST)
    date_str = f"{now:%Y年%m月%d日}（{WEEKDAYS_JA[now.weekday()]}）"
    history = load_history(now)
    taken: set[str] = set()

    lines = [f"# 📰 おはよう！{date_str} のニュースまとめ 👀", "─" * 30]
    all_failed, total = [], 0

    print("[INFO] マーケット指標 取得中...")
    indicators, indicator_failed = market_lines()
    if indicator_failed:
        all_failed.append("マーケット指標")
    if indicators:
        lines.append("\n**📊 マーケット指標**（直近値・前営業日比）")
        lines += indicators

    for category, conf in RSS_FEEDS.items():
        print(f"[INFO] {category} 取得中...")
        articles, failed = pick_articles(conf["feeds"], conf["max"], now, history, taken)
        all_failed += failed
        total += len(articles)

        lines.append(f"\n**{category}**")
        if articles:
            lines += [format_article(a) for a in articles]
        elif len(failed) == len(conf["feeds"]):
            lines.append("ニュースを取得できませんでした。")
        else:
            lines.append("新しいニュースはありませんでした。")

    lines.append("\n" + "─" * 30)
    if all_failed:
        lines.append(f"⚠️ 取得に失敗したフィード: {'、'.join(all_failed)}")
    lines.append(f"✅ 以上 {total}件！今日も一日がんばろう 💪")

    send_lines(lines)

    # 送信に成功した記事だけを履歴に記録する
    stamp = now.isoformat(timespec="seconds")
    for key in taken:
        history[key] = stamp
    if not DRY_RUN:
        save_history(history)
    print(f"[INFO] 送信完了: {total}件 / 失敗フィード {len(all_failed)}件")


if __name__ == "__main__":
    main()
