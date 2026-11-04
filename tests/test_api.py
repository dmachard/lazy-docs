import pytest
import io
import zipfile
from fastapi.testclient import TestClient

from app.main import app
from app.database import init_db


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Set temp directory paths
    db_file = tmp_path / "test_api.db"
    storage_dir = tmp_path / "documents"
    storage_dir.mkdir()

    init_db(db_file)

    monkeypatch.setattr("app.main.DB_PATH", db_file)
    monkeypatch.setattr("app.main.STORAGE_DIR", storage_dir)
    monkeypatch.setattr("app.api.DB_PATH", db_file)
    monkeypatch.setattr("app.api.STORAGE_DIR", storage_dir)
    monkeypatch.setattr("app.worker.DB_PATH", db_file)
    monkeypatch.setattr("app.worker.STORAGE_DIR", storage_dir)

    with TestClient(app) as test_client:
        yield test_client


def test_upload_and_get_document(client):
    # 1. Check system status before upload
    res_status = client.get("/api/status")
    assert res_status.status_code == 200
    assert res_status.json()["total"] == 0

    # 2. Upload valid PDF
    pdf_bytes = b"%PDF-1.7\n%...Test PDF file content...\nFacture EDF 2026 132,45 euro"
    files = [("files", ("Facture_EDF.pdf", io.BytesIO(pdf_bytes), "application/pdf"))]
    
    response = client.post("/api/documents", files=files)
    assert response.status_code == 201
    data = response.json()
    assert len(data) == 1
    doc_id = data[0]["id"]
    assert data[0]["filename"] == "Facture_EDF.pdf"
    assert data[0]["ocr_status"] == "pending"
    assert data[0].get("is_duplicate") is False

    # 2b. Upload exact duplicate file
    dup_files = [("files", ("Facture_EDF_Copie.pdf", io.BytesIO(pdf_bytes), "application/pdf"))]
    dup_res = client.post("/api/documents", files=dup_files)
    assert dup_res.status_code == 201
    dup_data = dup_res.json()
    assert len(dup_data) == 1
    assert dup_data[0]["id"] == doc_id
    assert dup_data[0]["is_duplicate"] is True

    # Check status after upload
    res_status_after = client.get("/api/status")
    assert res_status_after.json()["total"] == 1
    assert res_status_after.json()["pending"] == 1

    # Verify list documents pagination
    res_list = client.get("/api/documents")
    assert res_list.status_code == 200
    list_data = res_list.json()
    assert list_data["total"] == 1
    assert list_data["page"] == 1
    assert len(list_data["documents"]) == 1
    assert list_data["documents"][0]["id"] == doc_id

    # 3. Get document details
    res_get = client.get(f"/api/documents/{doc_id}")
    assert res_get.status_code == 200
    assert res_get.json()["id"] == doc_id

    # 4. Add and remove tags
    res_tag = client.post(f"/api/documents/{doc_id}/tags", json={"name": "electricite"})
    assert res_tag.status_code == 200
    assert "electricite" in res_tag.json()

    res_untag = client.delete(f"/api/documents/{doc_id}/tags/electricite")
    assert res_untag.status_code == 200
    assert "electricite" not in res_untag.json()

    # 5. Backup export check
    res_backup = client.get("/api/backup")
    assert res_backup.status_code == 200
    assert res_backup.headers["content-type"] == "application/zip"
    
    # Verify backup zip contents
    with zipfile.ZipFile(io.BytesIO(res_backup.content)) as zf:
        namelist = zf.namelist()
        assert "database.sqlite" in namelist

    # 6. Download document
    res_file = client.get(f"/api/documents/{doc_id}/file")
    assert res_file.status_code == 200
    assert res_file.content == pdf_bytes

    # 7. Delete document
    res_del = client.delete(f"/api/documents/{doc_id}")
    assert res_del.status_code == 204

    # 8. Verify 404 after deletion
    res_get_del = client.get(f"/api/documents/{doc_id}")
    assert res_get_del.status_code == 404


def test_dynamic_sw_cache_name(client, monkeypatch):
    monkeypatch.setattr("app.api.TAG", "v1.2.3")
    res = client.get("/sw.js")
    assert res.status_code == 200
    assert "const CACHE_NAME = 'lazydocs-v1.2.3';" in res.text
    assert res.headers["cache-control"] == "no-cache, no-store, must-revalidate"


def _upload_test_pdf(client, filename="test.pdf", text_extra=""):
    content = f"%PDF-1.7\n%...dummy content {filename} {text_extra}".encode("utf-8")
    files = [("files", (filename, io.BytesIO(content), "application/pdf"))]
    res = client.post("/api/documents", files=files)
    assert res.status_code == 201
    return res.json()[0]


