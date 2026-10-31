#!/usr/bin/env python3
"""gsc_analyze.py — Search Console CSV opportunity analysis.

Reads a Google Search Console export CSV (Queries, or Queries x Pages)
and reports three classic SEO opportunity sets:

  1. Striking distance — queries ranking 8-20 with the most impressions.
  2. CTR opportunities  — high-impression queries underperforming their
     position peers. The benchmark is computed FROM THIS FILE (median CTR
     per rounded position), never from external "average CTR" tables.
  3. Cannibalization   — the same query ranking on 2+ distinct pages
     (needs a page/URL column in the CSV).

Zero dependencies: Python 3 standard library only.

Expected GSC export columns (case-insensitive, tolerant):
  "Top queries" / "Query", "Top pages" / "Page" / "URL" (optional),
  "Clicks", "Impressions", "CTR", "Position" / "Avg. position".
"""

import argparse
import csv
import json
import statistics
import sys

# Header aliases -> canonical field name (all compared lower-cased & stripped)
HEADER_ALIASES = {
    "query": ["top queries", "query", "queries"],
    "page": ["top pages", "page", "url", "landing page"],
    "clicks": ["clicks"],
    "impressions": ["impressions"],
    "ctr": ["ctr"],
    "position": ["position", "avg. position", "avg position"],
}


def parse_ctr(value):
    """Parse a CTR cell like '12.5%', 0.125 or 12.5 into a 0-1 float."""
    if value is None:
        return 0.0
    text = str(value).strip().replace(",", "")
    if not text:
        return 0.0
    had_percent = text.endswith("%")
    text = text.rstrip("%").strip()
    try:
        number = float(text)
    except ValueError:
        return 0.0
    if had_percent or number > 1.0:
        number /= 100.0
    return max(0.0, min(1.0, number))


def parse_float(value):
    try:
        return float(str(value).strip().replace(",", ""))
    except (ValueError, AttributeError):
        return 0.0


def map_headers(headers):
    """Map CSV header names to canonical field names."""
    mapping = {}
    for header in headers:
        key = header.strip().lower()
        for canonical, aliases in HEADER_ALIASES.items():
            if key in aliases:
                mapping[header] = canonical
                break
    return mapping


def load_rows(path, encoding="utf-8-sig"):
    """Load and normalize a GSC export CSV into row dicts."""
    rows = []
    with open(path, newline="", encoding=encoding) as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("CSV has no header row")
        mapping = map_headers(reader.fieldnames)
        if "query" not in mapping.values():
            raise ValueError(
                "No query column found (expected 'Top queries' or 'Query')"
            )
        for raw in reader:
            norm = {mapping[h]: (v or "").strip() for h, v in raw.items()
                    if h in mapping}
            query = norm.get("query", "")
            if not query:
                continue
            rows.append({
                "query": query,
                "page": norm.get("page") or None,
                "clicks": parse_float(norm.get("clicks")),
                "impressions": parse_float(norm.get("impressions")),
                "ctr": parse_ctr(norm.get("ctr")),
                "position": parse_float(norm.get("position")),
            })
    return rows


def aggregate(rows):
    """Roll rows up per query: totals + impression-weighted avg position."""
    agg = {}
    for row in rows:
        key = row["query"].strip().lower()
        entry = agg.setdefault(key, {
            "query": row["query"].strip(),
            "clicks": 0.0,
            "impressions": 0.0,
            "_pos_weight": 0.0,
            "pages": {},
        })
        entry["clicks"] += row["clicks"]
        entry["impressions"] += row["impressions"]
        entry["_pos_weight"] += row["position"] * row["impressions"]
        if row["page"]:
            page = entry["pages"].setdefault(
                row["page"], {"position": row["position"], "clicks": 0.0})
            # keep the best (lowest) position seen for this page
            page["position"] = min(page["position"], row["position"])
            page["clicks"] += row["clicks"]
    for entry in agg.values():
        imp = entry["impressions"]
        entry["position"] = (entry["_pos_weight"] / imp) if imp else 0.0
        del entry["_pos_weight"]
        entry["ctr"] = (entry["clicks"] / imp) if imp else 0.0
    return list(agg.values())


def striking_distance(queries, limit=20, low=7.0, high=20.0):
    """Queries ranked (low, high] with the most impressions first."""
    hits = [q for q in queries if low < q["position"] <= high]
    hits.sort(key=lambda q: q["impressions"], reverse=True)
    return hits[:limit]


