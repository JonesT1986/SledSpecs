#!/usr/bin/env python3
"""SledSpecs static site generator.

Edit data/sleds.csv (one row per sled) and data/corrections.csv, then run:
    python3 build.py
Output goes to dist/. No third-party packages needed (Vercel runs this on every push).
Set the SLEDSPECS_CONTACT_EMAIL environment variable to choose where "send a correction" links go.
"""
import collections, csv, json, html, os, re, shutil, sys
from datetime import date

ROOT = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(ROOT, "dist")
SITE = "https://sledspecs.com"
SITE_NAME = "SledSpecs"
CONTACT_EMAIL = os.environ.get("SLEDSPECS_CONTACT_EMAIL", "").strip()  # empty = hide correction links
TODAY = date.today().isoformat()
import hashlib as _h
def _ver(f):
    try: return _h.md5(open(f,"rb").read()).hexdigest()[:10]
    except OSError: return TODAY
CSS_V, JS_V, SR_V = _ver("static/assets/site.css"), _ver("static/assets/app.js"), _ver("static/assets/search.js")

BRANDS = ["Ski-Doo", "Polaris", "Arctic Cat", "Yamaha"]
TYPES = ["Mountain", "Trail", "Crossover", "Utility", "Vintage"]
TYPE_BLURB = {
    "Mountain": "Deep-snow sleds with long, tall-lug tracks built for climbing and boondocking.",
    "Trail": "Short-track sleds built for groomed trails, cornering and bumps.",
    "Crossover": "Sleds that split the difference between trail and off-trail riding.",
    "Utility": "Work and two-up sleds: wide tracks, reverse, towing and hauling.",
    "Vintage": "Older sleds still running on traplines, ice and back trails.",
}
NUM = {"year": int, "cc": float, "cylinders": int, "hp": float, "dry_weight_lb": float,
       "track_length_in": float, "track_width_in": float, "lug_in": float, "fuel_gal": float,
       "length_in": float, "sprocket_pitch_in": float, "msrp_usd": float}

e = lambda s: html.escape(str(s), quote=True)


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def n(v):
    """Pretty number: 9.5 -> '9.5', 165.0 -> '165'."""
    if v is None:
        return None
    return str(int(v)) if float(v).is_integer() else str(v)


def hp_gap(s, long=False):
    """Wording for a missing horsepower figure. Modern Polaris/Yamaha genuinely don't publish it;
    for older sleds we only know our source doesn't list it."""
    if s["year"] >= 2010 and s["brand"] in ("Polaris", "Yamaha"):
        return f"Not published by {s['brand']}" if long else "Not published"
    return "Not in our source" if long else "Not listed"


def wt_gap(s, long=False):
    """Wording for a missing dry weight. Arctic Cat doesn't release weights for its 2026+ sleds."""
    if s["year"] >= 2026 and s["brand"] == "Arctic Cat":
        return "Not published by Arctic Cat" if long else "Not published"
    return None


AMAZON_TAG = os.environ.get("SLEDSPECS_AMAZON_TAG", "sledspecs-20").strip()


def amazon_url(s):
    """Amazon.ca search for this sled's OEM belt part number, tagged with our Associates ID."""
    q = re.sub(r"\s+", "+", f"{s['brand']} {s['belt_pn']} drive belt")
    return f"https://www.amazon.ca/s?k={q}&tag={AMAZON_TAG}"


def buy_link(s, cls="btn buy wide", label="Check belt price on Amazon"):
    if not (AMAZON_TAG and s["belt_pn"]):
        return ""
    return f'<a class="{cls}" href="{amazon_url(s)}" rel="sponsored nofollow noopener" target="_blank">{label}</a>'


FOUR_STROKE = re.compile(r"ACE|4-TEC|Genesis|ProStar|4-stroke|four-stroke|\b(7000|9000)\b", re.I)
SKIP_WORDS = {"patriot", "boost", "9r", "prostar", "s4", "rotax", "the"}
OIL = {"Ski-Doo": "Ski-Doo XPS 2-stroke synthetic oil", "Polaris": "Polaris VES 2-cycle oil",
       "Arctic Cat": "Arctic Cat C-TEC2 2-stroke oil", "Yamaha": "Yamalube 2-stroke snowmobile oil"}


def load_plugs():
    f = os.path.join(ROOT, "data", "plugs.csv")
    return list(csv.DictReader(open(f, encoding="utf-8"))) if os.path.exists(f) else []


PLUGS = None


def plug_for(s):
    global PLUGS
    if PLUGS is None:
        PLUGS = load_plugs()
    for p in PLUGS:
        if (p["brand"] == s["brand"] and p["engine"] == (s["engine"] or "").strip() and s["year"] >= int(p["min_year"] or 0)
                and (not p["model_contains"] or p["model_contains"] in s["model"])
                and (not p["model_excludes"] or p["model_excludes"] not in s["model"])):
            return p
    return None


def family(s):
    ws = s["model"].split()
    for i, w in enumerate(ws):
        if re.search(r"[a-z]", w, re.I) and w.lower() not in SKIP_WORDS and not re.match(r"^\d", w):
            return " ".join(ws[i:i + 2]) if w.lower() in ("grand", "pro", "safari") and i + 1 < len(ws) else w
    return ""


def amz(q):
    return f"https://www.amazon.ca/s?k={re.sub(r'\s+', '+', q.strip())}&tag={AMAZON_TAG}"


def cover_q(s, fam):
    plat = s["platform"] if s["platform"] and len(s["platform"]) < 20 and "(" not in s["platform"] and s["platform"] != "Youth" else ""
    tl = n(s["track_length_in"]) if s["track_length_in"] else ""
    return " ".join(x for x in [s["brand"], plat, fam, tl, "snowmobile cover"] if x)


def parts_box(s):
    """Tagged Amazon.ca searches for the parts and supplies this sled actually uses."""
    if not AMAZON_TAG:
        return ""
    br, fam, eng = s["brand"], family(s), (s["engine"] or "")
    four = bool(FOUR_STROKE.search(eng + " " + (s["engine_detail"] or "")))
    items = []
    if s["year"] < 1990:
        items += [("Parts for vintage " + br + " sleds", f"vintage {br} snowmobile parts"),
                  (f"{br} {fam} service manual", f"{br} {fam} snowmobile manual"),
                  ("Spark plugs", f"{br} {fam} snowmobile spark plug"),
                  ("2-stroke injection oil", "2-stroke snowmobile injection oil"),
                  ("Carbide runners and skags", "snowmobile carbide runners"),
                  ("Snowmobile cover", "universal snowmobile cover")]
    else:
        pl = plug_for(s)
        items += [(f"Spark plug: {pl['plug']}", f"{pl['plug']} spark plug") if pl else ("Spark plugs", f"{br} {eng} spark plug".replace(br + " " + br, br)),
                  ("Engine oil", f"{br} 4-stroke snowmobile oil 0W-40" if four else OIL.get(br, "2-stroke snowmobile oil")),
                  (f"{fam} sled cover" if fam else "Sled cover", cover_q(s, fam)),
                  ("Carbide runners and wear bars", f"{br} snowmobile carbide runners"),
                  ("Chaincase and gear oil", f"{br} snowmobile chaincase oil"),
                  ("Track studs and backers", "snowmobile track studs backers")]
    lis = "".join(f'<li><a href="{amz(q)}" rel="sponsored nofollow noopener" target="_blank">{e(label)}</a></li>' for label, q in items)
    return (f'<section class="parts"><h2>Parts and supplies</h2><p class="small">Amazon.ca searches matched to the {e(s["year"])} {e(br)} {e(s["model"])}. '
            f'Check fitment against your owner\'s manual before ordering. As an Amazon Associate, SledSpecs earns from qualifying purchases.</p>'
            f'<ul class="parts-list">{lis}</ul></section>')


def mailto(subject):
    return "mailto:" + CONTACT_EMAIL + "?subject=" + re.sub(r"\s", "%20", subject)


