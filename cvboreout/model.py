"""Document model: defaults, sample resume and migration of older files."""

from __future__ import annotations

import copy
import json
from pathlib import Path

LANGUAGES = [
    {"id": "de", "name": "Deutsch"},
    {"id": "en", "name": "English"},
]

# Accent presets. "color" carries headings and rules, "dark" fills the sidebar
# band of the modern template. Pastel entries pair a readable accent with a
# light band; the renderer picks the band's text colour from its luminance.
ACCENTS = [
    # blues, dark to bright
    {"name": "Marine", "color": "#1E3A8A", "dark": "#16296B"},
    {"name": "Royal", "color": "#1D4ED8", "dark": "#15369B"},
    {"name": "Azure", "color": "#0369A1", "dark": "#054A72"},
    {"name": "Petrol", "color": "#155E75", "dark": "#0E4257"},
    {"name": "Indigo", "color": "#4338CA", "dark": "#2E2A8F"},
    # greens, dark to soft
    {"name": "Pine", "color": "#14532D", "dark": "#0C3A1E"},
    {"name": "Emerald", "color": "#047857", "dark": "#03543D"},
    {"name": "Teal", "color": "#0F766E", "dark": "#0B4F4A"},
    {"name": "Moss", "color": "#3F6212", "dark": "#2C440D"},
    {"name": "Sage", "color": "#4D7C6F", "dark": "#35564D"},
    # neutral and warm
    {"name": "Graphite", "color": "#334155", "dark": "#1E293B"},
    {"name": "Bordeaux", "color": "#9F1239", "dark": "#6B0F28"},
    {"name": "Copper", "color": "#B45309", "dark": "#7C3A06"},
    # pastel bands with dark lettering
    {"name": "Sky pastel", "color": "#0369A1", "dark": "#D7E7F5"},
    {"name": "Mint pastel", "color": "#0F766E", "dark": "#D3EFE9"},
    {"name": "Lilac pastel", "color": "#5B21B6", "dark": "#E7E0F7"},
]

TEMPLATES = [
    {"id": "modern", "de": "Modern", "en": "Modern"},
    {"id": "classic", "de": "Klassisch", "en": "Classic"},
    {"id": "compact", "de": "Kompakt", "en": "Compact"},
]

FONTS = [
    {"id": "Noto Sans", "name": "Noto Sans"},
    {"id": "Liberation Sans", "name": "Liberation Sans (Arial-like)"},
    {"id": "DejaVu Sans", "name": "DejaVu Sans"},
    {"id": "Liberation Serif", "name": "Liberation Serif (Times-like)"},
    {"id": "Noto Serif", "name": "Noto Serif"},
]

# Section titles per language; used as defaults and for re-titling on switch.
SECTION_TITLES = {
    "de": {
        "summary": "Kurzprofil",
        "experience": "Berufserfahrung",
        "education": "Ausbildung",
        "projects": "Projekte",
        "publications": "Publikationen & Patente",
        "skills": "Kenntnisse",
        "languages": "Sprachen",
        "certificates": "Zertifikate",
        "interests": "Interessen",
    },
    "en": {
        "summary": "Profile",
        "experience": "Experience",
        "education": "Education",
        "projects": "Projects",
        "publications": "Publications & Patents",
        "skills": "Skills",
        "languages": "Languages",
        "certificates": "Certifications",
        "interests": "Interests",
    },
}

SECTION_LAYOUT = [
    ("summary", True, "main"),
    ("experience", True, "main"),
    ("education", True, "main"),
    ("projects", True, "main"),
    ("publications", False, "main"),
    ("skills", True, "side"),
    ("languages", True, "side"),
    ("certificates", True, "side"),
    ("interests", True, "side"),
]

PRESENT = {"de": "heute", "en": "present"}

