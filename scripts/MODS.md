# Mods data (for Clove)

Files: `data/mods/*.json`, one file per batch or engine family (e.g. `skidoo-850-etec.json`).
Each file is a list of sled objects. Run `python3 scripts/mods_check.py` before pushing.

```json
[
  {
    "sled_id": "ski-doo/2023-summit-x-850-e-tec-165",
    "mods": [
      {
        "category": "Clutch kits",
        "maker": "Maker name",
        "product_name": "Product name as the maker writes it",
        "sku": "ABC-123",
        "price": 899.95,
        "currency": "USD",
        "price_checked": "2026-11-20",
        "fitment_statement": "Maker's own fitment wording, copied, not paraphrased",
        "claims": ["+8 hp (maker claim)", "-4 lb"],
        "requirements": ["91 octane", "Maker's tune"],
        "impact_note": "SledSpecs editorial: warranty, noise, fuel, supporting mods",
        "source_url": "https://maker.com/product-page",
        "checked": "2026-11-20"
      }
    ],
    "not_listed": [
      {"maker": "Silber", "reason": "No kit listed for 2023 Summit X 850", "checked": "2026-11-20"}
    ]
  }
]
```

Rules
- `sled_id` = the sled page address after `/snowmobiles/`. Copy it from the live URL.
- `category` must be one of: Clutch kits, Exhaust cans, Full exhaust / stage kits, Turbo kits, Big bore kits, Other.
- Dates are YYYY-MM-DD. `price` needs `currency` and `price_checked`.
- Only `category, maker, product_name, source_url, checked` are required. Leave out what the maker doesn't publish. Never fill gaps.
- Every figure renders as a maker claim. `impact_note` renders separately as the SledSpecs note.
- A sled with no mods and no not_listed entries shows no Mods section.

TODO phase 2: `/mods/` hub page (by maker and category).
