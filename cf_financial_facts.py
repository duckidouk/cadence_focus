"""Download filed accounts and save figures in data/database/cf.db.

Run from the Cadence_Focus folder:
    .venv/bin/python cf_financial_facts.py --dry-run
    .venv/bin/python cf_financial_facts.py
    .venv/bin/python cf_financial_facts.py --company scci

The code works this way: 1. select company 2. find accounts 3. download 4. parse 5. save.
Uses requests and python-dotenv from the existing requirements.txt.
"""

import argparse
import json
import os
import re
import sqlite3
import sys
import xml.etree.ElementTree as ET
from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


BASE_DIR = Path(__file__).resolve().parent
API_URL = "https://api.company-information.service.gov.uk"
DOCUMENT_URL = "https://document-api.company-information.service.gov.uk"
COMPANIES = {
    "cadence": "10238359",
    "scci": "05150526",
    "jlas": "08686757",
    "3000-years":"14446571",
    "aquam":"09527628",
    "radio-data-networks":"02984975",
    "lee-dickens":"00735448",
    "lucky-number":"09391780",
    "scci-group": "06089974"
}
XBRL = "{http://www.xbrl.org/2003/instance}"
INLINE_NAMESPACES = {
    "http://www.xbrl.org/2008/inlineXBRL",
    "http://www.xbrl.org/2013/inlineXBRL",
}
# Added to the notebook's table without removing any existing columns or rows.
EXTRA_COLUMNS = {
    "period_start": "TEXT", "period_end": "TEXT", "instant": "TEXT",
    "dimensions_json": "TEXT", "unit_measure": "TEXT", "decimals": "TEXT",
    "scale": "INTEGER", "value_exact": "TEXT", "parse_status": "TEXT",
    "filing_date": "TEXT", "accounts_date": "TEXT",
}


def company_number(value):
    """Accept a familiar company nickname or a Companies House number."""
    number = COMPANIES.get(value.lower(), value.upper().strip())
    if number.isdigit():
        number = number.zfill(8)
    if not re.fullmatch(r"[A-Z0-9]{8}", number):
        raise ValueError("Use cadence, scci, jlas, or an eight-character company number.")
    return number


def make_session(project_dir):
    load_dotenv(Path(project_dir) / ".env")
    key = os.getenv("COMPANIES_HOUSE_API_KEY", "").strip()
    if not key:
        raise ValueError("Set COMPANIES_HOUSE_API_KEY in the project-root .env file.")
    session = requests.Session()
    session.auth = (key, "")
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retries))
    return session


def get_response(session, url, **kwargs):
    # Credentials only go to Companies House. requests strips auth on redirects
    # to the external storage host used for document downloads.
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in {
        "api.company-information.service.gov.uk",
        "document-api.company-information.service.gov.uk",
    }:
        raise ValueError("Unexpected Companies House API URL.")
    response = session.get(url, timeout=30, **kwargs)
    response.raise_for_status()
    return response


def find_accounts(session, number, accounts_date=None):
    """Find the newest filed AA document, optionally for a specific year end.

    AA01 is a change of accounting date, not an accounts document. Paginate so
    an older requested year can still be found. Never silently use older data.
    """
    start = 0
    while True:
        page = get_response(
            session, f"{API_URL}/company/{number}/filing-history",
            params={"category": "accounts", "items_per_page": 100, "start_index": start},
        ).json()
        items = page.get("items", [])
        for filing in items:
            made_up = filing.get("description_values", {}).get("made_up_date")
            if (filing.get("type") == "AA"
                    and filing.get("links", {}).get("document_metadata")
                    and (accounts_date is None or accounts_date == made_up)):
                return filing
        start += len(items)
        if not items or start >= page.get("total_count", start):
            raise ValueError(f"No matching accounts filing found for {number}.")


def download_accounts(session, number, filing):
    metadata_url = urljoin(DOCUMENT_URL, filing["links"]["document_metadata"])
    metadata = get_response(session, metadata_url).json()
    if metadata.get("company_number") and company_number(metadata["company_number"]) != number:
        raise ValueError("Document metadata belongs to a different company.")
    resources = metadata.get("resources", {})
    content_type = next((t for t in ("application/xhtml+xml", "application/xml") if t in resources), None)
    if content_type is None:
        raise ValueError(
            "This filing has no supported structured accounts (PDF-only filings need "
            "a separate extraction step). No figures have been saved."
        )
    source_url = urljoin(DOCUMENT_URL, metadata["links"]["document"])
    response = get_response(session, source_url, headers={"Accept": content_type})
    if response.content.lstrip().startswith(b"%PDF"):
        raise ValueError("Companies House returned a PDF instead of structured accounts.")
    document_id = urlparse(metadata_url).path.rstrip("/").split("/")[-1]
    return document_id, source_url, response.content


def local_name(name):
    return name.rsplit("}", 1)[-1].rsplit(":", 1)[-1]


