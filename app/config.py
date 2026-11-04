import os
from pathlib import Path

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Data and Storage directories (can be overridden via environment variables for Docker)
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
STORAGE_DIR = Path(os.getenv("STORAGE_DIR", DATA_DIR / "documents"))
DB_PATH = Path(os.getenv("DB_PATH", DATA_DIR / "lazydocs.db"))

# Upload security constraints
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_MIME_TYPES = {"application/pdf", "image/png", "image/jpeg", "image/webp"}
PDF_MAGIC_BYTES = b"%PDF-"

# Kev Decision Model Configuration
KEV_HOST = os.getenv("KEV_HOST", "http://localhost:8009")
KEV_MODEL = os.getenv("KEV_MODEL", "jaredpalmer/kev-0.8b")
USE_KEV_CLASSIFIER = os.getenv("USE_KEV_CLASSIFIER", "true").lower() == "true"

# Performance & Concurrency Configuration
WORKER_CONCURRENCY = int(os.getenv("WORKER_CONCURRENCY", "2"))
LLM_SNIPPET_MAX_CHARS = int(os.getenv("LLM_SNIPPET_MAX_CHARS", "2500"))

# External Categories Configuration Path
CATEGORIES_CONFIG_PATH = Path(os.getenv("CATEGORIES_CONFIG_PATH", BASE_DIR / "categories.yaml"))

# Application Version / Git Tag
TAG = os.getenv("TAG", "dev")

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
