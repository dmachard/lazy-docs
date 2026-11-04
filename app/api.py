import uuid
import datetime
import logging
import hashlib
from pathlib import Path
from typing import List

from fastapi import APIRouter, File, UploadFile, HTTPException, Query, BackgroundTasks, Response
from fastapi.responses import FileResponse, RedirectResponse

from app.config import STORAGE_DIR, DB_PATH, TAG
from app.database import get_db_connection, search_documents, sync_fts
from app.security import validate_uploaded_file, sanitize_filename, safe_join_path, SecurityValidationError
from app.models import DocumentResponse, DocumentUpdate, SearchResult, TagCreate, DocumentListResponse
from app.worker import ocr_queue

logger = logging.getLogger("lazydocs.api")

router = APIRouter()


@router.get("/sw.js")
def get_service_worker():
    """Serves sw.js with dynamic CACHE_NAME derived from application TAG."""
    import re
    sw_file = Path(__file__).resolve().parent / "static" / "sw.js"
    if not sw_file.exists():
        raise HTTPException(status_code=404, detail="Service worker not found.")

    content = sw_file.read_text(encoding="utf-8")
    content = re.sub(
        r"const CACHE_NAME = ['\"][^'\"]+['\"];",
        f"const CACHE_NAME = 'lazydocs-{TAG}';",
        content,
        count=1
    )

    return Response(
        content=content,
        media_type="application/javascript",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Content-Type": "application/javascript"
        }
    )


