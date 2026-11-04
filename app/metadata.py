import re
from typing import Dict, Any, Optional, List
from datetime import datetime

MONTHS_MAP = {
    'janvier': '01', 'janv': '01', 'february': '02', 'février': '02', 'fevrier': '02', 'févr': '02',
    'mars': '03', 'mar': '03', 'avril': '04', 'avr': '04', 'mai': '05', 'juin': '06',
    'juillet': '07', 'juil': '07', 'août': '08', 'aout': '08', 'septembre': '09', 'sept': '09',
    'octobre': '10', 'oct': '10', 'novembre': '11', 'nov': '11', 'décembre': '12', 'decembre': '12', 'déc': '12'
}

# Generic Regex Utilities for Dates and Amounts (Offline Fallback Only)

def extract_document_date(text: str) -> Optional[str]:
    """
    Extracts document date in YYYY-MM-DD format (ISO standard).
    Supports ISO (YYYY-MM-DD), European (DD/MM/YYYY), and textual month dates across languages.
    """
    if not text:
        return None

    # Pattern 1: ISO YYYY-MM-DD or YYYY/MM/DD
    match = re.search(r'\b(19[89][0-9]|20[0-9]{2})[-/](0[1-9]|1[0-2])[-/](0[1-9]|[12][0-9]|3[01])\b', text)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"

    # Pattern 2: European DD/MM/YYYY or DD.MM.YYYY
    match = re.search(r'\b(0[1-9]|[12][0-9]|3[01])[-/\.](0[1-9]|1[0-2])[-/\.](19[89][0-9]|20[0-9]{2})\b', text)
    if match:
        return f"{match.group(3)}-{match.group(2)}-{match.group(1)}"

    # Pattern 2b: European DD/MM/YY (e.g. 14/10/16 -> 2016-10-14)
    match = re.search(r'\b(0?[1-9]|[12][0-9]|3[01])[-/\.](0?[1-9]|1[0-2])[-/\.](0[0-9]|1[0-9]|2[0-9])\b', text)
    if match:
        day = f"{int(match.group(1)):02d}"
        month = f"{int(match.group(2)):02d}"
        yy = int(match.group(3))
        yyyy = f"20{yy:02d}" if yy <= 30 else f"19{yy:02d}"
        return f"{yyyy}-{month}-{day}"

    # Pattern 3: Textual dates (e.g. 1er août 2025, 15 décembre 2026, 14 july 2026)
    match = re.search(
        r'\b(0?[1-9]|[12][0-9]|3[01]|1er)\s+([a-zA-][a-zàâéèêëîïôûùüç]+)\s+(19[89][0-9]|20[0-9]{2})\b',
        text,
        re.IGNORECASE
    )
    if match:
        day_str = match.group(1).lower().replace('1er', '01')
        day = f"{int(day_str):02d}"
        month_raw = match.group(2).lower()
        year = match.group(3)
        month = MONTHS_MAP.get(month_raw)
        if month:
            return f"{year}-{month}-{day}"

    return None


def extract_amount(text: str) -> Optional[float]:
    """
    Extracts total financial amount in a language-agnostic way (EUR, USD, GBP, CHF, etc.).
    """
    if not text:
        return None

    # Universal total keyword pattern across EN, FR, DE, ES, IT
    keyword_pattern = r'(?:TOTAL\s+TTC|TOTAL|AMOUNT|MONTANT|SUMME|IMPORTE|NET\s+À?\s*PAYER|TOTAL\s+DUE|DUE|BETRAG)\s*[:=]?\s*([0-9\s\.\,]+)'
    match = re.search(keyword_pattern, text, re.IGNORECASE)
    if match:
        raw_val = match.group(1).replace(' ', '').replace(',', '.')
        float_match = re.search(r'\d+(\.\d{1,2})?', raw_val)
        if float_match:
            try:
                val = float(float_match.group(0))
                if val > 0: return val
            except ValueError:
                pass

    # Universal currency number pattern: 1 250,50 € or 132.45 EUR or $125.00
    currency_pattern = r'(?:€|\$|£|CHF|EUR|USD|GBP)?\s*([0-9]{1,3}(?:[\s.][0-9]{3})*[\.,][0-9]{2})\s*(?:€|\$|£|CHF|EUR|USD|GBP)?'
    matches = re.findall(currency_pattern, text, re.IGNORECASE)
    if matches:
        floats = []
        for raw in matches:
            if not raw: continue
            try:
                clean_num = raw.replace(' ', '').replace(',', '.')
                floats.append(float(clean_num))
            except ValueError:
                pass
        if floats:
            return max(floats)

    return None



