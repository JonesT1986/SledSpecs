#!/usr/bin/env python3
"""SledSpecs static site generator.

Edit data/sleds.csv (one row per sled) and data/corrections.csv, then run:
    python3 build.py
Output goes to dist/. No third-party packages needed (Vercel runs this on every push).
Set the SLEDSPECS_CONTACT_EMAIL environment variable to choose where "send a correction" links go.
"""
import csv, json, html, os, re, shutil, sys
from datetime import date

ROOT = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(ROOT, "dist")
SITE = "https://sledspecs.com"
SITE_NAME = "SledSpecs"
CONTACT_EMAIL = os.environ.get("SLEDSPECS_CONTACT_EMAIL", "").strip()  # empty = hide correction links
TODAY = date.today().isoformat()

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


def mailto(subject):
    return "mailto:" + CONTACT_EMAIL + "?subject=" + re.sub(r"\s", "%20", subject)


# ---------------------------------------------------------------- data
def load():
    rows = list(csv.DictReader(open(os.path.join(ROOT, "data", "sleds.csv"), encoding="utf-8")))
    sleds, seen, problems = [], set(), []
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
        if s["brand"] not in BRANDS:
            problems.append(f"{s['id']}: unknown brand {s['brand']}")
        if s["category"] not in TYPES:
            problems.append(f"{s['id']}: unknown category {s['category']}")
        if not s.get("source") or "NEEDED" in (s.get("source") or "").upper():
            problems.append(f"{s['id']}: no source recorded")
            s["source"] = None
        s["brand_slug"] = slug(s["brand"])
        s["full"] = f"{s['year']} {s['brand']} {s['model']}"
        s["url"] = f"/snowmobiles/{s['brand_slug']}/{s['year']}-{s['id']}/"
        s["track"] = track_text(s)
        s["lb_per_hp"] = round(s["dry_weight_lb"] / s["hp"], 2) if s["hp"] and s["dry_weight_lb"] else None
        sleds.append(s)
    for p in problems:
        print("warning:", p, file=sys.stderr)
    sleds.sort(key=lambda s: (-s["year"], s["brand"], s["model"]))
    return sleds


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
<link rel="canonical" href="{canon}">
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
<link rel="stylesheet" href="/assets/site.css?v={TODAY}">
{ld}
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="mast">
  <div class="wrap mast-in">
    <a class="logo" href="/"><img src="/assets/logo-dark.webp" alt="SledSpecs.com home" width="628" height="112"></a>
    <nav class="mainnav" aria-label="Main">{nav}</nav>
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
      <p>Factory snowmobile specs, belt and track fitment, gathered from manufacturer spec sheets and owner's manuals. Every figure names its source.</p>
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
      <ul><li><a href="/belt-finder/">Drive belt finder</a></li><li><a href="/compare/">Compare sleds</a></li><li><a href="/about/">How the data is gathered</a></li><li><a href="/about/#corrections">Corrections log</a></li>{('<li><a href="' + mailto('SledSpecs correction') + '">Send a correction</a></li>') if CONTACT_EMAIL else ''}</ul>
    </div>
  </div>
  <div class="wrap foot-legal"><p>Ski-Doo, Polaris, Arctic Cat and Yamaha are trademarks of their owners. SledSpecs is independent and not affiliated with any manufacturer. Always confirm part numbers with your dealer before ordering.</p></div>
</footer>
<div class="tray" id="tray" hidden>
  <span id="trayNames"></span>
  <a class="btn go" id="trayGo" href="/compare/">Compare</a>
  <button class="btn ghost" id="trayClear" type="button">Clear</button>
</div>
<script src="/assets/app.js?v={TODAY}" defer></script>
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
  <form class="find" action="/" method="get" role="search">
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