@router.post("/api/documents", response_model=List[DocumentResponse], status_code=201)
async def upload_documents(
    files: List[UploadFile] = File(...),
    background_tasks: BackgroundTasks = None
):
    """
    Upload one or multiple PDF administrative documents.
    Files are stored with a unique UUID on disk and queued for background OCR/text extraction.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    created_docs = []
    current_year = str(datetime.datetime.now().year)
    year_dir = STORAGE_DIR / current_year
    year_dir.mkdir(parents=True, exist_ok=True)

    conn = get_db_connection(DB_PATH)

    try:
        for file in files:
            content = await file.read()
            original_filename = sanitize_filename(file.filename or "document.pdf")

            # Security validation
            try:
                validate_uploaded_file(original_filename, content)
            except SecurityValidationError as e:
                raise HTTPException(status_code=400, detail=f"Invalid file '{original_filename}': {str(e)}")

            ext = Path(original_filename).suffix.lower() or ".pdf"
            mime_type = "application/pdf" if ext == ".pdf" else f"image/{ext.lstrip('.')}"
            if ext == ".jpg":
                mime_type = "image/jpeg"

            # Compute SHA-256 hash to detect duplicates
            file_hash = hashlib.sha256(content).hexdigest()

            cursor = conn.cursor()
            existing = cursor.execute(
                "SELECT id, filename, storage_path, mime_type, file_size, created_at, ocr_status FROM documents WHERE file_hash = ?",
                (file_hash,)
            ).fetchone()

            if existing:
                # Document already exists, skip creating duplicate
                existing_tags = [row["name"] for row in cursor.execute("""
                    SELECT t.name FROM tags t
                    JOIN document_tags dt ON t.id = dt.tag_id
                    WHERE dt.document_id = ?
                """, (existing["id"],)).fetchall()]

                created_docs.append(DocumentResponse(
                    id=existing["id"],
                    filename=existing["filename"],
                    storage_path=existing["storage_path"],
                    mime_type=existing["mime_type"],
                    file_size=existing["file_size"],
                    created_at=str(existing["created_at"]),
                    ocr_status=existing["ocr_status"],
                    tags=existing_tags,
                    is_duplicate=True
                ))
                continue

            # Generate UUID for unique storage path
            doc_id = str(uuid.uuid4())
            storage_rel_path = f"{current_year}/{doc_id}{ext}"
            full_path = year_dir / f"{doc_id}{ext}"

            # Write file to disk
            with open(full_path, "wb") as f:
                f.write(content)

            # Insert into database with status 'pending'
            cursor.execute("""
                INSERT INTO documents (id, filename, storage_path, mime_type, file_size, file_hash, ocr_status)
                VALUES (?, ?, ?, ?, ?, ?, 'pending')
            """, (doc_id, original_filename, storage_rel_path, mime_type, len(content), file_hash))
            conn.commit()

            # Push to OCR queue
            await ocr_queue.put(doc_id)

            # Build response item
            created_docs.append(DocumentResponse(
                id=doc_id,
                filename=original_filename,
                storage_path=storage_rel_path,
                mime_type="application/pdf",
                file_size=len(content),
                created_at=datetime.datetime.now().isoformat(),
                ocr_status="pending",
                tags=[]
            ))
    finally:
        conn.close()

    return created_docs


@router.post("/share-target")
async def share_target_upload(
    files: List[UploadFile] = File(...),
    background_tasks: BackgroundTasks = None
):
    """
    Web Share Target API endpoint for mobile PWA.
    Receives shared files from native mobile apps, queues them, and redirects to home.
    """
    if files:
        await upload_documents(files=files, background_tasks=background_tasks)
    return RedirectResponse(url="/?shared=1", status_code=303)


@router.get("/api/documents", response_model=DocumentListResponse)
def list_documents(page: int = 1, limit: int = 20):
    """Lists documents with pagination support."""
    page = max(1, page)
    limit = max(1, min(100, limit))
    offset = (page - 1) * limit

    conn = get_db_connection(DB_PATH)
    try:
        cursor = conn.cursor()
        total = cursor.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        pages = (total + limit - 1) // limit if total > 0 else 1

        rows = cursor.execute("""
            SELECT 
                d.id, d.filename, d.storage_path, d.mime_type, d.file_size, d.created_at,
                d.document_date, d.document_type, d.organization, d.amount, d.person_name, d.ocr_status, d.ocr_error, d.content, d.raw_metadata,
                (
                    SELECT GROUP_CONCAT(t.name, ',')
                    FROM tags t
                    JOIN document_tags dt ON t.id = dt.tag_id
                    WHERE dt.document_id = d.id
                ) AS tag_list
            FROM documents d
            ORDER BY d.created_at DESC
            LIMIT ? OFFSET ?
        """, (limit, offset)).fetchall()

        results = []
        for r in rows:
            tags = r["tag_list"].split(",") if r["tag_list"] else []
            results.append(DocumentResponse(
                id=r["id"],
                filename=r["filename"],
                storage_path=r["storage_path"],
                mime_type=r["mime_type"],
                file_size=r["file_size"],
                created_at=str(r["created_at"]),
                document_date=r["document_date"],
                document_type=r["document_type"],
                organization=r["organization"],
                amount=r["amount"],
                person_name=r["person_name"],
                ocr_status=r["ocr_status"],
                ocr_error=r["ocr_error"],
                content=r["content"],
                raw_metadata=r["raw_metadata"],
                tags=tags
            ))
        return DocumentListResponse(
            total=total,
            page=page,
            limit=limit,
            pages=pages,
            documents=results
        )
    finally:
        conn.close()


@router.get("/api/documents/{doc_id}", response_model=DocumentResponse)
def get_document(doc_id: str):
    """Returns single document details, metadata, and extracted text."""
    conn = get_db_connection(DB_PATH)
    try:
        cursor = conn.cursor()
        r = cursor.execute("""
            SELECT 
                d.id, d.filename, d.storage_path, d.mime_type, d.file_size, d.created_at,
                d.document_date, d.document_type, d.organization, d.amount, d.person_name, d.ocr_status, d.ocr_error, d.content, d.raw_metadata,
                (
                    SELECT GROUP_CONCAT(t.name, ',')
                    FROM tags t
                    JOIN document_tags dt ON t.id = dt.tag_id
                    WHERE dt.document_id = d.id
                ) AS tag_list
            FROM documents d
            WHERE d.id = ?
        """, (doc_id,)).fetchone()

        if not r:
            raise HTTPException(status_code=404, detail="Document not found.")

        tags = r["tag_list"].split(",") if r["tag_list"] else []
        return DocumentResponse(
            id=r["id"],
            filename=r["filename"],
            storage_path=r["storage_path"],
            mime_type=r["mime_type"],
            file_size=r["file_size"],
            created_at=str(r["created_at"]),
            document_date=r["document_date"],
            document_type=r["document_type"],
            organization=r["organization"],
            amount=r["amount"],
            person_name=r["person_name"],
            ocr_status=r["ocr_status"],
            ocr_error=r["ocr_error"],
            content=r["content"],
            raw_metadata=r["raw_metadata"],
            tags=tags
        )
    finally:
        conn.close()


@router.get("/api/documents/{doc_id}/file")
def download_document_file(doc_id: str):
    """Views original PDF or image document inline in browser."""
    conn = get_db_connection(DB_PATH)
    try:
        cursor = conn.cursor()
        r = cursor.execute("SELECT storage_path, filename, mime_type FROM documents WHERE id = ?", (doc_id,)).fetchone()
        if not r:
            raise HTTPException(status_code=404, detail="Document not found.")

        storage_rel_path = r["storage_path"]
        try:
            full_path = safe_join_path(STORAGE_DIR, storage_rel_path)
        except SecurityValidationError:
            raise HTTPException(status_code=403, detail="Forbidden file access.")

        if not full_path.exists():
            raise HTTPException(status_code=404, detail="File not found on storage.")

        media_type = r["mime_type"] if r["mime_type"] else "application/pdf"

        return FileResponse(
            path=str(full_path),
            filename=r["filename"],
            media_type=media_type,
            content_disposition_type="inline"
        )
    finally:
        conn.close()


@router.get("/api/documents/{doc_id}/thumbnail")
def get_document_thumbnail(doc_id: str, size: int = 600):
    """Generates a high-quality JPEG thumbnail of the first page (PDF) or resizes image."""
    import io
    from fastapi.responses import Response as FastAPIResponse

    conn = get_db_connection(DB_PATH)
    try:
        cursor = conn.cursor()
        r = cursor.execute("SELECT storage_path, mime_type FROM documents WHERE id = ?", (doc_id,)).fetchone()
        if not r:
            raise HTTPException(status_code=404, detail="Document not found.")

        try:
            full_path = safe_join_path(STORAGE_DIR, r["storage_path"])
        except SecurityValidationError:
            raise HTTPException(status_code=403, detail="Forbidden access.")

        if not full_path.exists():
            raise HTTPException(status_code=404, detail="File not found on storage.")

        mime = r["mime_type"] or "application/pdf"
        img = None

        try:
            from PIL import Image as PILImage
            if mime == "application/pdf":
                from pdf2image import convert_from_path
                pages = convert_from_path(str(full_path), dpi=150, first_page=1, last_page=1)
                if pages:
                    img = pages[0].convert("RGB")
            else:
                img = PILImage.open(str(full_path)).convert("RGB")
        except Exception as e:
            logger.warning(f"Thumbnail error for {doc_id}: {e}")
            raise HTTPException(status_code=422, detail="Unable to generate thumbnail.")

        if img is None:
            raise HTTPException(status_code=422, detail="Unable to generate thumbnail.")

        # Resize with high-quality resampling (LANCZOS)
        img.thumbnail((size, size), resample=PILImage.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90, optimize=True, subsampling=0)
        buf.seek(0)

        return FastAPIResponse(
            content=buf.read(),
            media_type="image/jpeg",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    finally:
        conn.close()


@router.get("/api/documents/{doc_id}/status")
def get_document_status(doc_id: str):
    """Gets OCR processing status for frontend polling."""
    conn = get_db_connection(DB_PATH)
    try:
        cursor = conn.cursor()
        r = cursor.execute("SELECT ocr_status, ocr_error FROM documents WHERE id = ?", (doc_id,)).fetchone()
        if not r:
            raise HTTPException(status_code=404, detail="Document not found.")
        return {"status": r["ocr_status"], "error": r["ocr_error"]}
    finally:
        conn.close()


@router.patch("/api/documents/{doc_id}", response_model=DocumentResponse)
def update_document(doc_id: str, payload: DocumentUpdate):
    """Updates document metadata or filename."""
    conn = get_db_connection(DB_PATH)
    try:
        cursor = conn.cursor()
        doc = cursor.execute("SELECT id FROM documents WHERE id = ?", (doc_id,)).fetchone()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found.")

        updates = []
        params = []
        if payload.filename is not None:
            updates.append("filename = ?")
            params.append(sanitize_filename(payload.filename))
        if payload.document_date is not None:
            updates.append("document_date = ?")
            params.append(payload.document_date)
        if payload.document_type is not None:
            updates.append("document_type = ?")
            params.append(payload.document_type)
        if payload.organization is not None:
            updates.append("organization = ?")
            params.append(payload.organization)
        if payload.amount is not None:
            updates.append("amount = ?")
            params.append(payload.amount)
        if payload.person_name is not None:
            updates.append("person_name = ?")
            params.append(payload.person_name)

        if updates:
            params.append(doc_id)
            cursor.execute(f"UPDATE documents SET {', '.join(updates)} WHERE id = ?", params)
            conn.commit()
            sync_fts(conn, doc_id)
            conn.commit()

        return get_document(doc_id)
    finally:
        conn.close()


@router.delete("/api/documents/{doc_id}", status_code=204)
def delete_document(doc_id: str):
    """Deletes document from database, FTS index, and disk storage."""
    conn = get_db_connection(DB_PATH)
    try:
        cursor = conn.cursor()
        r = cursor.execute("SELECT storage_path FROM documents WHERE id = ?", (doc_id,)).fetchone()
        if not r:
            raise HTTPException(status_code=404, detail="Document not found.")

        storage_rel_path = r["storage_path"]

        # 1. Delete from database (cascades document_tags)
        cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        # 2. Delete from FTS5 table
        cursor.execute("DELETE FROM documents_fts WHERE document_id = ?", (doc_id,))
        conn.commit()

        # 3. Delete file from disk
        try:
            full_path = safe_join_path(STORAGE_DIR, storage_rel_path)
            if full_path.exists():
                full_path.unlink()
        except Exception as e:
            logger.warning(f"Unable to delete disk file {storage_rel_path}: {e}")

        return None
    finally:
        conn.close()


@router.delete("/api/documents", status_code=204)
def batch_delete_documents(doc_ids: List[str] = Query(...)):
    """Deletes multiple documents in bulk from database, FTS index, and disk storage."""
    if not doc_ids:
        raise HTTPException(status_code=400, detail="No documents specified.")

    conn = get_db_connection(DB_PATH)
    try:
        cursor = conn.cursor()
        placeholders = ",".join(["?"] * len(doc_ids))
        rows = cursor.execute(f"SELECT id, storage_path FROM documents WHERE id IN ({placeholders})", doc_ids).fetchall()

        # 1. Delete from DB and FTS
        cursor.execute(f"DELETE FROM documents WHERE id IN ({placeholders})", doc_ids)
        cursor.execute(f"DELETE FROM documents_fts WHERE document_id IN ({placeholders})", doc_ids)
        conn.commit()

        # 2. Delete files from disk
        for r in rows:
            try:
                full_path = safe_join_path(STORAGE_DIR, r["storage_path"])
                if full_path.exists():
                    full_path.unlink()
            except Exception as e:
                logger.warning(f"Unable to delete disk file {r['storage_path']}: {e}")

        return None
    finally:
        conn.close()


@router.get("/api/search", response_model=SearchResult)
def search(q: str = Query(..., min_length=1), limit: int = 50, offset: int = 0):
    """Performs fast SQLite FTS5 search across content, filename, tags, organization, and document type."""
    conn = get_db_connection(DB_PATH)
    try:
        results_data = search_documents(conn, q, limit=limit, offset=offset)
        formatted_results = [DocumentResponse(**r) for r in results_data]
        return SearchResult(
            query=q,
            total=len(formatted_results),
            results=formatted_results
        )
    finally:
        conn.close()


@router.get("/api/suggested-filters")
def get_suggested_filters():
    """Returns top distinct document types (as extracted by LLM) to display as quick filter pills under search."""
    conn = get_db_connection(DB_PATH)
    try:
        cursor = conn.cursor()
        rows = cursor.execute(
            "SELECT document_type, COUNT(*) as cnt FROM documents WHERE document_type IS NOT NULL AND document_type != '' GROUP BY document_type ORDER BY cnt DESC LIMIT 12"
        ).fetchall()

        filters = [r["document_type"] for r in rows if r["document_type"]]
        return {"filters": filters}
    finally:
        conn.close()


@router.get("/api/stats")
def get_stats():
    """Returns aggregated stats for dashboard view."""
    conn = get_db_connection(DB_PATH)
    try:
        cursor = conn.cursor()
        total_docs = cursor.execute("SELECT COUNT(*) as cnt FROM documents").fetchone()["cnt"]

        orgs_count = cursor.execute(
            "SELECT COUNT(DISTINCT organization) as cnt FROM documents WHERE organization IS NOT NULL AND organization != ''"
        ).fetchone()["cnt"]

        types_count = cursor.execute(
            "SELECT COUNT(DISTINCT document_type) as cnt FROM documents WHERE document_type IS NOT NULL AND document_type != ''"
        ).fetchone()["cnt"]

        total_amount = cursor.execute(
            "SELECT SUM(amount) as total FROM documents WHERE amount IS NOT NULL"
        ).fetchone()["total"] or 0.0

        type_breakdown = cursor.execute(
            "SELECT document_type, COUNT(*) as cnt FROM documents WHERE document_type IS NOT NULL AND document_type != '' GROUP BY document_type ORDER BY cnt DESC"
        ).fetchall()

        top_orgs = cursor.execute(
            "SELECT organization, COUNT(*) as cnt FROM documents WHERE organization IS NOT NULL AND organization != '' GROUP BY organization ORDER BY cnt DESC LIMIT 8"
        ).fetchall()

        return {
            "total_docs": total_docs,
            "total_orgs": orgs_count,
            "total_types": types_count,
            "total_amount": round(total_amount, 2),
            "type_breakdown": [{"type": r["document_type"], "count": r["cnt"]} for r in type_breakdown],
            "top_orgs": [{"organization": r["organization"], "count": r["cnt"]} for r in top_orgs]
        }
    finally:
        conn.close()


@router.post("/api/reindex")
async def reindex_all_documents():
    """Re-queues all existing documents for OCR and LLM metadata extraction."""
    conn = get_db_connection(DB_PATH)
    try:
        cursor = conn.cursor()
        rows = cursor.execute("SELECT id FROM documents").fetchall()
        if not rows:
            return {"message": "No documents to reindex.", "count": 0}

        doc_ids = [r["id"] for r in rows]
        placeholders = ",".join(["?"] * len(doc_ids))
        cursor.execute(f"UPDATE documents SET ocr_status = 'pending', ocr_error = NULL WHERE id IN ({placeholders})", doc_ids)
        conn.commit()

        for doc_id in doc_ids:
            await ocr_queue.put(doc_id)

        return {"message": f"Reindexing started for {len(doc_ids)} document(s).", "count": len(doc_ids)}
    finally:
        conn.close()


@router.post("/api/documents/{doc_id}/reindex")
async def reindex_single_document(doc_id: str):
    """Re-queues a single document for OCR and LLM metadata re-analysis."""
    conn = get_db_connection(DB_PATH)
    try:
        cursor = conn.cursor()
        doc = cursor.execute("SELECT id FROM documents WHERE id = ?", (doc_id,)).fetchone()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found.")

        cursor.execute("UPDATE documents SET ocr_status = 'pending', ocr_error = NULL WHERE id = ?", (doc_id,))
        conn.commit()

        await ocr_queue.put(doc_id)
        return {"message": "Re-analysis started for document.", "id": doc_id}
    finally:
        conn.close()


@router.post("/api/cancel-indexing")
def cancel_indexing():
    """Empties the background OCR queue and resets pending documents to ready."""
    count = 0
    while not ocr_queue.empty():
        try:
            ocr_queue.get_nowait()
            count += 1
        except Exception:
            break

    conn = get_db_connection(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE documents SET ocr_status = 'ready' WHERE ocr_status IN ('pending', 'processing')")
        conn.commit()
    finally:
        conn.close()

    logger.info(f"Indexing cancelled. {count} task(s) removed from queue.")
    return {"message": "Indexing successfully cancelled.", "cancelled_tasks": count}


@router.post("/api/documents/{doc_id}/tags", response_model=List[str])
def add_tag_to_document(doc_id: str, payload: TagCreate):
    """Adds a manual tag to a document."""
    tag_name = payload.name.strip().lower()
    if not tag_name:
        raise HTTPException(status_code=400, detail="Invalid tag name.")

    conn = get_db_connection(DB_PATH)
    try:
        cursor = conn.cursor()
        # Verify doc exists
        doc = cursor.execute("SELECT id FROM documents WHERE id = ?", (doc_id,)).fetchone()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found.")

        # Insert or get tag
        cursor.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag_name,))
        tag_row = cursor.execute("SELECT id FROM tags WHERE name = ?", (tag_name,)).fetchone()
        tag_id = tag_row["id"]

        # Link document to tag
        cursor.execute("INSERT OR IGNORE INTO document_tags (document_id, tag_id) VALUES (?, ?)", (doc_id, tag_id))
        conn.commit()

        # Sync FTS
        sync_fts(conn, doc_id)
        conn.commit()

        # Return updated tags list
        rows = cursor.execute("""
            SELECT t.name FROM tags t
            JOIN document_tags dt ON t.id = dt.tag_id
            WHERE dt.document_id = ?
        """, (doc_id,)).fetchall()
        return [r["name"] for r in rows]
    finally:
        conn.close()


@router.delete("/api/documents/{doc_id}/tags/{tag_name}", response_model=List[str])
def remove_tag_from_document(doc_id: str, tag_name: str):
    """Removes a tag from a document."""
    conn = get_db_connection(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM document_tags 
            WHERE document_id = ? AND tag_id = (SELECT id FROM tags WHERE name = ?)
        """, (doc_id, tag_name.strip().lower()))
        conn.commit()

        # Sync FTS
        sync_fts(conn, doc_id)
        conn.commit()

        # Return updated tags list
        rows = cursor.execute("""
            SELECT t.name FROM tags t
            JOIN document_tags dt ON t.id = dt.tag_id
            WHERE dt.document_id = ?
        """, (doc_id,)).fetchall()
        return [r["name"] for r in rows]
    finally:
        conn.close()


