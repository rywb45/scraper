import re

from app.scraper.base import ScrapedContact

# Common email patterns
PATTERNS = [
    ("{first}.{last}", 0.7),
    ("{first}{last}", 0.6),
    ("{f}{last}", 0.6),
    ("{first}_{last}", 0.5),
    ("{first}", 0.4),
    ("{last}", 0.3),
    ("{f}.{last}", 0.5),
    ("{last}.{first}", 0.4),
    ("{last}{f}", 0.4),
]


def discover_email_pattern(known_emails: list[str], domain: str) -> tuple[str, float] | None:
    """Detect the email pattern used by a domain based on known emails."""
    domain_emails = [e for e in known_emails if e.endswith(f"@{domain}")]
    if not domain_emails:
        return None

    # Analyze local parts
    local_parts = [e.split("@")[0].lower() for e in domain_emails]

    # Check for common separators
    has_dot = any("." in lp for lp in local_parts)
    has_underscore = any("_" in lp for lp in local_parts)

    if has_dot:
        # likely first.last or f.last
        sample = local_parts[0]
        parts = sample.split(".")
        if len(parts) == 2 and len(parts[0]) == 1:
            return "{f}.{last}", 0.7
        return "{first}.{last}", 0.8
    elif has_underscore:
        return "{first}_{last}", 0.7
    else:
        sample = local_parts[0]
        if len(sample) <= 2:
            return "{f}{last_initial}", 0.5
        return "{first}{last}", 0.6


def generate_email_candidates(
    contact: ScrapedContact,
    domain: str,
    detected_pattern: tuple[str, float] | None = None,
) -> list[tuple[str, float]]:
    """Generate possible emails for a contact given a domain."""
    if not contact.first_name or not contact.last_name:
        return []

    first = _clean_name(contact.first_name)
    last = _clean_name(contact.last_name)
    f = first[0] if first else ""

    candidates = []

    if detected_pattern:
        pattern, base_conf = detected_pattern
        email = _apply_pattern(pattern, first, last, f, domain)
        if email:
            candidates.append((email, min(base_conf * 100, 70.0)))

    for pattern, conf in PATTERNS:
        email = _apply_pattern(pattern, first, last, f, domain)
        if email and not any(e == email for e, _ in candidates):
            candidates.append((email, conf * 100 * 0.6))  # Lower than detected pattern

    return candidates[:5]


def _apply_pattern(pattern: str, first: str, last: str, f: str, domain: str) -> str | None:
    try:
        local = pattern.format(first=first, last=last, f=f, last_initial=last[0] if last else "")
        return f"{local}@{domain}"
    except (KeyError, IndexError):
        return None


def _clean_name(name: str) -> str:
    return re.sub(r"[^a-z]", "", name.lower())
