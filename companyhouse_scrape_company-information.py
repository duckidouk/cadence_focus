import json
import os

import requests

cadence_equity = "10238359"
scci = "05150526"
jlas = "08686757"

API_BASE_URL = "https://api.company-information.service.gov.uk"
COMPANY_NUMBER = scci
MAX_ITEMS = 10


class CompaniesHouseClient:
    def __init__(self, api_key):
        self.session = requests.Session()
        self.session.auth = (api_key, "")

    def get(self, path, params=None, optional=False):
        response = self.session.get(
            f"{API_BASE_URL}{path}",
            params=params,
            timeout=15,
        )

        if optional and response.status_code == 404:
            return {}

        try:
            response.raise_for_status()
        except requests.HTTPError as error:
            raise RuntimeError(
                f"Companies House returned {response.status_code} for {response.url}: "
                f"{response.text}"
            ) from error

        return response.json()

    def company_profile(self, company_number):
        return self.get(f"/company/{company_number}")

    def search(self, query):
        return self.get("/search/companies", params={"q": query})

    def officers(self, company_number):
        return self.get(f"/company/{company_number}/officers")

    def psc_ownership(self, company_number):
        return self.get(
            f"/company/{company_number}/persons-with-significant-control"
        )

    def filing_history(self, company_number):
       return self.get(f"/company/{company_number}/filing-history")

    def charges(self, company_number):
       return self.get(f"/company/{company_number}/charges", optional=True)

    def insolvency(self, company_number):
        return self.get(f"/company/{company_number}/insolvency", optional=True)

    def officer_networks(self, officers, company_number):
        networks = []

        for officer in officers.get("items", []):
            appointments_path = officer.get("links", {}).get("officer", {}).get(
                "appointments"
            )
            if not appointments_path:
                continue

            appointments = self.get(appointments_path).get("items", [])
            related_companies = []

            for appointment in appointments:
                company = appointment.get("appointed_to", {})
                if company.get("company_number") == company_number:
                    continue

                related_companies.append(
                    {
                        "name": company.get("company_name", "Unknown company"),
                        "number": company.get("company_number", "Unknown"),
                        "role": appointment.get("officer_role", "Unknown role"),
                        "appointed": appointment.get("appointed_on", "Unknown"),
                        "resigned": appointment.get("resigned_on"),
                    }
                )

            if related_companies:
                networks.append(
                    {
                        "officer_name": officer.get("name", "Unknown officer"),
                        "companies": related_companies,
                    }
                )

        return networks


def format_address(address):
    fields = [
        "premises",
        "address_line_1",
        "address_line_2",
        "locality",
        "region",
        "postal_code",
        "country",
    ]
    return ", ".join(str(address[field]) for field in fields if address.get(field))


def heading(number, title):
    print(f"\n{number}. {title}")
    print("-" * (len(title) + 3))


