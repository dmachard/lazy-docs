import asyncio
import logging
from pathlib import Path
import contextlib

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.config import STORAGE_DIR, DB_PATH, TAG
from app.database import get_db_connection, init_db
from app.worker import ocr_queue, ocr_worker_loop
from app.api import router as api_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("lazydocs.main")


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    """Initializes DB schema, re-queues pending documents, and launches background OCR worker task."""
    init_db(DB_PATH)

    # Recover any pending or stuck processing documents from DB into queue
    try:
        conn = get_db_connection(DB_PATH)
        cursor = conn.cursor()
        stuck_docs = cursor.execute(
            "SELECT id FROM documents WHERE ocr_status IN ('pending', 'processing')"
        ).fetchall()
        for doc in stuck_docs:
            ocr_queue.put_nowait(doc["id"])
        if stuck_docs:
            logger.info(f"{len(stuck_docs)} pending document(s) re-queued for processing.")
        conn.close()
    except Exception as e:
        logger.error(f"Error re-queuing pending documents: {e}")

    worker_task = asyncio.create_task(ocr_worker_loop())
    yield
    worker_task.cancel()


app = FastAPI(
    title="LazyDocs API",
    description="Smart & Zero-Effort Document Organizer (Local AI & OCR)",
    version=TAG,
    lifespan=lifespan
)

# Enable CORS for local convenience
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount REST API router
app.include_router(api_router)

# Mount static files for web UI frontend
STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


