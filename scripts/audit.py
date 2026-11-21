"""SledSpecs data audit. Run before every push, and after pulling anyone else's upload:

    python3 scripts/audit.py              # audit every row
    python3 scripts/audit.py --since REV  # only rows added or changed since git revision REV

Prints problems grouped by severity. Exit code 1 when anything would put a wrong or
unconfirmed figure on the site (HOLD or FIX), so it can gate a push.
"""
import csv, io, re, subprocess, sys
from collections import Counter, defaultdict

ROOT = __file__.rsplit("/scripts/", 1)[0]
CSV = f"{ROOT}/data/sleds.csv"
CURRENT_MY = 2027                      # newest model year that can exist

UNCONFIRMED = [r"verify\b[^.;]*\bbefore publishing", r"availability\b[^.;]*\bnot confirmed",
               r"spec table not yet captured", r"data captured is from a MY ?\d{4}",
               r"carried from the [^.;]*family", r"(?<!not )(?<!than )\bassumed\b", r"\bestimated? by\b",
               r"\bapprox(?:imately)?\b", r"\btypical(?:ly)?\b", r"\bprobably\b", r"\bshould be\b"]
BELT = {"Polaris": r"^32\d{5}$|^3211\d{3}$|^3212\d{3}$|^32\d{5}$",
        "Ski-Doo": r"^4173\d{5}$|^4150\d{5}$|^4140\d{5}$|^4176\d{5}$|^605 ?\d{3} ?\d{3}$|^41[4-7]\d{6}$",
        "Arctic Cat": r"^0\d{3}-\d{3}$",
        "Yamaha": r"^[0-9A-Z]{3}-[0-9]{5}-[0-9]{2}(-00)?$"}
RANGE = {"dry_weight_lb": (60, 1200), "track_length_in": (40, 180), "track_width_in": (8, 25),
         "lug_in": (0.3, 3.6), "fuel_gal": (0.3, 20), "length_in": (50, 160), "hp": (1, 260),
         "cc": (40, 1600)}


def rows_at(rev=None):
    text = (subprocess.run(["git", "-C", ROOT, "show", f"{rev}:data/sleds.csv"], capture_output=True, text=True).stdout
            if rev else open(CSV, newline="", encoding="utf-8").read())
    return list(csv.DictReader(io.StringIO(text.replace("\r\n", "\n"))))


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def holds():
    try:
        with open(f"{ROOT}/data/holds.csv", newline="", encoding="utf-8") as fh:
            return {(h["year"], h["brand"], h["id"]) for h in csv.DictReader(fh)}
    except FileNotFoundError:
        return set()