def print_results(
    profile,
    search_results,
    officers,
    psc_ownership,
    filing_history,
    charges,
    insolvency,
    officer_networks,
):
    heading(1, "COMPANY PROFILE")
    print(f"Name: {profile.get('company_name', 'Unknown')}")
    print(f"Number: {profile.get('company_number', 'Unknown')}")
    print(f"Status: {profile.get('company_status', 'Unknown')}")
    print(f"Created: {profile.get('date_of_creation', 'Unknown')}")
    print(f"Address: {format_address(profile.get('registered_office_address', {}))}")

    heading(2, "OTHER SEARCH MATCHES")
    matches = [
        item
        for item in search_results.get("items", [])
        if item.get("company_number") != profile.get("company_number")
    ]
    if not matches:
        print("No other matches.")
    for item in matches[:MAX_ITEMS]:
        print(
            f"- {item.get('title', 'Unknown')} "
            f"({item.get('company_number', 'Unknown')}) — "
            f"{item.get('company_status', 'Unknown')}"
        )

    heading(3, "OFFICERS")
    officer_items = officers.get("items", [])
    print(f"Total: {officers.get('total_results', len(officer_items))}")
    for officer in officer_items[:MAX_ITEMS]:
        end_date = f", resigned {officer['resigned_on']}" if officer.get("resigned_on") else ""
        print(
            f"- {officer.get('name', 'Unknown')} — "
            f"{officer.get('officer_role', 'Unknown role')}, "
            f"appointed {officer.get('appointed_on', 'Unknown')}{end_date}"
        )

    heading(4, "PSC OWNERSHIP")
    psc_items = psc_ownership.get("items", [])
    print(f"Total: {psc_ownership.get('total_results', len(psc_items))}")
    for psc in psc_items[:MAX_ITEMS]:
        controls = ", ".join(psc.get("natures_of_control", [])) or "Not provided"
        print(f"- {psc.get('name', 'Unknown')}")
        print(f"  Control: {controls}")

    heading(5, "LATEST FILING HISTORY")
    filing_items = filing_history.get("items", [])
    print(f"Showing up to {MAX_ITEMS} of {filing_history.get('total_count', len(filing_items))}")
    for filing in filing_items[:MAX_ITEMS]:
        print(
            f"- {filing.get('date', 'Unknown')} — "
            f"{filing.get('description', 'No description')} "
            f"[{filing.get('category', 'uncategorised')}]"
        )

    heading(6, "CHARGES")
    charge_items = charges.get("items", [])
    print(f"Total: {charges.get('total_count', len(charge_items))}")
    for charge in charge_items[:MAX_ITEMS]:
        classifications = ", ".join(
            item.get("description", "") for item in charge.get("classification", [])
        )
        print(
            f"- {charge.get('created_on', 'Unknown date')} — "
            f"{charge.get('status', 'Unknown status')}"
        )
        if classifications:
            print(f"  {classifications}")

    heading(7, "INSOLVENCY")
    cases = insolvency.get("cases", [])
    print(f"Total cases: {len(cases)}")
    for case in cases[:MAX_ITEMS]:
        print(
            f"- Case {case.get('number', 'Unknown')} — "
            f"{case.get('type', 'Unknown type')}"
        )

    heading(8, "FILED-ACCOUNT DOCUMENTS")
    account_filings = [
        filing for filing in filing_items if filing.get("category") == "accounts"
    ]
    if not account_filings:
        print("No account documents in the latest filing-history page.")
    for filing in account_filings[:MAX_ITEMS]:
        metadata_url = filing.get("links", {}).get("document_metadata")
        document_id = metadata_url.rstrip("/").split("/")[-1] if metadata_url else None
        print(f"- {filing.get('date', 'Unknown')} — {filing.get('description', 'Accounts')}")
        if document_id:
            print(
                "  Download: "
                "https://document-api.company-information.service.gov.uk"
                f"/document/{document_id}/content"
            )

    heading(9, "OFFICER NETWORKS")
    if not officer_networks:
        print("No appointments at other companies found.")
    for network in officer_networks:
        print(f"{network['officer_name']}:")
        for company in network["companies"][:MAX_ITEMS]:
            status = f", resigned {company['resigned']}" if company["resigned"] else ""
            print(
                f"- {company['name']} ({company['number']}) — "
                f"{company['role']}{status}"
            )


def main():
    api_key = os.getenv("COMPANIES_HOUSE_API_KEY")
    if not api_key:
        raise RuntimeError("COMPANIES_HOUSE_API_KEY is not set")

    client = CompaniesHouseClient(api_key.strip())


    profile = client.company_profile(COMPANY_NUMBER)
    search_results = client.search(profile["company_name"])
    officers = client.officers(COMPANY_NUMBER)
    psc_ownership = client.psc_ownership(COMPANY_NUMBER)
    filing_history = client.filing_history(COMPANY_NUMBER)
    charges = client.charges(COMPANY_NUMBER)
    insolvency = client.insolvency(COMPANY_NUMBER)
    officer_networks = client.officer_networks(officers, COMPANY_NUMBER)

    results = {
        "company_profile": profile,
        "search_results": search_results,
        "officers": officers,
        "psc_ownership": psc_ownership,
        "filing_history": filing_history,
        "charges": charges,
        "insolvency": insolvency,
        "officer_networks": officer_networks,
    }

    company_name = profile['company_name'].lower().replace(" ","-")

    output_file = f"company_data_{company_name}.json"
    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(results, file, indent=2, ensure_ascii=False)

    print(f"Saved Companies House data to {output_file}")


if __name__ == "__main__":
    main()
