from app.industries.definitions import INDUSTRIES

# Queries targeting small/mid-market private B2B companies, not Fortune 500
SEARCH_TEMPLATES = [
    '"{keyword}" manufacturer USA -wikipedia -fortune -NYSE -NASDAQ',
    '"{keyword}" supplier company USA small business',
    '"{keyword}" distributor LLC United States',
    '"{keyword}" manufacturer Inc USA',
    '"{keyword}" custom manufacturer company USA',
    '"{keyword}" fabrication company USA',
    '"{keyword}" precision manufacturer USA',
    '"{keyword}" OEM supplier USA',
]

DIRECTORY_QUERIES = {
    "thomasnet": [
        'site:thomasnet.com/profile "{keyword}"',
    ],
    "industrynet": [
        'site:industrynet.com "{keyword}"',
    ],
}


def generate_queries(industry_name: str) -> list[str]:
    """Generate search queries for an industry, targeting mid-market private companies."""
    industry = INDUSTRIES.get(industry_name)
    if not industry:
        return []

    queries = []

    # Google queries — use more keywords but fewer templates per keyword for breadth
    for keyword in industry.keywords[:7]:
        for template in SEARCH_TEMPLATES[:5]:
            queries.append(template.format(keyword=keyword))

    # Sub-industry specific queries
    for sub in industry.sub_industries[:4]:
        queries.append(f'"{sub}" manufacturer USA company')
        queries.append(f'"{sub}" supplier LLC USA')

    # Directory queries
    for templates in DIRECTORY_QUERIES.values():
        for keyword in industry.keywords[:3]:
            for template in templates:
                queries.append(template.format(keyword=keyword))

    return queries
