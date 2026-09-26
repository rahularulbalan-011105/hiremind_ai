from __future__ import annotations

from pathlib import Path

from app.core.exceptions import ValidationError
from app.core.logging import get_logger

log = get_logger(__name__)

# A resume page typically yields >200 chars of text. Below this threshold we
# assume the document is image-based and fall back to OCR.
_MIN_TEXT_THRESHOLD = 200


def extract_text(path: Path) -> str:
    """
    Extract text from a PDF or DOCX. Returns the raw text (whitespace preserved
    enough to keep line structure). Does NOT run OCR — that's a separate step.
    """
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf(path)
    if suffix == ".docx":
        return _extract_docx(path)
    if suffix == ".doc":
        # An OLE binary, not a zip: python-docx cannot open it, and pretending otherwise
        # produced an empty parse rather than a clear message.
        raise ValidationError("Legacy .doc files are not supported — save the résumé as .docx or PDF.")
    raise ValidationError(f"Unsupported resume format: {suffix}. Use PDF or DOCX.")


def looks_image_based(text: str) -> bool:
    return len((text or "").strip()) < _MIN_TEXT_THRESHOLD


def _extract_pdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    chunks: list[str] = []
    for i, page in enumerate(reader.pages):
        try:
            chunks.append(page.extract_text() or "")
        except Exception as exc:  # pragma: no cover
            log.warning("pdf_page_extract_failed", page=i, error=str(exc))
    return "\n".join(chunks).strip()


_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_P = f"{_W}p"
_T = f"{_W}t"
# Word writes shape content twice: the modern DrawingML version inside mc:Choice and a
# legacy VML copy inside mc:Fallback. Reading both would duplicate every line.
_FALLBACK = "{http://schemas.openxmlformats.org/markup-compatibility/2006}Fallback"


def _inside_fallback(node) -> bool:
    for ancestor in node.iterancestors():
        if ancestor.tag == _FALLBACK:
            return True
    return False


def _own_text(paragraph) -> str:
    """The paragraph's own runs, not those of paragraphs nested inside it.

    A text box lives in a run of an outer paragraph and holds paragraphs of its own, so
    without this check the outer paragraph would repeat everything the box contains.
    """
    chunks: list[str] = []
    for node in paragraph.iter(_T):
        owner = node.getparent()
        while owner is not None and owner.tag != _P:
            owner = owner.getparent()
        if owner is paragraph:
            chunks.append(node.text or "")
    return "".join(chunks).strip()


def _lines(element) -> list[str]:
    """Every paragraph of text under an XML element, in document order."""
    lines: list[str] = []
    for paragraph in element.iter(_P):
        if _inside_fallback(paragraph):
            continue
        text = _own_text(paragraph)
        if text:
            lines.append(text)
    return lines


def _extract_docx(path: Path) -> str:
    """
    All the text in a .docx, wherever Word put it.

    Reading `document.paragraphs` alone covers only top-level body paragraphs. Designed
    résumés — the two-column ones with a coloured sidebar — keep their content in text
    boxes and shapes instead, and those paragraphs are nested inside a run, so such a CV
    extracted as an empty string and the whole parse came back blank. Walking the XML for
    every `w:p`, plus each section's header and footer, picks all of it up. Table cells
    are ordinary paragraphs, so they come along too.
    """
    from docx import Document  # python-docx

    document = Document(str(path))
    lines: list[str] = _lines(document.element.body)

    # Headers and footers repeat per section and often per page variant; keep the first
    # copy of each distinct line so a name in the letterhead is read exactly once.
    seen = set(lines)
    for section in document.sections:
        parts = (
            getattr(section, "first_page_header", None), getattr(section, "header", None),
            getattr(section, "even_page_header", None), getattr(section, "footer", None),
            getattr(section, "first_page_footer", None), getattr(section, "even_page_footer", None),
        )
        for part in parts:
            element = getattr(part, "_element", None)
            if element is None:
                continue
            for line in _lines(element):
                if line not in seen:
                    seen.add(line)
                    lines.append(line)

    return "\n".join(lines).strip()
