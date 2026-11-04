import logging
from pathlib import Path
from typing import Tuple
from pypdf import PdfReader

logger = logging.getLogger("lazydocs.extractor")

MIN_NATIVE_TEXT_LEN = 50


def extract_text_from_pdf(pdf_path: Path) -> Tuple[str, bool]:
    """Deprecated alias for extract_text_from_file."""
    return extract_text_from_file(pdf_path)


def normalize_text(text: str) -> str:
    """Normalizes whitespace and blank lines from extracted text."""
    if not text:
        return ""
    # Collapse multiple blank lines into single clean line breaks
    lines = [line.strip() for line in text.splitlines()]
    non_empty_lines = [line for line in lines if line]
    return "\n".join(non_empty_lines)


def extract_text_from_file(file_path: Path) -> Tuple[str, bool]:
    """
    Extracts text from a PDF or image file (PNG, JPG, WEBP).
    For PDFs, tries native text extraction first, falling back to Tesseract OCR.
    For images, runs Tesseract OCR directly via PIL.

    Returns:
        Tuple[str, bool]: (extracted_text, used_ocr)
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Fichier non trouvé : {file_path}")

    ext = file_path.suffix.lower()

    # Image files handling (PNG, JPG, JPEG, WEBP)
    if ext in (".png", ".jpg", ".jpeg", ".webp"):
        logger.info(f"Direct OCR extraction on image file {file_path.name}...")
        try:
            import pytesseract
            from PIL import Image, ImageOps, ImageEnhance

            with Image.open(file_path) as img:
                # Convert to RGB then grayscale for uniform processing
                img = img.convert("L")
                # Auto contrast enhancement to eliminate shadows & dark backgrounds
                img = ImageOps.autocontrast(img)
                # Enhance sharpness for text edges
                enhancer = ImageEnhance.Sharpness(img)
                img = enhancer.enhance(2.0)

                ocr_text = pytesseract.image_to_string(img, lang="fra+eng")
                return normalize_text(ocr_text), True
        except Exception as e:
            logger.error(f"Error during OCR on image {file_path.name}: {e}")
            raise RuntimeError(f"Image OCR failure: {e}") from e

    # PDF files handling
    native_text = ""
    try:
        reader = PdfReader(str(file_path))
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                native_text += page_text + "\n"
    except Exception as e:
        logger.warning(f"Native PDF extraction failed for {file_path.name}: {e}")

    clean_native = normalize_text(native_text)

    # Detect glued PDF native text (missing space operators in PDF stream like "EDF-SAaucapitalde2000466841euros")
    import re
    has_glued_words = bool(re.search(r'[a-zA-Z]{22,}', clean_native))

    if len(clean_native) >= MIN_NATIVE_TEXT_LEN and not has_glued_words:
        logger.info(f"Native text extracted from PDF {file_path.name} ({len(clean_native)} chars). OCR skipped.")
        return clean_native, False

    # Fallback to Tesseract OCR for scanned PDF or PDFs with glued words
    logger.info(f"PDF {file_path.name} requires Tesseract OCR (glued_words={has_glued_words}, len={len(clean_native)})...")
    try:
        import pytesseract
        from pdf2image import convert_from_path

        images = convert_from_path(str(file_path), dpi=200, first_page=1, last_page=10)
        ocr_text = ""
        from PIL import ImageOps, ImageEnhance
        for i, img in enumerate(images):
            # Preprocess PDF scanned page
            gray_img = ImageOps.autocontrast(img.convert("L"))
            enhanced_img = ImageEnhance.Sharpness(gray_img).enhance(2.0)
            page_ocr = pytesseract.image_to_string(enhanced_img, lang="fra+eng")
            if page_ocr:
                ocr_text += page_ocr + "\n"

        clean_ocr = normalize_text(ocr_text)
        return clean_ocr, True
    except Exception as e:
        logger.error(f"Error during Tesseract OCR on {file_path.name}: {e}")
        if clean_native:
            return clean_native, False
        raise RuntimeError(f"OCR failure: {e}") from e

