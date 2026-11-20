# Daily sled news update

The /news/ page and the homepage "Latest sled news" box are built from `data/news.csv`.
The homepage shows the 5 newest rows; /news/ shows all of them, newest first.

## Columns
date,title,source,url,category,summary

- **date**: the story's publish date, YYYY-MM-DD. Never the day you found it.
- **title**: your own short headline, under 80 characters. Don't copy the article's headline word for word.
- **source**: the publication (Snow Goer, Sled Magazine, Powersports Business, a maker's own newsroom, CPSC, Transport Canada...).
- **url**: the direct link to the story itself, not a homepage or tag page. Must start with https://.
- **category**: exactly one of: New models, Reviews, Racing, Recalls, Vintage, Trails and clubs, Industry
- **summary**: one or two sentences in your own words, under 280 characters. Never paste sentences from the article.

## Rules
1. Snowmobile stories only, from North America first. Aim for a mix: new models, reviews,
   snocross/hillclimb/drag racing, recalls (CPSC, Transport Canada, maker recall pages),
   vintage shows and sled history, trail/club/permit news, industry business news.
2. Only add stories you opened or saw in search results with a date and a direct link. Never invent or guess a date, URL or fact.
3. Skip anything already in the file (same URL, or the same story from another outlet).
4. Skip dealer ads, sales promos, rumours and "predictions" pieces.
5. Up to 5 new rows a day. Zero is fine when nothing new came out.
6. Run `python3 scripts/news_check.py` and `python3 build.py`; both must pass before pushing.
