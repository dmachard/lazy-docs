import sqlite3
import re
from typing import List, Dict, Any
from pathlib import Path
from app.config import DB_PATH


def get_db_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """
    Creates and returns a SQLite connection with Row factory and WAL mode enabled.
    """
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def init_db(db_path: Path = DB_PATH) -> None:
    """
    Initializes database tables and FTS5 virtual table for full-text search.
    """
    conn = get_db_connection(db_path)
    with conn:
        # 1. Documents table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                storage_path TEXT NOT NULL,
                mime_type TEXT NOT NULL DEFAULT 'application/pdf',
                file_size INTEGER NOT NULL DEFAULT 0,
                file_hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                document_date TEXT,
                document_type TEXT,
                organization TEXT,
                amount REAL,
                ocr_status TEXT NOT NULL DEFAULT 'pending',
                ocr_error TEXT,
                content TEXT
            );
        """)

        # Auto-migration: add file_hash and raw_metadata columns if missing (existing DBs)
        try:
            conn.execute("ALTER TABLE documents ADD COLUMN file_hash TEXT;")
        except sqlite3.OperationalError:
            pass

        try:
            conn.execute("ALTER TABLE documents ADD COLUMN raw_metadata TEXT;")
        except sqlite3.OperationalError:
            pass

        try:
            conn.execute("ALTER TABLE documents ADD COLUMN person_name TEXT;")
        except sqlite3.OperationalError:
            pass

        # 2. Tags table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            );
        """)

        # 3. Document Tags table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS document_tags (
                document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
                PRIMARY KEY (document_id, tag_id)
            );
        """)

        # 4. Check if existing documents_fts table has amount column, drop if obsolete
        try:
            columns = [row[1] for row in conn.execute("PRAGMA table_info(documents_fts)").fetchall()]
            if columns and "amount" not in columns:
                conn.execute("DROP TABLE documents_fts;")
        except sqlite3.OperationalError:
            pass

        # 5. FTS5 Virtual Table for accent/case-insensitive fast full text search
        # Using unicode61 remove_diacritics 2 for French accent normalization
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
                document_id UNINDEXED,
                filename,
                content,
                organization,
                document_type,
                document_date,
                amount,
                tags,
                tokenize='unicode61 remove_diacritics 2'
            );
        """)

        # 6. Quick cleanup of existing English document types in SQLite DB
        conn.execute("UPDATE documents SET document_type = 'Carte d''identité' WHERE LOWER(document_type) IN ('identity card', 'id card', 'identity');")
        conn.execute("UPDATE documents SET document_type = 'Passeport' WHERE LOWER(document_type) = 'passport';")

        # 6b. Sanitize existing organization strings in SQLite DB
        from app.metadata import sanitize_organization
        rows = conn.execute("SELECT id, organization FROM documents WHERE organization IS NOT NULL AND organization != '';").fetchall()
        updated_org_count = 0
        for r in rows:
            old_org = r["organization"]
            new_org = sanitize_organization(old_org)
            if new_org and new_org != old_org:
                conn.execute("UPDATE documents SET organization = ? WHERE id = ?", (new_org, r["id"]))
                updated_org_count += 1

        # 7. Ensure all existing documents are indexed in FTS5
        doc_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        fts_count = conn.execute("SELECT COUNT(*) FROM documents_fts").fetchone()[0]
        if updated_org_count > 0 or doc_count != fts_count or fts_count == 0:
            doc_ids = [row["id"] for row in conn.execute("SELECT id FROM documents").fetchall()]
            for d_id in doc_ids:
                sync_fts(conn, d_id)