# Language proficiency levels offered in the editor; the dot level follows.
PROFICIENCY = [
    {"id": "native", "level": 5, "de": "Muttersprache", "en": "Native speaker"},
    {"id": "C2", "level": 5, "de": "C2 – verhandlungssicher", "en": "C2 – proficient"},
    {"id": "C1", "level": 4, "de": "C1 – verhandlungssicher", "en": "C1 – advanced"},
    {"id": "B2", "level": 4, "de": "B2 – gute Kenntnisse", "en": "B2 – upper intermediate"},
    {"id": "B1", "level": 3, "de": "B1 – Grundkenntnisse", "en": "B1 – intermediate"},
    {"id": "A2", "level": 2, "de": "A2 – Grundkenntnisse", "en": "A2 – elementary"},
    {"id": "A1", "level": 1, "de": "A1 – Anfänger", "en": "A1 – beginner"},
]


def default_sections(language: str = "de") -> list[dict]:
    titles = SECTION_TITLES.get(language, SECTION_TITLES["de"])
    return [
        {"id": sid, "title": titles[sid], "enabled": enabled, "column": column}
        for sid, enabled, column in SECTION_LAYOUT
    ]


EMPTY = {
    "meta": {
        "language": "de",
        "template": "modern",
        "accent": "#0F766E",
        "accentDark": "#0B4F4A",
        "font": "Noto Sans",
        "fontSize": 9.6,
        "density": "normal",        # tight | normal | airy
        "showLevels": True,
        "pageNumbers": True,
        "uppercaseHeadings": True,
        "sections": default_sections("de"),
    },
    "person": {
        "firstName": "",
        "lastName": "",
        "title": "",
        "position": "",
        "email": "",
        "phone": "",
        "location": "",
        "birthDate": "",
        "nationality": "",
        "photo": "",
        "links": [],
    },
    "summary": "",
    "experience": [],
    "education": [],
    "projects": [],
    "publications": [],
    "skills": [],
    "languages": [],
    "certificates": [],
    "interests": [],
    "letter": {
        "company": "",
        "contactName": "",
        "street": "",
        "city": "",
        "reference": "",
        "subject": "",
        "senderCity": "",
        "date": "",           # empty -> today
        "salutation": "",     # empty -> default for the document language
        "body": "",
        "closing": "",        # empty -> default for the document language
        "attachments": [],
    },
}

SALUTATION = {"de": "Sehr geehrte Damen und Herren,", "en": "Dear Sir or Madam,"}
CLOSING = {"de": "Mit freundlichen Grüßen", "en": "Kind regards"}
ATTACHMENTS_LABEL = {"de": "Anlagen", "en": "Enclosures"}
DEFAULT_ATTACHMENTS = {
    "de": ["Lebenslauf", "Zeugnisse"],
    "en": ["Curriculum vitae", "Certificates"],
}

