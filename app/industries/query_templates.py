from app.industries.definitions import INDUSTRIES

SEARCH_TEMPLATES = [
    '"{keyword}" manufacturer USA company',
    '"{keyword}" supplier United States',
    '"{keyword}" company directory USA',
    'top "{keyword}" companies USA',
    '"{keyword}" distributor United States',
]

DIRECTORY_TEMPLATES = {
    "thomasnet": "site:thomasnet.com {keyword}",
    "kompass": "site:kompass.com {keyword} United States",
    "industrynet": "site:industrynet.com {keyword}",
}


def generate_queries(industry_name: str, source: str = "google") -> list[str]:
    industry = INDUSTRIES.get(industry_name)
    if not industry:
        return []

    queries = []
    templates = DIRECTORY_TEMPLATES if source != "google" else SEARCH_TEMPLATES

    if source in DIRECTORY_TEMPLATES:
        template = DIRECTORY_TEMPLATES[source]
        for keyword in industry.keywords[:5]:
            queries.append(template.format(keyword=keyword))
    else:
        for keyword in industry.keywords[:5]:
            for template in SEARCH_TEMPLATES[:3]:
                queries.append(template.format(keyword=keyword))

    return queries
