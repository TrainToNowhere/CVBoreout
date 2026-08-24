"""Self-test: renders every template and checks the results."""

from __future__ import annotations

import base64
import copy
import json
import sys
import time
from pathlib import Path

from cvboreout import model, pdf, prompts, providers, render, settings

OUT = Path("export/test")


def _contrast(first: str, second: str) -> float:
    values = sorted(render._luminance(color) for color in (first, second))
    return (values[1] + 0.05) / (values[0] + 0.05)


def check(condition: bool, message: str) -> bool:
    print(f"  {'✓' if condition else '✗'} {message}")
    return condition


def _first_ink_mm(page) -> float:
    """Distance from the top edge to the first content pixel of the main column."""
    image = page.render(scale=1.0).to_pil().convert("L")
    width, height = image.size
    pixels = image.load()
    left = int(width * 0.45)          # skip the coloured sidebar band
    for y in range(height):
        for x in range(left, width, 3):
            if pixels[x, y] < 128:
                return y / height * 297.0
    return 297.0


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    failures = 0
    data = model.normalize(copy.deepcopy(model.SAMPLE))
    sample_name = data["person"]["lastName"]
    sample_company = data["experience"][0]["company"]
    sample_recipient = data["letter"]["company"]

    for template in (entry["id"] for entry in model.TEMPLATES):
        print(f"\nTemplate „{template}“")
        variant = copy.deepcopy(data)
        variant["meta"]["template"] = template
        started = time.time()
        html = render.render_html(variant)
        doc = pdf.document(variant)
        raw = doc.write_pdf()
        elapsed = time.time() - started

        (OUT / f"{template}.html").write_text(html, encoding="utf-8")
        (OUT / f"{template}.pdf").write_bytes(raw)
        images = pdf.page_images(raw, 1.2)
        for number, image in enumerate(images):
            (OUT / f"{template}-{number + 1}.jpg").write_bytes(
                base64.b64decode(image.split(",", 1)[1]))

        failures += not check(raw.startswith(b"%PDF"), "PDF produced")
        failures += not check(1 <= len(doc.pages) <= 3, f"{len(doc.pages)} page(s)")
        failures += not check(len(images) == len(doc.pages), "preview images complete")
        failures += not check(sample_name in html and sample_company in html,
                              "content in the HTML")
        failures += not check(elapsed < 5, f"render time {elapsed:.2f}s")

    print("\nLayout")
    long_cv = copy.deepcopy(data)
    long_cv["experience"] = long_cv["experience"] * 4
    raw = pdf.pdf_bytes(long_cv)
    import pypdfium2 as pdfium

    pages = pdfium.PdfDocument(raw)
    failures += not check(len(pages) >= 2, f"multi-page resume ({len(pages)} pages)")
    top_mm = _first_ink_mm(pages[1])
    (OUT / "page2.jpg").write_bytes(base64.b64decode(pdf.page_images(raw, 1.0)[1].split(",", 1)[1]))
    failures += not check(8 <= top_mm <= 22, f"page 2 keeps its top margin ({top_mm:.1f} mm)")
    pages.close()

    print("\nCover letter")
    letter_doc = pdf.document(data, "letter")
    letter_html = render.render_letter(data)
    (OUT / "letter.pdf").write_bytes(letter_doc.write_pdf())
    (OUT / "letter.html").write_text(letter_html, encoding="utf-8")
    failures += not check(len(letter_doc.pages) == 1, f"letter fits one page ({len(letter_doc.pages)})")
    failures += not check(sample_recipient in letter_html and "Kennziffer" in letter_html,
                          "recipient block rendered")
    failures += not check("Sehr geehrte Damen und Herren," in letter_html
                          and "Mit freundlichen Grüßen" in letter_html, "defaults filled in")
    failures += not check(letter_html.count("<p>") == 4, "paragraphs split on blank lines")
    failures += not check("Anlagen: Lebenslauf" in letter_html, "enclosures listed")

    combined = pdf.document(data, "both")
    resume_pages = len(pdf.document(data, "resume").pages)
    failures += not check(len(combined.pages) == resume_pages + 1,
                          f"combined PDF has {len(combined.pages)} pages")
    failures += not check(pdf.pdf_bytes(data, "both").startswith(b"%PDF"), "combined PDF writes")

    english_letter = copy.deepcopy(data)
    english_letter["meta"]["language"] = "en"
    html_en = render.render_letter(english_letter)
    failures += not check("Dear Sir or Madam," in html_en and "Kind regards" in html_en,
                          "English letter defaults")

    custom = copy.deepcopy(data)
    custom["letter"]["salutation"] = "Sehr geehrte Frau Sturm,"
    custom["letter"]["date"] = "01.09.2026"
    html_custom = render.render_letter(custom)
    failures += not check("Sehr geehrte Frau Sturm," in html_custom
                          and "München, 01.09.2026" in html_custom, "custom salutation and date")

    empty_letter = model.normalize({})
    failures += not check(pdf.pdf_bytes(empty_letter, "letter").startswith(b"%PDF"),
                          "empty letter renders")

    _, letter_prompt, letter_kind, letter_apply = prompts.build("letter", data, {"posting": "EtherCAT"})
    failures += not check(letter_kind == "letter" and letter_apply
                          and sample_recipient in letter_prompt, "letter prompt")

    print("\nSpecial cases")
    blank = model.normalize({})
    failures += not check(pdf.pdf_bytes(blank).startswith(b"%PDF"), "empty resume renders")

    english = copy.deepcopy(data)
    english["meta"]["language"] = "en"
    english = model.retitle_sections(english, "en")
    html = render.render_html(english)
    failures += not check("Experience" in html and "present" in html, "English document")
    failures += not check("Kurzprofil" not in html, "no German titles left")

    unsafe = copy.deepcopy(blank)
    unsafe["person"]["firstName"] = "<script>alert(1)</script>"
    failures += not check("<script>" not in render.render_html(unsafe), "HTML is escaped")

    print("\nPalette")
    failures += not check(len(model.ACCENTS) >= 16, f"{len(model.ACCENTS)} accent presets")
    worst_accent, worst_band = 99.0, 99.0
    for accent in model.ACCENTS:
        worst_accent = min(worst_accent, _contrast(accent["color"], "#ffffff"))
        ink = "#12181f" if render._luminance(accent["dark"]) > 0.2 else "#ffffff"
        worst_band = min(worst_band, _contrast(accent["dark"], ink))
    failures += not check(worst_accent >= 4.5, f"headings on white: worst {worst_accent:.2f}:1")
    failures += not check(worst_band >= 4.5, f"sidebar lettering: worst {worst_band:.2f}:1")

    pastel = next(a for a in model.ACCENTS if a["name"].endswith("pastel"))
    light = copy.deepcopy(data)
    light["meta"]["accent"], light["meta"]["accentDark"] = pastel["color"], pastel["dark"]
    css = render.base_css(light["meta"])
    failures += not check("--sidebar-ink: rgb(18, 24, 31)" in css, "pastel band gets dark lettering")
    failures += not check("rgba(255,255,255" not in render.render_html(light),
                          "no hard-coded white left on a light band")
    dark_css = render.base_css(data["meta"])
    failures += not check("--sidebar-ink: rgb(255, 255, 255)" in dark_css,
                          "dark band keeps white lettering")
    failures += not check(pdf.pdf_bytes(light).startswith(b"%PDF"), "pastel resume renders")

    print("\nMigration")
    legacy = {
        "meta": {"vorlage": "klassisch", "dichte": "luftig", "akzent": "#1D4ED8",
                 "abschnitte": [{"id": "profil", "titel": "Kurzprofil", "an": True, "spalte": "haupt"}]},
        "person": {"vorname": "Max", "nachname": "Muster", "telefon": "123"},
        "profil": "Text",
        "erfahrung": [{"position": "Dev", "firma": "ACME", "von": "01/2020", "bis": "heute",
                       "punkte": ["a"], "tech": ["C"]}],
        "projekte": [{"name": "P", "zeitraum": "seit 2019"}],
        "sprachen": [{"name": "Deutsch", "niveau": "Muttersprache", "level": 5}],
    }
    migrated = model.normalize(legacy)
    failures += not check(migrated["person"]["lastName"] == "Muster", "person migrated")
    failures += not check(migrated["meta"]["template"] == "classic"
                          and migrated["meta"]["density"] == "airy", "meta migrated")
    failures += not check(migrated["experience"][0]["to"] == "present", "'heute' becomes 'present'")
    failures += not check(migrated["projects"][0]["from"] == "2019"
                          and migrated["projects"][0]["to"] == "present", "period split up")
    failures += not check(migrated["languages"][0]["proficiency"] == "native", "proficiency mapped")
    failures += not check(pdf.pdf_bytes(migrated).startswith(b"%PDF"), "migrated document renders")

    print("\nAI plumbing")
    system, prompt, kind, applicable = prompts.build("summary", data, {})
    failures += not check(sample_company in prompt and kind == "text" and applicable,
                          "prompt carries the resume")
    failures += not check(len(prompts.parse_skills("Tools: Git, CMake\nLanguages: C")) == 2,
                          "skills answer parser")
    failures += not check(prompts.parse_lines("- a\n2) b\n* c") == ["a", "b", "c"], "bullet parser")
    _, english_prompt, _, _ = prompts.build("review", english, {})
    failures += not check("TASK" in english_prompt, "English prompt")
    for provider in ("ollama", "anthropic", "openai", "openrouter"):
        headers = providers._headers(provider, "k")
        expected = "x-api-key" if provider == "anthropic" else (
            "Authorization" if provider != "ollama" else "Content-Type")
        failures += not check(expected in headers, f"{provider}: auth header")
    failures += not check("anthropic" in settings.ENV_KEYS, "environment key fallback")

    round_trip = model.normalize(json.loads(json.dumps(data)))
    failures += not check(round_trip["person"]["lastName"] == sample_name, "JSON round trip")

    print(f"\n{'All good.' if not failures else f'{failures} check(s) failed.'}")
    print(f"Artifacts in {OUT}/")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