def audit(rows, only=None):
    out = defaultdict(list)          # severity -> [(row label, problem)]
    held = holds()
    raw = open(CSV, "rb").read()
    if b"\r\n" in raw:
        out["TIDY"].append(("data/sleds.csv", "saved with Windows (CRLF) line endings; save with LF"))
    keys = Counter((r["year"], r["brand"], r["id"]) for r in rows)
    names = Counter((r["year"], r["brand"], r["model"].strip().lower()) for r in rows)
    for r in rows:
        k = (r["year"], r["brand"], r["id"])
        if only is not None and k not in only:
            continue
        lab = f'{r["year"]} {r["brand"]} {r["model"]}'
        y = r["year"]
        note = r.get("notes") or ""
        src = r.get("source") or ""
        # identity
        if keys[k] > 1:
            out["FIX"].append((lab, f"id {r['id']} used twice for the same year and brand"))
        if names[(y, r["brand"], r["model"].strip().lower())] > 1:
            out["FIX"].append((lab, "same model name appears twice for this year"))
        if not y.isdigit() or not 1955 <= int(y) <= CURRENT_MY:
            out["FIX"].append((lab, f"model year {y} out of range"))
        if re.search(rf"(^|-){y}(-|$)", r["id"]):
            out["TIDY"].append((lab, f"id repeats the year: {r['id']}"))
        t = r["id"].split("-")
        if any(t[i:i+2] == t[j:j+2] for i in range(len(t) - 1) for j in range(i + 2, len(t) - 1)
               if re.fullmatch(r"[a-z][a-z0-9]*", t[i]) and re.fullmatch(r"[a-z][a-z0-9]*", t[i+1])):
            out["TIDY"].append((lab, f"id says the model name twice: {r['id']}"))
        # sourcing
        if not src.strip():
            out["HOLD"].append((lab, "no source recorded"))
        if not (r.get("checked") or "").strip():
            out["TIDY"].append((lab, "no checked date"))
        for pat in ([] if k in held else UNCONFIRMED):
            m = re.search(pat, note, re.I)
            if m:
                out["HOLD"].append((lab, f'notes say a figure isn\'t confirmed: "...{note[max(0, m.start()-40):m.end()+40]}..."'))
                break
        other = sorted({int(m) for m in re.findall(r"\bMY ?(\d{4})\b", src + " " + note)} - {int(y)}) if y.isdigit() else []
        if other and not re.search(rf"\bMY ?{y}\b|\b{y}\b", src):
            out["CHECK"].append((lab, f"source mentions model year {other} but not {y}"))
        # press-sourced figures: allowed, but labelled on the site until a factory document replaces them
        if re.search(r"as published by|launch materials|lineup coverage", src, re.I):
            out["TIDY"].append((lab, "figures from magazine launch coverage; replace with a factory spec sheet or manual when found"))
        # values
        for f, (lo, hi) in RANGE.items():
            v = num(r.get(f))
            if v is not None and not lo <= v <= hi:
                out["FIX"].append((lab, f"{f} = {r[f]} is outside {lo}-{hi}"))
        tl = num(r.get("track_length_in"))
        mt = re.findall(r"\b(1[0-7]\d)\b", r["model"])
        cc0 = num(r.get("cc"))
        if tl and mt and abs(int(mt[-1]) - tl) > 1 and not (cc0 and abs(cc0 - int(mt[-1])) < 15):
            out["FIX"].append((lab, f"name says {mt[-1]} in track but track_length_in is {r['track_length_in']}"))
        cc = num(r.get("cc"))
        me = re.search(r"\b(120|200|250|340|400|440|500|550|600|650|700|800|850|900|1000)\b", r["model"])
        tl0 = num(r.get("track_length_in"))
        if cc and me and r["year"].isdigit() and int(r["year"]) >= 2000 and not (tl0 and abs(tl0 - int(me.group(1))) < 2):
            want = int(me.group(1))
            if not (0.6 * want <= cc <= 1.25 * want):
                out["CHECK"].append((lab, f"name says {want} but cc is {r['cc']}"))
        b = (r.get("belt_pn") or "").strip()
        if re.fullmatch(r"\d{3}( \d{3}){2}", b): b = b.replace(" ", "")
        if b and not re.search(r"\d{3}", b):
            out["FIX"].append((lab, f"belt_pn holds text, not a part number: {b!r}"))
        elif b and r["brand"] in BELT and not re.match(BELT[r["brand"]], b):
            out["CHECK"].append((lab, f"belt number {b} doesn't look like a {r['brand']} part number"))
        if num(r.get("hp")) and not (re.search(r"SR ?Viper", r["model"], re.I) and num(r.get("hp")) == 125) and r["brand"] in ("Polaris", "Yamaha") and y.isdigit() and int(y) >= 2010:
            out["CHECK"].append((lab, f"{r['brand']} rarely publishes hp; confirm {r['hp']} hp is from a factory source"))
    return out


def apply_overrides(rows):
    """Apply data/overrides.csv the same way build.py does, so the audit sees what the site shows."""
    try:
        with open(f"{ROOT}/data/overrides.csv", newline="", encoding="utf-8") as fh:
            ovr = list(csv.DictReader(fh))
    except FileNotFoundError:
        return rows
    idx = {(r["year"], r["brand"], r["id"]): r for r in rows}
    for o in ovr:
        r = idx.get((o["year"], o["brand"], o["id"]))
        if r is not None and o["field"] in r:
            r[o["field"]] = o["value"]
    return rows


def main():
    rows = apply_overrides(rows_at())
    only = None
    if "--since" in sys.argv:
        rev = sys.argv[sys.argv.index("--since") + 1]
        before = {(r["year"], r["brand"], r["id"]): r for r in rows_at(rev)}
        only = {(r["year"], r["brand"], r["id"]) for r in rows
                if before.get((r["year"], r["brand"], r["id"])) != r}
        gone = set(before) - {(r["year"], r["brand"], r["id"]) for r in rows}
        print(f"{len(only)} rows added or changed, {len(gone)} removed since {rev}")
        for g in sorted(gone):
            print(f"  REMOVED  {' '.join(g)}")
    res = audit(rows, only)
    order = [("FIX", "Wrong or impossible values"), ("HOLD", "Unconfirmed or unsourced, keep off the site"),
             ("CHECK", "Looks odd, check against the source"), ("TIDY", "Housekeeping")]
    for sev, title in order:
        items = res.get(sev, [])
        if items:
            print(f"\n{sev}: {title} ({len(items)})")
            if sev == "TIDY" and len(items) > 15:
                for kind, n in Counter(re.sub(r":.*", "", m) for _, m in items).most_common():
                    print(f"  {n} x {kind}")
                continue
            for lab, msg in items[:200]:
                print(f"  {lab}: {msg}")
    if not any(res.values()):
        print("audit clean")
    sys.exit(1 if res.get("FIX") or res.get("HOLD") else 0)


if __name__ == "__main__":
    main()
