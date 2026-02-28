from app.industries.definitions import INDUSTRIES

# Broad templates that work for any industry name — reduced from 5 to 3 (cut weakest performers)
SEARCH_TEMPLATES = [
    '"{industry}" company {location} -wikipedia -fortune -NYSE -NASDAQ',
    '"{industry}" manufacturer {location} LLC OR Inc',
    '"{industry}" supplier {location} small business',
]

# Extra templates for known industries — uses curated keywords for depth
KEYWORD_TEMPLATES = [
    '"{keyword}" manufacturer company {location}',
    '"{keyword}" supplier {location} -wikipedia',
    '"{keyword}" company {location} LLC OR Inc',
]


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
        # Cap keywords at 3 (was 6) — top keywords only
        for keyword in industry.keywords[:3]:
            for template in KEYWORD_TEMPLATES:
                queries.append(template.format(keyword=keyword, location=loc))

        # Cap sub-industry queries at 2 (was 4)
        for sub in industry.sub_industries[:2]:
            queries.append(f'"{sub}" company {loc} -wikipedia')

    return queries
