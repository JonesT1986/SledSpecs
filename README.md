# SledSpecs.com

Static snowmobile spec site. Every page is generated from two spreadsheets.

## Add or fix a sled
1. Open `data/sleds.csv` (Excel, Google Sheets or Numbers all work; save as CSV).
2. Add one row per sled. `id` is a short unique slug like `summit-x-850-165`.
   `brand` must be Ski-Doo, Polaris, Arctic Cat or Yamaha; `category` must be Mountain, Trail, Crossover, Utility or Vintage.
   Leave a cell empty if the source doesn't state the figure. Never estimate.
3. Fill `source` (the document the numbers came from) and `checked` (YYYY-MM-DD).
4. If you change an existing figure, add a line to `data/corrections.csv`.
5. Commit and push. Vercel rebuilds the site automatically.

## Build locally
    python3 build.py          # writes dist/
    cd dist && python3 -m http.server 8000

The build warns about duplicate ids, unknown brands or types, and sleds with no source.

## Settings
- Contact address for "Send a correction" links: set the `SLEDSPECS_CONTACT_EMAIL` environment variable in Vercel (Project Settings > Environment Variables). Until it's set, the correction links are hidden.
- Any `*.vercel.app` address sends a noindex header, so only sledspecs.com gets indexed.
