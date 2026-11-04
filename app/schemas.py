"""
Centralized Kev System One Decision Schema
Loads document categories and criteria from external categories.yaml.
"""

import logging
from typing import Dict, Any, List
from pathlib import Path
import yaml
from app.config import CATEGORIES_CONFIG_PATH

logger = logging.getLogger("lazydocs.schemas")


def load_kev_document_question() -> Dict[str, Any]:
    """Loads Kev question and criteria from external YAML configuration."""
    config_path = Path(CATEGORIES_CONFIG_PATH)
    if not config_path.exists():
        logger.error(f"Categories config not found at {config_path}")
        return {"type": "choice", "instructions": "", "criteria": {}}

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        criteria = data.get("criteria", {})
        instructions = data.get("instructions", "What kind of official or personal document is this? / Quelle est la nature de ce document ?")
        logger.info(f"Loaded {len(criteria)} categories from {config_path}")

        return {
            "type": "choice",
            "instructions": instructions,
            "criteria": criteria
        }
    except Exception as e:
        logger.error(f"Failed to parse {config_path}: {e}")
        return {"type": "choice", "instructions": "", "criteria": {}}


# Loaded Kev Decision Question and Persons
KEV_DOCUMENT_TYPE_QUESTION: Dict[str, Any] = load_kev_document_question()


def get_configured_persons() -> List[str]:
    """Returns candidate persons list from categories.yaml if configured, otherwise empty list."""
    config_path = Path(CATEGORIES_CONFIG_PATH)
    if not config_path.exists() or not config_path.is_file():
        return []
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if isinstance(data, dict) and "persons" in data and isinstance(data["persons"], dict):
            candidates = data["persons"].get("candidates", [])
            if isinstance(candidates, dict):
                return [k.strip() for k in candidates.keys() if isinstance(k, str) and k.strip()]
            if isinstance(candidates, list):
                return [c.strip() for c in candidates if isinstance(c, str) and c.strip()]
    except Exception as e:
        logger.warning(f"Failed to parse persons from {config_path}: {e}")
    return []


def get_supported_types(lang: str = "fr") -> List[str]:
    """Returns the list of document categories supported by Kev."""
    categories = list(KEV_DOCUMENT_TYPE_QUESTION["criteria"].keys())
    if "Autre" not in categories:
        categories.append("Autre")
    return categories
