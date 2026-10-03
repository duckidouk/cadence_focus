"""Offline regression tests: .venv/bin/python -m unittest test_cf_financial_facts.py"""
import sqlite3
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import Mock, patch

import cf_financial_facts as cf


def document(value="1,321", attributes='format="ixt:numcommadot" scale="3" sign="-"', number="10238359"):
    return f'''<html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"
        xmlns:x="http://www.xbrl.org/2003/instance" xmlns:core="urn:core">
        <x:context id="current"><x:entity><x:identifier scheme="http://www.companieshouse.gov.uk/">{number}</x:identifier></x:entity>
        <x:period><x:instant>2025-06-30</x:instant></x:period></x:context>
        <x:unit id="GBP"><x:measure>iso4217:GBP</x:measure></x:unit>
        <ix:nonFraction name="core:CurrentAssets" contextRef="current" unitRef="GBP" {attributes}>{value}</ix:nonFraction>
        </html>'''.encode()


def parse(content):
    return cf.parse_facts(content, "10238359", "doc1", "https://example.test/accounts", {"date": "2025-10-30"})


class FinancialFactsTests(unittest.TestCase):
    def test_sign_scale_and_dates(self):
        fact = parse(document())[0]
        self.assertEqual(fact["value_exact"], "-1321000")
        self.assertEqual(fact["instant"], "2025-06-30")
        self.assertEqual(fact["unit_measure"], "iso4217:GBP")

    def test_company_mismatch_stops_import(self):
        with self.assertRaisesRegex(ValueError, "does not match"):
            parse(document(number="05150526"))

    def test_decimal_comma(self):
        fact = parse(document("1.234,50", 'format="ixt:num-comma-decimal"'))[0]
        self.assertEqual(fact["value_exact"], "1234.50")

    def test_nil_and_unknown_format_remain_missing(self):
        fact = parse(document("123", 'format="ixt:unknown"'))[0]
        self.assertIsNone(fact["value_numeric"])
        self.assertEqual(fact["parse_status"], "unsupported_format:unknown")
        tag = ET.fromstring('<n xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:nil="true"/>')
        self.assertEqual(cf.numeric_value(tag, ""), (None, "nil"))

    def test_dash_zero_requires_explicit_transformation(self):
        self.assertEqual(parse(document("-", 'format="ixt:zerodash"'))[0]["value_exact"], "0")
        self.assertIsNone(parse(document("-", ""))[0]["value_exact"])

    def test_conflicting_duplicate_is_not_silently_overwritten(self):
        content = document().replace(b"</html>", b'<ix:nonFraction name="core:CurrentAssets" contextRef="current" unitRef="GBP">9</ix:nonFraction></html>')
        with self.assertRaisesRegex(ValueError, "Conflicting duplicate"):
            parse(content)

    def test_empty_document(self):
        with self.assertRaisesRegex(ValueError, "No supported numeric"):
            parse(b"<html/>")

    def test_repeat_import_and_existing_schema_migration(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp) / "cf.db"
            with sqlite3.connect(db) as conn:
                conn.execute('CREATE TABLE company (company_number TEXT)')
                conn.execute("INSERT INTO company VALUES ('05150526')")
                conn.execute('''CREATE TABLE financial_facts (
                    fact_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_number TEXT NOT NULL, document_id TEXT NOT NULL,
                    concept TEXT NOT NULL, concept_local_name TEXT NOT NULL,
                    value_raw TEXT, value_numeric NUMERIC, unit TEXT,
                    context_ref TEXT NOT NULL, source_url TEXT,
                    UNIQUE(company_number, document_id, concept, context_ref))''')
            facts = parse(document())
            backup = cf.save_facts(facts, db)
            self.assertTrue(backup.exists())
            cf.save_facts(facts, db)
            with sqlite3.connect(db) as conn:
                self.assertEqual(conn.execute('SELECT count(*) FROM financial_facts').fetchone()[0], 1)
                self.assertEqual(conn.execute('SELECT company_number FROM company').fetchone()[0], '05150526')
                self.assertEqual(conn.execute('SELECT value_exact FROM financial_facts').fetchone()[0], '-1321000')
            with sqlite3.connect(backup) as conn:
                self.assertEqual(conn.execute('SELECT count(*) FROM financial_facts').fetchone()[0], 0)

    def test_save_facts_inserts_and_updates_company_profile(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp) / "cf.db"
            facts = parse(document())
            profile = {
                "company_number": "10238359",
                "company_name": "CADENCE EQUITY PARTNERS LIMITED",
            }

            cf.save_facts(facts, db, profile)
            profile["company_name"] = "UPDATED COMPANY NAME"
            cf.save_facts(facts, db, profile)

            with sqlite3.connect(db) as conn:
                rows = conn.execute(
                    "SELECT company_number, company_name FROM company"
                ).fetchall()

            self.assertEqual(rows, [("10238359", "UPDATED COMPANY NAME")])

    def test_filing_pagination_skips_aa01(self):
        pages = [Mock(), Mock()]
        pages[0].json.return_value = {"items": [{"type": "AA01"}], "total_count": 2}
        expected = {"type": "AA", "links": {"document_metadata": "/document/a"}}
        pages[1].json.return_value = {"items": [expected], "total_count": 2}
        with patch.object(cf, "get_response", side_effect=pages) as get:
            self.assertEqual(cf.find_accounts(None, "10238359"), expected)
            self.assertEqual(get.call_args.kwargs["params"]["start_index"], 1)

    def test_pdf_only_does_not_request_an_unsupported_format(self):
        response = Mock()
        response.json.return_value = {"company_number": "10238359", "resources": {"application/pdf": {}}}
        with patch.object(cf, "get_response", return_value=response) as get:
            with self.assertRaisesRegex(ValueError, "PDF-only"):
                cf.download_accounts(None, "10238359", {"links": {"document_metadata": "/document/a"}})
            self.assertEqual(get.call_count, 1)


if __name__ == "__main__":
    unittest.main()