# ---------------------------------------------------------------- data
def load():
    rows = list(csv.DictReader(open(os.path.join(ROOT, "data", "sleds.csv"), encoding="utf-8")))
    sleds, seen, problems, seen_urls = [], set(), [], set()
    held_keys = load_holds()
    for r in rows:
        s = {k: (v.strip() if isinstance(v, str) else v) for k, v in r.items()}
        for k, f in NUM.items():
            s[k] = f(s[k]) if s.get(k) not in (None, "") else None
        for k in list(s):
            if s[k] == "":
                s[k] = None
        key = f"{s['year']}-{s['id']}"
        if key in seen:
            problems.append("duplicate year+id " + key)
        seen.add(key)
        s["key"] = key
        why = held_keys.get((str(s["year"]), s["brand"], s["id"])) or auto_hold_reason(s)
        if why:
            HELD.append((s["year"], s["brand"], s["model"], why))
            continue
        if s["brand"] not in BRANDS:
            problems.append(f"{s['id']}: unknown brand {s['brand']}")
        if s["category"] not in TYPES:
            problems.append(f"{s['id']}: unknown category {s['category']}")
        if not s.get("source") or "NEEDED" in (s.get("source") or "").upper():
            problems.append(f"{s['id']}: no source recorded")
            s["source"] = None
        s["brand_slug"] = slug(s["brand"])
        s["full"] = f"{s['year']} {s['brand']} {s['model']}"
        s["slug"] = f"{s['year']}-{clean_id(s['id'], s['year'])}"
        s["old_url"] = f"/snowmobiles/{s['brand_slug']}/{s['year']}-{s['id']}/"
        s["url"] = f"/snowmobiles/{s['brand_slug']}/{s['slug']}/"
        if s["url"] in seen_urls:
            problems.append("two sleds share the address " + s["url"])
        seen_urls.add(s["url"])
        s["track"] = track_text(s)
        s["lb_per_hp"] = round(s["dry_weight_lb"] / s["hp"], 2) if s["hp"] and s["dry_weight_lb"] else None
        sleds.append(s)
    for p in problems:
        print("warning:", p, file=sys.stderr)
    sleds.sort(key=lambda s: (-s["year"], s["brand"], s["model"]))
    return sleds


def clean_id(i, y):
    """Tidy a sled id for its URL: drop a repeated year and model words said twice."""
    y = str(y)
    i = re.sub(r'^' + y + r'-', '', i); i = re.sub(r'-' + y + r'$', '', i)
    t = i.split('-')
    for n in range(4, 1, -1):          # only runs of 2+ words, e.g. indy-sport ... indy-sport
        a = 0
        while a <= len(t) - n:
            seq = t[a:a+n]
            if all(re.fullmatch(r'[a-z][a-z0-9]*', x) for x in seq):
                for b in range(a + n, len(t) - n + 1):
                    if t[b:b+n] == seq:
                        t = t[:b] + t[b+n:]; break
            a += 1
    # single model word repeated after the engine size: voyageur-650-voyageur-146
    if len(t) >= 3 and re.fullmatch(r'[a-z]{3,}', t[0]):
        for b in range(1, len(t)):
            if t[b] == t[0] and any(re.fullmatch(r'\d+r?', x) for x in t[1:b]):
                t = t[:b] + t[b+1:]; break
    return '-'.join(t)


# Sleds kept off the site until their figures are confirmed for that model year.
# data/holds.csv lists them by hand; auto_hold_reason() catches research notes that say the
# figures weren't confirmed (e.g. "verify before publishing", "spec table not yet captured").
HELD = []
AUTO_HOLD = [r"verify\b[^.;]*\bbefore publishing", r"availability\b[^.;]*\bnot confirmed",
             r"spec table not yet captured", r"data captured is from a MY ?\d{4}",
             r"carried from the [^.;]*family"]


def load_holds():
    path = os.path.join(ROOT, "data", "holds.csv")
    if not os.path.exists(path):
        return {}
    with open(path, newline="", encoding="utf-8") as fh:
        return {(r["year"].strip(), r["brand"].strip(), r["id"].strip()): r["reason"] for r in csv.DictReader(fh)}


def auto_hold_reason(s):
    text = s.get("notes") or ""
    for pat in AUTO_HOLD:
        if re.search(pat, text, re.I):
            return "research notes say the figures aren't confirmed for this model year"
    return None


def track_text(s):
    parts = [n(s[k]) for k in ("track_length_in", "track_width_in", "lug_in")]
    if not parts[0]:
        return None
    if parts[1] and parts[2]:
        return f"{parts[0]} × {parts[1]} × {parts[2]} in"
    if parts[1]:
        return f"{parts[0]} × {parts[1]} in"
    return f"{parts[0]} in"


def load_corrections():
    p = os.path.join(ROOT, "data", "corrections.csv")
    return list(csv.DictReader(open(p, encoding="utf-8"))) if os.path.exists(p) else []


