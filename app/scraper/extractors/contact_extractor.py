import re

from bs4 import BeautifulSoup

from app.scraper.base import ScrapedContact

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
LINKEDIN_RE = re.compile(r"https?://(?:www\.)?linkedin\.com/in/[\w-]+/?")

TITLE_KEYWORDS = [
    "CEO", "CTO", "CFO", "COO", "CIO", "CMO", "VP", "President",
    "Director", "Manager", "Owner", "Founder", "Partner",
    "General Manager", "Sales Manager", "Engineering Manager",
    "Vice President", "Executive", "Principal", "Head of",
]

SKIP_EMAILS = {"info@", "sales@", "support@", "contact@", "admin@",
               "noreply@", "no-reply@", "help@", "webmaster@", "marketing@"}


def extract_contacts(html: str, source_url: str = "") -> list[ScrapedContact]:
    soup = BeautifulSoup(html, "lxml")
    contacts = []

    # Extract mailto links
    for link in soup.select("a[href^='mailto:']"):
        email = link["href"].replace("mailto:", "").split("?")[0].strip().lower()
        if not email or any(email.startswith(skip) for skip in SKIP_EMAILS):
            continue

        contact = ScrapedContact(
            email=email,
            email_confidence=100.0,
            source="mailto_link",
            source_url=source_url,
        )

        # Try to find name near the email
        parent = link.parent
        if parent:
            _extract_name_from_context(parent, contact)

        contacts.append(contact)

    # Extract emails from text
    text = soup.get_text()
    found_emails = set(c.email for c in contacts)
    for match in EMAIL_RE.finditer(text):
        email = match.group().lower()
        if email in found_emails:
            continue
        if any(email.startswith(skip) for skip in SKIP_EMAILS):
            continue
        found_emails.add(email)
        contacts.append(ScrapedContact(
            email=email,
            email_confidence=90.0,
            source="page_regex",
            source_url=source_url,
        ))

    # Extract LinkedIn profiles
    for link in soup.select('a[href*="linkedin.com/in/"]'):
        href = link.get("href", "")
        match = LINKEDIN_RE.match(href)
        if match:
            name_text = link.get_text(strip=True)
            contact = _find_or_create(contacts, linkedin_url=match.group())
            if name_text and len(name_text) < 60:
                _parse_name(contact, name_text)

    # Try to find people in structured sections
    for section in soup.select(".team, .staff, .leadership, .management, .about-team"):
        _extract_people_from_section(section, contacts, source_url)

    return contacts


def _extract_people_from_section(section, contacts: list, source_url: str):
    for card in section.select(".team-member, .person, .staff-member, article, .card"):
        contact = ScrapedContact(source="team_page", source_url=source_url)
        name_el = card.select_one("h2, h3, h4, .name, .team-name")
        if name_el:
            _parse_name(contact, name_el.get_text(strip=True))

        title_el = card.select_one(".title, .position, .role, .team-title")
        if title_el:
            contact.title = title_el.get_text(strip=True)[:200]

        email_el = card.select_one("a[href^='mailto:']")
        if email_el:
            contact.email = email_el["href"].replace("mailto:", "").split("?")[0].strip().lower()
            contact.email_confidence = 100.0

        if contact.full_name or contact.email:
            contacts.append(contact)


def _extract_name_from_context(element, contact: ScrapedContact):
    text = element.get_text(strip=True)
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    for line in lines:
        if "@" not in line and len(line) < 60:
            words = line.split()
            if 2 <= len(words) <= 4 and all(w[0].isupper() for w in words if w):
                _parse_name(contact, line)
                break

    # Check for title
    for line in lines:
        for kw in TITLE_KEYWORDS:
            if kw.lower() in line.lower():
                contact.title = line[:200]
                break


def _parse_name(contact: ScrapedContact, name: str):
    name = name.strip()
    contact.full_name = name
    parts = name.split()
    if len(parts) >= 2:
        contact.first_name = parts[0]
        contact.last_name = parts[-1]
    elif len(parts) == 1:
        contact.first_name = parts[0]


def _find_or_create(contacts: list, linkedin_url: str = "") -> ScrapedContact:
    for c in contacts:
        if linkedin_url and c.linkedin_url == linkedin_url:
            return c
    contact = ScrapedContact(linkedin_url=linkedin_url)
    contacts.append(contact)
    return contact
