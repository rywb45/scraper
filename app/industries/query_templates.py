from app.industries.definitions import INDUSTRIES

# Broad templates that work for any industry name — no keyword mapping required
SEARCH_TEMPLATES = [
    '"{industry}" company {location} -wikipedia -fortune -NYSE -NASDAQ',
    '"{industry}" supplier {location} small business',
    '"{industry}" manufacturer {location} LLC OR Inc',
    '"{industry}" distributor company {location}',
    '"{industry}" services company {location}',
]

# Extra templates for known industries — uses curated keywords for depth
KEYWORD_TEMPLATES = [
    '"{keyword}" manufacturer company {location}',
    '"{keyword}" supplier {location} -wikipedia',
    '"{keyword}" company {location} LLC OR Inc',
]

DIRECTORY_QUERIES = {
    "thomasnet": 'site:thomasnet.com/profile "{keyword}"',
    "industrynet": 'site:industrynet.com "{keyword}"',
}


def generate_queries(industry_name: str, location: str = "") -> list[str]:
    """Generate search queries for an industry.

    Works for ANY industry name (including custom ones the user types in).
    If we have curated keywords for the industry, we also generate
    keyword-specific queries for better coverage.
    """
    loc = location.strip() if location else "USA"
    queries = []

    # Always generate queries from the industry name directly — works for anything
    for template in SEARCH_TEMPLATES:
        queries.append(template.format(industry=industry_name, location=loc))

    # If we have curated data for this industry, add keyword-specific queries
    industry = INDUSTRIES.get(industry_name)
    if industry:
        for keyword in industry.keywords[:6]:
            for template in KEYWORD_TEMPLATES:
                queries.append(template.format(keyword=keyword, location=loc))

        # Sub-industry queries
        for sub in industry.sub_industries[:4]:
            queries.append(f'"{sub}" company {loc} -wikipedia')

        # Directory queries using keywords
        for keyword in industry.keywords[:3]:
            for tpl in DIRECTORY_QUERIES.values():
                q = tpl.format(keyword=keyword)
                if location:
                    q += f" {location}"
                queries.append(q)
    else:
        # Custom/unknown industry — use the name itself for directory searches
        for tpl in DIRECTORY_QUERIES.values():
            q = tpl.format(keyword=industry_name)
            if location:
                q += f" {location}"
            queries.append(q)

    return queries