SAMPLE = {
    "meta": copy.deepcopy(EMPTY["meta"]),
    "person": {
        "firstName": "Manuela",
        "lastName": "Musterfrau",
        "title": "M.Sc.",
        "position": "Embedded Systems Engineer",
        "email": "manuela.musterfrau@example.de",
        "phone": "+49 151 2345678",
        "location": "12345 Musterstadt",
        "birthDate": "",
        "nationality": "",
        "photo": "",
        "links": [
            {"label": "GitHub", "url": "github.com/m.musterfrau"},
            {"label": "LinkedIn", "url": "linkedin.com/in/m.musterfrau"},
        ],
    },
    "summary": (
        "Embedded-Entwicklerin mit sechs Jahren Erfahrung in sicherheitskritischer "
        "Firmware für Automotive- und Industrieanwendungen. Schwerpunkte: ARM Cortex-M, "
        "AUTOSAR Classic und Echtzeit-Regelung. Führte die ISO-26262-Qualifizierung einer "
        "Bremssteuerungs-Plattform bis ASIL-D und senkte die Latenz der Regelschleife um 38 %."
    ),
    "experience": [
        {
            "position": "Senior Embedded Software Engineer",
            "company": "Vektor Mobility Systems GmbH",
            "location": "München",
            "from": "03/2022",
            "to": "present",
            "bullets": [
                "Architektur und Umsetzung der Firmware für eine ASIL-D-Bremssteuerung (ARM Cortex-M7, AUTOSAR Classic, MISRA C:2012).",
                "Latenz der Regelschleife von 2,1 ms auf 1,3 ms reduziert durch DMA-basierte Sensorerfassung und Neuaufteilung der Tasks.",
                "Aufbau einer Hardware-in-the-Loop-Teststrecke (dSPACE, Python, GitLab CI); Regressionslauf von 6 h auf 40 min verkürzt.",
                "Fachliche Führung von drei Entwickler:innen sowie Review-Verantwortung für sicherheitsrelevante Module.",
            ],
            "tech": ["C", "C++17", "AUTOSAR", "ISO 26262", "CAN/CAN-FD", "Python"],
        },
        {
            "position": "Embedded Software Engineer",
            "company": "Isarwerk Automation AG",
            "location": "Augsburg",
            "from": "09/2019",
            "to": "02/2022",
            "bullets": [
                "Entwicklung von Motorsteuerungs-Firmware (FOC) für Servoantriebe bis 15 kW auf STM32-Plattform.",
                "EtherCAT-Slave-Stack integriert und Zykluszeit von 1 ms stabil erreicht (Jitter < 15 µs).",
                "Bootloader mit signiertem Firmware-Update (ECDSA) eingeführt; Feldrückläufer durch fehlerhafte Updates auf null gesenkt.",
            ],
            "tech": ["C", "STM32", "FreeRTOS", "EtherCAT", "Regelungstechnik"],
        },
    ],
    "education": [
        {
            "degree": "M.Sc. Elektrotechnik und Informationstechnik",
            "institution": "Technische Universität München",
            "location": "München",
            "from": "10/2017",
            "to": "08/2019",
            "grade": "1,3",
            "details": "Schwerpunkt Regelungstechnik & eingebettete Systeme. Masterarbeit: „Modellprädiktive Regelung für Servoantriebe auf ressourcenbeschränkter Hardware“ (1,0).",
        },
        {
            "degree": "B.Sc. Elektrotechnik",
            "institution": "Universität Stuttgart",
            "location": "Stuttgart",
            "from": "10/2014",
            "to": "09/2017",
            "grade": "1,7",
            "details": "",
        },
    ],
    "projects": [
        {
            "name": "openservo-rt",
            "role": "Maintainer",
            "from": "2021",
            "to": "present",
            "description": "Open-Source-Echtzeit-Regelungsbibliothek für BLDC-Antriebe; 1,4k Sterne, Einsatz in mehreren Forschungsprojekten.",
            "tech": ["C++", "CMake", "Zephyr"],
            "link": "github.com/lhoffmann/openservo-rt",
        }
    ],
    "publications": [
        {
            "title": "Resource-Aware MPC for Low-Cost Servo Drives",
            "source": "IEEE Transactions on Industrial Electronics",
            "year": "2021",
            "link": "",
        }
    ],
    "skills": [
        {"category": "Sprachen", "items": [
            {"name": "C / C++17", "level": 5},
            {"name": "Python", "level": 4},
            {"name": "Rust", "level": 3},
        ]},
        {"category": "Plattformen", "items": [
            {"name": "ARM Cortex-M", "level": 5},
            {"name": "FreeRTOS / Zephyr", "level": 4},
            {"name": "Linux (Yocto)", "level": 3},
        ]},
        {"category": "Methoden", "items": [
            {"name": "ISO 26262", "level": 4},
            {"name": "HIL-Test / CI", "level": 4},
            {"name": "Regelungstechnik", "level": 4},
        ]},
    ],
    "languages": [
        {"name": "Deutsch", "proficiency": "native", "level": 5},
        {"name": "Englisch", "proficiency": "C1", "level": 4},
        {"name": "Französisch", "proficiency": "B1", "level": 3},
    ],
    "certificates": [
        {"name": "Certified Automotive Functional Safety Professional", "issuer": "TÜV Süd", "year": "2023"},
        {"name": "Scrum Master (PSM I)", "issuer": "Scrum.org", "year": "2021"},
    ],
    "interests": ["Modellflug (Eigenbau-Flugregler)", "Wettkampfklettern", "Jugend-forscht-Mentorin"],
    "letter": {
        "company": "Nordlicht Robotics GmbH",
        "contactName": "Personalabteilung",
        "street": "Hafenstraße 12",
        "city": "20457 Hamburg",
        "reference": "Kennziffer ER-2481",
        "subject": "Bewerbung als Embedded Systems Engineer",
        "senderCity": "München",
        "date": "",
        "salutation": "",
        "body": (
            "mit großem Interesse habe ich Ihre Ausschreibung für die Entwicklung von "
            "Antriebsregelungen gelesen. Nach sechs Jahren in sicherheitskritischer "
            "Firmware für Automotive- und Industrieanwendungen suche ich eine Aufgabe, "
            "in der Regelungstechnik und funktionale Sicherheit zusammenkommen — genau "
            "die Verbindung, die Ihre Stelle beschreibt.\n\n"
            "Bei Vektor Mobility verantworte ich die Firmware einer ASIL-D-Bremssteuerung "
            "auf ARM Cortex-M7. Die Latenz der Regelschleife habe ich dort von 2,1 ms auf "
            "1,3 ms gesenkt und eine Hardware-in-the-Loop-Teststrecke aufgebaut, die den "
            "Regressionslauf von sechs Stunden auf 40 Minuten verkürzt hat. Die "
            "ISO-26262-Qualifizierung der Plattform habe ich bis zum Abschluss begleitet.\n\n"
            "Ihre Antriebsplattform arbeitet mit EtherCAT und feldaktualisierbarer "
            "Firmware. Beides habe ich bei Isarwerk Automation aufgebaut: einen "
            "EtherCAT-Slave-Stack mit 1 ms Zykluszeit und einen Bootloader mit signiertem "
            "Update, der Feldrückläufer durch fehlerhafte Updates auf null gesenkt hat.\n\n"
            "Über ein Gespräch freue ich mich sehr."
        ),
        "closing": "",
        "attachments": ["Lebenslauf", "Zeugnisse", "Zertifikate"],
    },
}