def ctr_opportunities(queries, min_impressions=100.0, ratio=0.5,
                      min_bucket_size=3):
    """High-impression queries underperforming their position peers.

    Peer benchmark = median CTR of queries in this file at the same
    rounded position (1-10). A query is flagged when its CTR is below
    `ratio` * peer median and it has >= min_impressions impressions.
    """
    buckets = {}
    for q in queries:
        pos = round(q["position"])
        if 1 <= pos <= 10 and q["impressions"] >= min_impressions:
            buckets.setdefault(pos, []).append(q["ctr"])
    medians = {p: statistics.median(v) for p, v in buckets.items()
               if len(v) >= min_bucket_size}
    flagged = []
    for q in queries:
        pos = round(q["position"])
        median = medians.get(pos)
        if median is None or q["impressions"] < min_impressions:
            continue
        if median > 0 and q["ctr"] < ratio * median:
            flagged.append({
                "query": q["query"],
                "position": round(q["position"], 1),
                "impressions": int(q["impressions"]),
                "clicks": int(q["clicks"]),
                "ctr": round(q["ctr"] * 100, 2),
                "peer_median_ctr": round(median * 100, 2),
                "est_extra_clicks": int(
                    q["impressions"] * max(0.0, median - q["ctr"])),
            })
    flagged.sort(key=lambda f: f["est_extra_clicks"], reverse=True)
    return flagged


def cannibalization(queries, max_position=50.0):
    """Queries ranking on 2+ distinct pages (needs a page column)."""
    hits = []
    for q in queries:
        pages = [(url, info) for url, info in q["pages"].items()
                 if info["position"] <= max_position]
        if len(pages) >= 2:
            pages.sort(key=lambda item: item[1]["position"])
            hits.append({
                "query": q["query"],
                "pages": [
                    {"url": url,
                     "position": round(info["position"], 1),
                     "clicks": int(info["clicks"])}
                    for url, info in pages
                ],
            })
    hits.sort(key=lambda h: len(h["pages"]), reverse=True)
    return hits


def analyze(path, limit=20, min_impressions=100.0):
    rows = load_rows(path)
    queries = aggregate(rows)
    return {
        "meta": {
            "rows": len(rows),
            "queries": len(queries),
            "file": path,
        },
        "striking_distance": [
            {"query": q["query"],
             "position": round(q["position"], 1),
             "impressions": int(q["impressions"]),
             "clicks": int(q["clicks"]),
             "ctr": round(q["ctr"] * 100, 2),
             "pages": len(q["pages"])}
            for q in striking_distance(queries, limit=limit)
        ],
        "ctr_opportunities": ctr_opportunities(
            queries, min_impressions=min_impressions),
        "cannibalization": cannibalization(queries),
    }


def pct(value):
    return f"{value * 100:.1f}%"


def render_text(result):
    lines = []
    meta = result["meta"]
    lines.append(
        f"GSC opportunity analysis — {meta['queries']} queries, "
        f"{meta['rows']} rows ({meta['file']})")
    lines.append("")

    sd = result["striking_distance"]
    lines.append(f"== Striking distance (position 8-20): {len(sd)} queries ==")
    for i, q in enumerate(sd, 1):
        lines.append(
            f"{i}. {q['query']} — pos {q['position']}, "
            f"{q['impressions']:,} impressions, {q['clicks']:,} clicks "
            f"(CTR {q['ctr']}%)")
    if not sd:
        lines.append("(none)")
    lines.append("")

    ctr = result["ctr_opportunities"]
    lines.append(f"== CTR opportunities: {len(ctr)} queries ==")
    lines.append("(benchmark = median CTR of same-position peers in this file)")
    for i, q in enumerate(ctr, 1):
        lines.append(
            f"{i}. {q['query']} — pos {q['position']}, CTR {q['ctr']}% "
            f"vs peer median {q['peer_median_ctr']}%, "
            f"~{q['est_extra_clicks']:,} extra clicks if fixed")
    if not ctr:
        lines.append("(none)")
    lines.append("")

    can = result["cannibalization"]
    lines.append(f"== Cannibalization candidates: {len(can)} queries ==")
    for i, q in enumerate(can, 1):
        pages = "; ".join(
            f"{p['url']} (pos {p['position']}, {p['clicks']} clicks)"
            for p in q["pages"])
        lines.append(f"{i}. {q['query']} — {pages}")
    if not can:
        lines.append("(none — or CSV has no page column)")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Analyze a Search Console CSV export for SEO opportunities.")
    parser.add_argument("csv", help="GSC export CSV (Queries or Queries x Pages)")
    parser.add_argument("--json", action="store_true",
                        help="emit JSON instead of a text report")
    parser.add_argument("--limit", type=int, default=20,
                        help="max striking-distance rows (default 20)")
    parser.add_argument("--min-impressions", type=float, default=100,
                        help="min impressions for CTR-opportunity flags (default 100)")
    args = parser.parse_args(argv)

    try:
        result = analyze(args.csv, limit=args.limit,
                         min_impressions=args.min_impressions)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(render_text(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
