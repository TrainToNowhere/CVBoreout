"""Prompt construction and answer parsing for the AI assistant."""

from __future__ import annotations

from .model import PROFICIENCY

SYSTEM = {
    "de": (
        "Du bist ein erfahrener Bewerbungscoach für MINT-Berufe im deutschsprachigen Raum "
        "(Ingenieurwesen, Informatik, Naturwissenschaften, Mathematik). "
        "Du schreibst präzise, sachlich und ohne Werbefloskeln. "
        "Du nutzt starke Tätigkeitsverben, konkrete Technologien und – wenn vorhanden – "
        "messbare Ergebnisse. Du erfindest niemals Fakten, Zahlen oder Arbeitgeber hinzu. "
        "Antworte ausschließlich auf Deutsch, ohne Markdown-Auszeichnung, ohne Vorrede "
        "und ohne abschließende Erklärung."
    ),
    "en": (
        "You are an experienced career coach for STEM professions "
        "(engineering, computer science, natural sciences, mathematics). "
        "You write precisely and factually, without marketing language. "
        "You use strong action verbs, concrete technologies and – where available – "
        "measurable results. You never invent facts, numbers or employers. "
        "Answer in English only, without Markdown formatting, without a preamble "
        "and without a closing explanation."
    ),
}

TASKS = {
    "summary": {
        "de": (
            "AUFGABE: Schreibe ein Kurzprofil für den Kopf dieses Lebenslaufs. "
            "3 bis 4 Sätze, maximal 65 Wörter. Beginne nicht mit dem Namen und verwende keine "
            "Pronomen; formuliere unpersönlich (z. B. „Embedded-Entwicklerin mit sechs Jahren "
            "Erfahrung in sicherheitskritischer Firmware …“). Nenne Fachgebiet, Erfahrungsjahre, "
            "zwei bis drei Kernkompetenzen und einen belegten Erfolg. "
            "Gib ausschließlich den Profiltext aus."
        ),
        "en": (
            "TASK: Write a professional summary for the top of this resume. "
            "3 to 4 sentences, at most 65 words. Do not start with the name and do not use "
            "pronouns; keep it impersonal (e.g. \"Embedded engineer with six years of experience "
            "in safety-critical firmware …\"). Name the field, years of experience, two or three "
            "core competencies and one proven achievement. Output the summary text only."
        ),
    },
    "bullets": {
        "de": (
            "AUFGABE: Formuliere 3 bis 5 Stichpunkte für diese Station. "
            "Jeder Punkt beginnt mit einem starken Tätigkeitsverb, nennt die eingesetzte Technik "
            "und – sofern in den Daten vorhanden – das Ergebnis mit Zahl. Maximal 25 Wörter pro "
            "Punkt. Erfinde keine Kennzahlen. Gib eine Zeile pro Stichpunkt aus, jeweils mit "
            "„- “ beginnend, ohne weitere Ausgabe."
        ),
        "en": (
            "TASK: Write 3 to 5 bullet points for this position. "
            "Each starts with a strong action verb, names the technology used and – where present "
            "in the data – the measurable result. At most 25 words per bullet. Do not invent "
            "metrics. Output one line per bullet, each starting with \"- \", nothing else."
        ),
    },
    "proofread": {
        "de": (
            "AUFGABE: Korrigiere Rechtschreibung, Grammatik und Zeichensetzung im folgenden Text "
            "und glätte den Stil behutsam. Inhalt, Zahlen und Fachbegriffe bleiben unverändert. "
            "Behalte die Zeilenstruktur bei. Gib ausschließlich den korrigierten Text aus."
        ),
        "en": (
            "TASK: Correct spelling, grammar and punctuation in the following text and gently "
            "smooth the style. Content, numbers and technical terms stay unchanged. Keep the line "
            "structure. Output the corrected text only."
        ),
    },
    "skills": {
        "de": (
            "AUFGABE: Leite aus Erfahrung, Projekten und Ausbildung eine Kenntnis-Übersicht ab. "
            "Nutze 3 bis 5 Kategorien, die für MINT-Lebensläufe üblich sind (z. B. "
            "Programmiersprachen, Werkzeuge, Plattformen, Methoden, Normen). Nenne nur Kenntnisse, "
            "die aus den Daten hervorgehen. Format pro Zeile exakt: "
            "Kategorie: Eintrag, Eintrag, Eintrag. Keine weitere Ausgabe."
        ),
        "en": (
            "TASK: Derive a skills overview from the experience, projects and education. "
            "Use 3 to 5 categories common in STEM resumes (e.g. programming languages, tools, "
            "platforms, methods, standards). Only list skills supported by the data. "
            "Format per line exactly: Category: item, item, item. Nothing else."
        ),
    },
    "match": {
        "de": (
            "AUFGABE: Vergleiche den Lebenslauf mit der Stellenanzeige. Gib aus:\n"
            "1) PASSUNG: eine Zeile mit Einschätzung in Prozent und Begründung in einem Satz.\n"
            "2) STÄRKEN: drei Stichpunkte, die im Lebenslauf hervorgehoben werden sollten.\n"
            "3) LÜCKEN: bis zu drei fehlende Anforderungen, jeweils mit einem konkreten Vorschlag, "
            "wie sie aus vorhandener Erfahrung belegt werden können.\n"
            "4) SCHLÜSSELBEGRIFFE: bis zu zehn Begriffe aus der Anzeige, die im Lebenslauf fehlen.\n"
            "Nutze schlichte Zeilen ohne Markdown."
        ),
        "en": (
            "TASK: Compare the resume with the job posting. Output:\n"
            "1) MATCH: one line with a percentage estimate and a one-sentence rationale.\n"
            "2) STRENGTHS: three bullets that the resume should highlight.\n"
            "3) GAPS: up to three missing requirements, each with a concrete suggestion for "
            "evidencing it from existing experience.\n"
            "4) KEYWORDS: up to ten terms from the posting that are missing in the resume.\n"
            "Use plain lines without Markdown."
        ),
    },
    "letter": {
        "de": (
            "AUFGABE: Schreibe den Fließtext eines Bewerbungsanschreibens. "
            "Vier Absätze, insgesamt höchstens 280 Wörter, getrennt durch Leerzeilen:\n"
            "1) Einstieg: konkreter Bezug zur Stelle und zum Unternehmen, kein "
            "„hiermit bewerbe ich mich“.\n"
            "2) Fachlicher Kern: der stärkste passende Nachweis aus dem Lebenslauf, "
            "mit Technik und Kennzahl.\n"
            "3) Zweiter Nachweis, der eine andere Anforderung der Stelle abdeckt.\n"
            "4) Kurzer Schluss mit Gesprächswunsch.\n"
            "Beginne ohne Anrede und ende ohne Grußformel – beides steht bereits im "
            "Dokument. Der erste Absatz schließt an die Anrede an und beginnt daher "
            "klein. Nutze nur Fakten aus dem Lebenslauf."
        ),
        "en": (
            "TASK: Write the body of a cover letter. Four paragraphs, at most 280 words "
            "in total, separated by blank lines:\n"
            "1) Opening: a concrete link to the role and the company, no "
            "\"I hereby apply\".\n"
            "2) Core evidence: the strongest matching proof from the resume, with "
            "technology and a metric.\n"
            "3) A second proof covering a different requirement of the role.\n"
            "4) A short closing expressing interest in a conversation.\n"
            "Start without a salutation and end without a sign-off – the document "
            "already contains both. Use only facts from the resume."
        ),
    },
    "review": {
        "de": (
            "AUFGABE: Prüfe diesen MINT-Lebenslauf wie eine erfahrene Recruiterin. Nenne fünf "
            "konkrete Schwachstellen mit jeweils einer direkt umsetzbaren Korrektur. Achte auf "
            "fehlende Kennzahlen, schwache Verben, Lücken im Zeitverlauf, unklare "
            "Technologieangaben und Länge. Ein Befund pro Zeile, Format: Befund → Korrektur."
        ),
        "en": (
            "TASK: Review this STEM resume like an experienced recruiter. Name five concrete "
            "weaknesses, each with a directly actionable fix. Watch for missing metrics, weak "
            "verbs, timeline gaps, vague technology claims and length. One finding per line, "
            "format: Finding → Fix."
        ),
    },
}