# --- Migration of the first-generation German schema ----------------------

_META_KEYS = {
    "vorlage": "template", "akzent": "accent", "akzent_dunkel": "accentDark",
    "schrift": "font", "schriftgroesse": "fontSize", "dichte": "density",
    "skill_level": "showLevels", "seitenzahl": "pageNumbers",
    "grossbuchstaben": "uppercaseHeadings", "abschnitte": "sections",
}
_PERSON_KEYS = {
    "vorname": "firstName", "nachname": "lastName", "titel": "title",
    "position": "position", "email": "email", "telefon": "phone", "ort": "location",
    "geburtsdatum": "birthDate", "staatsangehoerigkeit": "nationality",
    "foto": "photo", "links": "links",
}
_LIST_KEYS = {
    "erfahrung": "experience", "ausbildung": "education", "projekte": "projects",
    "publikationen": "publications", "skills": "skills", "sprachen": "languages",
    "zertifikate": "certificates", "interessen": "interests", "profil": "summary",
}
_ENTRY_KEYS = {
    "position": "position", "firma": "company", "ort": "location",
    "von": "from", "bis": "to", "punkte": "bullets", "tech": "tech",
    "abschluss": "degree", "institution": "institution", "note": "grade",
    "details": "details", "name": "name", "rolle": "role",
    "zeitraum": "_period", "beschreibung": "description", "link": "link",
    "titel": "title", "quelle": "source", "jahr": "year",
    "kategorie": "category", "eintraege": "items", "level": "level",
    "niveau": "_proficiency_label", "aussteller": "issuer",
}
_DENSITY = {"eng": "tight", "normal": "normal", "luftig": "airy"}
_TEMPLATES = {"modern": "modern", "klassisch": "classic", "kompakt": "compact"}


def _rename(entry: dict, mapping: dict) -> dict:
    return {mapping.get(key, key): value for key, value in entry.items()}


_PRESENT_WORDS = {"heute", "today", "now", "present", "aktuell", "jetzt", "current"}


def _normalize_dates(entry: dict) -> dict:
    """Map free-text 'heute'/'today' onto the 'present' sentinel."""
    for key in ("from", "to"):
        value = str(entry.get(key, "") or "").strip()
        if value.lower() in _PRESENT_WORDS:
            entry[key] = "present"
    return entry