@router.get("/api/tags/suggestions", response_model=List[str])
def get_tag_suggestions():
    """Lists existing tags for auto-completion suggestions."""
    conn = get_db_connection(DB_PATH)
    try:
        cursor = conn.cursor()
        rows = cursor.execute("SELECT name FROM tags ORDER BY name ASC").fetchall()
        return [r["name"] for r in rows]
    finally:
        conn.close()


@router.get("/api/status")
def get_system_status():
    """Returns total document count and pending/processing OCR count."""
    conn = get_db_connection(DB_PATH)
    try:
        cursor = conn.cursor()
        total = cursor.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        pending = cursor.execute("SELECT COUNT(*) FROM documents WHERE ocr_status IN ('pending', 'processing')").fetchone()[0]
        return {
            "total": total,
            "pending": pending
        }
    finally:
        conn.close()


@router.get("/api/backup")
def export_backup():
    """Generates and downloads a ZIP archive containing database and documents."""
    import zipfile
    import tempfile

    temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    zip_path = Path(temp_zip.name)
    temp_zip.close()

    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # 1. Add database if exists
            if DB_PATH.exists():
                zipf.write(DB_PATH, arcname="database.sqlite")

            # 2. Add documents directory recursively
            if STORAGE_DIR.exists():
                for file_path in STORAGE_DIR.rglob("*"):
                    if file_path.is_file():
                        rel_path = file_path.relative_to(STORAGE_DIR)
                        zipf.write(file_path, arcname=f"documents/{rel_path}")

        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        return FileResponse(
            path=str(zip_path),
            filename=f"lazydocs_backup_{date_str}.zip",
            media_type="application/zip"
        )
    except Exception as e:
        logger.error(f"Error creating backup archive: {e}")
        raise HTTPException(status_code=500, detail="Unable to create backup archive.")