HEADINGS = {
    "de": {"experience": "BERUFSERFAHRUNG", "education": "AUSBILDUNG", "projects": "PROJEKTE",
           "skills": "KENNTNISSE", "languages": "SPRACHEN", "posting": "STELLENANZEIGE",
           "target": "ZU ÜBERARBEITENDE STATION", "current": "Aktuelle Stichpunkte",
           "none": "(noch keine)", "tech": "Technologien", "context": "KONTEXT",
           "name": "Name", "role": "Zielposition", "summary": "Kurzprofil",
           "text": "TEXT", "task": "AUFGABE", "grade": "Note",
           "company": "Unternehmen", "subject": "Betreff", "position": "BEWORBENE STELLE",
           "tailor": "Richte den Text auf die Stellenanzeige aus."},
    "en": {"experience": "EXPERIENCE", "education": "EDUCATION", "projects": "PROJECTS",
           "skills": "SKILLS", "languages": "LANGUAGES", "posting": "JOB POSTING",
           "target": "POSITION TO REWRITE", "current": "Current bullets",
           "none": "(none yet)", "tech": "Technologies", "context": "CONTEXT",
           "name": "Name", "role": "Target role", "summary": "Summary",
           "text": "TEXT", "task": "TASK", "grade": "Grade",
           "company": "Company", "subject": "Subject", "position": "ROLE APPLIED FOR",
           "tailor": "Tailor the text to the job posting."},
}