# ---------------------------------------------------------------- page shell
def page(path, title, desc, body, *, jsonld=None, noindex=False, active=None, hero=""):
    canon = SITE + path
    ld = ""
    if jsonld:
        ld = '<script type="application/ld+json">' + json.dumps(jsonld, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/") + "</script>"
    nav = "".join(
        f'<a href="{u}"{" aria-current=page" if active == k else ""}>{t}</a>'
        for k, u, t in [("brands", "/snowmobiles/", "Brands"), ("belts", "/belt-finder/", "Belt finder"),
                        ("compare", "/compare/", "Compare"), ("about", "/about/", "About the data")])
    robots = "noindex, follow" if noindex else "index, follow, max-image-preview:large"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
{"" if path == "/404" else f'<link rel="canonical" href="{canon}">'}
<meta name="robots" content="{robots}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{SITE_NAME}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{canon}">
<meta property="og:image" content="{SITE}/assets/og.jpg">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#0a1f32">
<link rel="icon" href="/favicon.ico" sizes="48x48">
<link rel="icon" type="image/png" sizes="32x32" href="/assets/icon-32.png">
<link rel="apple-touch-icon" href="/assets/icon-192.png">
<link rel="manifest" href="/site.webmanifest">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600;700&family=Barlow+Semi+Condensed:ital,wght@1,700;1,800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/site.css?v={CSS_V}">
{ld}
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="mast">
  <div class="wrap mast-in">
    <a class="logo" href="/"><img src="/assets/logo-dark.webp" alt="SledSpecs.com home" width="628" height="112"></a>
    <nav class="mainnav" aria-label="Main">{nav}</nav>
    {'' if hero else '<form class="msearch" action="/search/" method="get" role="search"><label class="sr" for="mq">Search sleds</label><input id="mq" name="q" type="search" placeholder="Search sleds or belt numbers" autocomplete="off"><button class="btn go" type="submit">Find specs</button></form>'}
  </div>
  {hero}
</header>
<main id="main" class="wrap">
{body}
</main>
<footer class="foot">
  <div class="wrap foot-in">
    <div>
      <img class="foot-logo" src="/assets/logo-dark.webp" alt="SledSpecs" width="157" height="28" loading="lazy">
      <p>Factory snowmobile specs, belt and track fitment, gathered from manufacturer spec sheets and owner's manuals. Every figure names its source.</p>{('<p class="small">As an Amazon Associate, SledSpecs earns from qualifying purchases. Belt links go to Amazon.ca.</p>') if AMAZON_TAG else ''}
    </div>
    <div>
      <h2>Brands</h2>
      <ul>{''.join(f'<li><a href="/snowmobiles/{slug(b)}/">{b} specs</a></li>' for b in BRANDS)}</ul>
    </div>
    <div>
      <h2>Types</h2>
      <ul>{''.join(f'<li><a href="/snowmobiles/type/{slug(t)}/">{t} sleds</a></li>' for t in TYPES)}</ul>
    </div>
    <div>
      <h2>SledSpecs</h2>
      <ul><li><a href="/belt-finder/">Drive belt finder</a></li><li><a href="/parts/">Belt and plug part numbers</a></li><li><a href="/vs/">Model vs model comparisons</a></li><li><a href="/compare/">Compare sleds</a></li><li><a href="/about/">How the data is gathered</a></li><li><a href="/about/#corrections">Corrections log</a></li>{('<li><a href="' + mailto('SledSpecs correction') + '">Send a correction</a></li>') if CONTACT_EMAIL else ''}</ul>
    </div>
  </div>
  <div class="wrap foot-legal"><p>Ski-Doo, Polaris, Arctic Cat and Yamaha are trademarks of their owners. SledSpecs is independent and not affiliated with any manufacturer. Always confirm part numbers with your dealer before ordering.</p></div>
</footer>
<div class="tray" id="tray" hidden>
  <span id="trayNames"></span>
  <a class="btn go" id="trayGo" href="/compare/">Compare</a>
  <button class="btn ghost" id="trayClear" type="button">Clear</button>
</div>
<script src="/assets/app.js?v={JS_V}" defer></script>
<script src="/assets/search.js?v={SR_V}" defer></script>
</body>
</html>
"""


def crumbs(items):
    """items: list of (name, path); last is current page."""
    li = []
    for i, (name, path) in enumerate(items):
        if i == len(items) - 1:
            li.append(f'<li aria-current="page">{e(name)}</li>')
        else:
            li.append(f'<li><a href="{path}">{e(name)}</a></li>')
    html_ = '<nav class="crumbs" aria-label="Breadcrumb"><ol>' + "".join(li) + "</ol></nav>"
    ld = {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": name, "item": SITE + path}
        for i, (name, path) in enumerate(items)]}
    return html_, ld


# ---------------------------------------------------------------- catalogue table
def cat_table(sleds, caption, filters=True, table_id="cat"):
    rows = []
    for s in sleds:
        hp = f'{n(s["hp"])} hp' if s["hp"] else f'<span class="np">{hp_gap(s)}</span>'
        search = " ".join(str(x) for x in [s["full"], s["category"], s["engine"] or "", s["cc"] or "",
                                           n(s["track_length_in"]) or "", s["belt_pn"] or ""]).lower()
        rows.append(f"""<tr data-brand="{e(s['brand'])}" data-type="{e(s['category'])}" data-year="{s['year']}" data-cc="{s['cc'] or 0}" data-hp="{s['hp'] or 0}" data-weight="{s['dry_weight_lb'] or 0}" data-track="{s['track_length_in'] or 0}" data-lbhp="{s['lb_per_hp'] or 0}" data-search="{e(search)}">
<th scope="row" class="m"><a href="{s['url']}">{e(s['year'])} {e(s['brand'])} {e(s['model'])}</a><span class="t">{e(s['category'])}</span></th>
<td class="cc" data-l="Engine"><b>{n(s['cc'])} cc</b><span>{e(s['engine'])}</span></td>
<td class="hp" data-l="Power">{hp}</td>
<td class="wt" data-l="Dry weight">{(n(s['dry_weight_lb'])+' lb') if s['dry_weight_lb'] else '—'}</td>
<td class="tr" data-l="Track">{e(s['track'] or '—')}</td>
<td class="fu" data-l="Fuel">{(n(s['fuel_gal'])+' gal') if s['fuel_gal'] else '—'}</td>
<td class="ac"><button class="btn small" type="button" data-compare="{s['key']}" aria-pressed="false">Compare</button></td>
</tr>""")
    tools = ""
    if filters:
        brands = [b for b in BRANDS if any(s["brand"] == b for s in sleds)]
        types = [t for t in TYPES if any(s["category"] == t for s in sleds)]

        def seg(name, vals):
            if len(vals) < 2:
                return ""
            opts = "".join(f'<option value="{e(v)}">{e(v)}</option>' for v in vals)
            return f'<label class="fld">{name}<select data-filter="{name.lower()}"><option value="">All</option>{opts}</select></label>'
        tools = f"""<div class="tools" data-for="{table_id}">
  <label class="fld grow">Filter this list<input type="search" data-filter="q" placeholder="Model, engine, track length or belt number" autocomplete="off"></label>
  {seg('Brand', brands)}{seg('Type', types)}
  <label class="fld">Sort<select data-sort>
    <option value="year">Newest first</option><option value="weight">Lightest first</option>
    <option value="hp">Most horsepower</option><option value="lbhp">Best power-to-weight</option>
    <option value="track">Longest track</option><option value="cc">Biggest engine</option></select></label>
</div>"""
    return f"""{tools}
<div class="sheet">
<table class="cat" id="{table_id}">
<caption><span data-count>{len(sleds)} sleds</span>. {caption} A dash means the figure isn't in the source we used for that sled.</caption>
<thead><tr><th scope="col">Sled</th><th scope="col">Engine</th><th scope="col">Power</th><th scope="col">Dry weight</th><th scope="col">Track (L × W × lug)</th><th scope="col">Fuel</th><th scope="col"><span class="sr">Compare</span></th></tr></thead>
<tbody>{''.join(rows)}</tbody>
</table>
<p class="empty" hidden>Nothing matches. Try a brand, an engine size like 850, or a track length like 155.</p>
</div>"""


def itemlist(sleds, name):
    return {"@type": "ItemList", "name": name, "numberOfItems": len(sleds),
            "itemListElement": [{"@type": "ListItem", "position": i + 1, "url": SITE + s["url"], "name": s["full"]}
                                for i, s in enumerate(sleds)]}


def faq_block(qas, heading="Questions"):
    if not qas:
        return "", None
    h = "".join(f'<details><summary>{e(q)}</summary><p>{a}</p></details>' for q, a in qas)
    ld = {"@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": html.unescape(re.sub("<[^>]+>", "", a))}}
        for q, a in qas]}
    return f'<section class="faq"><h2>{heading}</h2>{h}</section>', ld


def graph(*items):
    return {"@context": "https://schema.org", "@graph": [i for i in items if i]}


ORG = {"@type": "Organization", "@id": SITE + "/#org", "name": SITE_NAME, "url": SITE + "/",
       "logo": SITE + "/assets/icon-192.png"}
WEBSITE = {"@type": "WebSite", "@id": SITE + "/#site", "name": SITE_NAME, "url": SITE + "/",
           "publisher": {"@id": SITE + "/#org"},
           "potentialAction": {"@type": "SearchAction", "target": SITE + "/?q={search_term_string}",
                               "query-input": "required name=search_term_string"}}


def types_list(sleds):
    return "".join(f'<li><a href="/snowmobiles/type/{slug(t)}/">{t}</a><span>{e(TYPE_BLURB[t])}</span></li>'
                   for t in TYPES if any(s["category"] == t for s in sleds))


# ---------------------------------------------------------------- pages
def home(sleds):
    def lead(label, s, fig):
        return f'<li><span class="lab">{label}</span><a href="{s["url"]}">{e(s["full"])}</a><b>{fig}</b></li>' if s else ""
    w = [s for s in sleds if s["dry_weight_lb"]]
    p = [s for s in sleds if s["lb_per_hp"]]
    t = [s for s in sleds if s["track_length_in"]]
    f = [s for s in sleds if s["fuel_gal"]]
    light = min(w, key=lambda s: s["dry_weight_lb"]) if w else None
    pwr = min(p, key=lambda s: s["lb_per_hp"]) if p else None
    longest = max(t, key=lambda s: s["track_length_in"]) if t else None
    tank = max(f, key=lambda s: s["fuel_gal"]) if f else None
    leaders = "".join([
        lead("Lightest", light, f"{n(light['dry_weight_lb'])} lb dry" if light else ""),
        lead("Best power-to-weight", pwr, f"{pwr['lb_per_hp']} lb per hp" if pwr else ""),
        lead("Longest track", longest, longest["track"] if longest else ""),
        lead("Biggest fuel tank", tank, f"{n(tank['fuel_gal'])} gal" if tank else ""),
    ])
    brands = "".join(
        f'<a href="/snowmobiles/{slug(b)}/">{b}<span>{sum(1 for s in sleds if s["brand"] == b)}</span></a>' for b in BRANDS)
    hero = f"""<div class="wrap hero">
  <h1>Snowmobile specs, model by model</h1>
  <p>Engine, horsepower, dry weight, track size and drive belt numbers for Ski-Doo, Polaris, Arctic Cat and Yamaha sleds, taken from factory spec sheets.</p>
  <form class="find" action="/search/" method="get" role="search">
    <label class="sr" for="q">Search sleds</label>
    <input id="q" name="q" type="search" placeholder="Try “Summit 165”, “850 RMK” or “3211216”" autocomplete="off">
    <button class="btn go" type="submit">Find specs</button>
  </form>
  <div class="brandrow">{brands}</div>
</div>"""
    faq, faq_ld = faq_block([
        ("Where do these snowmobile specs come from?",
         "Each sled's figures come from the manufacturer's spec sheet, owner's manual or a dealer spec sheet. The source is named at the bottom of every model page, along with the date it was checked."),
        ("Why do some sleds say horsepower is not published?",
         "Polaris and Yamaha don't publish horsepower for most of their sleds. Rather than guess, SledSpecs leaves the figure out and says so."),
        ("What does dry weight mean on a snowmobile?",
         "Dry weight is the sled's weight without fuel, oil or other fluids. A full tank adds roughly 6 lb per US gallon, so ready-to-ride weight is noticeably higher."),
        ("How do I find the right drive belt for my sled?",
         'Open your sled\'s page or use the <a href="/belt-finder/">belt finder</a>. Belt numbers are listed only when the owner\'s manual or factory parts data states them. Confirm with your dealer before ordering.'),
    ], "Common questions")
    body = f"""
<section class="block" id="catalogue">
  <h2>All sleds</h2>
  {cat_table(sleds, "Factory figures for every sled in the catalogue.", table_id="cat")}
</section>
<section class="block two">
  <div><h2>Standouts</h2><ul class="leaders">{leaders}</ul></div>
  <div><h2>Browse by type</h2><ul class="types">{types_list(sleds)}</ul></div>
</section>
{faq}"""
    ld = graph(ORG, WEBSITE, itemlist(sleds, "Snowmobile specifications"), faq_ld)
    return page("/", "Snowmobile Specs: Engine, HP, Weight, Track & Belt | SledSpecs",
                f"Factory snowmobile specs for {len(sleds)} sleds from Ski-Doo, Polaris, Arctic Cat and Yamaha: horsepower, dry weight, track size, fuel capacity and drive belt part numbers.",
                body, jsonld=ld, hero=hero)


def listing_page(path, h1, intro, sleds, title, desc, crumb_items, active=None):
    c_html, c_ld = crumbs(crumb_items)
    body = f"""{c_html}
<section class="block"><h1 class="h1">{e(h1)}</h1><p class="lede">{intro}</p>
{cat_table(sleds, "Factory figures.", table_id="cat")}</section>"""
    return page(path, title, desc, body, jsonld=graph(ORG, c_ld, itemlist(sleds, h1)), active=active)


def brand_page(brand, sleds):
    ss = [s for s in sleds if s["brand"] == brand]
    years = sorted({s["year"] for s in ss})
    yr = f"{years[0]}" if len(years) == 1 else f"{years[0]} to {years[-1]}"
    types = sorted({s["category"] for s in ss}, key=TYPES.index)
    intro = (f"{len(ss)} {brand} {'sled' if len(ss) == 1 else 'sleds'} from {yr}, covering "
             f"{', '.join(t.lower() for t in types)} models. Open any sled for its full spec sheet, belt number and source.")
    return listing_page(f"/snowmobiles/{slug(brand)}/", f"{brand} snowmobile specs", intro, ss,
                        f"{brand} Snowmobile Specs ({yr}) | SledSpecs",
                        f"{brand} snowmobile specifications {yr}: horsepower, dry weight, track size, fuel capacity and drive belt numbers for {len(ss)} models.",
                        [("Home", "/"), ("Snowmobiles", "/snowmobiles/"), (brand, f"/snowmobiles/{slug(brand)}/")], "brands")


def type_page(t, sleds):
    ss = [s for s in sleds if s["category"] == t]
    intro = f"{e(TYPE_BLURB[t])} {len(ss)} {'sled' if len(ss) == 1 else 'sleds'} listed."
    return listing_page(f"/snowmobiles/type/{slug(t)}/", f"{t} snowmobile specs", intro, ss,
                        f"{t} Snowmobile Specs Compared | SledSpecs",
                        f"Compare {t.lower()} snowmobiles side by side: engine, horsepower, dry weight, track length and fuel capacity.",
                        [("Home", "/"), ("Snowmobiles", "/snowmobiles/"), (f"{t} sleds", f"/snowmobiles/type/{slug(t)}/")], "brands")


def all_brands_page(sleds):
    cards = "".join(f'<li><a href="/snowmobiles/{slug(b)}/">{b}</a><span>{sum(1 for s in sleds if s["brand"] == b)} sleds</span></li>' for b in BRANDS)
    c_html, c_ld = crumbs([("Home", "/"), ("Snowmobiles", "/snowmobiles/")])
    body = f"""{c_html}<section class="block"><h1 class="h1">Snowmobile specs by brand</h1>
<ul class="types">{cards}</ul>
<h2>By type</h2><ul class="types">{types_list(sleds)}</ul></section>"""
    return page("/snowmobiles/", "Snowmobile Specs by Brand and Type | SledSpecs",
                "Browse snowmobile specifications by brand (Ski-Doo, Polaris, Arctic Cat, Yamaha) or by type (mountain, trail, crossover, utility, vintage).",
                body, jsonld=graph(ORG, c_ld), active="brands")


FIELD_WORDS = {
    "dry_weight_lb": "Dry weight", "width_in": "Width", "height_in": "Height", "length_in": "Length",
    "track_length_in": "Track length", "track_width_in": "Track width", "lug_in": "Lug height",
    "fuel_gal": "Fuel capacity", "msrp_usd": "MSRP", "belt_pn": "Drive belt", "cc": "Displacement",
    "hp": "Horsepower", "cylinders": "Cylinders", "secondary_clutch": "Secondary clutch",
    "primary_clutch": "Primary clutch", "front_travel_in": "Front travel", "rear_travel_in": "Rear travel",
    "ski_stance_in": "Ski stance", "url": "Source link", "track_name": "Track", "starter": "Starter",
}
RESEARCH_NOTE = re.compile(r"left null|rather than guessed|is recorded|recorded\b|OEM-fed|spec[- ]feed|dealer (?:spec|inventory|listing|data|feed)|"
                           r"conflict|cross-check|do not assume|verify|not split out|sheet figure used|archive (?:spec )?page|"
                           r"\b[a-z]+\.[a-z_]+\b|\b[a-z]+_[a-z_]+\b", re.I)


def humanize_note(t):
    """Turn research-log notes (field codes, 'left null', 'recorded') into plain reader-facing text."""
    def word(m):
        pre, key = m.group(1), m.group(2) or m.group(3)
        if pre == "track" and key in ("width_in", "length_in"):
            return "Track " + key.split("_")[0]
        return FIELD_WORDS.get(key, key.replace("_", " ").capitalize())
    t = re.sub(r"\b(dimensions|engine|track|suspension|capacities|drivetrain|source|chassis|features)\.([a-z_]+)\b|\b([a-z]+(?:_[a-z]+)+)\b", word, t)
    for a_, b_ in [(r"left null rather than guessed", "so it is not shown"), (r"left null", "not shown"),
                   (r"no record created", "no page was made"), (r"\bis recorded\b", "is shown"),
                   (r"\bare recorded\b", "are shown"), (r"\brecorded\b", "shown"), (r"\bOEM-fed\b", "manufacturer-supplied"),
                   (r"\bspec[- ]feed\b", "spec data"), (r"\bsheet figure used\b", "the sheet figure is shown"),
                   (r"\bdo not assume\b", "not assumed"), (r"\bDX1\b ?", "")]:
        t = re.sub(a_, b_, t, flags=re.I)
    t = re.sub(r"\s+", " ", t).strip()
    labels = (r"(?:dry weight|width|height|length|track length|track width|track pitch|track options|track|lug height|fuel capacity|"
              r"msrp|drive belt|secondary clutch|primary clutch|front travel|rear travel|ski stance|source link|engine bore|"
              r"bore x stroke|oil capacity|starter|cooling|cylinders|horsepower|conflict|model|engine oil capacity)")
    t = re.sub(r"(?<=[a-z0-9\)\.\"'%])(?<!track)(?<!engine)(?<!the)(?<!oil)(?<!dry)(?<!front)(?<!rear)(?<!overall)\s+(?="
               + labels + r"\b\s*(?:-|:|is from|\d))", "\x00", t, flags=re.I)
    t = re.sub(r"\.?\x00([a-z]?)", lambda m: ". " + m.group(1).upper(), t)
    t = t[:1].upper() + t[1:]
    return t if t.endswith((".", ")")) else t + "."


def render_note(t):
    if not t:
        return ""
    if RESEARCH_NOTE.search(t):
        return ('<details class="srcnotes"><summary>How these figures were checked</summary>'
                f'<p>{e(humanize_note(t))}</p></details>')
    return f'<p class="note">{e(t)}</p>'


def fit_title(*cands, limit=62):
    """First candidate short enough for Google to show in full; else the shortest."""
    for c in cands:
        if len(c) <= limit:
            return c
    return min(cands, key=len)


def summary(s, nm):
    cc = n(s["cc"]) if s["cc"] else ""
    art = "an" if cc and (cc[0] == "8" or cc[:2] in ("11", "18") and len(cc.split(".")[0]) in (2, 4, 5)) else "a"
    bits = [f"{art} {cc} cc {e(s['engine'])}" if s["engine"] and cc else (f"{art} {cc} cc engine" if cc else "")]
    if s["hp"]: bits.append(f"makes {n(s['hp'])} hp")
    if s["dry_weight_lb"]: bits.append(f"weighs {n(s['dry_weight_lb'])} lb dry")
    if s["track"]: bits.append(f"runs a {e(s['track'])} track")
    if s["belt_pn"]: bits.append(f"uses drive belt {e(s['belt_pn'])}")
    bits = [x for x in bits if x]
    if not bits:
        return ""
    first = ("has " + bits[0]) if bits[0].startswith(("a ", "an ")) else bits[0]
    rest = bits[1:]
    txt = first + ("" if not rest else (", " + ", ".join(rest[:-1]) + (", and " if len(rest) > 1 else " and ") + rest[-1] if len(rest) > 1 else " and " + rest[0]))
    return f"The {e(nm)} {txt}."


def model_page(s, sleds):
    def row(k, v):
        return f"<tr><th scope=row>{k}</th><td>{v}</td></tr>" if v not in (None, "", "—") else ""
    hp = f"{n(s['hp'])} hp" if s["hp"] else None
    missing = [label for label, v in [("horsepower", s["hp"] or hp_gap(s) == "Not published"),
                                      ("dry weight", s["dry_weight_lb"] or wt_gap(s)), ("track size", s["track"]),
                                      ("fuel capacity", s["fuel_gal"]), ("drive belt part number", s["belt_pn"]),
                                      ("clutching", s["clutch"]), ("overall length", s["length_in"])] if not v]
    plate = "".join(f'<div><dt>{k}</dt><dd>{v}</dd></div>' for k, v in [
        ("Engine", f"{n(s['cc'])} cc"),
        ("Power", hp or hp_gap(s)),
        ("Dry weight", f"{n(s['dry_weight_lb'])} lb" if s["dry_weight_lb"] else (wt_gap(s) or "—")),
        ("Track", f"{n(s['track_length_in'])} in" if s["track_length_in"] else "—"),
    ])
    engine = (row("Engine", e(s["engine"])) + row("Type", e(s["engine_detail"] or "")) +
              row("Displacement", f"{n(s['cc'])} cc") + row("Cylinders", n(s["cylinders"])) +
              row("Horsepower", hp or hp_gap(s, long=True)) +
              row("Power-to-weight", f"{s['lb_per_hp']} lb per hp" if s["lb_per_hp"] else None))
    drive = (row("Track", e(s["track"]) if s["track"] else None) + row("Track model", e(s["track_name"]) if s["track_name"] else None) +
             row("Drive belt", f'<a class="pn" href="{belt_url(s["belt_pn"])}">{e(s["belt_pn"])}</a>' if s["belt_pn"] else None) +
             row("Clutching", e(s["clutch"]) if s["clutch"] else None) +
             row("Drive sprocket pitch", f"{n(s['sprocket_pitch_in'])} in" if s["sprocket_pitch_in"] else None) +
             row("Starter", e(s["starter"]) if s["starter"] else None) +
             (row("Spark plug", f'<a href="{plug_url(plug_for(s)["plug"])}">{e(plug_for(s)["plug"])}</a> <span class="small">({e(plug_for(s)["source"])})</span>') if plug_for(s) else ""))
    chassis = (row("Dry weight", f"{n(s['dry_weight_lb'])} lb" if s["dry_weight_lb"] else wt_gap(s, long=True)) +
               row("Fuel capacity", f"{n(s['fuel_gal'])} US gal ({round(s['fuel_gal'] * 3.785, 1)} L)" if s["fuel_gal"] else None) +
               row("Overall length", f"{n(s['length_in'])} in" if s["length_in"] else None) +
               row("Platform", e(s["platform"]) if s["platform"] else None) +
               row("Skis", e(s["skis"]) if s["skis"] else None) +
               row("Launch MSRP", f"${int(s['msrp_usd']):,} US" if s["msrp_usd"] else None))
    tables = "".join(f'<table class="spec"><caption>{cap}</caption>{rows}</table>' for cap, rows in
                     [("Engine", engine), ("Track and drive", drive), ("Chassis and capacities", chassis)] if rows)

    same_belt = [x for x in sleds if s["belt_pn"] and x["belt_pn"] == s["belt_pn"] and x["key"] != s["key"]]
    # similar = same brand and type, nearest model years first
    related = sorted([x for x in sleds if x["key"] != s["key"] and x["brand"] == s["brand"] and x["category"] == s["category"]],
                     key=lambda x: (abs(x["year"] - s["year"]), x["model"]))[:6]
    if len(related) < 3:
        related += [x for x in sleds if x["key"] != s["key"] and x not in related and x["category"] == s["category"]][:6 - len(related)]
    side = ""
    if s["belt_pn"]:
        side += f'<div class="fit"><h2>Drive belt</h2><p class="pn big">{e(s["belt_pn"])}</p>'
        side += buy_link(s)
        if same_belt:
            side += "<p>Also fits:</p><ul>" + "".join(f'<li><a href="{x["url"]}">{e(x["full"])}</a></li>' for x in same_belt[:8]) + "</ul>"
            if len(same_belt) > 8:
                side += f'<p class="small"><a href="{belt_url(s["belt_pn"])}">See all {len(same_belt) + 1} sleds that use the {e(s["belt_pn"])}</a></p>'
        side += '<p class="small">Confirm the part number with your dealer before ordering.' + (' As an Amazon Associate, SledSpecs earns from qualifying purchases.' if AMAZON_TAG else '') + '</p></div>'
    side += f'<button class="btn go wide" type="button" data-compare="{s["key"]}" aria-pressed="false">Add to compare</button>'
    if VS.get(s["key"]):
        side += '<div class="rel"><h2>Compare with rivals</h2><ul>' + "".join(
            f'<li><a href="{u}">vs {e(x["brand"])} {e(x["model"])}</a></li>' for x, u in VS[s["key"]]) + "</ul></div>"
    if related:
        side += '<div class="rel"><h2>Similar sleds</h2><ul>' + "".join(
            f'<li><a href="{x["url"]}">{e(x["full"])}</a></li>' for x in related) + "</ul></div>"

    nm = f"{s['year']} {s['brand']} {s['model']}"
    qas = [(f"How much horsepower does the {nm} have?",
            f"The {nm} makes {n(s['hp'])} hp from its {e(s['engine'])} ({n(s['cc'])} cc)." if s["hp"] else
            (f"{e(s['brand'])} doesn't publish a horsepower figure for the {nm}." if hp_gap(s) == "Not published"
             else f"Our source for the {nm} doesn't list horsepower.") + f" It uses the {e(s['engine'])}, {n(s['cc'])} cc.")]
    if s["dry_weight_lb"]:
        qas.append((f"How much does the {nm} weigh?", f"The factory dry weight is {n(s['dry_weight_lb'])} lb, without fuel or oil."))
    if s["track"]:
        qas.append((f"What size track does the {nm} have?",
                    f"{e(s['track'])}" + (f" ({e(s['track_name'])})." if s["track_name"] else ".")))
    if s["belt_pn"]:
        qas.append((f"What drive belt does the {nm} use?", f"Factory drive belt part number {e(s['belt_pn'])}."))
    if s["fuel_gal"]:
        qas.append((f"How big is the fuel tank on the {nm}?", f"{n(s['fuel_gal'])} US gallons ({round(s['fuel_gal'] * 3.785, 1)} L)."))
    faq, faq_ld = faq_block(qas, "Quick answers")

    c_html, c_ld = crumbs([("Home", "/"), ("Snowmobiles", "/snowmobiles/"), (s["brand"], f"/snowmobiles/{s['brand_slug']}/"), (f"{s['year']} {s['model']}", s["url"])])
    src = (f"<p><b>Source:</b> {e(s['source'])}. Checked {e(s['checked'] or '')}.</p>" if s["source"]
           else "<p><b>Source:</b> being confirmed.</p>")
    gaps = (f"<p>Not on file yet for this sled: {', '.join(missing)}."
            + (f' Have the owner\'s manual? <a href="{mailto("Correction: " + nm)}">Send us the page</a>.' if CONTACT_EMAIL else "") + "</p>") if missing else ""
    note = render_note(s["notes"])

    body = f"""{c_html}
<article class="model">
  <header class="model-h">
    <p class="kicker"><a href="/snowmobiles/{s['brand_slug']}/">{e(s['brand'])}</a> / <a href="/snowmobiles/type/{slug(s['category'])}/">{e(s['category'])}</a></p>
    <h1 class="h1">{e(nm)} specs</h1>
    <p class="lede">{summary(s, nm)}</p>
    {note}
  </header>
  <dl class="plate">{plate}</dl>
  <div class="model-grid">
    <div class="specs">{tables}
      <div class="srcbox">{src}{gaps}</div>
    </div>
    <aside class="side">{side}</aside>
  </div>
  {parts_box(s)}
  {faq}
</article>"""

    props = [("Engine", s["engine"]), ("Displacement", f"{n(s['cc'])} cc"), ("Horsepower", hp),
             ("Dry weight", f"{n(s['dry_weight_lb'])} lb" if s["dry_weight_lb"] else None), ("Track", s["track"]),
             ("Fuel capacity", f"{n(s['fuel_gal'])} US gal" if s["fuel_gal"] else None),
             ("Drive belt part number", s["belt_pn"]), ("Category", s["category"])]
    veh = {"@type": "Vehicle", "@id": SITE + s["url"] + "#sled", "name": nm, "url": SITE + s["url"],
           "brand": {"@type": "Brand", "name": s["brand"]}, "model": s["model"], "vehicleModelDate": str(s["year"]),
           "category": f"{s['category']} snowmobile", "image": SITE + "/assets/og.jpg",
           "vehicleEngine": {"@type": "EngineSpecification", "name": s["engine"],
                             "engineDisplacement": {"@type": "QuantitativeValue", "value": s["cc"], "unitCode": "CMQ"}},
           "additionalProperty": [{"@type": "PropertyValue", "name": k, "value": v} for k, v in props if v]}
    if s["hp"]:
        veh["vehicleEngine"]["enginePower"] = {"@type": "QuantitativeValue", "value": s["hp"], "unitCode": "BHP"}
    if s["dry_weight_lb"]:
        veh["weightTotal"] = {"@type": "QuantitativeValue", "value": s["dry_weight_lb"], "unitCode": "LBR"}
    if s["fuel_gal"]:
        veh["fuelCapacity"] = {"@type": "QuantitativeValue", "value": s["fuel_gal"], "unitCode": "GLL"}

    bits = [f"{n(s['cc'])} cc {s['engine']}"]
    if hp: bits.append(hp)
    if s["dry_weight_lb"]: bits.append(f"{n(s['dry_weight_lb'])} lb dry")
    if s["track"]: bits.append(f"{s['track']} track")
    if s["belt_pn"]: bits.append(f"belt {s['belt_pn']}")
    desc = f"{nm} specs: " + ", ".join(bits) + ". Factory figures with source."
    title_bits = "HP, Weight, Track" + (" & Belt" if s["belt_pn"] else "")
    return page(s["url"], fit_title(f"{nm} Specs: {title_bits} | SledSpecs", f"{nm} Specs: {title_bits}",
                                     f"{nm} Specs: HP, Weight, Track", f"{nm} Specs and Weight", f"{nm} Specs"), desc, body,
                jsonld=graph(ORG, c_ld, veh, faq_ld), active="brands")


def belt_page(sleds):
    rows = "".join(f"""<tr data-search="{e((s['full']+' '+(s['belt_pn'] or '')+' '+(s['track'] or '')).lower())}"><th scope=row class="m"><a href="{s['url']}">{e(s['full'])}</a></th>
<td data-l="Drive belt">{('<b class="pn">'+e(s['belt_pn'])+'</b> '+buy_link(s, cls="buy-sm", label="Amazon")) if s['belt_pn'] else '<span class="np">Not on file yet</span>'}</td>
<td data-l="Track">{e(s['track'] or '—')}</td><td data-l="Sprocket pitch">{(n(s['sprocket_pitch_in'])+' in') if s['sprocket_pitch_in'] else '—'}</td></tr>""" for s in sleds)
    c_html, c_ld = crumbs([("Home", "/"), ("Belt finder", "/belt-finder/")])
    body = f"""{c_html}
<section class="block"><h1 class="h1">Snowmobile drive belt finder</h1>
<p class="lede">Find the factory drive belt part number and track size for your sled. Belt numbers are listed only where the owner's manual or factory parts data states them. We never guess one.</p>
<div class="tools" data-for="belts"><label class="fld grow">Find your sled or belt number<input type="search" data-filter="q" placeholder="e.g. Pro-RMK, Summit 165, 3211216" autocomplete="off"></label></div>
<div class="sheet"><table class="cat belts" id="belts"><caption><span data-count>{len(sleds)} sleds</span>. Always confirm with your dealer before ordering a belt.</caption>
<thead><tr><th scope=col>Sled</th><th scope=col>Drive belt</th><th scope=col>Track (L × W × lug)</th><th scope=col>Sprocket pitch</th></tr></thead><tbody>{rows}</tbody></table>
<p class="empty" hidden>No sled or belt number matches that.</p></div></section>"""
    return page("/belt-finder/", "Snowmobile Drive Belt Finder by Model | SledSpecs",
                "Look up the factory drive belt part number and track size for Ski-Doo, Polaris, Arctic Cat and Yamaha snowmobiles.",
                body, jsonld=graph(ORG, c_ld), active="belts")


def join_and(xs):
    xs = list(xs)
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1] if xs else ""


def belt_url(pn):
    return f"/parts/belts/{slug(pn)}/"


def plug_url(plug):
    return f"/parts/spark-plugs/{slug(plug)}/"


def part_groups(sleds):
    belts, plugs = {}, {}
    for s in sleds:
        if s["belt_pn"]:
            belts.setdefault(s["belt_pn"], []).append(s)
        pl = plug_for(s)
        if pl:
            plugs.setdefault(pl["plug"], []).append(s)
    return belts, plugs


def part_page(kind, pn, group):
    group = sorted(group, key=lambda x: (-x["year"], x["model"]))
    brand = max({x["brand"] for x in group}, key=lambda b: sum(x["brand"] == b for x in group))
    yrs = sorted({x["year"] for x in group})
    span = f"{yrs[0]}" if yrs[0] == yrs[-1] else f"{yrs[0]} to {yrs[-1]}"
    engines = sorted({x["engine"] for x in group if x["engine"]})
    fams = sorted({family(x) for x in group if family(x)})
    if kind == "belt":
        url, what, noun = belt_url(pn), f"{brand} {pn} drive belt", "drive belt"
        q = f"{brand} {pn} drive belt"
        src = "Belt part numbers come from each sled's owner's manual or the manufacturer's genuine-parts fitment, named on every sled page."
    else:
        url, what, noun = plug_url(pn), f"{pn} spark plug", "spark plug"
        q = f"{pn} spark plug"
        src = "Plug numbers come from the manufacturer's genuine-parts listings and owner's manuals: " + e(plug_for(group[0])["source"]) + "."
    lede = (f"The {e(what)} is the factory {noun} for {len(group)} {e(brand)} snowmobile{'s' if len(group) != 1 else ''} "
            f"from {span}, including the {e(join_and(fams[:6]))} {'line' if len(fams[:6]) == 1 else 'lines'} with the {e(join_and([x.replace('Rotax ', '') for x in engines[:4]]))} engine{'s' if len(engines) > 1 else ''}.")
    rows = "".join(f'<tr><td>{x["year"]}</td><th scope=row class="m"><a href="{x["url"]}">{e(x["brand"])} {e(x["model"])}</a></th><td>{e(x["engine"] or "")}</td></tr>' for x in group)
    btn = (f'<a class="btn buy" href="{amz(q)}" rel="sponsored nofollow noopener" target="_blank">Check {e(pn)} price on Amazon</a>'
           f'<p class="small">As an Amazon Associate, SledSpecs earns from qualifying purchases. Confirm the part number with your dealer before ordering.</p>') if AMAZON_TAG else ""
    c_html, c_ld = crumbs([("Home", "/"), ("Parts", "/parts/"), (what, url)])
    qas = [(f"What snowmobiles use the {what}?", f"{len(group)} sleds in our catalogue list it, from {span}: " + ", ".join(f"{x['year']} {x['brand']} {x['model']}" for x in group[:8]) + (" and more." if len(group) > 8 else ".")),
           (f"Where does the {pn} number come from?", src)]
    faq, faq_ld = faq_block(qas, "Questions")
    body = f"""{c_html}<section class="block"><h1 class="h1">{e(what)}: which sleds it fits</h1>
<p class="lede">{lede}</p>{btn}
<div class="sheet"><table class="cat"><caption>{len(group)} sleds use the {e(pn)}</caption><thead><tr><th scope=col>Year</th><th scope=col>Sled</th><th scope=col>Engine</th></tr></thead><tbody>{rows}</tbody></table></div>
{faq}</section>"""
    title = f"{what.replace(brand + ' ', brand + ' ', 1)}: Fits {len(group)} Snowmobiles ({span}) | SledSpecs"
    desc = f"Which snowmobiles use the {what}: {len(group)} {brand} sleds from {span}, with model years and engines. Factory part number, sourced."
    return url, page(url, title, desc, body, jsonld=graph(ORG, c_ld, itemlist(group, f"Sleds that use the {pn}"), faq_ld), active="belts")


def parts_index(belts, plugs):
    def lst(d, fn, noun):
        items = sorted(d.items(), key=lambda kv: -len(kv[1]))
        return "<ul class=\"cols\">" + "".join(f'<li><a href="{fn(k)}">{e(k)}</a> <span class="small">({len(v)} sleds)</span></li>' for k, v in items) + "</ul>"
    c_html, c_ld = crumbs([("Home", "/"), ("Parts", "/parts/")])
    body = f"""{c_html}<section class="block prose"><h1 class="h1">Snowmobile part numbers: belts and spark plugs</h1>
<p class="lede">Look up a factory drive belt or spark plug number and see every sled it fits. Every number is sourced from the manufacturer.</p>
<h2>Drive belts</h2>{lst(belts, belt_url, "belt")}
<h2>Spark plugs</h2>{lst(plugs, plug_url, "plug")}</section>"""
    return page("/parts/", "Snowmobile Drive Belt & Spark Plug Part Numbers | SledSpecs",
                "Factory snowmobile drive belt and spark plug part numbers, with every Ski-Doo, Polaris, Arctic Cat and Yamaha sled each one fits.",
                body, jsonld=graph(ORG, c_ld), active="belts")


VS = {}
RIVALS = [("Ski-Doo", "Polaris"), ("Ski-Doo", "Arctic Cat"), ("Polaris", "Arctic Cat"), ("Ski-Doo", "Yamaha"), ("Polaris", "Yamaha")]


def vs_pairs(sleds):
    """Closest cross-brand rival for each modern sled: same year, type, engine class and track length."""
    pairs, used = [], collections.Counter()
    for ba, bb in RIVALS:
        cands = []
        for a in sleds:
            if a["brand"] != ba or a["year"] < 2025 or not (a["cc"] and a["track_length_in"]):
                continue
            for c in sleds:
                if (c["brand"] == bb and c["year"] == a["year"] and c["category"] == a["category"] and c["cc"] and c["track_length_in"]
                        and abs(c["cc"] - a["cc"]) / a["cc"] <= 0.12 and abs(c["track_length_in"] - a["track_length_in"]) <= 9):
                    score = abs(c["cc"] - a["cc"]) / a["cc"] * 10 + abs(c["track_length_in"] - a["track_length_in"]) + (0 if (a["dry_weight_lb"] and c["dry_weight_lb"]) else 5)
                    cands.append((score, a, c))
        for score, a, c in sorted(cands, key=lambda t: t[0]):
            if used[a["key"]] >= 1 or used[c["key"]] >= 2:
                continue
            pairs.append((a, c)); used[a["key"]] += 1; used[c["key"]] += 1
    return pairs


def vs_url(a, c):
    return f"/vs/{a['slug']}-vs-{c['slug']}/"


def vs_page(a, c):
    na, nc = f"{a['year']} {a['brand']} {a['model']}", f"{c['year']} {c['brand']} {c['model']}"
    sa, sc = f"{a['brand']} {a['model']}", f"{c['brand']} {c['model']}"
    diffs = []
    if a["hp"] and c["hp"]:
        d = a["hp"] - c["hp"]
        diffs.append(f"The {sa} makes {n(a['hp'])} hp to the {sc}'s {n(c['hp'])} hp" + (f", {n(abs(d))} hp {'more' if d > 0 else 'less'}." if d else ", the same."))
    else:
        missing = [x["brand"] for x in (a, c) if not x["hp"]]
        if missing:
            diffs.append(f"{join_and(sorted(set(missing)))} doesn't publish horsepower for {'this sled' if len(missing) == 1 else 'these sleds'}, so a power comparison isn't possible from factory figures.")
    if a["dry_weight_lb"] and c["dry_weight_lb"]:
        d = a["dry_weight_lb"] - c["dry_weight_lb"]
        diffs.append(f"Dry weight is {n(a['dry_weight_lb'])} lb for the {sa} and {n(c['dry_weight_lb'])} lb for the {sc}" +
                     (f": the {sa if d < 0 else sc} is {n(abs(d))} lb lighter." if d else ", identical."))
    if a["track"] and c["track"]:
        diffs.append(f"Tracks are {e(a['track'])} on the {sa} and {e(c['track'])} on the {sc}.")
    diffs.append(f"Engines: {e(a['engine'])} ({n(a['cc'])} cc) against the {e(c['engine'])} ({n(c['cc'])} cc).")
    if a["fuel_gal"] and c["fuel_gal"]:
        diffs.append(f"Fuel capacity is {n(a['fuel_gal'])} US gal versus {n(c['fuel_gal'])} US gal.")
    if a["lb_per_hp"] and c["lb_per_hp"]:
        diffs.append(f"Power-to-weight works out to {a['lb_per_hp']} lb per hp for the {sa} and {c['lb_per_hp']} for the {sc}; lower is quicker.")
    if a["belt_pn"] and c["belt_pn"]:
        diffs.append(f"Drive belts: {e(a['belt_pn'])} and {e(c['belt_pn'])}.")
    def v(s, k, f=lambda x: x):
        return f(s[k]) if s[k] else "—"
    rows = [("Engine", v(a, "engine", e), v(c, "engine", e)),
            ("Displacement", f"{n(a['cc'])} cc", f"{n(c['cc'])} cc"),
            ("Horsepower", f"{n(a['hp'])} hp" if a["hp"] else hp_gap(a), f"{n(c['hp'])} hp" if c["hp"] else hp_gap(c)),
            ("Dry weight", f"{n(a['dry_weight_lb'])} lb" if a["dry_weight_lb"] else (wt_gap(a) or "—"), f"{n(c['dry_weight_lb'])} lb" if c["dry_weight_lb"] else (wt_gap(c) or "—")),
            ("Track", v(a, "track", e), v(c, "track", e)),
            ("Fuel", f"{n(a['fuel_gal'])} US gal" if a["fuel_gal"] else "—", f"{n(c['fuel_gal'])} US gal" if c["fuel_gal"] else "—"),
            ("Platform", v(a, "platform", e), v(c, "platform", e)),
            ("Drive belt", v(a, "belt_pn", e), v(c, "belt_pn", e)),
            ("Launch MSRP", f"${int(a['msrp_usd']):,} US" if a["msrp_usd"] else "—", f"${int(c['msrp_usd']):,} US" if c["msrp_usd"] else "—")]
    tbl = "".join(f"<tr><th scope=row>{k}</th><td>{x}</td><td>{y}</td></tr>" for k, x, y in rows if not (x == "—" and y == "—"))
    url = vs_url(a, c)
    c_html, c_ld = crumbs([("Home", "/"), ("Comparisons", "/vs/"), (f"{sa} vs {sc}", url)])
    lede = (f"The {e(na)} and {e(nc)} are both {e(a['category'].lower())} sleds with {e(n(a['cc']))} and {e(n(c['cc']))} cc engines. "
            + e(diffs[0]) if diffs else "")
    qas = [(f"Which is lighter, the {sa} or the {sc}?",
            (f"The {sa if a['dry_weight_lb'] < c['dry_weight_lb'] else sc} is lighter: {n(min(a['dry_weight_lb'], c['dry_weight_lb']))} lb dry against {n(max(a['dry_weight_lb'], c['dry_weight_lb']))} lb."
             if a["dry_weight_lb"] and c["dry_weight_lb"] and a["dry_weight_lb"] != c["dry_weight_lb"] else "Factory dry weights aren't available for both sleds, so we can't say from published figures.")),
           (f"Do the {sa} and {sc} use the same drive belt?",
            (f"No. The {sa} uses {a['belt_pn']} and the {sc} uses {c['belt_pn']}." if a["belt_pn"] and c["belt_pn"] and a["belt_pn"] != c["belt_pn"] else
             f"Both use {a['belt_pn']}." if a["belt_pn"] and a["belt_pn"] == c["belt_pn"] else "We don't have a factory belt number for both sleds yet."))]
    faq, faq_ld = faq_block(qas, "Questions")
    body = f"""{c_html}<section class="block"><h1 class="h1">{e(na)} vs {e(nc)}</h1>
<p class="lede">{lede}</p>
<div class="sheet"><table class="spec vs"><caption>Factory specs side by side</caption><thead><tr><th scope=col></th><th scope=col><a href="{a['url']}">{e(sa)}</a></th><th scope=col><a href="{c['url']}">{e(sc)}</a></th></tr></thead><tbody>{tbl}</tbody></table></div>
<h2>Key differences</h2><ul>{''.join(f'<li>{e(x)}</li>' for x in diffs[1:]) or '<li>See the table above.</li>'}</ul>
<p class="small">Figures come from each manufacturer's spec sheet or owner's manual, named on each sled's page. Dry weights exclude fuel and oil.</p>
{faq}</section>"""
    title = fit_title(f"{a['year']} {sa} vs {sc}: Specs Compared | SledSpecs", f"{a['year']} {sa} vs {sc}: Specs Compared",
                      f"{a['year']} {sa} vs {sc} Specs", f"{a['year']} {sa} vs {sc}")
    desc = f"{na} vs {nc}: horsepower, dry weight, track, fuel and drive belt side by side, from factory specs."
    return url, page(url, title, desc, body, jsonld=graph(ORG, c_ld, faq_ld), active="compare")


def vs_index(pairs):
    items = sorted(pairs, key=lambda p: (-p[0]["year"], p[0]["category"], p[0]["model"]))
    c_html, c_ld = crumbs([("Home", "/"), ("Comparisons", "/vs/")])
    lis = "".join(f'<li><a href="{vs_url(a, c)}">{a["year"]} {e(a["brand"])} {e(a["model"])} vs {e(c["brand"])} {e(c["model"])}</a></li>' for a, c in items)
    body = f"""{c_html}<section class="block prose"><h1 class="h1">Snowmobile comparisons: model vs model</h1>
<p class="lede">Head-to-head factory specs for rival sleds of the same year, type, engine class and track length.</p><ul>{lis}</ul></section>"""
    return page("/vs/", "Snowmobile Comparisons: Ski-Doo vs Polaris vs Arctic Cat vs Yamaha | SledSpecs",
                "Side-by-side factory spec comparisons of rival snowmobiles: horsepower, dry weight, track and drive belt.", body, jsonld=graph(ORG, c_ld), active="compare")


def search_page():
    body = """<section class="block"><h1 class="h1" id="srHead">Search snowmobile specs</h1>
<form class="find srform" action="/search/" method="get" role="search">
  <label class="sr" for="srq">Search sleds</label>
  <input id="srq" name="q" type="search" placeholder="Try “Summit 165”, “850 RMK” or “3211216”" autocomplete="off">
  <button class="btn go" type="submit">Find specs</button>
</form>
<div id="srOut"><noscript><p>Search needs JavaScript. <a href="/#catalogue">Browse every sled</a> instead.</p></noscript></div></section>"""
    return page("/search/", "Search Snowmobile Specs | SledSpecs",
                "Search factory snowmobile specs by model, engine size, track length or drive belt number.", body, noindex=True)


def compare_page():
    c_html, _ = crumbs([("Home", "/"), ("Compare", "/compare/")])
    body = f"""{c_html}<section class="block"><h1 class="h1">Compare sleds</h1>
<p class="lede" id="cmpLede">Pick two or three sleds with their Compare buttons, then come back here.</p>
<div id="cmpOut"></div></section>"""
    return page("/compare/", "Compare Snowmobiles Side by Side | SledSpecs",
                "Compare snowmobile specs side by side: horsepower, dry weight, track and fuel.", body,
                noindex=True, active="compare")


def about_page(sleds, corrections):
    srcs = sorted({s["source"] for s in sleds if s["source"]})
    log = "".join(f"<tr><td>{e(c['date'])}</td><td>{e(c['what'])}</td><td>{e(c['change'])}</td></tr>" for c in reversed(corrections))
    c_html, c_ld = crumbs([("Home", "/"), ("About the data", "/about/")])
    spot = (f"<h2>Spot a mistake?</h2><p><a href=\"{mailto('SledSpecs correction')}\">Email a correction</a> with a photo of the manual page or spec sheet. We'll update the sled and log the change here.</p>"
            if CONTACT_EMAIL else "")
    body = f"""{c_html}<section class="block prose"><h1 class="h1">How the data is gathered</h1>
<p>Every sled starts from one document: the manufacturer's spec sheet, the owner's manual specifications chapter, or a dealer spec sheet for that exact model year. That source is named on the sled's page with the date it was last checked.</p>
<h2>What we don't do</h2>
<p>We don't estimate. If Polaris or Yamaha doesn't publish horsepower, the page says so. If a belt number isn't in the manual we used, it's listed as not on file yet. Manufacturer documents stay with the manufacturer; SledSpecs publishes the facts from them in its own tables.</p>
<h2>Sources used so far</h2><ul>{''.join(f'<li>{e(x)}</li>' for x in srcs)}</ul>
<h2 id="corrections">Corrections log</h2><p>When a figure changes, it's recorded here.</p>
<div class="sheet"><table class="log"><thead><tr><th scope=col>Date</th><th scope=col>Sled or field</th><th scope=col>Change</th></tr></thead><tbody>{log}</tbody></table></div>
{spot}
</section>"""
    return page("/about/", "How SledSpecs Gathers Snowmobile Specs | SledSpecs",
                "Where SledSpecs snowmobile specifications come from, how gaps are handled, and a log of every correction.",
                body, jsonld=graph(ORG, c_ld), active="about")


def notfound():
    return page("/404", "Page not found | SledSpecs", "That page isn't here.",
                '<section class="block"><h1 class="h1">That page isn\'t here</h1><p class="lede">The sled may have moved. Search the <a href="/">full catalogue</a> or browse <a href="/snowmobiles/">by brand</a>.</p></section>',
                noindex=True)


# ---------------------------------------------------------------- write
def write(path, content):
    full = os.path.join(DIST, path.lstrip("/"))
    if path.endswith("/"):
        full = os.path.join(full, "index.html")
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as fh:
        fh.write(content)


def main():
    sleds = load()
    corrections = load_corrections()
    if os.path.exists(DIST):
        shutil.rmtree(DIST)
    shutil.copytree(os.path.join(ROOT, "static"), DIST)
    shutil.copy(os.path.join(DIST, "assets", "favicon.ico"), os.path.join(DIST, "favicon.ico"))

    urls = [("/", TODAY), ("/snowmobiles/", TODAY), ("/belt-finder/", TODAY), ("/about/", TODAY)]
    write("/", home(sleds))
    write("/snowmobiles/", all_brands_page(sleds))
    for b in BRANDS:
        if any(s["brand"] == b for s in sleds):
            write(f"/snowmobiles/{slug(b)}/", brand_page(b, sleds)); urls.append((f"/snowmobiles/{slug(b)}/", TODAY))
    for t in TYPES:
        if any(s["category"] == t for s in sleds):
            write(f"/snowmobiles/type/{slug(t)}/", type_page(t, sleds)); urls.append((f"/snowmobiles/type/{slug(t)}/", TODAY))
    for a, c in vs_pairs(sleds):
        VS.setdefault(a["key"], []).append((c, vs_url(a, c))); VS.setdefault(c["key"], []).append((a, vs_url(a, c)))
    for s in sleds:
        write(s["url"], model_page(s, sleds)); urls.append((s["url"], s["checked"] or TODAY))
    write("/belt-finder/", belt_page(sleds))
    belts, plugs = part_groups(sleds)
    for pn, g in belts.items():
        u, html_ = part_page("belt", pn, g); write(u, html_); urls.append((u, TODAY))
    for pl, g in plugs.items():
        u, html_ = part_page("plug", pl, g); write(u, html_); urls.append((u, TODAY))
    write("/parts/", parts_index(belts, plugs)); urls.append(("/parts/", TODAY))
    pairs = vs_pairs(sleds)
    for a, c in pairs:
        u, html_ = vs_page(a, c); write(u, html_); urls.append((u, TODAY))
    write("/vs/", vs_index(pairs)); urls.append(("/vs/", TODAY))
    write("/compare/", compare_page())
    write("/search/", search_page())
    write("/about/", about_page(sleds, corrections))
    write("/404.html", notfound())

    pub = [{k: s[k] for k in ("key", "full", "brand", "model", "year", "category", "engine", "cc", "hp", "dry_weight_lb",
                              "track", "track_length_in", "fuel_gal", "belt_pn", "lb_per_hp", "url")} for s in sleds]
    write("/assets/sleds.json", json.dumps(pub, separators=(",", ":")))
    write("/assets/search.json", json.dumps([[s["full"], s["url"], s["category"], s["engine"] or "", s["track"] or "",
                                              s["belt_pn"] or "", s["year"]] for s in sleds], ensure_ascii=False, separators=(",", ":")))
    write("/sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
          "".join(f"<url><loc>{SITE}{u}</loc><lastmod>{d}</lastmod></url>\n" for u, d in urls) + "</urlset>\n")
    write("/robots.txt", f"User-agent: *\nAllow: /\nDisallow: /compare/\nDisallow: /search/\n\nSitemap: {SITE}/sitemap.xml\n")
    write("/site.webmanifest", json.dumps({"name": "SledSpecs", "short_name": "SledSpecs", "start_url": "/",
                                           "display": "browser", "background_color": "#f2f5f7", "theme_color": "#0a1f32",
                                           "icons": [{"src": "/assets/icon-192.png", "sizes": "192x192", "type": "image/png"}]}))
    moves = [[s["old_url"], s["url"]] for s in sleds if s["old_url"] != s["url"]]
    moves += [[f"/vs/{a['key']}-vs-{c['key']}/", vs_url(a, c)] for a, c in pairs if f"/vs/{a['key']}-vs-{c['key']}/" != vs_url(a, c)]
    with open(os.path.join(ROOT, ".moves.json"), "w") as fh:  # old -> new addresses, merged into vercel.json by tools/redirects.py
        json.dump(moves, fh)
    with open(os.path.join(ROOT, ".held.json"), "w") as fh:
        json.dump(HELD, fh, indent=1)
    if HELD:
        print(f"held back {len(HELD)} sled(s) until confirmed (see data/holds.csv and .held.json)")
    print(f"built {len(urls)} indexable pages for {len(sleds)} sleds -> dist/")


if __name__ == "__main__":
    main()
