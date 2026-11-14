#!/usr/bin/env python3
"""schema_forge.py — JSON-LD schema generator and validator.

Builds valid schema.org JSON-LD for the four types SEOs reach for most,
and validates existing JSON-LD (from a file or a live page) against the
required / recommended fields Google actually checks for rich results.

  generate  --type LocalBusiness|Article|FAQPage|Product --spec spec.json
  validate  file.jsonld | --url https://example.com/page | (stdin)
  template  --type FAQPage        # print a fill-in spec to start from
  types                           # list supported types + their fields

Zero dependencies: Python 3 standard library only. No network calls
unless you pass --url, and no data leaves the machine either way.

Validation rules (errors = rich result won't fire; warnings = Google
recommends the field but the markup still parses):

  LocalBusiness  required: name
                 recommended: address, telephone, url, image,
                 priceRange, openingHours
  Article        required: headline, author, datePublished
                 recommended: image, publisher, dateModified,
                 mainEntityOfPage
  FAQPage        required: mainEntity with >= 1 Question, each with a
                 non-empty name and acceptedAnswer.text
                 recommended: inLanguage
  Product        required: name + at least one of offers,
                 aggregateRating, review
                 recommended: description, image, brand, sku

Field values are checked, not just presence: dates must be YYYY-MM-DD
(or full ISO 8601), URLs must start with http(s)://, prices must be
numeric, and a Question without an answer is an error, not a warning.
"""
import argparse
import html.parser
import json
import re
import sys
import urllib.request

SCHEMA_CONTEXT = "https://schema.org"

# type -> {required, recommended, help} — the single source of truth
# for both generation (what a spec may contain) and validation.
TYPES = {
    "LocalBusiness": {
        "required": ["name"],
        "recommended": ["address", "telephone", "url", "image",
                        "priceRange", "openingHours"],
        "help": "A local shop, clinic, restaurant or service business.",
    },
    "Article": {
        "required": ["headline", "author", "datePublished"],
        "recommended": ["image", "publisher", "dateModified",
                        "mainEntityOfPage"],
        "help": "A news article, blog post or guide.",
    },
    "FAQPage": {
        "required": ["mainEntity"],
        "recommended": ["inLanguage"],
        "help": "A page of questions and answers.",
    },
    "Product": {
        "required": ["name", "offers|aggregateRating|review"],
        "recommended": ["description", "image", "brand", "sku"],
        "help": "A product page (needs name + an offer, a rating or a review).",
    },
}

# Spec keys that map to nested schema.org objects. The value in the
# spec is a plain dict; the builder adds the @type.
NESTED = {
    "address": "PostalAddress",
    "geo": "GeoCoordinates",
    "author": None,          # Person or Organization — set by spec @type
    "publisher": "Organization",
    "offers": "Offer",
    "aggregateRating": "AggregateRating",
    "review": "Review",
    "mainEntity": "Question",  # list of {name, acceptedAnswer}
}

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2})?"
                     r"(Z|[+-]\d{2}:\d{2})?)?$")
URL_RE = re.compile(r"^https?://\S+$")


def template_spec(schema_type):
    """A fill-in spec dict for a type (placeholder values)."""
    base = {
        "LocalBusiness": {
            "name": "Your Business Name",
            "address": {"streetAddress": "123 Main Street",
                        "addressLocality": "Your City",
                        "addressRegion": "Your Region",
                        "postalCode": "12345",
                        "addressCountry": "US"},
            "telephone": "+1-555-010-1234",
            "url": "https://example.com",
            "image": "https://example.com/photo.jpg",
            "priceRange": "$$",
            "openingHours": "Mo-Fr 09:00-18:00",
        },
        "Article": {
            "headline": "Your article headline",
            "author": {"@type": "Person", "name": "Author Name",
                       "url": "https://example.com/authors/author-name"},
            "datePublished": "2026-11-14",
            "dateModified": "2026-11-14",
            "image": "https://example.com/article-image.jpg",
            "publisher": {"name": "Your Site Name",
                          "url": "https://example.com"},
            "mainEntityOfPage": "https://example.com/your-article",
        },
        "FAQPage": {
            "inLanguage": "en",
            "mainEntity": [
                {"name": "What is your question?",
                 "acceptedAnswer": {"text": "Your answer here."}},
                {"name": "A second question?",
                 "acceptedAnswer": {"text": "A second answer here."}},
            ],
        },
        "Product": {
            "name": "Your Product Name",
            "description": "A one-sentence description of the product.",
            "image": "https://example.com/product.jpg",
            "brand": "Your Brand",
            "sku": "SKU-0001",
            "offers": {"priceCurrency": "USD", "price": "49.00",
                       "availability": "https://schema.org/InStock",
                       "url": "https://example.com/product"},
            "aggregateRating": {"ratingValue": "4.5",
                                "reviewCount": "12"},
        },
    }
    return base[schema_type]


