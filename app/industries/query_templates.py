from app.industries.definitions import INDUSTRIES

# Queries targeting small/mid-market private B2B companies, not Fortune 500
SEARCH_TEMPLATES = [
    '"{keyword}" manufacturer {location} -wikipedia -fortune -NYSE -NASDAQ',
    '"{keyword}" supplier company {location} small business',
    '"{keyword}" distributor LLC {location}',
    '"{keyword}" manufacturer Inc {location}',
    '"{keyword}" custom manufacturer company {location}',
    '"{keyword}" fabrication company {location}',
    '"{keyword}" precision manufacturer {location}',
    '"{keyword}" OEM supplier {location}',
]

DIRECTORY_QUERIES = {
    "thomasnet": [
        'site:thomasnet.com/profile "{keyword}"',
    ],
    "industrynet": [
        'site:industrynet.com "{keyword}"',
    ],
}


def generate_queries(industry_name: str, location: str = "") -> list[str]:
    """Generate search queries for an industry, targeting mid-market private companies."""
    industry = INDUSTRIES.get(industry_name)
    if not industry:
        return []

    loc = location.strip() if location else "USA"

    queries = []

    # Google queries — use more keywords but fewer templates per keyword for breadth
    for keyword in industry.keywords[:7]:
        for template in SEARCH_TEMPLATES[:5]:
            queries.append(template.format(keyword=keyword, location=loc))

    # Sub-industry specific queries
    for sub in industry.sub_industries[:4]:
        queries.append(f'"{sub}" manufacturer {loc} company')
        queries.append(f'"{sub}" supplier LLC {loc}')

    # Directory queries
    for templates in DIRECTORY_QUERIES.values():
        for keyword in industry.keywords[:3]:
            for template in templates:
                q = template.format(keyword=keyword)
                if location:
                    q += f" {location}"
                queries.append(q)

    return queries
