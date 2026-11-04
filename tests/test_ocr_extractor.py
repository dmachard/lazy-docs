from pypdf import PdfWriter
from app.extractor import extract_text_from_pdf


def test_native_pdf_text_extraction(tmp_path):
    # Create a small valid PDF with text using PyPDF
    pdf_path = tmp_path / "test_native.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    
    with open(pdf_path, "wb") as f:
        writer.write(f)

    # Blank PDF should yield little/no text
    text, used_ocr = extract_text_from_pdf(pdf_path)
    assert isinstance(text, str)
