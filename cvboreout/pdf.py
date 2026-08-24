"""HTML -> PDF (WeasyPrint) and PDF -> PNG preview (pypdfium2)."""

from __future__ import annotations

import base64
import io
from pathlib import Path

from . import render


class RenderError(RuntimeError):
    pass


def _weasyprint():
    try:
        from weasyprint import HTML  # noqa: PLC0415
    except ImportError as error:  # pragma: no cover
        raise RenderError("WeasyPrint is missing. Run 'make setup'.") from error
    return HTML


def _render(HTML, markup: str):
    # base_url is required so that data URIs (page band, photo) resolve.
    return HTML(string=markup, base_url=str(Path.cwd())).render()


def resume_document(data: dict):
    """Render the resume; single-page resumes drop the page footer."""
    HTML = _weasyprint()
    wants_footer = bool(data["meta"].get("pageNumbers", True))
    doc = _render(HTML, render.render_html(data, page_numbers=wants_footer))
    if wants_footer and len(doc.pages) == 1:
        doc = _render(HTML, render.render_html(data, page_numbers=False))
    return doc


def letter_document(data: dict):
    return _render(_weasyprint(), render.render_letter(data))


def document(data: dict, kind: str = "resume"):
    """kind: resume | letter | both (letter first, then the resume)."""
    if kind == "letter":
        return letter_document(data)
    if kind == "both":
        letter = letter_document(data)
        resume = resume_document(data)
        return letter.copy(letter.pages + resume.pages)
    return resume_document(data)


def pdf_bytes(data: dict, kind: str = "resume") -> bytes:
    return document(data, kind).write_pdf()


def write_pdf(data: dict, target: Path, kind: str = "resume") -> Path:
    target = Path(target).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(pdf_bytes(data, kind))
    return target


def page_images(pdf: bytes, scale: float = 1.6) -> list[str]:
    """Rasterize every page and return data URIs for the preview."""
    try:
        import pypdfium2 as pdfium  # noqa: PLC0415
    except ImportError as error:  # pragma: no cover
        raise RenderError("pypdfium2 is missing. Run 'make setup'.") from error

    doc = pdfium.PdfDocument(pdf)
    images = []
    try:
        for number in range(len(doc)):
            image = doc[number].render(scale=scale).to_pil()
            buffer = io.BytesIO()
            image.convert("RGB").save(buffer, "JPEG", quality=88, optimize=True)
            images.append("data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode())
    finally:
        doc.close()
    return images


def preview(data: dict, scale: float = 1.6, kind: str = "resume") -> dict:
    pdf = pdf_bytes(data, kind)
    return {"pages": page_images(pdf, scale), "size": len(pdf)}
