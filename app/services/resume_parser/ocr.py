from __future__ import annotations

from pathlib import Path
from typing import Literal

from app.core.exceptions import DependencyError
from app.core.logging import get_logger

log = get_logger(__name__)

OcrEngine = Literal["paddle", "tesseract"]


def ocr_pdf(path: Path, engine: OcrEngine) -> str:
    """
    Rasterize a PDF and OCR each page. Engines are lazy-imported so the parser
    works without OCR libs installed, as long as no image-based resume is uploaded.
    """
    if engine == "tesseract":
        return _tesseract_pdf(path)
    if engine == "paddle":
        return _paddle_pdf(path)
    raise DependencyError(f"Unknown OCR engine: {engine}")


def _tesseract_pdf(path: Path) -> str:
    try:
        import pytesseract
        from pdf2image import convert_from_path
    except ImportError as exc:
        raise DependencyError(
            "Tesseract OCR path requires `pytesseract`, `pdf2image`, the `tesseract` "
            "binary, and `poppler`. Install them or change OCR_ENGINE."
        ) from exc

    try:
        images = convert_from_path(str(path))
    except Exception as exc:
        raise DependencyError(
            "Failed to rasterize PDF — is poppler installed and on PATH?"
        ) from exc

    pages: list[str] = []
    for i, img in enumerate(images):
        try:
            pages.append(pytesseract.image_to_string(img))
        except Exception as exc:
            log.warning("tesseract_page_failed", page=i, error=str(exc))
    return "\n".join(pages).strip()


def _paddle_pdf(path: Path) -> str:  # pragma: no cover — optional
    try:
        from paddleocr import PaddleOCR  # type: ignore
        from pdf2image import convert_from_path
    except ImportError as exc:
        raise DependencyError(
            "PaddleOCR path requires `paddleocr` and `pdf2image` + `poppler`. "
            "Install them or change OCR_ENGINE."
        ) from exc

    ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
    images = convert_from_path(str(path))
    pages: list[str] = []
    for img in images:
        result = ocr.ocr(img, cls=True)
        for line in result[0] if result and result[0] else []:
            pages.append(line[1][0])
    return "\n".join(pages).strip()
