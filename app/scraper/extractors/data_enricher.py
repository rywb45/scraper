"""Enrich company data using Google search snippets and knowledge graph."""

import re

import httpx

from app.config import settings

REVENUE_PATTERNS = [
    re.compile(r"\$\s*([\d,.]+)\s*(billion|million|B|M)\b", re.IGNORECASE),
    re.compile(r"revenue[:\s]+\$?\s*([\d,.]+)\s*(billion|million|B|M)", re.IGNORECASE),
    re.compile(r"annual\s+(?:revenue|sales)[:\s]+\$?\s*([\d,.]+)\s*(billion|million|B|M)", re.IGNORECASE),
]

EMPLOYEE_PATTERNS = [
    re.compile(r"([\d,]+)\s*(?:\+\s*)?employees", re.IGNORECASE),
    re.compile(r"(?:employs?|workforce|staff|headcount|team)[:\s]+([\d,]+)", re.IGNORECASE),
    re.compile(r"([\d,]+)\s*(?:people|workers|staff)", re.IGNORECASE),
]

US_STATES = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
    "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
    "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
    "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
    "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
    "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT",
    "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
    "Wisconsin": "WI", "Wyoming": "WY",
}

STATE_ABBREVS = set(US_STATES.values())

# City, State pattern
LOCATION_PATTERN = re.compile(
    r"(?:headquartered|based|located|headquarters)[:\s]+(?:in\s+)?([A-Z][a-z]+(?:\s[A-Z][a-z]+)*),\s*([A-Z]{2}|[A-Z][a-z]+(?:\s[A-Z][a-z]+)*)",
    re.IGNORECASE,
)
CITY_STATE_PATTERN = re.compile(
    r"([A-Z][a-z]+(?:\s[A-Z][a-z]+)*),\s*([A-Z]{2})\b"
)


async def enrich_company(company_name: str, domain: str) -> dict:
    """Search Google for company info and return enrichment data."""
    result = {
        "estimated_revenue": "",
        "revenue_source": "",
        "employee_count": None,
        "employee_count_range": "",
        "city": "",
        "state": "",
    }

    if not settings.serp_api_key:
        return result

    # Do two targeted searches
    queries = [
        f'"{company_name}" revenue employees headquarters',
        f'"{domain}" company revenue annual sales employees',
    ]

    all_text = ""
    kg_data = {}

    for query in queries:
        try:
            data = await _serper_search(query)
            if not data:
                continue

            # Knowledge graph is the best source
            kg = data.get("knowledgeGraph", {})
            if kg:
                kg_data = {**kg_data, **kg}

            # Collect all text from snippets + answer boxes
            if data.get("answerBox"):
                ab = data["answerBox"]
                all_text += " " + (ab.get("answer", "") or ab.get("snippet", ""))

            for r in data.get("organic", []):
                all_text += " " + (r.get("snippet", "") or "")
                all_text += " " + (r.get("title", "") or "")

            # People also ask
            for paa in data.get("peopleAlsoAsk", []):
                all_text += " " + (paa.get("snippet", "") or "")

        except Exception:
            continue

    # Extract from knowledge graph first
    if kg_data:
        _extract_from_kg(kg_data, result)

    # Fill gaps from snippets
    if not result["estimated_revenue"]:
        rev, src = _extract_revenue_from_text(all_text)
        if rev:
            result["estimated_revenue"] = rev
            result["revenue_source"] = src

    if not result["employee_count"]:
        count, rng = _extract_employees_from_text(all_text)
        if count:
            result["employee_count"] = count
            result["employee_count_range"] = rng

    if not result["state"]:
        city, state = _extract_location_from_text(all_text)
        if state:
            result["city"] = city
            result["state"] = state

    # If we have employees but not revenue, estimate
    if not result["estimated_revenue"] and result["employee_count"]:
        count = result["employee_count"]
        est = count * 300  # $300K per employee rough average
        if est >= 1_000_000:
            result["estimated_revenue"] = f"~${est / 1_000_000:,.1f}B"
        elif est >= 1_000:
            result["estimated_revenue"] = f"~${est / 1_000:,.0f}M"
        else:
            result["estimated_revenue"] = f"~${est:,.0f}K"
        result["revenue_source"] = "estimated"

    return result