def _migrate_period(entry: dict) -> dict:
    """'seit 2021' / '2019 – 2021' from the old free-text period field."""
    period = (entry.pop("_period", "") or "").strip()
    if not period or entry.get("from"):
        return entry
    lowered = period.lower()
    if lowered.startswith(("seit", "since")):
        entry["from"] = period.split(maxsplit=1)[-1].strip()
        entry["to"] = "present"
    elif "–" in period or "-" in period:
        first, _, second = period.replace("-", "–").partition("–")
        entry["from"], entry["to"] = first.strip(), second.strip()
    else:
        entry["from"] = period
    return entry


def _migrate_proficiency(entry: dict) -> dict:
    label = (entry.pop("_proficiency_label", "") or "").strip()
    if entry.get("proficiency"):
        return entry
    if label:
        upper = label.upper()
        for level in PROFICIENCY:
            if level["id"] != "native" and upper.startswith(level["id"]):
                entry["proficiency"] = level["id"]
                return entry
        if "mutter" in label.lower() or "native" in label.lower():
            entry["proficiency"] = "native"
            return entry
        entry["proficiency"] = "custom"
        entry["proficiencyLabel"] = label
    return entry


def migrate(data: dict) -> dict:
    """Convert a first-generation German document to the English schema."""
    if not isinstance(data, dict) or "person" not in data:
        return data
    if "vorname" not in (data.get("person") or {}) and "profil" not in data:
        return data  # already the current schema

    result = {"meta": {}, "person": {}}
    meta = _rename(data.get("meta", {}), _META_KEYS)
    meta["template"] = _TEMPLATES.get(meta.get("template", "modern"), "modern")
    meta["density"] = _DENSITY.get(meta.get("density", "normal"), "normal")
    meta.setdefault("language", "de")
    sections = []
    for section in meta.get("sections", []):
        sections.append({
            "id": {"profil": "summary", "erfahrung": "experience", "ausbildung": "education",
                   "projekte": "projects", "publikationen": "publications", "skills": "skills",
                   "sprachen": "languages", "zertifikate": "certificates",
                   "interessen": "interests"}.get(section.get("id"), section.get("id")),
            "title": section.get("titel", ""),
            "enabled": section.get("an", True),
            "column": "side" if section.get("spalte") == "seite" else "main",
        })
    meta["sections"] = sections or default_sections(meta["language"])
    result["meta"] = meta
    result["person"] = _rename(data.get("person", {}), _PERSON_KEYS)

    for old, new in _LIST_KEYS.items():
        if old not in data:
            continue
        value = data[old]
        if not isinstance(value, list):
            result[new] = value
            continue
        entries = []
        for entry in value:
            if not isinstance(entry, dict):
                entries.append(entry)
                continue
            converted = _normalize_dates(_migrate_period(_rename(entry, _ENTRY_KEYS)))
            if new == "languages":
                converted = _migrate_proficiency(converted)
            if new == "skills":
                converted["items"] = [_rename(i, _ENTRY_KEYS) for i in converted.get("items", [])]
            entries.append(converted)
        result[new] = entries
    return result


def _merge(defaults, data):
    if not isinstance(data, dict):
        return copy.deepcopy(defaults)
    merged = copy.deepcopy(defaults)
    for key, value in data.items():
        if key in merged and isinstance(merged[key], dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def normalize(data: dict) -> dict:
    """Fill in missing fields and keep the section list complete."""
    data = _merge(EMPTY, migrate(data or {}))
    language = data["meta"].get("language", "de")
    known = {section.get("id") for section in data["meta"].get("sections", [])}
    for section in default_sections(language):
        if section["id"] not in known:
            data["meta"]["sections"].append(section)
    return data


def retitle_sections(data: dict, language: str) -> dict:
    """After a language switch, translate titles that are still the defaults."""
    other = "en" if language == "de" else "de"
    for section in data["meta"].get("sections", []):
        sid = section.get("id")
        if sid in SECTION_TITLES[other] and section.get("title") == SECTION_TITLES[other][sid]:
            section["title"] = SECTION_TITLES[language][sid]
    return data


def load(path: Path) -> dict:
    if path.exists():
        try:
            return normalize(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            pass
    return normalize(copy.deepcopy(SAMPLE))


def save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
