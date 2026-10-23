---
name: site-audit
description: Audit any web page's on-page and technical SEO with a deterministic local tool (title, meta description, H1, canonical, robots meta, Open Graph, JSON-LD schema, images/alt, links, word count) and get a 0-100 score with prioritized fixes. Use when the user asks to audit, check, review, or score a URL or website for SEO, or asks "how is this page doing SEO-wise". No API keys, no external services — the bundled script fetches and analyzes the page locally.
---

# Site Audit

Run a real audit with the bundled script — never guess SEO metrics.

## Run the audit

```bash
python3 scripts/seo_audit.py <URL> --json
```

Run it from this skill's directory (the folder containing this SKILL.md).
The script is zero-dependency Python 3 (standard library only).

## Interpret the report

The JSON report contains: `status`, `response_time_s`, `title`,
`meta_description`, `h1`, `canonical`, `robots_meta`, `meta` (Open Graph),
`json_ld_blocks`, `json_ld_types`, `images`, `images_with_alt`,
`links_internal_bucket`, `links_external_bucket`, `word_count`, and a
0–100 `score`.

Score bands: 85–100 strong · 70–84 good with gaps · 50–69 needs work ·
below 50 poor.

## Present results to the user

1. Lead with the score and a one-line verdict.
2. List problems in priority order (missing/duplicate title or H1,
   missing meta description, missing canonical, `noindex` in robots meta,
   missing JSON-LD, images without alt, thin content) with the actual
   values the tool found.
3. End with the top 3 fixes, in the order they should be done.

## Rules

- Only report values the tool returned. Never invent metrics the tool
  does not measure (no backlink counts, no traffic estimates, no
  keyword volumes).
- If the fetch fails (non-200, timeout), say so plainly and report the
  status code instead of auditing error-page content.
- For multiple URLs, audit each one separately and compare scores in a
  small table.
