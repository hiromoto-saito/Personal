import re, requests
r = requests.get("https://feeds.cnn.co.jp/rss/cnn/cnn.rdf", headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
t = r.content.decode("utf-8", "replace")
print("HIST", [(h.status_code, h.headers.get("location")) for h in r.history])
print("TITLE", re.findall(r"<title>(.*?)</title>", t, re.S)[:2])
print("DESC", re.findall(r'name="description" content="([^"]*)"', t)[:1])
body = re.sub(r"<script.*?</script>|<style.*?</style>", " ", t, flags=re.S)
txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body))
print("TEXT", txt[:1500])