def numeric_value(tag, raw):
    """Return exact decimal text and status; never guess an unknown format."""
    if tag.get("{http://www.w3.org/2001/XMLSchema-instance}nil") in ("true", "1"):
        return None, "nil"
    fmt = local_name(tag.get("format", ""))
    value = re.sub(r"\s+", "", raw)
    if fmt in ("zerodash", "numdash", "fixed-zero"):
        value = "0"
    elif fmt in ("numcommadot", "numdotdecimal", "num-dot-decimal", "numspacedot"):
        value = value.replace(",", "")
    elif fmt in ("numdotcomma", "numcommadecimal", "num-comma-decimal", "numspacecomma"):
        value = value.replace(".", "").replace(",", ".")
    elif fmt:
        return None, f"unsupported_format:{fmt}"
    if not value or value in ("-", "—", "–"):
        return None, "empty"
    try:
        number = Decimal(value)
        if not number.is_finite():
            return None, "invalid_number"
        scale = int(tag.get("scale", "0"))
        if abs(scale) > 100:
            return None, "unsupported_scale"
        with localcontext() as arithmetic:
            arithmetic.prec = max(28, len(number.as_tuple().digits) + abs(scale) + 1)
            number *= Decimal(10) ** scale
            if tag.get("sign") == "-":
                number = -abs(number)
        return format(number, "f"), "ok"
    except (InvalidOperation, ValueError):
        return None, "invalid_number"


def parse_facts(content, number, document_id, source_url, filing):
    """Read numeric facts, their dates, currencies and dimensional breakdowns.

    XML namespaces let core:CurrentAssets and frs-core:CurrentAssets both work.
    Keep current AND comparative periods; do not take the first matching tag.
    """
    root = ET.fromstring(content)
    contexts = {t.get("id"): t for t in root.iter(f"{XBRL}context")}
    units = {t.get("id"): t for t in root.iter(f"{XBRL}unit")}
    facts = {}
    for tag in root.iter():
        namespace = tag.tag[1:].split("}")[0] if tag.tag.startswith("{") else ""
        inline = namespace in INLINE_NAMESPACES and local_name(tag.tag) == "nonFraction"
        plain = namespace not in INLINE_NAMESPACES and tag.get("contextRef") and tag.get("unitRef")
        if not (inline or plain):
            continue
        concept = tag.get("name") if inline else tag.tag
        context_ref, unit_ref = tag.get("contextRef"), tag.get("unitRef")
        if not concept or context_ref not in contexts or unit_ref not in units:
            raise ValueError("A numeric fact has a missing concept, context or unit.")
        context = contexts[context_ref]
        identifier = context.find(f"{XBRL}entity/{XBRL}identifier")
        if identifier is None or company_number(identifier.text or "") != number:
            raise ValueError("Accounts contain a company identifier that does not match the selected company.")
        period = context.find(f"{XBRL}period")
        if period is None:
            raise ValueError("A financial context has no reporting period.")
        dimensions = {
            t.get("dimension"): "".join(t.itertext()).strip()
            for t in context.iter() if local_name(t.tag) in ("explicitMember", "typedMember")
        }
        # Excluded/continued text requires a more complete inline-XBRL processor.
        # Keep the raw text visible, but never turn it into a misleading number.
        raw = "".join(tag.itertext()).strip()
        exact, status = numeric_value(tag, raw)
        if tag.get("continuedAt") or any(local_name(t.tag) == "exclude" for t in tag.iter()):
            exact, status = None, "unsupported_inline_text"
        unit = units[unit_ref]
        measures = [t.text for t in unit.iter(f"{XBRL}measure")]
        unit_measure = measures[0] if len(measures) == 1 else ET.tostring(unit, encoding="unicode")
        fact = {
            "company_number": number, "document_id": document_id,
            "concept": concept, "concept_local_name": local_name(concept),
            "value_raw": raw, "value_numeric": exact, "value_exact": exact,
            "unit": unit_ref, "context_ref": context_ref, "source_url": source_url,
            "period_start": period.findtext(f"{XBRL}startDate"),
            "period_end": period.findtext(f"{XBRL}endDate"),
            "instant": period.findtext(f"{XBRL}instant"),
            "dimensions_json": json.dumps(dimensions, sort_keys=True),
            "unit_measure": unit_measure, "decimals": tag.get("decimals"),
            "scale": int(tag.get("scale", "0")), "parse_status": status,
            "filing_date": filing.get("date"),
            "accounts_date": filing.get("description_values", {}).get("made_up_date"),
        }
        key = (concept, context_ref)
        previous = facts.get(key)
        if previous and any(previous[k] != fact[k] for k in ("value_exact", "unit", "parse_status")):
            raise ValueError(f"Conflicting duplicate fact: {concept}, context {context_ref}.")
        facts[key] = fact
    if not facts:
        raise ValueError("No supported numeric XBRL facts found; nothing saved.")
    return list(facts.values())


