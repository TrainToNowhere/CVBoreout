"""Turns the document model into print-ready HTML (the basis for PDF and preview)."""

from __future__ import annotations

from html import escape
from datetime import date as _date

from .model import (ATTACHMENTS_LABEL, CLOSING, PRESENT, PROFICIENCY,
                    SALUTATION)

# --- Small helpers --------------------------------------------------------


def e(value) -> str:
    return escape(str(value or "")).strip()


def multiline(value) -> str:
    return e(value).replace("\n", "<br>")


def date_word(value: str, language: str) -> str:
    if str(value or "").strip().lower() == "present":
        return PRESENT.get(language, "present")
    return e(value)


def date_range(start, end, language: str) -> str:
    start, end = date_word(start, language), date_word(end, language)
    if start and end:
        return f"{start} – {end}"
    return start or end


def proficiency_label(entry: dict, language: str) -> str:
    key = entry.get("proficiency", "")
    if key == "custom":
        return e(entry.get("proficiencyLabel", ""))
    for level in PROFICIENCY:
        if level["id"] == key:
            return e(level[language])
    return e(entry.get("proficiencyLabel", ""))


ICONS = {
    "mail": "M2 4h12v8H2z M2 4l6 4.5L14 4",
    "phone": "M3 2.5h3l1.2 3-1.7 1.2a9 9 0 0 0 4 4L10.5 9l3 1.2v3a1 1 0 0 1-1.1 1A11.5 11.5 0 0 1 2 3.6 1 1 0 0 1 3 2.5z",
    "pin": "M8 14s5-4.5 5-8A5 5 0 0 0 3 6c0 3.5 5 8 5 8z M8 7.5h.01",
    "link": "M6.5 9.5a3 3 0 0 0 4.2 0l2-2a3 3 0 0 0-4.2-4.2l-1 1 M9.5 6.5a3 3 0 0 0-4.2 0l-2 2a3 3 0 0 0 4.2 4.2l1-1",
    "cal": "M2.5 3.5h11v10h-11z M2.5 6.5h11 M5.5 2v3 M10.5 2v3",
    "user": "M8 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6z M2.5 14a5.5 5.5 0 0 1 11 0",
}


def icon(name: str, size: str = "1em") -> str:
    path = ICONS.get(name)
    if not path:
        return ""
    return (
        f'<svg class="ic" viewBox="0 0 16 16" width="{size}" height="{size}" '
        f'fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" '
        f'stroke-linejoin="round"><path d="{path}"/></svg>'
    )


def dots(level: int, on: str, off: str) -> str:
    level = max(0, min(5, int(level or 0)))
    return '<span class="dots">' + "".join(
        f'<span class="dot" style="background:{on if i < level else off}"></span>'
        for i in range(5)
    ) + "</span>"


