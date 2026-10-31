---
name: striking-distance
description: Analyze a Google Search Console CSV export to find SEO quick wins: striking-distance queries (ranking 8-20), CTR underperformers vs their position peers, and keyword cannibalization across pages. Use when the user has GSC performance data (or a CSV of queries with clicks/impressions/CTR/position) and asks about low-hanging keywords, quick wins, or cannibalization. Bundled script is zero-dependency Python 3 — no API keys, no external services.
---

# Striking Distance

Find the queries that are one push away from page one — with a deterministic local script, never vibes.

## Get the data

Export from Google Search Console: **Performance → Export** (Queries, or Queries × Pages for cannibalization detection). The script also accepts any CSV with query/clicks/impressions/CTR/position columns; headers are matched case-insensitively (`Top queries`/`Query`, `Top pages`/`Page`, `CTR` as `12.5%` or `0.125`).

## Run the analysis

```bash
python3 scripts/gsc_analyze.py <export.csv>
python3 scripts/gsc_analyze.py <export.csv> --json --limit 30 --min-impressions 200
```

Run it from this skill's directory. Try it on the bundled example first:

```bash
python3 scripts/gsc_analyze.py scripts/sample_gsc.csv
```

Real output on the sample file:

```
GSC opportunity analysis — 20 queries, 22 rows (scripts/sample_gsc.csv)

== Striking distance (position 8-20): 11 queries ==
1. buy running shoes — pos 9.2, 5,200 impressions, 130 clicks (CTR 2.5%)
2. best budget laptop 2026 — pos 12.4, 3,100 impressions, 62 clicks (CTR 2.0%)
...

== CTR opportunities: 2 queries ==
(benchmark = median CTR of same-position peers in this file)
1. buy running shoes — pos 9.2, CTR 2.5% vs peer median 7.0%, ~234 extra clicks if fixed
2. dubai visa apply — pos 4.4, CTR 3.0% vs peer median 7.5%, ~148 extra clicks if fixed

== Cannibalization candidates: 2 queries ==
1. wireless earbuds under 50 — /audio (pos 11.8, 114 clicks); /deals (pos 23.0, 12 clicks)
2. gorgan restaurants — /restaurants (pos 8.1, 95 clicks); /food (pos 14.3, 18 clicks)
```

## Interpret the report

- **Striking distance (positions 8–20), sorted by impressions.** These are the highest-leverage queries: a small ranking push moves them onto page one. Prioritize by impressions, then by how close to position 7 they are.
- **CTR opportunities.** A query is flagged when it has ≥100 impressions and its CTR is under half the **median CTR of same-position queries in this same file** (self-benchmarked — no external "average CTR" tables, so it adapts to your niche and brand strength). `est_extra_clicks` estimates the clicks you'd gain by matching the peer median — a prioritization aid, not a promise.
- **Cannibalization candidates.** Same query ranking on 2+ distinct pages (needs the Page dimension in the export). Typical remedies: merge content, canonicalize, or differentiate intent — but check manually first, because split coverage can be intentional.

## Present results to the user

1. Lead with the #1 striking-distance query (impressions + position + CTR).
2. Table the top 5–10 striking-distance queries with the concrete push each needs.
3. Show CTR opportunities with their estimated extra clicks.
4. List cannibalization candidates with the competing URLs and positions, and recommend which page should win.

## Rules

- Only report values the tool returned. Never invent traffic, revenue, or ranking projections.
- Striking distance means *opportunity*, not guaranteed page-one — say what would need to change (content depth, intent match, internal links).
- A cannibalization flag is a candidate, not a verdict: confirm intent overlap before recommending merges or redirects.
- The peer-median CTR benchmark is file-local. Never compare it across sites, countries, or date ranges, and never present it as an industry standard.
