import json

from bs4 import BeautifulSoup


def extract_organization_data(soup: BeautifulSoup) -> dict | None:
    """Extract organization data from JSON-LD or microdata."""
    # Try JSON-LD
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string or "")
            org = _find_org_in_jsonld(data)
            if org:
                return org
        except (json.JSONDecodeError, TypeError):
            continue

    # Try microdata (itemscope/itemprop)
    org_el = soup.find(attrs={"itemtype": lambda v: v and "Organization" in str(v)})
    if org_el:
        return _extract_microdata_org(org_el)

    return None


def _find_org_in_jsonld(data) -> dict | None:
    if isinstance(data, list):
        for item in data:
            result = _find_org_in_jsonld(item)
            if result:
                return result
        return None

    if isinstance(data, dict):
        schema_type = data.get("@type", "")
        if isinstance(schema_type, list):
            schema_type = " ".join(schema_type)
        if any(t in str(schema_type) for t in ["Organization", "Corporation", "LocalBusiness"]):
            return {
                "name": data.get("name", ""),
                "description": data.get("description", ""),
                "telephone": data.get("telephone", ""),
                "email": data.get("email", ""),
                "url": data.get("url", ""),
                "address": data.get("address", {}),
                "numberOfEmployees": data.get("numberOfEmployees", {}),
            }
        # Check @graph
        graph = data.get("@graph")
        if graph:
            return _find_org_in_jsonld(graph)

    return None


def _extract_microdata_org(element) -> dict:
    org = {}
    for prop in element.find_all(attrs={"itemprop": True}):
        name = prop.get("itemprop")
        if name == "name":
            org["name"] = prop.get("content", prop.get_text(strip=True))
        elif name == "description":
            org["description"] = prop.get("content", prop.get_text(strip=True))
        elif name == "telephone":
            org["telephone"] = prop.get("content", prop.get_text(strip=True))
        elif name == "email":
            org["email"] = prop.get("content", prop.get_text(strip=True))
        elif name == "addressLocality":
            org.setdefault("address", {})["addressLocality"] = prop.get("content", prop.get_text(strip=True))
        elif name == "addressRegion":
            org.setdefault("address", {})["addressRegion"] = prop.get("content", prop.get_text(strip=True))
        elif name == "postalCode":
            org.setdefault("address", {})["postalCode"] = prop.get("content", prop.get_text(strip=True))
    return org