def model_page(s, sleds):
    def row(k, v):
        return f"<tr><th scope=row>{k}</th><td>{v}</td></tr>" if v not in (None, "", "—") else ""
    hp = f"{n(s['hp'])} hp" if s["hp"] else None
    missing = [label for label, v in [("horsepower", s["hp"] or hp_gap(s) == "Not published"),
                                      ("dry weight", s["dry_weight_lb"]), ("track size", s["track"]),
                                      ("fuel capacity", s["fuel_gal"]), ("drive belt part number", s["belt_pn"]),
                                      ("clutching", s["clutch"]), ("overall length", s["length_in"])] if not v]
    plate = "".join(f'<div><dt>{k}</dt><dd>{v}</dd></div>' for k, v in [
        ("Engine", f"{n(s['cc'])} cc"),
        ("Power", hp or hp_gap(s)),
        ("Dry weight", f"{n(s['dry_weight_lb'])} lb" if s["dry_weight_lb"] else "—"),
        ("Track", f"{n(s['track_length_in'])} in" if s["track_length_in"] else "—"),
    ])
    engine = (row("Engine", e(s["engine"])) + row("Type", e(s["engine_detail"] or "")) +
              row("Displacement", f"{n(s['cc'])} cc") + row("Cylinders", n(s["cylinders"])) +
              row("Horsepower", hp or hp_gap(s, long=True)) +
              row("Power-to-weight", f"{s['lb_per_hp']} lb per hp" if s["lb_per_hp"] else None))
    drive = (row("Track", e(s["track"]) if s["track"] else None) + row("Track model", e(s["track_name"]) if s["track_name"] else None) +
             row("Drive belt", f'<b class="pn">{e(s["belt_pn"])}</b>' if s["belt_pn"] else None) +
             row("Clutching", e(s["clutch"]) if s["clutch"] else None) +
             row("Drive sprocket pitch", f"{n(s['sprocket_pitch_in'])} in" if s["sprocket_pitch_in"] else None) +
             row("Starter", e(s["starter"]) if s["starter"] else None))
    chassis = (row("Dry weight", f"{n(s['dry_weight_lb'])} lb" if s["dry_weight_lb"] else None) +
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
        if same_belt:
            side += "<p>Also fits:</p><ul>" + "".join(f'<li><a href="{x["url"]}">{e(x["full"])}</a></li>' for x in same_belt) + "</ul>"
        side += '<p class="small">Confirm with your dealer before ordering.</p></div>'
    side += f'<button class="btn go wide" type="button" data-compare="{s["key"]}" aria-pressed="false">Add to compare</button>'
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
    note = f'<p class="note">{e(s["notes"])}</p>' if s["notes"] else ""

    body = f"""{c_html}
<article class="model">
  <header class="model-h">
    <p class="kicker"><a href="/snowmobiles/{s['brand_slug']}/">{e(s['brand'])}</a> / <a href="/snowmobiles/type/{slug(s['category'])}/">{e(s['category'])}</a></p>
    <h1 class="h1">{e(nm)} specs</h1>
    {note}
  </header>
  <dl class="plate">{plate}</dl>
  <div class="model-grid">
    <div class="specs">{tables}
      <div class="srcbox">{src}{gaps}</div>
    </div>
    <aside class="side">{side}</aside>
  </div>
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
    return page(s["url"], f"{nm} Specs: {title_bits} | SledSpecs", desc, body,
                jsonld=graph(ORG, c_ld, veh, faq_ld), active="brands")


def belt_page(sleds):
    rows = "".join(f"""<tr data-search="{e((s['full']+' '+(s['belt_pn'] or '')+' '+(s['track'] or '')).lower())}"><th scope=row class="m"><a href="{s['url']}">{e(s['full'])}</a></th>
<td data-l="Drive belt">{('<b class="pn">'+e(s['belt_pn'])+'</b>') if s['belt_pn'] else '<span class="np">Not on file yet</span>'}</td>
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
    for s in sleds:
        write(s["url"], model_page(s, sleds)); urls.append((s["url"], s["checked"] or TODAY))
    write("/belt-finder/", belt_page(sleds))
    write("/compare/", compare_page())
    write("/about/", about_page(sleds, corrections))
    write("/404.html", notfound())

    pub = [{k: s[k] for k in ("key", "full", "brand", "model", "year", "category", "engine", "cc", "hp", "dry_weight_lb",
                              "track", "track_length_in", "fuel_gal", "belt_pn", "lb_per_hp", "url")} for s in sleds]
    write("/assets/sleds.json", json.dumps(pub, separators=(",", ":")))
    write("/sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
          "".join(f"<url><loc>{SITE}{u}</loc><lastmod>{d}</lastmod></url>\n" for u, d in urls) + "</urlset>\n")
    write("/robots.txt", f"User-agent: *\nAllow: /\nDisallow: /compare/\n\nSitemap: {SITE}/sitemap.xml\n")
    write("/site.webmanifest", json.dumps({"name": "SledSpecs", "short_name": "SledSpecs", "start_url": "/",
                                           "display": "browser", "background_color": "#f2f5f7", "theme_color": "#0a1f32",
                                           "icons": [{"src": "/assets/icon-192.png", "sizes": "192x192", "type": "image/png"}]}))
    print(f"built {len(urls)} indexable pages for {len(sleds)} sleds -> dist/")


if __name__ == "__main__":
    main()