def sync_fts(conn: sqlite3.Connection, document_id: str) -> None:
    """
    Synchronizes FTS5 index for a single document.
    """
    cursor = conn.cursor()
    
    # Fetch document
    doc = cursor.execute(
        "SELECT id, filename, content, organization, document_type, document_date, amount, person_name FROM documents WHERE id = ?",
        (document_id,)
    ).fetchone()
    
    if not doc:
        # Delete from FTS if removed
        cursor.execute("DELETE FROM documents_fts WHERE document_id = ?", (document_id,))
        return

    # Fetch tags joined as a single string
    tag_rows = cursor.execute("""
        SELECT t.name FROM tags t
        JOIN document_tags dt ON t.id = dt.tag_id
        WHERE dt.document_id = ?
    """, (document_id,)).fetchall()
    
    tags_str = " ".join([t["name"] for t in tag_rows])

    # Format amount strings (e.g. 132.45 132,45 132)
    amount_str = ""
    if doc["amount"] is not None:
        amt = doc["amount"]
        int_amt = int(amt) if float(amt).is_integer() else None
        amount_str = f"{amt} {str(amt).replace('.', ',')}"
        if int_amt is not None:
            amount_str += f" {int_amt}"

    # Delete existing FTS record first
    cursor.execute("DELETE FROM documents_fts WHERE document_id = ?", (document_id,))

    # Insert updated FTS record
    cursor.execute("""
        INSERT INTO documents_fts (document_id, filename, content, organization, document_type, document_date, amount, tags)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        doc["id"],
        doc["filename"] or "",
        f"{doc['content'] or ''} {doc['person_name'] or ''}",
        doc["organization"] or "",
        doc["document_type"] or "",
        doc["document_date"] or "",
        amount_str,
        tags_str
    ))


def format_fts_query(raw_query: str, mode: str = "AND", strict_year: bool = True) -> str:
    """
    Converts raw user search string into FTS5 query format.
    Handles French apostrophes (e.g. d'imposition -> avis imposition), quotes, and punctuation.
    When mode="AND", terms are joined with AND. When mode="OR", terms are joined with OR for BM25 ranking.
    """
    if not raw_query:
        return ""

    # Replace apostrophes, hyphens, and punctuation with spaces
    cleaned = re.sub(r"[^\w\s]", " ", raw_query)
    
    tokens = cleaned.strip().split()
    if not tokens:
        return ""
    
    sanitized_tokens = []
    for token in tokens:
        clean = token.strip()
        if not clean:
            continue
            
        # Match 4-digit years (19xx or 20xx) strictly as exact terms
        if re.match(r"^(19|20)\d{2}$", clean):
            if strict_year:
                year_clause = f"(filename:{clean} OR document_date:{clean}* OR organization:{clean} OR document_type:{clean} OR tags:{clean})"
                sanitized_tokens.append(year_clause)
            else:
                sanitized_tokens.append(f'"{clean}"')
        elif len(clean) <= 2:
            # Short words (<=2 chars like "de", "in", "to", "at", "by", "of") -> EXACT match without wildcard '*'
            sanitized_tokens.append(f'"{clean}"')
        else:
            # Words with 3+ chars -> allow prefix matching with '*'
            sanitized_tokens.append(f'"{clean}"*')
            
    if not sanitized_tokens:
        sanitized_tokens = [f'"{t}"*' for t in tokens if t]

    join_str = " AND " if mode.upper() == "AND" else " OR "
    return join_str.join(sanitized_tokens)


def search_documents(conn: sqlite3.Connection, query_str: str, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """
    Performs fast FTS5 full text search.
    0. If query matches a document type category (e.g. "Acte de décès", "Facture"), filters directly by category.
    1. Tries strict AND query matching years to filename/metadata/date.
    2. Tries standard AND body text query.
    3. Falls back to flexible OR query sorted by BM25 relevance score matching maximum terms.
    """
    if not query_str or not query_str.strip():
        return []

    q_clean = query_str.strip()

    # 0. Check if query matches a document_type category directly
    cursor = conn.cursor()
    type_match = cursor.execute(
        "SELECT COUNT(*) FROM documents WHERE LOWER(document_type) = LOWER(?)",
        (q_clean,)
    ).fetchone()[0]

    if type_match > 0:
        clean_type = re.sub(r'[^\w\s]', ' ', q_clean).strip()
        type_fts_query = f'document_type:"{clean_type}"'
        results = _execute_fts_search(conn, type_fts_query, limit, offset)
        if results:
            for r in results:
                r["snippet"] = None
            return results

    has_year = bool(re.search(r'\b(19|20)\d{2}\b', query_str))

    # 1. Try strict AND query first
    strict_and = format_fts_query(query_str, mode="AND", strict_year=True)
    if strict_and:
        results = _execute_fts_search(conn, strict_and, limit, offset)
        if results:
            return results

    # 2. Fallback to standard AND query
    standard_and = format_fts_query(query_str, mode="AND", strict_year=False)
    if standard_and and standard_and != strict_and:
        results = _execute_fts_search(conn, standard_and, limit, offset)
        if results:
            return results

    # If query contains an explicit year (e.g. 2024) and no match was found, return [] without falling back to OR
    if has_year:
        return []

    # 3. Fallback to flexible OR query (only if no explicit year was specified)
    or_query = format_fts_query(query_str, mode="OR", strict_year=False)
    if or_query:
        return _execute_fts_search(conn, or_query, limit, offset)

    return []


def _execute_fts_search(conn: sqlite3.Connection, fts_query: str, limit: int, offset: int) -> List[Dict[str, Any]]:
    """Helper executing FTS5 SQL query with BM25 column weighting."""
    cursor = conn.cursor()
    # BM25 Column Weights: filename=10.0, content=1.0, organization=5.0, document_type=5.0, document_date=10.0, amount=8.0, tags=10.0
    sql = """
        SELECT 
            d.id,
            d.filename,
            d.storage_path,
            d.mime_type,
            d.file_size,
            d.created_at,
            d.document_date,
            d.document_type,
            d.organization,
            d.amount,
            d.ocr_status,
            d.content,
            d.raw_metadata,
            d.person_name,
            snippet(documents_fts, -1, '<mark>', '</mark>', '...', 15) AS snippet_content,
            (
                SELECT GROUP_CONCAT(t.name, ',')
                FROM tags t
                JOIN document_tags dt ON t.id = dt.tag_id
                WHERE dt.document_id = d.id
            ) AS tag_list
        FROM documents_fts fts
        JOIN documents d ON d.id = fts.document_id
        WHERE documents_fts MATCH ?
        ORDER BY bm25(documents_fts, 10.0, 1.0, 5.0, 5.0, 10.0, 8.0, 10.0)
        LIMIT ? OFFSET ?
    """
    
    try:
        rows = cursor.execute(sql, (fts_query, limit, offset)).fetchall()
    except sqlite3.OperationalError:
        return []

    results = []
    for r in rows:
        tags = r["tag_list"].split(",") if r["tag_list"] else []
        snippet = r["snippet_content"]
        if not snippet and r["content"]:
            clean_content = r["content"].strip().replace('\n', ' ')
            snippet = clean_content[:120] + "..." if len(clean_content) > 120 else clean_content

        results.append({
            "id": r["id"],
            "filename": r["filename"],
            "storage_path": r["storage_path"],
            "mime_type": r["mime_type"],
            "file_size": r["file_size"],
            "created_at": r["created_at"],
            "document_date": r["document_date"],
            "document_type": r["document_type"],
            "organization": r["organization"],
            "amount": r["amount"],
            "ocr_status": r["ocr_status"],
            "snippet": snippet,
            "tags": tags,
            "raw_metadata": r["raw_metadata"],
            "person_name": r["person_name"]
        })

    return results

