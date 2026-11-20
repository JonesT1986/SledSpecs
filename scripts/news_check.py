"""Validate data/news.csv. Exit 1 on any problem."""
import csv, re, sys
from datetime import date
ROOT = __file__.rsplit("/scripts/", 1)[0]
CATS = {"New models", "Reviews", "Racing", "Recalls", "Vintage", "Trails and clubs", "Industry"}
bad, urls = [], set()
with open(f"{ROOT}/data/news.csv", newline="", encoding="utf-8") as fh:
    rows = list(csv.DictReader(fh))
for i, r in enumerate(rows, 2):
    if list(r.keys()) != ["date", "title", "source", "url", "category", "summary"]:
        bad.append(f"line {i}: wrong columns"); continue
    try:
        d = date.fromisoformat(r["date"])
        if d > date.today():
            bad.append(f"line {i}: date in the future")
    except ValueError:
        bad.append(f"line {i}: bad date {r['date']!r}")
    if not r["url"].startswith("https://"): bad.append(f"line {i}: url must start with https://")
    if r["url"] in urls: bad.append(f"line {i}: duplicate url")
    urls.add(r["url"])
    if r["category"] not in CATS: bad.append(f"line {i}: category {r['category']!r} not allowed")
    if not 10 <= len(r["title"]) <= 90: bad.append(f"line {i}: title length {len(r['title'])}")
    if not 30 <= len(r["summary"]) <= 300: bad.append(f"line {i}: summary length {len(r['summary'])}")
    if not r["source"].strip(): bad.append(f"line {i}: no source")
print("\n".join(bad) or f"news.csv ok: {len(rows)} stories")
sys.exit(1 if bad else 0)
