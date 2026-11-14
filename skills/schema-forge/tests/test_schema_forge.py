#!/usr/bin/env python3
"""Tests for schema_forge.py — run from the skill directory:

    python3 -m unittest discover -s tests -v
"""
import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
SCRIPT = os.path.join(SKILL, "scripts", "schema_forge.py")
EXAMPLES = os.path.join(SKILL, "scripts", "examples")

sys.path.insert(0, os.path.join(SKILL, "scripts"))
import schema_forge  # noqa: E402

SAMPLE_HTML = """<!doctype html><html><head>
<script type="application/ld+json">
{"@context": "https://schema.org", "@type": "FAQPage",
 "mainEntity": [{"@type": "Question", "name": "Q?",
   "acceptedAnswer": {"@type": "Answer", "text": "A."}}]}
</script>
<script>var x = 1;</script>
<script type="application/ld+json">{not json</script>
<script type="application/ld+json">
[{"@context": "https://schema.org", "@type": "Product", "name": "Widget"}]
</script>
</head><body></body></html>"""


def example_spec(name):
    with open(os.path.join(EXAMPLES, name), encoding="utf-8") as fh:
        return json.load(fh)


class BuildTest(unittest.TestCase):
    def test_localbusiness_build(self):
        doc = schema_forge.build("LocalBusiness",
                                 example_spec("localbusiness.json"))
        self.assertEqual(doc["@context"], "https://schema.org")
        self.assertEqual(doc["@type"], "LocalBusiness")
        self.assertEqual(doc["name"], "Riverside Books")
        self.assertEqual(doc["address"]["@type"], "PostalAddress")
        self.assertEqual(doc["address"]["postalCode"], "62701")

    def test_article_build_author_person(self):
        doc = schema_forge.build("Article", example_spec("article.json"))
        self.assertEqual(doc["author"]["@type"], "Person")
        self.assertEqual(doc["publisher"]["@type"], "Organization")
        self.assertEqual(doc["headline"],
                         "The beginner's guide to composting at home")

    def test_faq_build_questions(self):
        doc = schema_forge.build("FAQPage", example_spec("faq.json"))
        self.assertEqual(len(doc["mainEntity"]), 3)
        self.assertEqual(doc["mainEntity"][0]["@type"], "Question")
        self.assertEqual(doc["mainEntity"][0]["acceptedAnswer"]["@type"],
                         "Answer")

    def test_product_build_offer_rating(self):
        doc = schema_forge.build("Product", example_spec("product.json"))
        self.assertEqual(doc["offers"]["@type"], "Offer")
        self.assertEqual(doc["aggregateRating"]["@type"], "AggregateRating")
        self.assertEqual(doc["offers"]["price"], "49.00")

    def test_unknown_type_raises(self):
        with self.assertRaises(ValueError):
            schema_forge.build("Recipe", {"name": "Soup"})

    def test_empty_values_dropped(self):
        doc = schema_forge.build("LocalBusiness",
                                 {"name": "X", "telephone": "",
                                  "priceRange": None})
        self.assertNotIn("telephone", doc)
        self.assertNotIn("priceRange", doc)

    def test_template_specs_build_clean(self):
        for schema_type in ("LocalBusiness", "Article", "FAQPage",
                            "Product"):
            spec = schema_forge.template_spec(schema_type)
            doc = schema_forge.build(schema_type, spec)
            errors, _ = schema_forge.validate(doc)
            self.assertEqual(errors, [], schema_type)