def _extract_from_kg(kg: dict, result: dict):
    """Extract structured data from Google Knowledge Graph."""
    # Revenue from KG attributes
    for key in ["revenue", "annual_revenue", "annualRevenue"]:
        val = kg.get(key, "")
        if val:
            rev = _parse_revenue_string(str(val))
            if rev:
                result["estimated_revenue"] = rev
                result["revenue_source"] = "knowledge_graph"
                break

    # Check description and attributes
    desc = kg.get("description", "")
    attrs = kg.get("attributes", {})

    for key, val in attrs.items():
        key_lower = key.lower()
        val_str = str(val)

        if "revenue" in key_lower or "sales" in key_lower:
            rev = _parse_revenue_string(val_str)
            if rev:
                result["estimated_revenue"] = rev
                result["revenue_source"] = "knowledge_graph"

        if "employee" in key_lower or "staff" in key_lower or "size" in key_lower:
            count = _parse_employee_string(val_str)
            if count:
                result["employee_count"] = count
                result["employee_count_range"] = _count_to_range(count)

        if "headquarter" in key_lower or "location" in key_lower or "address" in key_lower:
            city, state = _parse_location_string(val_str)
            if state:
                result["city"] = city
                result["state"] = state

    # Headquarters from KG
    hq = kg.get("headquarters", "") or kg.get("location", "")
    if hq and not result["state"]:
        city, state = _parse_location_string(str(hq))
        if state:
            result["city"] = city
            result["state"] = state


def _extract_revenue_from_text(text: str) -> tuple[str, str]:
    for pattern in REVENUE_PATTERNS:
        match = pattern.search(text)
        if match:
            amount_str = match.group(1).replace(",", "")
            try:
                amount = float(amount_str)
            except ValueError:
                continue
            suffix = match.group(2).upper()
            if suffix in ("BILLION", "B"):
                return f"${amount:,.1f}B", "search_snippet"
            elif suffix in ("MILLION", "M"):
                return f"${amount:,.0f}M", "search_snippet"
    return "", ""


def _extract_employees_from_text(text: str) -> tuple[int | None, str]:
    for pattern in EMPLOYEE_PATTERNS:
        match = pattern.search(text)
        if match:
            count = int(match.group(1).replace(",", ""))
            if 1 <= count <= 500_000:
                return count, _count_to_range(count)
    return None, ""


def _extract_location_from_text(text: str) -> tuple[str, str]:
    # Try "headquartered in City, State" pattern
    match = LOCATION_PATTERN.search(text)
    if match:
        city = match.group(1).strip()
        state_raw = match.group(2).strip()
        state = _normalize_state(state_raw)
        if state:
            return city, state

    # Try "City, ST" pattern — take the first US match
    for match in CITY_STATE_PATTERN.finditer(text):
        city = match.group(1).strip()
        state = match.group(2).strip()
        if state in STATE_ABBREVS:
            return city, state

    return "", ""


def _parse_revenue_string(s: str) -> str:
    for pattern in REVENUE_PATTERNS:
        match = pattern.search(s)
        if match:
            amount_str = match.group(1).replace(",", "")
            try:
                amount = float(amount_str)
            except ValueError:
                continue
            suffix = match.group(2).upper()
            if suffix in ("BILLION", "B"):
                return f"${amount:,.1f}B"
            elif suffix in ("MILLION", "M"):
                return f"${amount:,.0f}M"
    # Try just a dollar amount
    match = re.search(r"\$\s*([\d,.]+)", s)
    if match:
        val = match.group(1).replace(",", "")
        try:
            amount = float(val)
            if amount >= 1_000_000_000:
                return f"${amount / 1e9:,.1f}B"
            elif amount >= 1_000_000:
                return f"${amount / 1e6:,.0f}M"
        except ValueError:
            pass
    return ""


def _parse_employee_string(s: str) -> int | None:
    for pattern in EMPLOYEE_PATTERNS:
        match = pattern.search(s)
        if match:
            raw = match.group(1).replace(",", "").strip()
            if not raw:
                continue
            try:
                count = int(raw)
            except ValueError:
                continue
            if 1 <= count <= 500_000:
                return count
    # Try raw number
    match = re.search(r"([\d,]+)", s)
    if match:
        raw = match.group(1).replace(",", "").strip()
        if raw:
            try:
                count = int(raw)
            except ValueError:
                return None
            if 1 <= count <= 500_000:
                return count
    return None


def _parse_location_string(s: str) -> tuple[str, str]:
    # "City, State" or "City, ST"
    match = re.search(r"([A-Za-z\s]+),\s*([A-Z]{2}|[A-Za-z\s]+)", s)
    if match:
        city = match.group(1).strip()
        state_raw = match.group(2).strip()
        state = _normalize_state(state_raw)
        if state:
            return city, state
    return "", ""


def _normalize_state(s: str) -> str:
    s = s.strip()
    if s.upper() in STATE_ABBREVS:
        return s.upper()
    for full_name, abbrev in US_STATES.items():
        if s.lower() == full_name.lower():
            return abbrev
    return ""


def _count_to_range(count: int) -> str:
    if count <= 10: return "1-10"
    if count <= 50: return "11-50"
    if count <= 200: return "51-200"
    if count <= 500: return "201-500"
    if count <= 1000: return "501-1,000"
    if count <= 5000: return "1,001-5,000"
    if count <= 10000: return "5,001-10,000"
    return "10,000+"


async def _serper_search(query: str) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://google.serper.dev/search",
                json={"q": query, "gl": "us", "num": 5},
                headers={"X-API-KEY": settings.serp_api_key},
            )
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return None
