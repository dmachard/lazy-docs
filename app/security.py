import re
from pathlib import Path
from app.config import ALLOWED_EXTENSIONS, MAX_FILE_SIZE_BYTES, PDF_MAGIC_BYTES


class SecurityValidationError(ValueError):
    """Raised when file validation or path traversal check fails."""
    pass


def sanitize_filename(filename: str) -> str:
    """
    Sanitizes a user-provided filename by removing dangerous path characters.
    Extracts only the basename, replaces spaces, and filters non-whitelisted characters.
    """
    if not filename:
        return "unnamed_document.pdf"
    
    # Strip path components (e.g. /etc/passwd -> passwd)
    basename = Path(filename).name
    
    # Replace spaces with underscores
    clean = basename.replace(" ", "_")
    
    # Keep alphanumeric, dots, hyphens, underscores
    clean = re.sub(r'[^a-zA-Z0-9_\.-]', '', clean)
    
    # Remove leading dots or multiple dots
    clean = re.sub(r'^\.+', '', clean)
    
    if not clean:
        return "unnamed_document.pdf"
        
    return clean[:255]


def safe_join_path(base_dir: Path, relative_path: str | Path) -> Path:
    """
    Safely joins a base directory with a relative path.
    Prevents path traversal attacks (e.g., ../../etc/passwd).
    """
    resolved_base = base_dir.resolve()
    target_path = (resolved_base / relative_path).resolve()
    
    # Check if target_path is within resolved_base
    try:
        target_path.relative_to(resolved_base)
    except ValueError:
        raise SecurityValidationError(f"Path traversal detected: {relative_path}")
        
    return target_path


def validate_pdf_file(filename: str, content: bytes) -> None:
    """Backward compatibility alias for validate_uploaded_file."""
    validate_uploaded_file(filename, content)


def validate_uploaded_file(filename: str, content: bytes) -> None:
    """
    Validates uploaded file size, extension, and file magic header (PDF or Image).
    """
    if len(content) == 0:
        raise SecurityValidationError("Le fichier est vide.")
        
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise SecurityValidationError(
            f"Le fichier dépasse la taille maximale autorisée de {MAX_FILE_SIZE_BYTES // (1024 * 1024)} Mo."
        )

    # Validate extension
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise SecurityValidationError(f"Format de fichier non autorisé : {ext}. Seuls PDF, PNG, JPG, WEBP sont acceptés.")

    # Validate magic bytes
    if ext == ".pdf":
        if not content.startswith(PDF_MAGIC_BYTES):
            raise SecurityValidationError("Le fichier fourni n'est pas un fichier PDF valide.")
    elif ext in (".png", ".jpg", ".jpeg", ".webp"):
        # Check image header magic bytes
        png_magic = b"\x89PNG\r\n\x1a\n"
        jpg_magic = b"\xff\xd8\xff"
        webp_magic = b"RIFF"
        if not (content.startswith(png_magic) or content.startswith(jpg_magic) or content.startswith(webp_magic)):
            raise SecurityValidationError("Le fichier image fourni est corrompu ou invalide.")