class ValidateTest(unittest.TestCase):
    def test_all_examples_validate_clean(self):
        for name, schema_type in (
                ("localbusiness.json", "LocalBusiness"),
                ("article.json", "Article"),
                ("faq.json", "FAQPage"),
                ("product.json", "Product")):
            doc = schema_forge.build(schema_type, example_spec(name))
            errors, warnings = schema_forge.validate(doc)
            self.assertEqual(errors, [], name)
            self.assertEqual(warnings, [], name)

    def test_missing_required_localbusiness(self):
        errors, _ = schema_forge.validate({"@context": "https://schema.org",
                                           "@type": "LocalBusiness"})
        self.assertIn("missing required field: name", errors)

    def test_missing_recommended_is_warning_not_error(self):
        doc = {"@context": "https://schema.org",
               "@type": "LocalBusiness", "name": "X"}
        errors, warnings = schema_forge.validate(doc)
        self.assertEqual(errors, [])
        self.assertTrue(any("telephone" in w for w in warnings))

    def test_missing_context_is_error(self):
        errors, _ = schema_forge.validate({"@type": "Article",
                                           "headline": "H",
                                           "author": "A",
                                           "datePublished": "2026-01-01"})
        self.assertTrue(any("@context" in e for e in errors))

    def test_faq_question_without_answer(self):
        doc = {"@context": "https://schema.org", "@type": "FAQPage",
               "mainEntity": [{"@type": "Question", "name": "Q?"}]}
        errors, _ = schema_forge.validate(doc)
        self.assertTrue(any("acceptedAnswer" in e for e in errors))

    def test_faq_empty_main_entity(self):
        doc = {"@context": "https://schema.org", "@type": "FAQPage",
               "mainEntity": []}
        errors, _ = schema_forge.validate(doc)
        self.assertTrue(any("at least one" in e for e in errors))

    def test_product_needs_offer_rating_or_review(self):
        doc = {"@context": "https://schema.org", "@type": "Product",
               "name": "Widget"}
        errors, _ = schema_forge.validate(doc)
        self.assertTrue(any("offers" in e and "aggregateRating" in e
                            for e in errors))

    def test_product_offer_only_is_enough(self):
        doc = {"@context": "https://schema.org", "@type": "Product",
               "name": "Widget",
               "offers": {"price": "9.99", "priceCurrency": "USD"}}
        errors, _ = schema_forge.validate(doc)
        self.assertEqual(errors, [])

    def test_bad_date_and_url(self):
        doc = {"@context": "https://schema.org", "@type": "Article",
               "headline": "H", "author": "A",
               "datePublished": "14 Nov 2026",
               "image": "example.com/img.jpg"}
        errors, _ = schema_forge.validate(doc)
        self.assertTrue(any("datePublished" in e for e in errors))
        self.assertTrue(any("image" in e for e in errors))

    def test_bad_price_and_rating(self):
        doc = {"@context": "https://schema.org", "@type": "Product",
               "name": "W",
               "offers": {"price": "free", "priceCurrency": "USD"},
               "aggregateRating": {"ratingValue": "7.2",
                                   "reviewCount": "3"}}
        errors, _ = schema_forge.validate(doc)
        self.assertTrue(any("price" in e for e in errors))
        self.assertTrue(any("ratingValue" in e for e in errors))

    def test_unknown_type_warns(self):
        _, warnings = schema_forge.validate(
            {"@context": "https://schema.org", "@type": "Recipe"})
        self.assertTrue(any("unknown @type" in w for w in warnings))


class ExtractTest(unittest.TestCase):
    def test_extract_two_docs_skips_broken_block(self):
        docs = schema_forge.extract_jsonld(SAMPLE_HTML)
        self.assertEqual(len(docs), 2)
        self.assertEqual(docs[0]["@type"], "FAQPage")
        self.assertEqual(docs[1]["@type"], "Product")

    def test_extract_none(self):
        self.assertEqual(schema_forge.extract_jsonld("<html></html>"), [])


class CliTest(unittest.TestCase):
    def run_cli(self, *args, input_text=None):
        return subprocess.run([sys.executable, SCRIPT, *args],
                              input=input_text, capture_output=True,
                              text=True, cwd=SKILL)

    def test_cli_generate_and_validate_roundtrip(self):
        for name, schema_type in (
                ("localbusiness.json", "LocalBusiness"),
                ("article.json", "Article"),
                ("faq.json", "FAQPage"),
                ("product.json", "Product")):
            gen = self.run_cli("generate", "--type", schema_type,
                               "--spec", os.path.join(EXAMPLES, name))
            self.assertEqual(gen.returncode, 0, gen.stderr)
            val = self.run_cli("validate", input_text=gen.stdout)
            self.assertEqual(val.returncode, 0, val.stdout)
            self.assertIn("valid", val.stdout)

    def test_cli_validate_html_file(self):
        path = os.path.join(HERE, "fixture.html")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(SAMPLE_HTML)
        try:
            result = self.run_cli("validate", path)
            self.assertEqual(result.returncode, 1)  # Product lacks offer
            self.assertIn("FAQPage: valid", result.stdout)
            self.assertIn("Product: INVALID", result.stdout)
        finally:
            os.remove(path)

    def test_cli_types_lists_four(self):
        result = self.run_cli("types")
        self.assertEqual(result.returncode, 0)
        for t in ("LocalBusiness", "Article", "FAQPage", "Product"):
            self.assertIn(t, result.stdout)

    def test_cli_template_is_valid_spec(self):
        result = self.run_cli("template", "--type", "FAQPage")
        self.assertEqual(result.returncode, 0)
        spec = json.loads(result.stdout)
        doc = schema_forge.build("FAQPage", spec)
        errors, _ = schema_forge.validate(doc)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