def _join(values) -> str:
    return ", ".join(str(v) for v in values if str(v).strip())


def _date(entry: dict, language: str) -> str:
    from .render import date_range
    return date_range(entry.get("from"), entry.get("to"), language)


def resume_text(data: dict, brief: bool = False) -> str:
    """Compact plain-text version of the resume, used as model context."""
    language = data["meta"].get("language", "de")
    words = HEADINGS[language]
    person = data.get("person", {})
    lines = [
        f"{words['name']}: {person.get('firstName', '')} {person.get('lastName', '')}".strip(),
        f"{words['role']}: {person.get('position', '')}",
    ]
    if data.get("summary"):
        lines.append(f"{words['summary']}: {data['summary']}")

    lines.append(f"\n{words['experience']}:")
    for entry in data.get("experience", []):
        lines.append(f"- {entry.get('position', '')} @ {entry.get('company', '')} "
                     f"({_date(entry, language)})")
        if not brief:
            for bullet in entry.get("bullets", []):
                lines.append(f"    * {bullet}")
        if entry.get("tech"):
            lines.append(f"    {words['tech']}: {_join(entry['tech'])}")

    lines.append(f"\n{words['education']}:")
    for entry in data.get("education", []):
        line = (f"- {entry.get('degree', '')}, {entry.get('institution', '')} "
                f"({_date(entry, language)})")
        if entry.get("grade"):
            line += f", {words['grade']} {entry['grade']}"
        lines.append(line)
        if entry.get("details") and not brief:
            lines.append(f"    {entry['details']}")

    if data.get("projects"):
        lines.append(f"\n{words['projects']}:")
        for entry in data["projects"]:
            lines.append(f"- {entry.get('name', '')} ({entry.get('role', '')}): "
                         f"{entry.get('description', '')} [{_join(entry.get('tech', []))}]")

    if data.get("skills"):
        lines.append(f"\n{words['skills']}:")
        for group in data["skills"]:
            names = _join(item.get("name", "") for item in group.get("items", []))
            lines.append(f"- {group.get('category', '')}: {names}")

    if data.get("languages"):
        labels = []
        for entry in data["languages"]:
            level = next((p[language] for p in PROFICIENCY if p["id"] == entry.get("proficiency")),
                         entry.get("proficiencyLabel", ""))
            labels.append(f"{entry.get('name', '')} ({level})")
        lines.append(f"\n{words['languages']}: {_join(labels)}")
    return "\n".join(lines)


