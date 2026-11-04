import logging
import asyncio
from pathlib import Path
from app.config import DB_PATH, STORAGE_DIR
from app.database import get_db_connection, sync_fts
from app.extractor import extract_text_from_file
from app.metadata import extract_metadata_llm

logger = logging.getLogger("lazydocs.worker")

# Simple in-memory asyncio queue for background OCR tasks
ocr_queue: asyncio.Queue[str] = asyncio.Queue()


def process_document_sync(document_id: str, db_path: Path = DB_PATH) -> None:
    """
    Synchronously extracts text (native or OCR) and metadata for a single document,
    updates SQLite database, and synchronizes FTS5 index.
    """
    conn = get_db_connection(db_path)
    try:
        # 1. Fetch document record
        cursor = conn.cursor()
        doc = cursor.execute(
            "SELECT id, filename, storage_path FROM documents WHERE id = ?", (document_id,)
        ).fetchone()

        if not doc:
            logger.error(f"Worker: document {document_id} not found in database.")
            return

        filename = doc["filename"] or ""
        storage_rel_path = doc["storage_path"]
        full_pdf_path = (STORAGE_DIR / storage_rel_path).resolve()

        # Update status to processing
        cursor.execute(
            "UPDATE documents SET ocr_status = 'processing', ocr_error = NULL WHERE id = ?",
            (document_id,)
        )
        conn.commit()

        # 2. Extract text (Native or OCR)
        text, used_ocr = extract_text_from_file(full_pdf_path)

        # 3. Extract Metadata via LLM (incorporating original filename clues)
        meta = extract_metadata_llm(text, filename=filename)

        import json
        raw_meta_str = json.dumps(meta.get("raw_metadata", {}), ensure_ascii=False) if meta.get("raw_metadata") else None

        # 4. Save results to database
        cursor.execute("""
            UPDATE documents SET 
                content = ?,
                ocr_status = 'ready',
                organization = ?,
                document_type = ?,
                document_date = ?,
                amount = ?,
                person_name = ?,
                raw_metadata = ?
            WHERE id = ?
        """, (
            text,
            meta.get("organization"),
            meta.get("document_type"),
            meta.get("document_date"),
            meta.get("amount"),
            meta.get("person_name"),
            raw_meta_str,
            document_id
        ))
        conn.commit()

        # 5. Sync FTS5 Index
        sync_fts(conn, document_id)
        conn.commit()

        logger.info(f"Document {document_id} successfully processed (used_ocr={used_ocr}).")

    except Exception as e:
        logger.error(f"Error while processing document {document_id}: {e}", exc_info=True)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE documents SET ocr_status = 'error', ocr_error = ? WHERE id = ?",
                (str(e), document_id)
            )
            conn.commit()
        except Exception:
            pass
    finally:
        conn.close()


async def _worker_task_consumer():
    """Individual consumer task processing queue items."""
    loop = asyncio.get_running_loop()
    while True:
        document_id = await ocr_queue.get()
        logger.info(f"OCR Worker: Dequeuing document {document_id}")
        try:
            await loop.run_in_executor(None, process_document_sync, document_id)
        except Exception as e:
            logger.error(f"Error processing document {document_id}: {e}")
        finally:
            ocr_queue.task_done()


async def ocr_worker_loop():
    """
    Background worker manager spawning WORKER_CONCURRENCY concurrent consumer tasks.
    """
    from app.config import WORKER_CONCURRENCY
    logger.info(f"Starting background OCR worker manager with concurrency = {WORKER_CONCURRENCY}...")

    workers = [asyncio.create_task(_worker_task_consumer()) for _ in range(WORKER_CONCURRENCY)]
    try:
        await asyncio.gather(*workers)
    except asyncio.CancelledError:
        logger.info("Stopping OCR worker manager...")
        for w in workers:
            w.cancel()
        await asyncio.gather(*workers, return_exceptions=True)

