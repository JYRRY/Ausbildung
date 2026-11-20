"""
ZUGZWANG - Facility Facts & Website Content Extraction Service
Responsible for:
- Fetching website content (home page + up to 4 subpages matching key topics)
- Clean HTML to plaintext (removing nav, footer, cookie banners, scripts)
- Classifying facility type (stationaer, ambulant, tagespflege, krankenhaus, gemischt_oder_unbekannt)
- Extracting formal contact person strictly from Impressum/Kontakt with explicit Herr/Frau and role
- Caching content in facility_text database table
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import re
import sqlite3
from typing import Optional
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup

from ..core.config import get_memory_db_path
from ..core.logger import get_logger

logger = get_logger(__name__)

FACILITY_KEYWORDS = {
    "stationaer": [
        "stationäre pflege", "stationaer", "altenheim", "pflegeheim",
        "seniorenheim", "seniorenresidenz", "vollstationär", "vollstationaer",
        "langzeitpflege", "wohnbereich", "pflegeplätze", "pflegeplaetze"
    ],
    "ambulant": [
        "ambulanter pflegedienst", "ambulante pflege", "häusliche pflege",
        "haeusliche pflege", "ambulant", "hauskrankenpflege", "sozialstation",
        "pflegedienst", "pflege zu hause", "tourenpflege"
    ],
    "tagespflege": [
        "tagespflege", "tagespflegeeinrichtung", "tagesgäste", "tagesgaeste", "tagesstätte", "tagesstaette"
    ],
    "krankenhaus": [
        "krankenhaus", "klinikum", "fachklinik", "hospital",
        "stationäre behandlung", "patientenversorgung", "akutklinik", "klinik"
    ],
}

ALLOWED_SUBPAGE_KEYWORDS = (
    "ueber-uns", "ueber_uns", "über-uns", "über uns", "ueberuns", "uber-uns",
    "leistungen", "leistung", "angebot", "angebote", "pflege",
    "ausbildung", "karriere", "jobs", "job", "team", "impressum", "kontakt"
)

ALLOWED_ROLES = (
    "einrichtungsleitung", "heimleitung", "einrichtungsleiterin", "einrichtungsleiter",
    "pflegedienstleitung", "pdl", "pflegedienstleiterin", "pflegedienstleiter",
    "geschäftsführung", "geschaeftsfuehrung", "geschäftsführer", "geschaeftsfuehrer",
    "geschäftsführerin", "geschaeftsfuehrerin",
    "ausbildungsleitung", "ausbildungsleiterin", "ausbildungsleiter"
)

_DOMAIN_LOCKS: dict[str, asyncio.Lock] = {}


def get_domain_lock(domain: str) -> asyncio.Lock:
    """Ensure at most 1 concurrent fetch per domain."""
    norm_dom = domain.lower().strip()
    if norm_dom not in _DOMAIN_LOCKS:
        _DOMAIN_LOCKS[norm_dom] = asyncio.Lock()
    return _DOMAIN_LOCKS[norm_dom]


def init_facility_text_table() -> None:
    """Ensure facility_text cache table exists."""
    try:
        db_path = get_memory_db_path()
        conn = sqlite3.connect(str(db_path), timeout=10.0)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS facility_text (
                lead_id TEXT,
                url TEXT,
                text TEXT,
                fetched_at TEXT,
                PRIMARY KEY (lead_id, url)
            )
        """)
        conn.commit()
        conn.close()
    except Exception as exc:
        logger.debug(f"Could not initialize facility_text table: {exc}")