def build(action: str, data: dict, options: dict) -> tuple[str, str, str, bool]:
    """Return (system prompt, user prompt, result kind, directly applicable).

    Result kind drives how the frontend applies the answer:
    text | bullets | skills | report
    """
    language = data["meta"].get("language", "de")
    words = HEADINGS[language]
    system = SYSTEM[language]
    context = resume_text(data)
    posting = (options.get("posting") or "").strip()
    posting_block = f"\n\n{words['posting']}:\n{posting}" if posting else ""

    if action == "summary":
        task = TASKS["summary"][language]
        if posting:
            task = f"{task} {words['tailor']}"
        return system, f"{context}{posting_block}\n\n{task}", "text", True

    if action == "bullets":
        entries = data.get("experience", [])
        index = int(options.get("index", 0))
        entry = entries[index] if 0 <= index < len(entries) else {}
        current = "\n".join(f"- {b}" for b in entry.get("bullets", []))
        prompt = (
            f"{words['context']}:\n{resume_text(data, brief=True)}{posting_block}\n\n"
            f"{words['target']}:\n{entry.get('position', '')} @ {entry.get('company', '')}\n"
            f"{words['tech']}: {_join(entry.get('tech', []))}\n"
            f"{words['current']}:\n{current or words['none']}\n\n"
            f"{TASKS['bullets'][language]}"
        )
        return system, prompt, "bullets", True

    if action == "proofread":
        prompt = f"{TASKS['proofread'][language]}\n\n{words['text']}:\n{options.get('text', '')}"
        return system, prompt, "text", True

    if action == "skills":
        return system, f"{context}{posting_block}\n\n{TASKS['skills'][language]}", "skills", True

    if action == "letter":
        letter = data.get("letter", {})
        target = [f"{words['company']}: {letter.get('company', '')}"]
        if letter.get("subject"):
            target.append(f"{words['subject']}: {letter['subject']}")
        prompt = (
            f"{context}{posting_block}\n\n{words['position']}:\n" + "\n".join(target)
            + f"\n\n{TASKS['letter'][language]}"
        )
        return system, prompt, "letter", True

    if action == "match":
        return system, f"{context}{posting_block}\n\n{TASKS['match'][language]}", "report", False

    if action == "review":
        return system, f"{context}\n\n{TASKS['review'][language]}", "report", False

    prompt = f"{context}{posting_block}\n\n{words['task']}: {options.get('text', '')}"
    return system, prompt, "report", False


def parse_lines(answer: str) -> list[str]:
    """Strip bullet and numbering prefixes from a model answer."""
    lines = []
    for raw in answer.splitlines():
        line = raw.strip()
        if not line:
            continue
        while line[:1] in "-•*–—":
            line = line[1:].strip()
        if line[:2].strip().rstrip(".)").isdigit():
            head, _, rest = line.partition(" ")
            if head.rstrip(".)").isdigit():
                line = rest.strip()
        if line:
            lines.append(line)
    return lines


def parse_skills(answer: str) -> list[dict]:
    groups = []
    for line in parse_lines(answer):
        if ":" not in line:
            continue
        category, _, rest = line.partition(":")
        items = [{"name": part.strip(), "level": 4} for part in rest.split(",") if part.strip()]
        if category.strip() and items:
            groups.append({"category": category.strip(), "items": items})
    return groups