def _build_nested(key, value):
    """Turn a spec value into its schema.org object form."""
    if isinstance(value, list):
        return [_build_nested(key, v) for v in value]
    if not isinstance(value, dict):
        return value
    out = dict(value)
    if "@type" not in out:
        if key == "mainEntity":
            out["@type"] = "Question"
            ans = out.get("acceptedAnswer")
            if isinstance(ans, dict) and "@type" not in ans:
                ans = dict(ans)
                ans["@type"] = "Answer"
                out["acceptedAnswer"] = ans
        elif key == "author":
            # Default Person; the spec may set Organization explicitly.
            out["@type"] = "Person"
        elif key in NESTED and NESTED[key]:
            out["@type"] = NESTED[key]
    return out


def build(schema_type, spec):
    """Build a JSON-LD document from a type + spec dict."""
    if schema_type not in TYPES:
        raise ValueError("unknown type %r (see: schema_forge.py types)"
                         % schema_type)
    doc = {"@context": SCHEMA_CONTEXT, "@type": schema_type}
    for key, value in spec.items():
        if value is None or value == "" or value == []:
            continue
        if key in NESTED:
            doc[key] = _build_nested(key, value)
        else:
            doc[key] = value
    return doc


def _is_url(value):
    return isinstance(value, str) and bool(URL_RE.match(value.strip()))


def _is_date(value):
    return isinstance(value, str) and bool(DATE_RE.match(value.strip()))


def validate(doc):
    """Validate one JSON-LD document.

    Returns (errors, warnings): lists of human-readable strings.
    """
    errors, warnings = [], []
    if not isinstance(doc, dict):
        return ["document is not a JSON object"], []
    schema_type = doc.get("@type")
    if not doc.get("@context"):
        errors.append("missing @context (should be https://schema.org)")
    elif doc["@context"] not in (SCHEMA_CONTEXT, "http://schema.org",
                                  "https://schema.org/"):
        warnings.append("@context is %r, expected https://schema.org"
                        % doc["@context"])
    if not schema_type:
        return errors + ["missing @type"], warnings
    if schema_type not in TYPES:
        warnings.append("unknown @type %r — not one of the four types "
                        "this tool validates" % schema_type)
        return errors, warnings

    spec = TYPES[schema_type]
    for field in spec["required"]:
        if "|" in field:  # any-of group, e.g. offers|aggregateRating|review
            options = field.split("|")
            if not any(doc.get(o) for o in options):
                errors.append("missing one of: %s (at least one is "
                              "required for %s rich results)"
                              % (", ".join(options), schema_type))
        elif not doc.get(field):
            errors.append("missing required field: %s" % field)
    for field in spec["recommended"]:
        if not doc.get(field):
            warnings.append("missing recommended field: %s" % field)

    # Value checks — presence alone is not enough.
    if schema_type == "FAQPage":
        entities = doc.get("mainEntity")
        if isinstance(entities, dict):
            entities = [entities]
        if isinstance(entities, list):
            if not entities:
                errors.append("mainEntity is empty — FAQPage needs at "
                              "least one Question")
            for i, q in enumerate(entities, 1):
                if not isinstance(q, dict):
                    errors.append("mainEntity[%d] is not an object" % i)
                    continue
                if not q.get("name"):
                    errors.append("mainEntity[%d] (Question) has no name"
                                  % i)
                ans = q.get("acceptedAnswer")
                text = ans.get("text") if isinstance(ans, dict) else None
                if not text:
                    errors.append("mainEntity[%d] (%s) has no "
                                  "acceptedAnswer.text"
                                  % (i, q.get("name") or "unnamed question"))
    if schema_type == "Product":
        offers = doc.get("offers")
        if isinstance(offers, dict) and offers.get("price") is not None:
            try:
                float(str(offers["price"]))
            except ValueError:
                errors.append("offers.price %r is not numeric"
                              % offers["price"])
        rating = doc.get("aggregateRating")
        if isinstance(rating, dict):
            try:
                value = float(str(rating.get("ratingValue", "")))
                if not 0 <= value <= 5:
                    errors.append("aggregateRating.ratingValue %r is "
                                  "outside 0-5" % rating.get("ratingValue"))
            except ValueError:
                errors.append("aggregateRating.ratingValue %r is not "
                              "numeric" % rating.get("ratingValue"))
    for field in ("datePublished", "dateModified"):
        if doc.get(field) and not _is_date(doc[field]):
            errors.append("%s %r is not a valid date (YYYY-MM-DD)"
                          % (field, doc[field]))
    for field in ("url", "image", "mainEntityOfPage"):
        if doc.get(field) and not _is_url(doc[field]):
            errors.append("%s %r is not a valid http(s) URL"
                          % (field, doc[field]))
    return errors, warnings


class _LdJsonExtractor(html.parser.HTMLParser):
    """Collect <script type="application/ld+json"> blocks from a page."""

    def __init__(self):
        super().__init__()
        self.blocks, self._in_ld, self._buf = [], False, []

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            attrs = dict(attrs)
            if attrs.get("type", "").strip() == "application/ld+json":
                self._in_ld, self._buf = True, []

    def handle_endtag(self, tag):
        if tag == "script" and self._in_ld:
            self.blocks.append("".join(self._buf))
            self._in_ld = False

    def handle_data(self, data):
        if self._in_ld:
            self._buf.append(data)


