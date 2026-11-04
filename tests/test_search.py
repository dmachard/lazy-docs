import pytest
import sqlite3
from app.database import init_db, sync_fts, search_documents


@pytest.fixture
def db_conn(tmp_path):
    db_file = tmp_path / "test_lazydocs.db"
    init_db(db_file)
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def test_fts5_accent_case_insensitive_search(db_conn):
    # Insert test documents
    with db_conn:
        db_conn.execute("""
            INSERT INTO documents (id, filename, storage_path, content, organization, document_type, amount, ocr_status)
            VALUES 
            ('doc-1', 'Facture_EDF_Juillet_2026.pdf', '2026/doc-1.pdf', 'Facture Électricité de France EDF pour le mois de juillet 2026. Montant 132,45 €.', 'EDF', 'Facture', 132.45, 'ready'),
            ('doc-2', 'Assurance_Habitation_2026.pdf', '2026/doc-2.pdf', 'Contrat assurance multirisque habitation maison MAIF numéro 987654. Cotisation annuelle.', 'MAIF', 'Contrat', 250.00, 'ready'),
            ('doc-3', 'Avis_Impot_Foncier.pdf', '2026/doc-3.pdf', 'Avis d imposable 2026 Trésor public impôts fonciers. Taxe locale.', 'Impôts', 'Avis d''imposition', 540.00, 'ready')
        """)
        
        # Sync FTS
        sync_fts(db_conn, 'doc-1')
        sync_fts(db_conn, 'doc-2')
        sync_fts(db_conn, 'doc-3')

    # Test 1: Search uppercase / lowercase / accents
    res_edf_upper = search_documents(db_conn, "EDF")
    res_edf_lower = search_documents(db_conn, "edf")
    res_edf_accent = search_documents(db_conn, "electricite")
    
    assert len(res_edf_upper) == 1
    assert len(res_edf_lower) == 1
    assert len(res_edf_accent) == 1
    assert res_edf_upper[0]["id"] == "doc-1"
    assert res_edf_accent[0]["id"] == "doc-1"

    # Test 2: Search multi-word query (EDF 2026)
    res_multi = search_documents(db_conn, "EDF 2026")
    assert len(res_multi) == 1
    assert res_multi[0]["id"] == "doc-1"

    # Test 3: Search with French apostrophe (avis d'imposition, d'impôt)
    res_apostrophe = search_documents(db_conn, "avis d'imposition")
    assert len(res_apostrophe) == 1
    assert res_apostrophe[0]["id"] == "doc-3"

    # Test 4: Amount search (132 or 132.45)
    res_amount = search_documents(db_conn, "132")
    assert len(res_amount) == 1
    assert res_amount[0]["id"] == "doc-1"

    # Test 5: Search with currency word (132 euros)
    res_currency = search_documents(db_conn, "132 euros")
    assert len(res_currency) >= 1
    assert res_currency[0]["id"] == "doc-1"

    # Test 6: Broad search fallback with multiple terms (facture maison edf)
    res_or = search_documents(db_conn, "facture maison edf")
    assert len(res_or) >= 2
    # Ranked by BM25 relevance: doc-1 matching 'facture' and 'edf' should be first
    assert res_or[0]["id"] == "doc-1"