def _call_kev(
    text: str,
    categories: List[str] = None,
    persons: List[str] = None,
    timeout_sec: float = 30.0
) -> Optional[Dict[str, str]]:
    """Helper to query the Kev Decision Model (System One API)."""
    import urllib.request
    import json
    import logging
    from app.config import KEV_HOST, KEV_MODEL
    from app.schemas import KEV_DOCUMENT_TYPE_QUESTION

    questions = {"document_type": KEV_DOCUMENT_TYPE_QUESTION}
    if persons:
        questions["person_name"] = {
            "type": "choice",
            "instructions": "Which person is the primary subject or owner of this document?",
            "criteria": {p: f"Subject or owner: {p}" for p in persons}
        }

    from app.config import LLM_SNIPPET_MAX_CHARS
    payload = json.dumps({
        "state": text[:LLM_SNIPPET_MAX_CHARS],
        "model": KEV_MODEL,
        "questions": questions
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{KEV_HOST}/v1/systemone",
        data=payload,
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            results = {}
            answers = res_data.get("answers", {})
            for q_id, ans in answers.items():
                choice = ans.get("choice")
                conf = ans.get("confidence", 1.0)
                if choice:
                    results[q_id] = choice
                    results[f"{q_id}_confidence"] = conf
            return results
    except Exception as e:
        logging.getLogger("lazydocs.metadata").warning(f"Kev Decision Model error: {e}")
        return None




from app.schemas import get_supported_types


def sanitize_organization(org: Optional[str]) -> Optional[str]:
    """Returns stripped organization name without regex manipulation."""
    if not org or not isinstance(org, str):
        return None
    s = org.strip()
    return s if s else None


def sanitize_person_name(person_name: Optional[str], filename: str = "") -> Optional[str]:
    """Returns stripped person name without regex manipulation."""
    if not person_name or not isinstance(person_name, str) or person_name == "Non spécifié":
        return None
    s = person_name.strip()
    return s if s else None


def sanitize_extracted_date(raw_date: Optional[str], text: str) -> Optional[str]:
    """Validates date string or falls back to text regex extraction."""
    current_year = datetime.now().year

    if isinstance(raw_date, str) and raw_date.strip():
        val = raw_date.strip()
        match = re.search(r'\b(19[5-9][0-9]|20[0-9]{2})[-/](0[1-9]|1[0-2])[-/](0[1-9]|[12][0-9]|3[01])\b', val)
        if match:
            year = int(match.group(1))
            if 1950 <= year <= current_year + 1:
                return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"

    return extract_document_date(text)


def extract_metadata_llm(text: str, filename: str = "", target_lang: str = "fr", model: Optional[str] = None) -> Dict[str, Any]:
    """
    Classification 100% Kev Decision Model + extraction dates/montants Regex (~30ms).
    """
    fallback = extract_metadata(text)
    if not text or len(text.strip()) < 10:
        return fallback

    from app.config import LLM_SNIPPET_MAX_CHARS, USE_KEV_CLASSIFIER
    # Prepend filename to context so Kev has filename information (e.g. CV, Facture)
    file_prefix = f"Fichier: {filename}\n" if filename else ""
    snippet = f"{file_prefix}{text}"[:LLM_SNIPPET_MAX_CHARS]
    from app.schemas import get_supported_types, get_configured_persons
    supported_types = get_supported_types(lang=target_lang)
    configured_persons = get_configured_persons()

    # Categorization via Kev Decision Model (100% Kev)
    import time
    t0 = time.perf_counter()
    kev_result = None
    if USE_KEV_CLASSIFIER:
        kev_result = _call_kev(text=snippet, categories=supported_types, persons=configured_persons if configured_persons else None)
    elapsed_ms = round((time.perf_counter() - t0) * 1000)

    doc_type = "Autre"
    person_kev = None
    if kev_result:
        choice = kev_result.get("document_type")
        conf = kev_result.get("document_type_confidence", 1.0)
        if choice and choice in supported_types and conf >= 0.05:
            doc_type = choice
        person_kev = kev_result.get("person_name")

    doc_date = extract_document_date(text) or fallback["document_date"]
    amount = extract_amount(text) or fallback["amount"]
    person_name = sanitize_person_name(person_kev, filename)

    import logging
    logger = logging.getLogger("lazydocs.metadata")
    if kev_result:
        logger.info(f"⚡ [Kev Classifier] Document '{filename}' categorized as '{doc_type}' ({elapsed_ms}ms)")
    else:
        logger.warning(f"⚠️ [Kev Classifier] Document '{filename}': Kev failed ({elapsed_ms}ms), fallback to '{doc_type}'")

    return {
        "organization": fallback.get("organization") or "",
        "document_type": doc_type,
        "document_date": doc_date,
        "amount": amount,
        "person_name": person_name,
        "classifier": "kev",
        "raw_metadata": {"kev_decisions": kev_result or {}}
    }


def extract_metadata(text: str) -> Dict[str, Any]:
    """
    Minimal fallback when LLM is unavailable.
    Uses universal generic regexes only (no hardcoded company or category lists).
    """
    if not text:
        return {
            "organization": None,
            "document_type": None,
            "document_date": None,
            "amount": None
        }

    return {
        "organization": None,
        "document_type": None,
        "document_date": extract_document_date(text),
        "amount": extract_amount(text)
    }

