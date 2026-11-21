#!/usr/bin/env python3
"""Check data/mods/*.json before pushing. Usage: python3 scripts/mods_check.py
Exits 1 on any FIX. sled_id must match a real sled page (the part of the URL after /snowmobiles/)."""
import json, os, re, sys, subprocess
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATS = ["Clutch kits", "Exhaust cans", "Full exhaust / stage kits", "Turbo kits", "Big bore kits", "Other"]
REQ = ["category", "maker", "product_name", "source_url", "checked"]
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
dist = os.path.join(ROOT, "dist", "snowmobiles")
if not os.path.isdir(dist):
    subprocess.run([sys.executable, os.path.join(ROOT, "build.py")], check=True, stdout=subprocess.DEVNULL)
problems = 0
def bad(where, msg):
    global problems; problems += 1; print(f"FIX  {where}: {msg}")
folder = os.path.join(ROOT, "data", "mods")
seen = 0
for fn in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
    if not fn.endswith(".json"): continue
    try:
        data = json.load(open(os.path.join(folder, fn), encoding="utf-8"))
    except Exception as ex:
        bad(fn, f"not valid JSON ({ex})"); continue
    for i, item in enumerate(data if isinstance(data, list) else [data]):
        sid = (item.get("sled_id") or "").strip("/"); w = f"{fn}#{i} {sid}"; seen += 1
        if not os.path.isfile(os.path.join(dist, sid, "index.html")):
            bad(w, "sled_id doesn't match any sled page")
        for j, m in enumerate(item.get("mods", [])):
            mw = f"{w} mod {j} ({m.get('maker','?')} {m.get('product_name','?')})"
            for k in REQ:
                if not m.get(k): bad(mw, f"missing {k}")
            if m.get("category") and m["category"] not in CATS: bad(mw, f"category must be one of {CATS}")
            if m.get("source_url") and not str(m["source_url"]).startswith("https://"): bad(mw, "source_url must be https")
            for k in ("checked", "price_checked"):
                if m.get(k) and not ISO.match(str(m[k])): bad(mw, f"{k} must be YYYY-MM-DD")
            if m.get("price") not in (None, ""):
                if not m.get("currency"): bad(mw, "price without currency")
                if not m.get("price_checked"): bad(mw, "price without price_checked")
            for k in ("claims", "requirements"):
                if k in m and not isinstance(m[k], list): bad(mw, f"{k} must be a list")
        for j, x in enumerate(item.get("not_listed", [])):
            for k in ("maker", "reason", "checked"):
                if not x.get(k): bad(f"{w} not_listed {j}", f"missing {k}")
print(f"{seen} sled entries checked, {problems} problems")
sys.exit(1 if problems else 0)