def test_update_document_metadata_and_status(client):
    doc = _upload_test_pdf(client, "facture_2026.pdf")
    doc_id = doc["id"]

    # Check status endpoint
    st_res = client.get(f"/api/documents/{doc_id}/status")
    assert st_res.status_code == 200
    assert st_res.json()["status"] == "pending"

    # Patch document metadata
    patch_payload = {
        "filename": "Facture_EDF_Janvier.pdf",
        "document_type": "Factures",
        "organization": "EDF",
        "amount": 89.50,
        "document_date": "2026-01-15",
        "person_name": "Jean Dupont"
    }
    patch_res = client.patch(f"/api/documents/{doc_id}", json=patch_payload)
    assert patch_res.status_code == 200
    updated = patch_res.json()
    assert updated["filename"] == "Facture_EDF_Janvier.pdf"
    assert updated["document_type"] == "Factures"
    assert updated["organization"] == "EDF"
    assert updated["amount"] == 89.50
    assert updated["document_date"] == "2026-01-15"
    assert updated["person_name"] == "Jean Dupont"

    # Verify 404 for unknown document patch
    res_404 = client.patch("/api/documents/nonexistent-id", json={"organization": "Test"})
    assert res_404.status_code == 404


def test_batch_delete_documents(client):
    doc1 = _upload_test_pdf(client, "doc1.pdf")
    doc2 = _upload_test_pdf(client, "doc2.pdf")

    # Batch delete both
    del_res = client.delete(f"/api/documents?doc_ids={doc1['id']}&doc_ids={doc2['id']}")
    assert del_res.status_code == 204

    # Verify neither exists
    assert client.get(f"/api/documents/{doc1['id']}").status_code == 404
    assert client.get(f"/api/documents/{doc2['id']}").status_code == 404


def test_search_and_suggested_filters(client):
    doc = _upload_test_pdf(client, "impots_2026.pdf")
    doc_id = doc["id"]

    # Set metadata and sync
    client.patch(f"/api/documents/{doc_id}", json={
        "document_type": "Impôts/Taxes",
        "organization": "DGFiP"
    })

    # Search by organization
    search_res = client.get("/api/search?q=DGFiP")
    assert search_res.status_code == 200
    results = search_res.json()["results"]
    assert len(results) >= 1
    assert any(r["id"] == doc_id for r in results)

    # Suggested filters endpoint
    filters_res = client.get("/api/suggested-filters")
    assert filters_res.status_code == 200
    assert "Impôts/Taxes" in filters_res.json()["filters"]


def test_stats_endpoint(client):
    doc = _upload_test_pdf(client, "contrat.pdf")
    client.patch(f"/api/documents/{doc['id']}", json={
        "document_type": "Contrats",
        "organization": "Assurance Auto",
        "amount": 250.0
    })

    stats_res = client.get("/api/stats")
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert stats["total_docs"] >= 1
    assert stats["total_orgs"] >= 1
    assert stats["total_types"] >= 1
    assert stats["total_amount"] >= 250.0
    assert isinstance(stats["type_breakdown"], list)
    assert isinstance(stats["top_orgs"], list)


def test_reindex_and_cancel_endpoints(client):
    doc = _upload_test_pdf(client, "doc_reindex.pdf")

    # Reindex single document
    res_single = client.post(f"/api/documents/{doc['id']}/reindex")
    assert res_single.status_code == 200
    assert res_single.json()["id"] == doc["id"]

    # Reindex all
    res_all = client.post("/api/reindex")
    assert res_all.status_code == 200
    assert res_all.json()["count"] >= 1

    # Cancel indexing
    res_cancel = client.post("/api/cancel-indexing")
    assert res_cancel.status_code == 200
    assert "cancelled_tasks" in res_cancel.json()


def test_share_target_upload(client):
    pdf_bytes = b"%PDF-1.7\n%share target test content"
    files = [("files", ("shared_doc.pdf", io.BytesIO(pdf_bytes), "application/pdf"))]
    res = client.post("/share-target", files=files, follow_redirects=False)
    assert res.status_code == 303
    assert res.headers["location"] == "/?shared=1"


def test_tags_suggestions_and_errors(client):
    doc = _upload_test_pdf(client, "doc_tagged.pdf")
    doc_id = doc["id"]

    client.post(f"/api/documents/{doc_id}/tags", json={"name": "Urgent"})

    # Tag suggestions
    sug_res = client.get("/api/tags/suggestions")
    assert sug_res.status_code == 200
    assert "urgent" in sug_res.json()

    # Empty tag error
    err_empty = client.post(f"/api/documents/{doc_id}/tags", json={"name": "   "})
    assert err_empty.status_code == 400

    # Unknown document tag error
    err_404 = client.post("/api/documents/unknown-id/tags", json={"name": "test"})
    assert err_404.status_code == 404


def test_upload_invalid_file_rejected(client):
    bad_bytes = b"MZ\x90\x00executable content"
    files = [("files", ("malicious.exe", io.BytesIO(bad_bytes), "application/octet-stream"))]
    res = client.post("/api/documents", files=files)
    assert res.status_code == 400

