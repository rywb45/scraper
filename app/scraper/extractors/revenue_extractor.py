"""Extract revenue and employee count from company web pages."""

import re

from bs4 import BeautifulSoup

# Revenue patterns: "$X million", "$X billion", "$XM", "$XB", "revenue of $X"
REVENUE_PATTERNS = [
    # "$50 million" / "$1.2 billion"
    re.compile(r"\$\s*([\d,.]+)\s*(billion|million|mil|B|M)\b", re.IGNORECASE),
    # "revenue of $50M"
    re.compile(r"revenue[s]?\s+(?:of\s+)?\$\s*([\d,.]+)\s*(billion|million|mil|B|M)?", re.IGNORECASE),
    # "annual sales of $50 million"
    re.compile(r"(?:annual\s+)?sales\s+(?:of\s+)?\$\s*([\d,.]+)\s*(billion|million|mil|B|M)?", re.IGNORECASE),
    # "$50M revenue" / "$1.2B in revenue"
    re.compile(r"\$\s*([\d,.]+)\s*(B|M|K)?\s+(?:in\s+)?(?:revenue|sales|turnover)", re.IGNORECASE),
]

# Employee count patterns
EMPLOYEE_PATTERNS = [
    re.compile(r"([\d,]+)\s*(?:\+\s*)?employees", re.IGNORECASE),
    re.compile(r"(?:team|staff|workforce)\s+(?:of\s+)?([\d,]+)", re.IGNORECASE),
    re.compile(r"([\d,]+)\s*(?:\+\s*)?(?:team members|associates|workers|people)", re.IGNORECASE),
    re.compile(r"(?:over|approximately|about|nearly|more than)\s+([\d,]+)\s*(?:\+\s*)?(?:employees|people|staff)", re.IGNORECASE),
]

EMPLOYEE_RANGE_PATTERNS = [
    re.compile(r"([\d,]+)\s*[-–to]+\s*([\d,]+)\s*employees", re.IGNORECASE),
]

# Rough revenue estimate per employee by industry (in thousands USD)
REVENUE_PER_EMPLOYEE = {
    "Aerospace & Defense": 350,
    "Industrial Machinery & Equipment": 280,
    "Specialty Chemicals": 400,
    "Commodity Trading": 1500,
    "Medical & Scientific Equipment": 320,
    "Building Materials": 300,
    "Electrical & Electronic Hardware": 300,
    "default": 300,
}

# Employee count estimate from ranges
RANGE_TO_COUNT = {
    "1-10": 5,
    "1-50": 25,
    "11-50": 30,
    "10-50": 30,
    "51-200": 125,
    "50-200": 125,
    "201-500": 350,
    "200-500": 350,
    "501-1000": 750,
    "500-1000": 750,
    "1001-5000": 3000,
    "1000-5000": 3000,
    "5001-10000": 7500,
    "5000-10000": 7500,
}


def extract_revenue(html: str) -> tuple[str, str]:
    """Extract revenue from page HTML. Returns (revenue_string, source)."""
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(separator=" ")

    for pattern in REVENUE_PATTERNS:
        match = pattern.search(text)
        if match:
            amount_str = match.group(1).replace(",", "")
            try:
                amount = float(amount_str)
            except ValueError:
                continue

            suffix = (match.group(2) or "").strip().upper() if len(match.groups()) > 1 and match.group(2) else ""

            # Normalize to a readable string
            if suffix in ("BILLION", "B"):
                if amount >= 1:
                    revenue = f"${amount:,.1f}B"
                else:
                    revenue = f"${amount * 1000:,.0f}M"
            elif suffix in ("MILLION", "MIL", "M"):
                revenue = f"${amount:,.0f}M"
            elif suffix == "K":
                revenue = f"${amount:,.0f}K"
            elif amount >= 1_000_000_000:
                revenue = f"${amount / 1_000_000_000:,.1f}B"
            elif amount >= 1_000_000:
                revenue = f"${amount / 1_000_000:,.0f}M"
            elif amount >= 1_000:
                revenue = f"${amount / 1_000:,.0f}K"
            else:
                continue  # Too small to be revenue

            return revenue, "page_text"

    return "", ""


def extract_employee_count(html: str) -> tuple[int | None, str]:
    """Extract employee count from page HTML. Returns (count, range_string)."""
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(separator=" ")

    # Try range patterns first
    for pattern in EMPLOYEE_RANGE_PATTERNS:
        match = pattern.search(text)
        if match:
            low = int(match.group(1).replace(",", ""))
            high = int(match.group(2).replace(",", ""))
            if 1 <= low <= 500_000 and 1 <= high <= 500_000:
                avg = (low + high) // 2
                return avg, f"{low:,}-{high:,}"

    # Try single number patterns
    for pattern in EMPLOYEE_PATTERNS:
        match = pattern.search(text)
        if match:
            count = int(match.group(1).replace(",", ""))
            if 1 <= count <= 500_000:
                return count, _count_to_range(count)

    return None, ""


def estimate_revenue(employee_count: int | None, employee_range: str, industry: str) -> tuple[str, str]:
    """Estimate revenue from employee count. Returns (revenue_string, source)."""
    count = employee_count

    # Try to get count from range string
    if not count and employee_range:
        count = RANGE_TO_COUNT.get(employee_range.replace(" ", ""))
        if not count:
            # Try to parse "X-Y" format
            match = re.match(r"(\d+)\s*[-–]\s*(\d+)", employee_range)
            if match:
                low, high = int(match.group(1)), int(match.group(2))
                count = (low + high) // 2

    if not count or count < 1:
        return "", ""

    rev_per_emp = REVENUE_PER_EMPLOYEE.get(industry, REVENUE_PER_EMPLOYEE["default"])
    estimated = count * rev_per_emp  # in thousands

    if estimated >= 1_000_000:
        revenue = f"~${estimated / 1_000_000:,.1f}B"
    elif estimated >= 1_000:
        revenue = f"~${estimated / 1_000:,.0f}M"
    else:
        revenue = f"~${estimated:,.0f}K"

    return revenue, "estimated"


def _count_to_range(count: int) -> str:
    if count <= 10:
        return "1-10"
    if count <= 50:
        return "11-50"
    if count <= 200:
        return "51-200"
    if count <= 500:
        return "201-500"
    if count <= 1000:
        return "501-1,000"
    if count <= 5000:
        return "1,001-5,000"
    if count <= 10000:
        return "5,001-10,000"
    return "10,000+"