def extract_jsonld(html):
    """Parse JSON-LD blocks out of HTML; returns a list of documents."""
    parser = _LdJsonExtractor()
    parser.feed(html)
    docs = []
    for block in parser.blocks:
        try:
            parsed = json.loads(block)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, list):
            docs.extend(d for d in parsed if isinstance(d, dict))
        elif isinstance(parsed, dict):
            docs.append(parsed)
    return docs


def fetch_url(url):
    req = urllib.request.Request(
        url, headers={"User-Agent": "schema-forge/0.3 (JSON-LD validator)"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def _report(docs, as_json, source_label):
    """Print a validation report; return exit code (0 = no errors)."""
    results = []
    total_errors = 0
    for i, doc in enumerate(docs, 1):
        errors, warnings = validate(doc)
        total_errors += len(errors)
        results.append({"index": i, "@type": doc.get("@type"),
                        "errors": errors, "warnings": warnings})
    if as_json:
        print(json.dumps({"source": source_label, "documents": len(docs),
                          "results": results}, indent=2, ensure_ascii=False))
    else:
        print("JSON-LD validation — %s (%d document%s)"
              % (source_label, len(docs), "" if len(docs) == 1 else "s"))
        if not docs:
            print("no JSON-LD blocks found")
        for r in results:
            status = ("INVALID (%d error%s)"
                      % (len(r["errors"]), "" if len(r["errors"]) == 1
                         else "s") if r["errors"] else "valid")
            extra = (" — %d warning%s" % (len(r["warnings"]),
                     "" if len(r["warnings"]) == 1 else "s")
                     if r["warnings"] else "")
            print("\n[%d] %s: %s%s" % (r["index"], r["@type"] or "?",
                                      status, extra))
            for e in r["errors"]:
                print("  ERROR: %s" % e)
            for w in r["warnings"]:
                print("  warning: %s" % w)
    return 0 if total_errors == 0 else 1


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="schema_forge.py",
        description="Generate and validate schema.org JSON-LD "
                    "(LocalBusiness, Article, FAQPage, Product).")
    sub = parser.add_subparsers(dest="command", required=True)

    p_gen = sub.add_parser("generate", help="build JSON-LD from a spec file")
    p_gen.add_argument("--type", required=True, choices=sorted(TYPES),
                       help="schema.org type to generate")
    p_gen.add_argument("--spec", required=True,
                       help="JSON spec file (see: template --type X)")
    p_gen.add_argument("--out", help="write output to this file "
                       "(default: stdout)")
    p_gen.add_argument("--compact", action="store_true",
                       help="single-line JSON instead of pretty-printed")

    p_val = sub.add_parser("validate", help="validate JSON-LD in a file, "
                           "on stdin, or on a live page")
    p_val.add_argument("file", nargs="?", help="JSON-LD file (.json/.jsonld) "
                       "or HTML file; omit to read stdin")
    p_val.add_argument("--url", help="fetch a page and validate its "
                       "embedded JSON-LD")
    p_val.add_argument("--json", action="store_true",
                       help="machine-readable report")

    p_tpl = sub.add_parser("template", help="print a fill-in spec")
    p_tpl.add_argument("--type", required=True, choices=sorted(TYPES))

    sub.add_parser("types", help="list supported types and their fields")

    args = parser.parse_args(argv)

    if args.command == "types":
        for name in sorted(TYPES):
            info = TYPES[name]
            print("%s — %s" % (name, info["help"]))
            print("  required:    %s" % ", ".join(info["required"]))
            print("  recommended: %s" % ", ".join(info["recommended"]))
        return 0

    if args.command == "template":
        print(json.dumps(template_spec(args.type), indent=2,
                         ensure_ascii=False))
        return 0

    if args.command == "generate":
        with open(args.spec, encoding="utf-8") as fh:
            spec = json.load(fh)
        doc = build(args.type, spec)
        errors, warnings = validate(doc)
        text = json.dumps(doc, indent=None if args.compact else 2,
                          ensure_ascii=False)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as fh:
                fh.write(text + "\n")
        else:
            print(text)
        for w in warnings:
            print("warning: %s" % w, file=sys.stderr)
        for e in errors:
            print("ERROR: %s" % e, file=sys.stderr)
        if errors:
            print("generated JSON-LD has %d error(s) — fix the spec "
                  "and re-run" % len(errors), file=sys.stderr)
            return 1
        return 0

    if args.command == "validate":
        if args.url:
            docs = extract_jsonld(fetch_url(args.url))
            return _report(docs, args.json, args.url)
        if args.file:
            with open(args.file, encoding="utf-8") as fh:
                raw = fh.read()
        else:
            raw = sys.stdin.read()
        try:
            parsed = json.loads(raw)
            docs = parsed if isinstance(parsed, list) else [parsed]
        except json.JSONDecodeError:
            docs = extract_jsonld(raw)  # maybe an HTML file
        return _report(docs, args.json, args.file or "stdin")

    return 2


if __name__ == "__main__":
    sys.exit(main())