def save_facts(facts, db_path, profile=None):
    """Back up an existing DB, then upsert the company profile and its facts.

    value_numeric stays compatible with existing notebook queries. value_exact
    stores decimal text so SQLite floating-point conversion cannot lose precision.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = None
    if db_path.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup_dir = db_path.parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / f"{db_path.name}.{stamp}.bak"
        with closing(sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)) as source:
            with closing(sqlite3.connect(backup_path)) as backup:
                source.backup(backup)
    with closing(sqlite3.connect(db_path, timeout=30)) as conn:
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("""CREATE TABLE IF NOT EXISTS company (
                company_name TEXT,
                company_number TEXT UNIQUE
            )""")
            if profile is not None:
                conn.execute("""INSERT INTO company (company_number, company_name)
                    VALUES (?, ?)
                    ON CONFLICT(company_number)
                    DO UPDATE SET company_name=excluded.company_name""", (
                        company_number(profile["company_number"]),
                        profile["company_name"],
                    ))
            conn.execute("""CREATE TABLE IF NOT EXISTS financial_facts (
                fact_id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_number TEXT NOT NULL, document_id TEXT NOT NULL,
                concept TEXT NOT NULL, concept_local_name TEXT NOT NULL,
                value_raw TEXT, value_numeric NUMERIC, unit TEXT,
                context_ref TEXT NOT NULL, source_url TEXT,
                UNIQUE(company_number, document_id, concept, context_ref)
            )""")
            existing = {row[1] for row in conn.execute("PRAGMA table_info(financial_facts)")}
            for column, sql_type in EXTRA_COLUMNS.items():
                if column not in existing:
                    conn.execute(f"ALTER TABLE financial_facts ADD COLUMN {column} {sql_type}")
            columns = list(facts[0])
            keys = {"company_number", "document_id", "concept", "context_ref"}
            assignments = ", ".join(f"{c}=excluded.{c}" for c in columns if c not in keys)
            sql = f"""INSERT INTO financial_facts ({', '.join(columns)})
                VALUES ({', '.join('?' for _ in columns)})
                ON CONFLICT(company_number, document_id, concept, context_ref)
                DO UPDATE SET {assignments}"""
            conn.executemany(sql, [[fact[c] for c in columns] for fact in facts])
    return backup_path


def print_summary(profile, filing, facts):
    print(f"{profile['company_name']} ({profile['company_number']})")
    print(f"Accounts date: {filing.get('description_values', {}).get('made_up_date', 'unknown')}")
    print(f"Unique numeric facts: {len(facts)}")
    for concept in ("CurrentAssets", "Turnover", "Revenue"):
        matches = [f for f in facts if f["concept_local_name"] == concept]
        if not matches:
            print(f"{concept}: no matching tagged fact in these accounts.")
        for fact in matches:
            date = fact["instant"] or fact["period_end"] or "unknown date"
            print(f"{concept}: {fact['value_exact']} {fact['unit_measure']} | {date} "
                  f"| context {fact['context_ref']} | dimensions {fact['dimensions_json']}")
    unparsed = sum(f["parse_status"] not in ("ok", "nil") for f in facts)
    if unparsed:
        print(f"Review needed: {unparsed} facts retained as raw text without a numeric value.")


def run(company="cadence", project_dir=BASE_DIR, db_path=None, accounts_date=None, dry_run=False):
    """Importable entry point for Cadence; returns the extracted rows as dictionaries."""
    number = company_number(company)
    with make_session(project_dir) as session:
        profile = get_response(session, f"{API_URL}/company/{number}").json()
        filing = find_accounts(session, number, accounts_date)
        document_id, source_url, content = download_accounts(session, number, filing)
    facts = parse_facts(content, number, document_id, source_url, filing)
    print_summary(profile, filing, facts)
    if dry_run:
        print("Dry run complete: database unchanged.")
    else:
        destination = (
            Path(db_path)
            if db_path
            else Path(project_dir) / "data" / "database" / "cf.db"
        )
        backup = save_facts(facts, destination, profile)
        print(f"Saved {len(facts)} facts to {destination}")
        if backup:
            print(f"Previous database backed up to {backup}")
    return facts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--company", default="cadence", help="cadence, scci, jlas, etc.. or company number")
    parser.add_argument("--project-dir", type=Path, default=BASE_DIR)
    parser.add_argument("--db", type=Path, help="Optional destination database")
    parser.add_argument("--accounts-date", help="Optional accounts year-end, YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true", help="Download and parse without writing")
    args = parser.parse_args()
    try:
        run(args.company, args.project_dir, args.db, args.accounts_date, args.dry_run)
    except (requests.RequestException, ValueError, ET.ParseError, sqlite3.Error, OSError, KeyError) as error:
        print(f"Could not import accounts: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
