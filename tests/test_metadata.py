from app.metadata import (
    extract_document_date,
    extract_amount,
    extract_metadata
)


def test_extract_document_date():
    assert extract_document_date("Fait le 14/07/2026 à Paris") == "2026-07-14"
    assert extract_document_date("Date de facture : 2026-08-01") == "2026-08-01"
    assert extract_document_date("Émis le 1er août 2025") == "2025-08-01"
    assert extract_document_date("Paris le 15 décembre 2026") == "2026-12-15"


def test_extract_amount():
    assert extract_amount("TOTAL TTC : 132,45 €") == 132.45
    assert extract_amount("NET À PAYER : 540.00 EUR") == 540.0
    assert extract_amount("Montant total de la facture: 1 250,50 €") == 1250.50


def test_extract_metadata_fallback():
    sample_text = """
    Électricité de France
    FACTURE N° 10928374
    Date d'émission: 14/07/2026
    
    Total de votre consommation : 132,45 €
    NET À PAYER : 132,45 €
    """
    meta = extract_metadata(sample_text)
    assert meta["organization"] is None
    assert meta["document_type"] is None
    assert meta["document_date"] == "2026-07-14"
    assert meta["amount"] == 132.45


def test_extract_metadata_llm_bulletin_paie(monkeypatch):
    from app.metadata import extract_metadata_llm

    calls = []
    def mock_call_kev(text, categories=None, persons=None, timeout_sec=3.0):
        calls.append(text)
        return {
            "document_type": "Bulletin de paie",
            "person_name": "Jean Dupont"
        }

    monkeypatch.setattr("app.metadata._call_kev", mock_call_kev)

    sample_text = """
    BULLETIN DE PAIE - JUIN 2026
    Employeur : ACME Corporation
    Salarié : Jean Dupont
    Date de virement : 30/06/2026
    NET À PAYER : 2 450,75 €
    """

    res = extract_metadata_llm(sample_text)
    assert res["document_type"] == "Bulletin de paie"
    assert res["person_name"] == "Jean Dupont"
    assert res["document_date"] == "2026-06-30"
    assert res["amount"] == 2450.75
    assert len(calls) == 1
    assert res["classifier"] == "kev"