def _luminance(color: str) -> float:
    """WCAG relative luminance of a #rrggbb colour."""
    value = color.strip().lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    try:
        channels = [int(value[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    except ValueError:
        return 0.0
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


DARK_INK = "18, 24, 31"
LIGHT_INK = "255, 255, 255"


def ink_channels(background: str) -> str:
    """Lettering that stays readable on the given background."""
    return DARK_INK if _luminance(background) > 0.2 else LIGHT_INK


DENSITY = {
    "tight": {"gap": 3.0, "line": 1.32, "section": 4.4},
    "normal": {"gap": 4.2, "line": 1.45, "section": 6.0},
    "airy": {"gap": 5.4, "line": 1.6, "section": 7.6},
}

# Page geometry in millimetres. The top margin is set on @page (not as padding)
# so that continuation pages keep the same inset as the first one.
PAGE_TOP = 13.0
PAGE_BOTTOM = 11.0
SIDEBAR_WIDTH = 66.0


# --- Section renderers ----------------------------------------------------


def _experience(entries, meta) -> str:
    language = meta.get("language", "de")
    parts = []
    for entry in entries:
        bullets = "".join(f"<li>{multiline(b)}</li>" for b in entry.get("bullets", []) if e(b))
        tech = [t for t in (entry.get("tech") or []) if e(t)]
        chips = ('<div class="chips">' + "".join(f'<span class="chip">{e(t)}</span>' for t in tech)
                 + "</div>") if tech else ""
        subtitle = " · ".join(x for x in [e(entry.get("company")), e(entry.get("location"))] if x)
        parts.append(
            '<div class="entry">'
            f'<div class="when">{date_range(entry.get("from"), entry.get("to"), language)}</div>'
            '<div class="what">'
            f'<div class="headline">{e(entry.get("position"))}</div>'
            f'<div class="subline">{subtitle}</div>'
            + (f"<ul>{bullets}</ul>" if bullets else "")
            + chips
            + "</div></div>"
        )
    return "".join(parts)


def _education(entries, meta) -> str:
    language = meta.get("language", "de")
    grade_word = "Note" if language == "de" else "Grade"
    parts = []
    for entry in entries:
        subtitle = " · ".join(
            x for x in [e(entry.get("institution")), e(entry.get("location"))] if x
        )
        if e(entry.get("grade")):
            subtitle = f'{subtitle} · {grade_word} {e(entry["grade"])}' if subtitle else \
                f'{grade_word} {e(entry["grade"])}'
        details = multiline(entry.get("details"))
        parts.append(
            '<div class="entry">'
            f'<div class="when">{date_range(entry.get("from"), entry.get("to"), language)}</div>'
            '<div class="what">'
            f'<div class="headline">{e(entry.get("degree"))}</div>'
            f'<div class="subline">{subtitle}</div>'
            + (f'<div class="prose">{details}</div>' if details else "")
            + "</div></div>"
        )
    return "".join(parts)


def _projects(entries, meta) -> str:
    language = meta.get("language", "de")
    parts = []
    for entry in entries:
        tech = [t for t in (entry.get("tech") or []) if e(t)]
        chips = ('<div class="chips">' + "".join(f'<span class="chip">{e(t)}</span>' for t in tech)
                 + "</div>") if tech else ""
        subtitle = " · ".join(x for x in [e(entry.get("role")), e(entry.get("link"))] if x)
        parts.append(
            '<div class="entry">'
            f'<div class="when">{date_range(entry.get("from"), entry.get("to"), language)}</div>'
            '<div class="what">'
            f'<div class="headline">{e(entry.get("name"))}</div>'
            + (f'<div class="subline">{subtitle}</div>' if subtitle else "")
            + (f'<div class="prose">{multiline(entry.get("description"))}</div>'
               if e(entry.get("description")) else "")
            + chips
            + "</div></div>"
        )
    return "".join(parts)


def _publications(entries, meta) -> str:
    parts = []
    for entry in entries:
        source = " · ".join(x for x in [e(entry.get("source")), e(entry.get("link"))] if x)
        parts.append(
            '<div class="entry">'
            f'<div class="when">{e(entry.get("year"))}</div>'
            '<div class="what">'
            f'<div class="headline small">{e(entry.get("title"))}</div>'
            f'<div class="subline">{source}</div>'
            "</div></div>"
        )
    return "".join(parts)


def _skills(groups, meta, on_sidebar: bool) -> str:
    show_levels = meta.get("showLevels", True)
    on = "currentColor"
    off = "var(--sidebar-dot)" if on_sidebar else "var(--dot-off)"
    parts = []
    for group in groups:
        items = [i for i in (group.get("items") or []) if e(i.get("name"))]
        if not items:
            continue
        if show_levels:
            rows = "".join(
                f'<div class="rate"><span>{e(item.get("name"))}</span>'
                f'{dots(item.get("level", 0), on, off)}</div>'
                for item in items
            )
        else:
            rows = '<div class="prose">' + ", ".join(e(i.get("name")) for i in items) + "</div>"
        parts.append(
            f'<div class="group"><div class="group-title">{e(group.get("category"))}</div>{rows}</div>'
        )
    return "".join(parts)


def _languages(entries, meta, on_sidebar: bool) -> str:
    language = meta.get("language", "de")
    on = "currentColor"
    off = "var(--sidebar-dot)" if on_sidebar else "var(--dot-off)"
    rows = []
    for entry in entries:
        if not e(entry.get("name")):
            continue
        label = proficiency_label(entry, language)
        if meta.get("showLevels", True):
            right = dots(entry.get("level", 0), on, off)
            below = f'<div class="subline">{label}</div>' if label else ""
        else:
            right = f'<span class="subline">{label}</span>'
            below = ""
        rows.append(f'<div class="rate"><span>{e(entry.get("name"))}</span>{right}</div>{below}')
    return "".join(rows)


def _certificates(entries, meta) -> str:
    rows = []
    for entry in entries:
        if not e(entry.get("name")):
            continue
        subtitle = " · ".join(x for x in [e(entry.get("issuer")), e(entry.get("year"))] if x)
        rows.append(
            f'<div class="cert"><div class="headline small">{e(entry.get("name"))}</div>'
            f'<div class="subline">{subtitle}</div></div>'
        )
    return "".join(rows)


def _interests(entries, meta) -> str:
    values = [e(x) for x in entries if e(x)]
    return f'<div class="prose">{" · ".join(values)}</div>' if values else ""


def section_body(sid: str, data: dict, on_sidebar: bool) -> str:
    meta = data["meta"]
    if sid == "summary":
        return f'<div class="prose">{multiline(data.get("summary"))}</div>' if e(data.get("summary")) else ""
    if sid == "experience":
        return _experience(data.get("experience", []), meta)
    if sid == "education":
        return _education(data.get("education", []), meta)
    if sid == "projects":
        return _projects(data.get("projects", []), meta)
    if sid == "publications":
        return _publications(data.get("publications", []), meta)
    if sid == "skills":
        return _skills(data.get("skills", []), meta, on_sidebar)
    if sid == "languages":
        return _languages(data.get("languages", []), meta, on_sidebar)
    if sid == "certificates":
        return _certificates(data.get("certificates", []), meta)
    if sid == "interests":
        return _interests(data.get("interests", []), meta)
    return ""


def sections_html(data: dict, column: str, single_column: bool) -> str:
    parts = []
    for section in data["meta"].get("sections", []):
        if not section.get("enabled", True):
            continue
        if not single_column and section.get("column", "main") != column:
            continue
        body = section_body(section["id"], data, on_sidebar=(column == "side" and not single_column))
        if not body:
            continue
        parts.append(
            f'<section class="sec sec-{section["id"]}">'
            f'<h2>{e(section.get("title"))}</h2>{body}</section>'
        )
    return "".join(parts)


# --- Header pieces --------------------------------------------------------


def contact_lines(person: dict, language: str, with_icons: bool = True) -> list[str]:
    lines = []
    born = "geb." if language == "de" else "born"
    pairs = [
        ("mail", person.get("email")),
        ("phone", person.get("phone")),
        ("pin", person.get("location")),
    ]
    if e(person.get("birthDate")):
        pairs.append(("cal", f'{born} {e(person["birthDate"])}'))
    if e(person.get("nationality")):
        pairs.append(("user", person.get("nationality")))
    for name, value in pairs:
        if e(value):
            lines.append(f'<div class="cl">{icon(name) if with_icons else ""}<span>{e(value)}</span></div>')
    for link in person.get("links", []):
        if e(link.get("url")):
            label = e(link.get("label")) or e(link.get("url"))
            lines.append(
                f'<div class="cl">{icon("link") if with_icons else ""}'
                f'<span>{label}: {e(link.get("url"))}</span></div>'
            )
    return lines


def full_name(person: dict) -> str:
    first, last = e(person.get("firstName")), e(person.get("lastName"))
    title = e(person.get("title"))
    name = " ".join(x for x in [first, last] if x) or "—"
    return f"{name}, {title}" if title else name


def photo_html(person: dict, css_class: str = "photo") -> str:
    source = (person.get("photo") or "").strip()
    if not source:
        return ""
    return f'<div class="{css_class}"><img src="{escape(source, quote=True)}" alt=""></div>'


# --- Base stylesheet ------------------------------------------------------


def base_css(meta: dict) -> str:
    density = DENSITY.get(meta.get("density", "normal"), DENSITY["normal"])
    font = meta.get("font") or "Noto Sans"
    size = float(meta.get("fontSize") or 9.6)
    caps = "uppercase" if meta.get("uppercaseHeadings", True) else "none"
    accent = meta.get("accent", "#0F766E")
    accent_dark = meta.get("accentDark", "#0B4F4A")
    # The sidebar band and the header band can each be dark or pastel, so the
    # lettering on top of them is derived from their luminance.
    sidebar_ink = ink_channels(accent_dark)
    band_ink = ink_channels(accent)
    sidebar_heading = accent if sidebar_ink == DARK_INK else "rgb(255, 255, 255)"
    return f"""
:root {{
  --accent: {accent};
  --accent-dark: {accent_dark};
  --sidebar-ink: rgb({sidebar_ink});
  --sidebar-soft: rgba({sidebar_ink}, .78);
  --sidebar-line: rgba({sidebar_ink}, .32);
  --sidebar-heading: {sidebar_heading};
  --band-ink: rgb({band_ink});
  --band-soft: rgba({band_ink}, .82);
  --band-line: rgba({band_ink}, .4);
  --dot-off: rgba(0, 0, 0, .14);
  --sidebar-dot: rgba({sidebar_ink}, .26);
  --gap: {density['gap']}mm;
  --section: {density['section']}mm;
  --text: #1b2027;
  --muted: #5b6472;
  --rule: #d9dee5;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  font-family: "{font}", "Noto Sans", "Liberation Sans", sans-serif;
  font-size: {size}pt;
  line-height: {density['line']};
  color: var(--text);
  hyphens: auto;
}}
h1, h2, h3 {{ margin: 0; font-weight: 700; }}
p {{ margin: 0; }}
ul {{ margin: 1.2mm 0 0; padding-left: 4.2mm; }}
li {{ margin-bottom: 1.1mm; }}
li::marker {{ color: var(--accent); }}
a {{ color: inherit; text-decoration: none; }}
.ic {{ vertical-align: -0.12em; flex: none; }}

.sec {{ margin-bottom: var(--section); }}
.sec:last-child {{ margin-bottom: 0; }}
.sec h2 {{
  font-size: 1.02em; letter-spacing: .06em; text-transform: {caps};
  color: var(--accent); margin-bottom: 2.2mm;
}}
.entry {{ display: flex; gap: 4mm; margin-bottom: var(--gap); break-inside: avoid; }}
.entry:last-child {{ margin-bottom: 0; }}
.when {{ width: 24mm; flex: none; color: var(--muted); font-size: .92em; padding-top: .2mm; }}
.what {{ flex: 1; min-width: 0; }}
.headline {{ font-weight: 700; }}
.headline.small {{ font-weight: 600; }}
.subline {{ color: var(--muted); font-size: .94em; }}
.prose {{ margin-top: .8mm; text-align: justify; }}
.chips {{ margin-top: 1.4mm; }}
.chip {{
  display: inline-block; font-size: .82em; padding: .3mm 1.6mm; margin: 0 1.2mm 1.2mm 0;
  border: .25mm solid var(--rule); border-radius: 1mm; color: var(--muted);
}}
.group {{ margin-bottom: 2.6mm; }}
.group:last-child {{ margin-bottom: 0; }}
.group-title {{ font-weight: 700; font-size: .92em; margin-bottom: 1mm; }}
.rate {{ display: flex; align-items: center; justify-content: space-between; gap: 2mm; margin-bottom: .8mm; }}
.dots {{ display: flex; gap: .8mm; flex: none; }}
.dot {{ width: 1.5mm; height: 1.5mm; border-radius: 50%; display: block; }}
.cert {{ margin-bottom: 2.2mm; break-inside: avoid; }}
.cl {{ display: flex; gap: 1.8mm; align-items: flex-start; margin-bottom: 1.4mm; word-break: break-word; }}
.photo img {{ width: 100%; height: 100%; object-fit: cover; }}
"""


def footer_css(meta: dict, person: dict, active: bool, right_margin: str = "14mm") -> str:
    """Page margins; with page numbers the bottom margin holds the footer."""
    bottom = PAGE_BOTTOM if active else PAGE_BOTTOM
    if not active:
        return f"@page {{ margin: {PAGE_TOP}mm 0 {bottom}mm 0; }}"
    label = e(full_name(person))
    word = "Seite" if meta.get("language", "de") == "de" else "Page"
    return f"""
@page {{
  margin: {PAGE_TOP}mm 0 {bottom}mm 0;
  @bottom-right {{
    content: "{label} · {word} " counter(page) " / " counter(pages);
    font-family: "{meta.get('font', 'Noto Sans')}", sans-serif;
    font-size: 7.4pt; color: #8b95a3; margin-right: {right_margin}; margin-bottom: 2mm;
  }}
}}
"""


# --- Templates ------------------------------------------------------------


def template_modern(data: dict, page_numbers: bool):
    meta, person = data["meta"], data["person"]
    css = f"""
@page {{ size: A4; background: #fff; }}
{footer_css(meta, person, page_numbers)}
/* Fixed boxes repeat on every page; the negative offsets let the band bleed
   into the page margins so it reaches the top and bottom edge. */
.band {{
  position: fixed; left: 0; top: -{PAGE_TOP}mm; bottom: -{PAGE_BOTTOM}mm;
  width: {SIDEBAR_WIDTH}mm; background: var(--accent-dark);
}}
.side {{ width: {SIDEBAR_WIDTH}mm; float: left; padding: 0 8mm;
        color: var(--sidebar-ink); position: relative; }}
.main {{ margin-left: {SIDEBAR_WIDTH}mm; padding: 0 12mm; }}
.side .sec h2 {{ color: var(--sidebar-heading); border-bottom: .35mm solid var(--sidebar-line);
                padding-bottom: 1.2mm; }}
.side .subline, .side .prose, .side .cl {{ color: var(--sidebar-soft); }}
.side .chip {{ border-color: var(--sidebar-line); color: var(--sidebar-soft); }}
.side li::marker {{ color: var(--sidebar-soft); }}
.head {{ margin-bottom: var(--section); }}
.head h1 {{ font-size: 2.05em; line-height: 1.1; letter-spacing: -.01em; }}
.head .role {{ color: var(--accent); font-weight: 600; font-size: 1.12em; margin-top: 1.2mm; }}
.head .rule {{ height: .8mm; width: 18mm; background: var(--accent); margin-top: 3mm; }}
.photo {{ width: 34mm; height: 34mm; border-radius: 50%; overflow: hidden; margin: 0 auto 6mm;
         border: .8mm solid var(--sidebar-line); }}
.contact {{ margin-bottom: var(--section); font-size: .95em; }}
"""
    head = (
        '<div class="head">'
        f'<h1>{e(full_name(person))}</h1>'
        + (f'<div class="role">{e(person.get("position"))}</div>' if e(person.get("position")) else "")
        + '<div class="rule"></div></div>'
    )
    contact = "".join(contact_lines(person, meta.get("language", "de")))
    return css, (
        '<div class="band"></div>'
        f'<aside class="side">{photo_html(person)}'
        f'<div class="contact">{contact}</div>'
        f'{sections_html(data, "side", False)}</aside>'
        f'<main class="main">{head}{sections_html(data, "main", False)}</main>'
    )


def template_classic(data: dict, page_numbers: bool):
    meta, person = data["meta"], data["person"]
    css = f"""
@page {{ size: A4; background: #fff; }}
{footer_css(meta, person, page_numbers, right_margin='20mm')}
body {{ padding: 0 20mm; }}
.head {{ display: flex; gap: 8mm; align-items: flex-start;
        border-bottom: .6mm solid var(--accent); padding-bottom: 4mm; margin-bottom: var(--section); }}
.head .text {{ flex: 1; }}
.head h1 {{ font-size: 2.1em; line-height: 1.08; }}
.head .role {{ color: var(--accent); font-weight: 600; font-size: 1.1em; margin-top: 1mm; }}
.contact {{ width: 62mm; flex: none; font-size: .9em; color: var(--muted); }}
.photo {{ width: 30mm; height: 38mm; overflow: hidden; flex: none; border-radius: 1.5mm; }}
.sec h2 {{ border-bottom: .3mm solid var(--rule); padding-bottom: 1.4mm; }}
.sec-skills .group, .sec-languages {{ break-inside: avoid; }}
"""
    head = (
        '<div class="head">'
        + photo_html(person)
        + '<div class="text">'
        f'<h1>{e(full_name(person))}</h1>'
        + (f'<div class="role">{e(person.get("position"))}</div>' if e(person.get("position")) else "")
        + "</div>"
        f'<div class="contact">{"".join(contact_lines(person, meta.get("language", "de")))}</div>'
        "</div>"
    )
    return css, f"{head}{sections_html(data, 'main', True)}"


def template_compact(data: dict, page_numbers: bool):
    meta, person = data["meta"], data["person"]
    side = 58
    css = f"""
@page {{ size: A4; background: #fff; }}
{footer_css(meta, person, page_numbers)}
@page :first {{ margin-top: 0; }}
.band {{ background: var(--accent); color: var(--band-ink); padding: 9mm 14mm; display: flex;
        gap: 8mm; align-items: center; }}
.band h1 {{ font-size: 1.95em; line-height: 1.1; }}
.band .role {{ font-size: 1.05em; color: var(--band-soft); margin-top: .8mm; }}
.band .text {{ flex: 1; }}
.band .contact {{ width: 62mm; flex: none; font-size: .86em; color: var(--band-soft); }}
.band .cl {{ margin-bottom: 1mm; }}
.photo {{ width: 26mm; height: 26mm; border-radius: 50%; overflow: hidden; flex: none;
         border: .6mm solid var(--band-line); }}
.body {{ padding: 9mm 14mm 0; }}
.side {{ float: right; width: {side}mm; padding-left: 8mm; border-left: .3mm solid var(--rule); }}
.main {{ margin-right: {side}mm; padding-right: 8mm; }}
.entry {{ gap: 3mm; }}
.when {{ width: 21mm; }}
.side .entry {{ display: block; }}
.side .when {{ width: auto; }}
"""
    head = (
        '<div class="band">'
        + photo_html(person)
        + '<div class="text">'
        f'<h1>{e(full_name(person))}</h1>'
        + (f'<div class="role">{e(person.get("position"))}</div>' if e(person.get("position")) else "")
        + "</div>"
        f'<div class="contact">{"".join(contact_lines(person, meta.get("language", "de")))}</div></div>'
    )
    return css, (
        f'{head}<div class="body">'
        f'<aside class="side">{sections_html(data, "side", False)}</aside>'
        f'<main class="main">{sections_html(data, "main", False)}</main></div>'
    )


TEMPLATE_FUNCTIONS = {
    "modern": template_modern,
    "classic": template_classic,
    "compact": template_compact,
}


def render_html(data: dict, page_numbers: bool | None = None) -> str:
    meta = data["meta"]
    if page_numbers is None:
        page_numbers = bool(meta.get("pageNumbers", True))
    build = TEMPLATE_FUNCTIONS.get(meta.get("template", "modern"), template_modern)
    template_css, body = build(data, page_numbers)
    language = e(meta.get("language", "de")) or "de"
    title = e(full_name(data["person"]))
    return (
        f"<!DOCTYPE html><html lang='{language}'><head><meta charset='utf-8'>"
        f"<title>{title}</title>"
        f"<style>{base_css(meta)}{template_css}</style></head>"
        f"<body class='template-{e(meta.get('template', 'modern'))}'>{body}</body></html>"
    )


# --- Cover letter ---------------------------------------------------------

# DIN 5008 keeps a wide binding margin on the left.
LETTER_MARGINS = {"top": 18.0, "right": 20.0, "bottom": 18.0, "left": 25.0}


def letter_date(letter: dict, language: str) -> str:
    """Explicit date, otherwise today in the document language."""
    given = e(letter.get("date"))
    if given:
        return given
    today = _date.today()
    if language == "de":
        return today.strftime("%d.%m.%Y")
    return f"{today.day} {today.strftime('%B %Y')}"


def letter_paragraphs(body: str) -> str:
    """Blank lines separate paragraphs, single line breaks stay inside one."""
    chunks = [chunk.strip() for chunk in str(body or "").split("\n\n")]
    return "".join(f"<p>{multiline(chunk)}</p>" for chunk in chunks if chunk.strip())


def _letter_head(data: dict, template: str) -> str:
    person = data["person"]
    language = data["meta"].get("language", "de")
    contact = "".join(contact_lines(person, language))
    name = f'<h1>{e(full_name(person))}</h1>'
    role = (f'<div class="role">{e(person.get("position"))}</div>'
            if e(person.get("position")) else "")

    if template == "compact":
        return (f'<div class="lhead band">{photo_html(person, "photo small")}'
                f'<div class="text">{name}{role}</div>'
                f'<div class="contact">{contact}</div></div>')
    if template == "modern":
        return (f'<div class="lhead modern"><div class="text">{name}{role}'
                '<div class="rule"></div></div>'
                f'<div class="contact">{contact}</div></div>')
    return (f'<div class="lhead classic"><div class="text">{name}{role}</div>'
            f'<div class="contact">{contact}</div></div>')


def letter_css(meta: dict) -> str:
    margins = LETTER_MARGINS
    return f"""
@page {{
  size: A4;
  margin: {margins['top']}mm {margins['right']}mm {margins['bottom']}mm {margins['left']}mm;
  background: #fff;
}}
body {{ padding: 0; }}
.lhead {{ display: flex; gap: 8mm; align-items: flex-start; margin-bottom: 6mm; }}
.lhead .text {{ flex: 1; }}
.lhead h1 {{ font-size: 1.7em; line-height: 1.1; }}
.lhead .role {{ color: var(--accent); font-weight: 600; margin-top: .8mm; }}
.lhead .contact {{ width: 58mm; flex: none; font-size: .88em; color: var(--muted); }}
.lhead.classic {{ border-bottom: .6mm solid var(--accent); padding-bottom: 3.5mm; }}
.lhead.modern .rule {{ height: .8mm; width: 18mm; background: var(--accent); margin-top: 2.5mm; }}
.lhead.band {{
  background: var(--accent); color: var(--band-ink); padding: 6mm; border-radius: 1.5mm;
  align-items: center;
}}
.lhead.band .role, .lhead.band .contact {{ color: var(--band-soft); }}
.photo.small {{ width: 22mm; height: 22mm; border-radius: 50%; overflow: hidden; flex: none; }}

.recipient {{ margin-top: 8mm; min-height: 32mm; line-height: 1.5; }}
.recipient .reference {{ color: var(--muted); margin-top: 2mm; font-size: .92em; }}
.dateline {{ text-align: right; margin-bottom: 6mm; }}
.subject {{ font-weight: 700; font-size: 1.05em; margin-bottom: 5mm; }}
.letter-body p {{ margin-bottom: 3.6mm; text-align: justify; }}
.letter-body p:last-child {{ margin-bottom: 0; }}
.salutation {{ margin-bottom: 3.6mm; }}
.closing {{ margin-top: 7mm; }}
.closing .name {{ margin-top: 12mm; }}
.attachments {{ margin-top: 9mm; font-size: .9em; color: var(--muted); }}
"""


def render_letter(data: dict) -> str:
    meta, person, letter = data["meta"], data["person"], data.get("letter", {})
    language = meta.get("language", "de")
    template = meta.get("template", "modern")

    recipient = "".join(
        f"<div>{e(value)}</div>"
        for value in [letter.get("company"), letter.get("contactName"),
                      letter.get("street"), letter.get("city")]
        if e(value)
    )
    if e(letter.get("reference")):
        recipient += f'<div class="reference">{e(letter["reference"])}</div>'

    where = e(letter.get("senderCity")) or e(person.get("location"))
    when = letter_date(letter, language)
    dateline = f"{where}, {when}" if where else when

    salutation = e(letter.get("salutation")) or SALUTATION[language]
    closing = e(letter.get("closing")) or CLOSING[language]
    attachments = [e(a) for a in letter.get("attachments", []) if e(a)]
    attachment_block = (
        f'<div class="attachments">{ATTACHMENTS_LABEL[language]}: {", ".join(attachments)}</div>'
        if attachments else ""
    )

    body = (
        f'{_letter_head(data, template)}'
        f'<div class="recipient">{recipient}</div>'
        f'<div class="dateline">{dateline}</div>'
        + (f'<div class="subject">{e(letter.get("subject"))}</div>'
           if e(letter.get("subject")) else "")
        + f'<div class="salutation">{salutation}</div>'
        f'<div class="letter-body">{letter_paragraphs(letter.get("body"))}</div>'
        f'<div class="closing">{closing}'
        f'<div class="name">{e(full_name(person))}</div></div>'
        f"{attachment_block}"
    )
    return (
        f"<!DOCTYPE html><html lang='{e(language) or 'de'}'><head><meta charset='utf-8'>"
        f"<title>{e(letter.get('subject')) or e(full_name(person))}</title>"
        f"<style>{base_css(meta)}{letter_css(meta)}</style></head>"
        f"<body class='letter template-{e(template)}'>{body}</body></html>"
    )
