"""
毎朝Discordにニュースを送信するボット（完全無料版）
- RSSフィードからテクノロジー・経済・政治・国際ニュースを取得
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
            "https://www3.nhk.or.jp/rss/news/cat4.xml",        # NHK 政治
            "https://news.yahoo.co.jp/rss/topics/domestic.xml",  # Yahoo!ニュース 国内
        ],
    },
    "💰 経済・マーケット": {
        "max": 8,
        "feeds": [
            "https://www3.nhk.or.jp/rss/news/cat5.xml",          # NHK 経済
            "https://news.yahoo.co.jp/rss/topics/business.xml",  # Yahoo!ニュース 経済
            "https://toyokeizai.net/list/feed/rss",              # 東洋経済オンライン
            "https://diamond.jp/list/feed/rss",                  # ダイヤモンド・オンライン
        ],
    },
    "🌍 国際": {
        "max": 8,
        "feeds": [
            "https://www3.nhk.or.jp/rss/news/cat6.xml",          # NHK 国際
            "https://feeds.bbci.co.uk/japanese/rss.xml",         # BBCニュース 日本語
            "https://feeds.afpbb.com/rss/afpbb/afpbbnews",       # AFPBB News
            "https://feeds.cnn.co.jp/rss/cnn/cnn.rdf",           # CNN Japan
            "https://news.yahoo.co.jp/rss/topics/world.xml",     # Yahoo!ニュース 国際
        ],
    },
    "🤖 テクノロジー・IT": {
        "max": 6,
        "feeds": [
            "https://rss.itmedia.co.jp/rss/2.0/news_bursts.xml",  # ITmedia NEWS
            "https://rss.itmedia.co.jp/rss/2.0/securitynews.xml",  # ITmedia セキュリティ
            "https://gigazine.net/news/rss_2.0/",                  # GIGAZINE
            "https://www.gizmodo.jp/index.xml",                    # Gizmodo Japan
        ],
    },
}

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


def fetch_feed(url: str) -> list[dict]:
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
        if not title or not link:
            continue
        articles.append({
            "title": title,
            "link": link,
            "key": normalize_link(link),
            "published": entry_published(entry),
        })
    articles.sort(key=lambda a: a["published"] or datetime.min.replace(tzinfo=timezone.utc),
                  reverse=True)
    return articles


def pick_articles(feeds: list[str], max_articles: int, now: datetime,
                  history: dict[str, str], taken: set[str]) -> tuple[list[dict], list[str]]:
    """
    各フィードから新しい未配信記事を集め、フィードを順番に巡って1件ずつ選ぶ。
    取得に失敗したフィードがあっても、他のフィードで枠を埋める。
    """
    fresh_cutoff = now - timedelta(hours=FRESH_HOURS)
    candidates, failed = [], []

    for url in feeds:
        try:
            articles = fetch_feed(url)
        except Exception as e:
            print(f"[WARN] フィード取得失敗: {url} -> {e}")
            failed.append(url)
            continue
        usable = [
            a for a in articles
            if (a["published"] is None or a["published"] >= fresh_cutoff)
            and not any(k in history or k in taken for k in history_keys(a))
        ]
        print(f"[INFO]   {url}: {len(articles)}件中 {len(usable)}件が新着")
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
    # [タイトル](<URL>) 形式：タイトルがリンクになり、<> でリンクプレビューを抑制する
    title = a["title"].replace("[", "［").replace("]", "］")
    return f"・[{title}](<{a['link']}>)"


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
        lines.append(f"⚠️ 取得に失敗したフィード: {len(all_failed)}件（Actionsのログを確認）")
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
