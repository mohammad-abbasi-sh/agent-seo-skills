---
name: schema-forge
description: Generate and validate schema.org JSON-LD for LocalBusiness, Article, FAQPage and Product — the four types that actually earn rich results. Use when the user wants structured data for a page, needs to check whether existing JSON-LD is valid, or asks why a rich result is not showing. Bundled script is zero-dependency Python 3 — no API keys, no external services; it checks required and recommended fields the way Google does, and catches value errors (bad dates, non-numeric prices, answers without questions) that a plain JSON parse misses.
---

# Schema Forge

Generate JSON-LD that parses *and* qualifies — with a deterministic local script, never vibes.

## Generate schema for a page

Pick a type, copy its template, fill it in, generate:

```bash
python3 scripts/schema_forge.py template --type FAQPage > my-faq.json
# edit my-faq.json with the page's real content, then:
python3 scripts/schema_forge.py generate --type FAQPage --spec my-faq.json
python3 scripts/schema_forge.py generate --type LocalBusiness --spec my-business.json --out business.jsonld
```

Run it from this skill's directory. Try it on the bundled examples first:

```bash
python3 scripts/schema_forge.py generate --type FAQPage --spec scripts/examples/faq.json
```

Real output (the FAQ example, a fictional bookshop):

```json
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "inLanguage": "en",
  "mainEntity": [
    {
      "acceptedAnswer": {
        "text": "Yes, we ship to over 40 countries. Delivery takes 5-10 business days and shipping costs are calculated at checkout.",
        "@type": "Answer"
      },
      "name": "Do you ship internationally?",
      "@type": "Question"
    },
    {
      "acceptedAnswer": {
        "text": "Yes. Books in their original condition can be returned within 30 days for a full refund.",
        "@type": "Answer"
      },
      "name": "Can I return a book?",
      "@type": "Question"
    },
    {
      "acceptedAnswer": {
        "text": "Yes, gift wrapping is free on all orders. Add a gift message at checkout and we will include a handwritten card.",
        "@type": "Answer"
      },
      "name": "Do you offer gift wrapping?",
      "@type": "Question"
    }
  ]
}
```

All four bundled examples validate clean — 4/4 with 0 errors and 0 warnings:

```
python3 scripts/schema_forge.py generate --type LocalBusiness --spec scripts/examples/localbusiness.json | python3 scripts/schema_forge.py validate
[1] LocalBusiness: valid
python3 scripts/schema_forge.py generate --type Article --spec scripts/examples/article.json | python3 scripts/schema_forge.py validate
[1] Article: valid
python3 scripts/schema_forge.py generate --type FAQPage --spec scripts/examples/faq.json | python3 scripts/schema_forge.py validate
[1] FAQPage: valid
python3 scripts/schema_forge.py generate --type Product --spec scripts/examples/product.json | python3 scripts/schema_forge.py validate
[1] Product: valid
```

## Validate existing JSON-LD

From a file, from stdin, or straight off a live page:

```bash
python3 scripts/schema_forge.py validate page.jsonld
python3 scripts/schema_forge.py validate --url https://example.com/page
cat page.html | python3 scripts/schema_forge.py validate
python3 scripts/schema_forge.py validate page.jsonld --json
```

Real output — a FAQPage whose question has no answer:

```
JSON-LD validation — stdin (1 document)

[1] FAQPage: INVALID (1 error) — 1 warning
  ERROR: mainEntity[1] (Do you ship?) has no acceptedAnswer.text
  warning: missing recommended field: inLanguage
```

Exit code is 1 when any document has errors, 0 when all are valid.

## What it checks

| Type | Required (error if missing) | Recommended (warning) |
|---|---|---|
| LocalBusiness | `name` | `address`, `telephone`, `url`, `image`, `priceRange`, `openingHours` |
| Article | `headline`, `author`, `datePublished` | `image`, `publisher`, `dateModified`, `mainEntityOfPage` |
| FAQPage | `mainEntity` with ≥ 1 Question, each with a name and `acceptedAnswer.text` | `inLanguage` |
| Product | `name` + at least one of `offers`, `aggregateRating`, `review` | `description`, `image`, `brand`, `sku` |

Value checks on top of presence: dates must be `YYYY-MM-DD` (or full ISO 8601), URLs must start with `http(s)://`, `offers.price` must be numeric, `aggregateRating.ratingValue` must be numeric and 0–5. `types` lists all four with their fields:

```bash
python3 scripts/schema_forge.py types
```

## Interpret the report

- **Errors mean the rich result will not fire.** Fix every error before pasting the markup on the page — a missing `acceptedAnswer.text` or a Product with no offer, rating or review is the usual cause of "valid JSON, no rich result".
- **Warnings mean the markup parses but is thin.** A LocalBusiness without `address` or `telephone` still validates, but Google has less to show. Fill recommended fields when the page genuinely has that information — never invent a phone number or price to silence a warning.
- **A valid result is not a guarantee.** Google decides whether to show a rich result; valid JSON-LD is the entry ticket, not the prize. Say that plainly when the user asks why a valid page still shows no rich result.
- **One document per check.** `--url` extracts every `<script type="application/ld+json">` block on the page and validates each separately, so a broken second block does not hide behind a valid first one.

## Present results to the user

1. Lead with the verdict per document: valid, or INVALID with the error count.
2. List errors first, each with the concrete fix (which field, what value it needs).
3. List warnings as "worth adding if true" — never as must-fix.
4. Paste the generated JSON-LD in a code block, ready to drop into `<script type="application/ld+json">`.

## Rules

- Only report values the tool returned. Never claim a page "will get rich results" — valid markup only makes it eligible.
- Never invent business details (name, address, phone, price, rating) to fill a template. If the user has not given a value, leave the field out and let the validator warn.
- Dates, URLs and prices come from the user's page or spec — check them, don't guess them.
- The four types here are the whole scope. For any other `@type`, the validator says so instead of pretending to check it.