def clean_html_text(html: str, max_words: int = 3000) -> str:
    """
    Remove navigation, footer, cookie banners, scripts, and CSS.
    Collapse whitespace and limit output to ~3000 words.
    """
    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")

    # Remove non-content tags
    for tag in soup(["script", "style", "noscript", "svg", "form", "iframe", "object"]):
        tag.decompose()

    # Remove navigation, headers, and footers
    for tag in soup.find_all(["nav", "header", "footer", "aside"]):
        tag.decompose()

    # Remove cookie banners, dialogs, and popups by class/id heuristics
    banner_pattern = re.compile(
        r"(cookie|consent|banner|modal|popup|overlay|privacy-notice|borlabs|klaro|usercentrics|cc-window)",
        re.IGNORECASE
    )
    for element in soup.find_all(True, attrs={"id": banner_pattern}):
        element.decompose()
    for element in soup.find_all(True, attrs={"class": banner_pattern}):
        element.decompose()

    text = soup.get_text(separator=" ")
    # Clean whitespace
    text = re.sub(r"[\t\r\xa0\u200b\ufeff]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text).strip()

    words = text.split()
    if len(words) > max_words:
        text = " ".join(words[:max_words])

    return text


def classify_facility_type(text: str) -> str:
    """
    Classify facility type into: stationaer, ambulant, tagespflege, krankenhaus, gemischt_oder_unbekannt.
    In case of ambiguity, returns 'gemischt_oder_unbekannt'.
    """
    if not text:
        return "gemischt_oder_unbekannt"

    text_lower = text.lower()
    scores: dict[str, int] = {"stationaer": 0, "ambulant": 0, "tagespflege": 0, "krankenhaus": 0}

    for f_type, keywords in FACILITY_KEYWORDS.items():
        for kw in keywords:
            # Count occurrences of keywords
            count = len(re.findall(r"\b" + re.escape(kw) + r"\b", text_lower))
            scores[f_type] += count

    # Filter types that have meaningful signal (>= 2 occurrences or strong presence)
    active_types = [t for t, s in scores.items() if s >= 2]

    if not active_types:
        # Check if single occurrence exists with no competitor
        single_types = [t for t, s in scores.items() if s >= 1]
        if len(single_types) == 1:
            return single_types[0]
        return "gemischt_oder_unbekannt"

    if len(active_types) == 1:
        return active_types[0]

    # Multiple active types -> check if one is overwhelmingly dominant (>= 2.5x the runner-up)
    sorted_types = sorted(active_types, key=lambda t: scores[t], reverse=True)
    best, runner_up = sorted_types[0], sorted_types[1]
    if scores[best] >= 2.5 * scores[runner_up]:
        return best

    return "gemischt_oder_unbekannt"


def extract_formal_contact_person(
    html_or_text: str,
    is_impressum_or_contact: bool = True
) -> tuple[str, str, str]:
    """
    Extract contact person strictly according to specification:
    - ONLY from Impressum or Contact pages
    - ONLY with recognized role (Einrichtungsleitung, Pflegedienstleitung, Geschäftsführung, Ausbildungsleitung)
    - AND explicit 'Herr' or 'Frau' + Nachname.
    - NEVER guess gender from first name.
    Returns (contact_person, anrede, empfaenger_zeile).
    """
    default_anrede = "Sehr geehrte Damen und Herren,"
    default_empfaenger = "Ausbildungsleitung Pflege"

    if not is_impressum_or_contact or not html_or_text:
        return "", default_anrede, default_empfaenger

    # Normalize input to text
    if "<" in html_or_text and ">" in html_or_text:
        clean_text = clean_html_text(html_or_text)
    else:
        clean_text = html_or_text

    # Role regex matching
    role_pattern_str = r"(?:Einrichtungsleitung|Heimleitung|Einrichtungsleiterin|Einrichtungsleiter|Pflegedienstleitung|PDL|Pflegedienstleiterin|Pflegedienstleiter|Geschäftsführung|Geschaeftsfuehrung|Geschäftsführerin|Geschaeftsfuehrerin|Geschäftsführer|Geschaeftsfuehrer|Ausbildungsleitung|Ausbildungsleiterin|Ausbildungsleiter)"
    
    # Pattern: Role ... Herr/Frau [Dr./Prof.] [Vorname] Nachname
    # Or: Herr/Frau [Dr./Prof.] [Vorname] Nachname ... Role
    pattern1 = re.compile(
        rf"\b({role_pattern_str})\b[^\n\r.,;]{{0,60}}?\b(Herr|Frau)\b\s+((?:(?:Dr\.|Prof\.|med\.|von|van|der|de|zu)\s*)*[A-ZÄÖÜ][a-zA-Zäöüß\-]+(?:\s+[A-ZÄÖÜ][a-zA-Zäöüß\-]+)?)",
        re.IGNORECASE
    )
    pattern2 = re.compile(
        rf"\b(Herr|Frau)\b\s+((?:(?:Dr\.|Prof\.|med\.|von|van|der|de|zu)\s*)*[A-ZÄÖÜ][a-zA-Zäöüß\-]+(?:\s+[A-ZÄÖÜ][a-zA-Zäöüß\-]+)?)[^\n\r.,;]{{0,60}}?\b({role_pattern_str})\b",
        re.IGNORECASE
    )

    matches = []
    for m in pattern1.finditer(clean_text):
        raw_role, salutation, name_str = m.group(1), m.group(2).capitalize(), m.group(3).strip()
        matches.append((raw_role, salutation, name_str))

    for m in pattern2.finditer(clean_text):
        salutation, name_str, raw_role = m.group(1).capitalize(), m.group(2).strip(), m.group(3)
        matches.append((raw_role, salutation, name_str))

    for raw_role, salutation, name_str in matches:
        # Validate name words (must have at least a last name, no digits)
        name_tokens = name_str.split()
        if not name_tokens or any(ch.isdigit() for ch in name_str):
            continue

        # Extract last name
        last_name = name_tokens[-1]
        title_prefix = " ".join([t for t in name_tokens[:-1] if t in ("Dr.", "Prof.", "med.", "von", "van", "der", "zu")])

        full_salutation_name = f"{salutation} {name_str}"

        # Standardize empfaenger_zeile based on recognized role
        role_lower = raw_role.lower()
        if "pflegedienst" in role_lower or "pdl" in role_lower:
            empfaenger = "Pflegedienstleitung"
        elif "einrichtung" in role_lower or "heim" in role_lower:
            empfaenger = "Einrichtungsleitung"
        elif "geschäft" in role_lower or "geschaeft" in role_lower:
            empfaenger = "Geschäftsführung"
        elif "ausbildung" in role_lower:
            empfaenger = "Ausbildungsleitung"
        else:
            empfaenger = default_empfaenger

        # Formal German greeting
        salutation_lead = "Sehr geehrte Frau" if salutation == "Frau" else "Sehr geehrter Herr"
        anrede = f"{salutation_lead} {title_prefix} {last_name},".replace("  ", " ")

        return full_salutation_name, anrede, empfaenger

    return "", default_anrede, default_empfaenger


def is_candidate_subpage_url(href: str, text: str = "") -> bool:
    """Check whether a link URL or text contains required subpage keywords."""
    combined = (href + " " + text).lower()
    return any(kw in combined for kw in ALLOWED_SUBPAGE_KEYWORDS)


def get_cached_facility_text(lead_id: str) -> Optional[dict]:
    """Retrieve cached facility facts for a lead if present in database."""
    init_facility_text_table()
    try:
        conn = sqlite3.connect(str(get_memory_db_path()), timeout=5.0)
        rows = conn.execute("SELECT url, text FROM facility_text WHERE lead_id = ?", (lead_id,)).fetchall()
        conn.close()
        if rows:
            urls = [r[0] for r in rows]
            combined_text = "\n\n".join(r[1] for r in rows)
            contact_person, anrede, empfaenger = "", "Sehr geehrte Damen und Herren,", "Ausbildungsleitung Pflege"
            for url, txt in rows:
                if "impressum" in url.lower() or "kontakt" in url.lower():
                    cp, anr, empf = extract_formal_contact_person(txt, is_impressum_or_contact=True)
                    if cp:
                        contact_person, anrede, empfaenger = cp, anr, empf
                        break
            f_type = classify_facility_type(combined_text)
            return {
                "lead_id": lead_id,
                "facility_type": f_type,
                "contact_person": contact_person,
                "anrede": anrede,
                "empfaenger_zeile": empfaenger,
                "cleaned_text": combined_text,
                "source_urls": urls,
            }
    except Exception:
        pass
    return None


def save_facility_text(lead_id: str, url: str, text: str) -> None:
    """Save scraped page text into facility_text cache table."""
    init_facility_text_table()
    try:
        conn = sqlite3.connect(str(get_memory_db_path()), timeout=5.0)
        now_iso = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO facility_text (lead_id, url, text, fetched_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(lead_id, url) DO UPDATE SET text=excluded.text, fetched_at=excluded.fetched_at",
            (lead_id, url, text, now_iso)
        )
        conn.commit()
        conn.close()
    except Exception as exc:
        logger.debug(f"Failed to cache facility text: {exc}")


async def check_robots_txt(base_url: str, user_agent: str = "*") -> bool:
    """Check robots.txt compliance for given base URL."""
    try:
        parsed = urlparse(base_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = RobotFileParser()
        rp.set_url(robots_url)
        # Fast non-blocking read
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, rp.read)
        return rp.can_fetch(user_agent, base_url)
    except Exception:
        return True


async def fetch_facility_facts(
    lead_id: str,
    website_url: str,
    browser_session: Optional[any] = None,
    max_subpages: int = 4,
    timeout_s: float = 20.0,
) -> dict:
    """
    Crawl website (homepage + up to 4 keyword subpages), clean text, and extract facts.
    Follows strict rate limiting (1-2s delay), domain concurrency locks, and 20s timeout with 1 retry.
    """
    cached = get_cached_facility_text(lead_id)
    if cached and cached.get("cleaned_text"):
        return cached

    if not website_url or not website_url.strip():
        return {
            "lead_id": lead_id,
            "facility_type": "gemischt_oder_unbekannt",
            "contact_person": "",
            "anrede": "Sehr geehrte Damen und Herren,",
            "empfaenger_zeile": "Ausbildungsleitung Pflege",
            "cleaned_text": "",
            "source_urls": [],
        }

    parsed = urlparse(website_url if "://" in website_url else f"https://{website_url}")
    domain = parsed.netloc or parsed.path.split("/")[0]
    base_url = f"{parsed.scheme or 'https'}://{domain}"

    domain_lock = get_domain_lock(domain)
    async with domain_lock:
        # Check robots.txt
        is_allowed = await check_robots_txt(base_url)
        if not is_allowed:
            logger.info(f"Robots.txt disallowed crawling for {base_url}")
            return {
                "lead_id": lead_id,
                "facility_type": "gemischt_oder_unbekannt",
                "contact_person": "",
                "anrede": "Sehr geehrte Damen und Herren,",
                "empfaenger_zeile": "Ausbildungsleitung Pflege",
                "cleaned_text": "",
                "source_urls": [],
            }

        # Need browser session or fallback HTTP
        scraped_pages: dict[str, str] = {}
        target_urls = [base_url]
        discovered_subpages: list[str] = []

        if browser_session is not None:
            # Use Playwright session
            page = await browser_session.new_page()
            try:
                for idx, url in enumerate(target_urls):
                    if idx > 0:
                        # 1-2s delay between requests
                        await asyncio.sleep(1.5)

                    # Attempt with 1 retry
                    html = ""
                    for attempt in range(2):
                        try:
                            resp = await page.goto(url, timeout=int(timeout_s * 1000), wait_until="domcontentloaded")
                            if resp and resp.ok:
                                html = await page.content()
                                break
                        except Exception as e:
                            if attempt == 1:
                                logger.debug(f"Failed to fetch {url} after retry: {e}")

                    if html:
                        scraped_pages[url] = html
                        save_facility_text(lead_id, url, clean_html_text(html))

                        # On homepage, discover up to max_subpages matching keywords
                        if url == base_url and not discovered_subpages:
                            soup = BeautifulSoup(html, "html.parser")
                            for a in soup.find_all("a", href=True):
                                href = a["href"].strip()
                                link_text = a.get_text(separator=" ").strip()
                                full_url = urljoin(base_url, href)
                                if urlparse(full_url).netloc == domain and full_url != base_url:
                                    if is_candidate_subpage_url(full_url, link_text):
                                        if full_url not in discovered_subpages:
                                            discovered_subpages.append(full_url)
                                            if len(discovered_subpages) >= max_subpages:
                                                break
                            target_urls.extend(discovered_subpages)
            finally:
                try:
                    await page.close()
                except Exception:
                    pass

    # Assemble cleaned texts
    combined_texts = []
    source_urls = list(scraped_pages.keys())
    contact_person, anrede, empfaenger = "", "Sehr geehrte Damen und Herren,", "Ausbildungsleitung Pflege"

    for url, html in scraped_pages.items():
        cleaned = clean_html_text(html)
        combined_texts.append(cleaned)
        is_contact_page = "impressum" in url.lower() or "kontakt" in url.lower()
        if is_contact_page and not contact_person:
            cp, anr, empf = extract_formal_contact_person(html, is_impressum_or_contact=True)
            if cp:
                contact_person, anrede, empfaenger = cp, anr, empf

    full_text = "\n\n".join(combined_texts)
    # Cap total words to 3000
    words = full_text.split()
    if len(words) > 3000:
        full_text = " ".join(words[:3000])

    f_type = classify_facility_type(full_text)

    return {
        "lead_id": lead_id,
        "facility_type": f_type,
        "contact_person": contact_person,
        "anrede": anrede,
        "empfaenger_zeile": empfaenger,
        "cleaned_text": full_text,
        "source_urls": source_urls,
    }

