# 🦥📄 LazyDocs — Zero-Effort Document Organizer

> **Philosophy: "Drop it, find it."**  
> Zero manual sorting. Zero folders to create. Zero tags to fill in.  
> A fast local decision model categorizes everything in the background.

**LazyDocs** is a 100% self-hosted, private document vault to archive, automatically classify, and instantly retrieve any administrative, personal, or financial document (invoices, tax returns, payslips, contracts, IDs, civic certificates, etc.).

---

## 💡 The Lazy Philosophy

- **Zero pre-sorting**: Drop PDFs, scans, or entire folder trees in bulk.
- **Zero reclassification**: Never waste time organizing files into subfolders.
- **Zero duplicates**: Automatic SHA-256 binary fingerprinting ignores existing files on upload.
- **Zero cloud reliance**: Everything runs locally on your machine or home server.

---

## ✨ Key Features

- 📥 **Frictionless Ingestion**:
  - Drag & drop files or whole directories.
  - Strict SHA-256 deduplication at upload time.
  - Mobile PWA with **Web Share Target** (share PDFs and images directly from Gmail, WhatsApp, or File manager).
  - Direct mobile camera scanner shortcut (`capture="environment"`).
- 🧠 **Ultra-Fast AI Classification (Kev Decision Model)**:
  - Powered by a local System One decision engine optimized for probabilistic choice.
  - Zero hallucination, zero verbose generation: direct selection among predefined categories.
  - Configurable external schema in [categories.yaml](categories.yaml) (supports optional household member detection).
- 🗂️ **Built-in Categories**:
  - *Invoices, Quotes, Banking, Payslips, Resumes, Employment, Taxes, Contracts, Housing, Vehicles, Administrative, Identity, Civil Status, Healthcare, Education*.
  - Fallback to `Autre` on low confidence.
- 🔍 **Instant Full-Text Search (SQLite FTS5)**:
  - Fast, accent-insensitive and case-insensitive search engine.
  - Snippet highlights across OCR and native text.
- 👁️ **Embedded Viewer**: Immediate in-browser preview of PDFs and images without forced downloads.
- 🌐 **Bilingual Interface (FR / EN)**: Full UI language toggle in one click.
- 🔄 **One-Click Reindexing**: Re-run AI categorization across your entire library when rules or categories evolve.

---

## 🛠️ Architecture & Tech Stack

- **Backend**: Python 3.11, [FastAPI](https://fastapi.tiangolo.com/), SQLite (WAL Mode + FTS5), PyMuPDF, Tesseract OCR.
- **AI Classification**: [Kev Decision Engine](https://github.com/jaredpalmer/kev) (Docker `lazydocs_kev`, local 0.8B model).
- **Frontend**: Vanilla HTML5 / CSS3 / ES6 (No heavy frameworks, snappy, mobile-responsive PWA).
- **Deployment**: Docker & Docker Compose.

---

## 🚀 Quickstart (Docker)

```bash
docker compose up -d
```

The web application will be accessible at: **`http://localhost:8085`**

---

## ⚙️ Configuration (`docker-compose.yml`)

```yaml
services:
  app:
    environment:
      - KEV_HOST=http://kev:8009
      - KEV_MODEL=jaredpalmer/kev-0.8b
      - LLM_SNIPPET_MAX_CHARS=2500  # Extracted text snippet sent to classifier
      - WORKER_CONCURRENCY=1        # Worker concurrency
    volumes:
      - ./categories.yaml:/app/categories.yaml:ro
      - lazydocs_data:/app/data
```

---

## 📁 Customizing Categories & Persons (`categories.yaml`)

Edit `categories.yaml` on the host to customize classification criteria or add family members without rebuilding the Docker container:

```yaml
instructions: "What kind of official or personal document is this? / Quelle est la nature de ce document ?"

criteria:
  Factures: "Commercial invoice, sales receipt, store receipt, utility bill..."
  Banque: "Banking documents: bank account statement, wire transfer..."
  # ...

persons:
  instructions: "Which person or family member is the primary subject or owner of this document?"
  candidates:
    - "John Doe"
    - "Jane Doe"
```

---

## 📡 REST API Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/documents` | Paginated list of documents with filters (query, category) |
| `POST` | `/api/documents` | Upload files (PDF / Images), SHA-256 deduplication |
| `POST` | `/share-target` | Mobile PWA Web Share Target endpoint |
| `GET` | `/api/search?q=...` | Full-text search (FTS5) with snippets |
| `GET` | `/api/stats` | Document counts and category breakdown for dashboard |
| `GET` | `/api/documents/{id}/file` | View original document inline |
| `POST` | `/api/reindex` | Full AI re-categorization of library |
| `DELETE` | `/api/documents/{id}` | Delete a document from DB, FTS, and storage |
