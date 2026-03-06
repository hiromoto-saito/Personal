"""
毎朝Discordにニュースを送信するボット（完全無料版）
- RSSフィードからテクノロジー・経済・社会ニュースを取得
- Discord Webhookで送信（AI要約なし）
"""

import os
import feedparser
import requests
from datetime import datetime, timezone, timedelta

# ─── 設定 ────────────────────────────────────────────────────────────────────

DISCORD_WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]

JST = timezone(timedelta(hours=9))

RSS_FEEDS = {
    "🤖 テクノロジー・AI": [
        "https://gigazine.net/news/rss_2.0/",
        "https://rss.itmedia.co.jp/rss/2.0/news_bursts.xml",
    ],
    "💰 経済・マーケット": [
        # ロイター 日本語（株・為替・マーケット速報）
        "https://feeds.reuters.com/reuters/JPbusinessNews",
        # Yahoo!ファイナンス（株・マーケット動向）
        "https://news.yahoo.co.jp/rss/topics/stock.xml",
        # NHK 経済（日本経済・景気全般）
        "https://www3.nhk.or.jp/rss/news/cat5.xml",
        # ロイター 世界経済（海外・グローバル動向）
        "https://feeds.reuters.com/reuters/businessNews",
    ],
    "🌍 社会・国際": [
        "https://www3.nhk.or.jp/rss/news/cat6.xml",
        "https://news.yahoo.co.jp/rss/topics/world.xml",
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://feeds.reuters.com/reuters/worldNews",
    ],
}

MAX_ARTICLES_PER_CATEGORY = 5


# ─── ニュース取得 ──────────────────────────────────────────────────────────────

def fetch_articles(feeds: list[str], max_articles: int) -> list[dict]:
    articles = []
    for url in feeds:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                articles.append({
                    "title": entry.get("title", "タイトルなし"),
                    "link":  entry.get("link", ""),
                })
        except Exception as e:
            print(f"[WARN] フィード取得失敗: {url} -> {e}")

    seen, unique = set(), []
    for a in articles:
        if a["title"] not in seen:
            seen.add(a["title"])
            unique.append(a)
        if len(unique) >= max_articles:
            break
    return unique


# ─── Discord送信 ───────────────────────────────────────────────────────────────

def send_to_discord(content: str) -> None:
    chunks = [content[i:i+1900] for i in range(0, len(content), 1900)]
    for chunk in chunks:
        resp = requests.post(
            DISCORD_WEBHOOK_URL,
            json={"content": chunk},
            timeout=10,
        )
        resp.raise_for_status()


# ─── メイン ───────────────────────────────────────────────────────────────────

def main():
    now = datetime.now(JST)
    date_str = now.strftime("%Y年%m月%d日 (%a)")

    send_to_discord(f"# 📰 おはよう！{date_str} の気になるニュースまとめ 👀\n{'─' * 40}")

    for category, feeds in RSS_FEEDS.items():
        print(f"[INFO] {category} 取得中...")
        articles = fetch_articles(feeds, MAX_ARTICLES_PER_CATEGORY)

        if not articles:
            send_to_discord(f"\n**{category}**\nニュースを取得できませんでした。\n")
            continue

        lines = [f"\n**{category}**"]
        for a in articles:
            lines.append(f"・{a['title']}\n　{a['link']}")
        send_to_discord("\n".join(lines))
        print(f"[INFO] {category} 送信完了")

    send_to_discord("─" * 40 + "\n✅ 以上！今日も一日がんばろう 💪")


if __name__ == "__main__":
    main()
