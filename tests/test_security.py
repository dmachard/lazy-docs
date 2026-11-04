import pytest
from pathlib import Path
from app.security import (
    sanitize_filename,
    safe_join_path,
    validate_pdf_file,
    SecurityValidationError,
)


def test_sanitize_filename():
    assert sanitize_filename("../../../etc/passwd") == "passwd"
    assert sanitize_filename("Facture EDF 2026.pdf") == "Facture_EDF_2026.pdf"
    assert sanitize_filename("Dangerous; Drop table;.pdf") == "Dangerous_Drop_table.pdf"
    assert sanitize_filename("") == "unnamed_document.pdf"
    assert sanitize_filename("...///...") == "unnamed_document.pdf"


def test_safe_join_path(tmp_path):
    base_dir = tmp_path / "storage"
    base_dir.mkdir()

    # Valid join
    valid_path = safe_join_path(base_dir, "2026/doc.pdf")
    assert valid_path == (base_dir / "2026/doc.pdf").resolve()

    # Traversal attempts
    with pytest.raises(SecurityValidationError, match="Path traversal detected"):
        safe_join_path(base_dir, "../../etc/passwd")

    with pytest.raises(SecurityValidationError, match="Path traversal detected"):
        safe_join_path(base_dir, "2026/../../etc/passwd")


def test_validate_pdf_file():
    valid_pdf_content = b"%PDF-1.7\n%...some pdf content"
    
    # Valid PDF
    validate_pdf_file("facture.pdf", valid_pdf_content)

    # Empty file
    with pytest.raises(SecurityValidationError, match="vide"):
        validate_pdf_file("facture.pdf", b"")

    # Invalid extension
    with pytest.raises(SecurityValidationError, match="Format de fichier non autorisé"):
        validate_pdf_file("script.sh", valid_pdf_content)

    # Invalid magic bytes (exe disguised as pdf)
    with pytest.raises(SecurityValidationError, match="pas un fichier PDF valide"):
        validate_pdf_file("malicious.pdf", b"MZ\x90\x00\x03\x00\x00\x00")
