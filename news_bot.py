"""
毎朝Discordにニュースを送信するボット（完全無料版）
- RSSフィードからテクノロジー・経済・社会ニュースを取得
- Discord Webhookで送信（AI要約なし・日本語メディアのみ）
"""

import os
import feedparser
import requests
from datetime import datetime, timezone, timedelta

# ─── 設定 ────────────────────────────────────────────────────────────────────

DISCORD_WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]

JST = timezone(timedelta(hours=9))

RSS_FEEDS = {
    "🤖 テクノロジー・IT": [
        # ITmedia NEWS（IT全般・スタートアップ）
        "https://rss.itmedia.co.jp/rss/2.0/news_bursts.xml",
        # ITmedia セキュリティ（サイバー・セキュリティ）
        "https://rss.itmedia.co.jp/rss/2.0/securitynews.xml",
        # Engadget 日本版（ガジェット・ハードウェア）
        "https://japanese.engadget.com/rss.xml",
         # GIGAZINE（AI・ガジェット・新サービス）
        "https://gigazine.net/news/rss_2.0/",
    ],
    "💰 経済・マーケット": [
        # Yahoo!ニュース 経済（国内経済全般）
        "https://news.yahoo.co.jp/rss/topics/business.xml",
        # NHK 経済（日本経済・景気）
        "https://www3.nhk.or.jp/rss/news/cat5.xml",
        # ブルームバーグ 日本語版（経済政策・金融ニュース）
        "https://www.bloomberg.co.jp/feeds/bpol/sitemap_news.xml",
        # ダイヤモンド・オンライン（経済解説・マーケット）
        "https://diamond.jp/list/feed/rss",
    ],
    "🌍 社会・国際": [
        # NHK 国際（海外ニュース日本語）
        "https://www3.nhk.or.jp/rss/news/cat6.xml",
        # CNN Japan（米CNNの日本語版）
        "https://feeds.cnn.co.jp/rss/cnn/cnn.rdf",
        # AFPBB News（AFP通信の日本語版・国際速報）
        "https://feeds.afpbb.com/rss/afpbb/afpbbnews",
        # Yahoo!ニュース 国際
        "https://news.yahoo.co.jp/rss/topics/world.xml",
    ],
}

MAX_ARTICLES_PER_CATEGORY = 8


# ─── ニュース取得 ──────────────────────────────────────────────────────────────

def fetch_articles(feeds: list[str], max_articles: int) -> list[dict]:
    # フィードごとに均等に件数を割り当てる
    per_feed = max(1, max_articles // len(feeds))
    all_articles = []

    for url in feeds:
        try:
            feed = feedparser.parse(url)
            count = 0
            for entry in feed.entries:
                if count >= per_feed:
                    break
                all_articles.append({
                    "title": entry.get("title", "タイトルなし"),
                    "link":  entry.get("link", ""),
                })
                count += 1
        except Exception as e:
            print(f"[WARN] フィード取得失敗: {url} -> {e}")

    # 重複排除
    seen, unique = set(), []
    for a in all_articles:
        if a["title"] not in seen:
            seen.add(a["title"])
            unique.append(a)
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
