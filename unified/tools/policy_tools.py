"""Policy Evidence Tools for PolicyProof Unified MCP.

Exposes tools for retrieving factual policy evidence from the structured JSON store.
Contains NO LLM logic, NO policy recommendations, and NO insurance decisions.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger("policyproof-unified-mcp.policy_tools")

# Determine evidence file path robustly across Windows, Linux, and Render
DEFAULT_EVIDENCE_PATH = Path(__file__).resolve().parent.parent / "evidence" / "policies.json"
EVIDENCE_FILE_PATH = Path(os.environ.get("POLICY_EVIDENCE_FILE", str(DEFAULT_EVIDENCE_PATH)))


def load_evidence_store() -> List[Dict[str, Any]]:
    """Loads policy evidence from the structured JSON store."""
    if not EVIDENCE_FILE_PATH.exists():
        logger.warning(f"Evidence file not found at {EVIDENCE_FILE_PATH}")
        return []
    try:
        with open(EVIDENCE_FILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("policies", [])
    except Exception as e:
        logger.error(f"Failed to load evidence file: {e}")
        return []


def search_evidence_records(policy_id: str, query: str) -> List[Dict[str, Any]]:
    """Searches matching policy evidence records based on policy_id and query keywords.

    Returns strictly factual evidence records without synthesis, recommendation, or evaluation.
    """
    normalized_policy_id = policy_id.strip().lower()
    normalized_query = query.strip().lower()
    query_tokens = [q for q in normalized_query.split() if q]

    policies = load_evidence_store()
    target_policy = None

    for policy in policies:
        if str(policy.get("policy_id", "")).strip().lower() == normalized_policy_id:
            target_policy = policy
            break

    if not target_policy:
        logger.info(f"No policy found matching policy_id='{policy_id}'")
        return []

    raw_evidence = target_policy.get("evidence", [])
    if not query_tokens:
        # Return all evidence records for the given policy if no query keywords provided
        return [
            {
                "source": item.get("source", ""),
                "page": item.get("page", 0),
                "excerpt": item.get("excerpt", ""),
                "source_url": item.get("source_url", ""),
            }
            for item in raw_evidence
        ]

    # Keyword matching against excerpt and source
    results: List[Dict[str, Any]] = []
    for item in raw_evidence:
        source_text = item.get("source", "").lower()
        excerpt_text = item.get("excerpt", "").lower()
        combined_text = f"{source_text} {excerpt_text}"

        # Match if any token is present in the record
        if any(token in combined_text for token in query_tokens):
            results.append({
                "source": item.get("source", ""),
                "page": item.get("page", 0),
                "excerpt": item.get("excerpt", ""),
                "source_url": item.get("source_url", ""),
            })

    return results


def search_policy_evidence(policy_id: str, query: str) -> Dict[str, Any]:
    """Searches the policy evidence store for citations, pages, and excerpts matching
    a specific policy ID and query terms.

    Returns factual evidence excerpts only. Does NOT evaluate claims, decide policy
    superiority, or make recommendations.

    Args:
        policy_id: The unique identifier of the policy (e.g. 'POL-HDFC-TEST', 'POL-CARE-TEST').
        query: Search keywords or question phrase (e.g. 'pre-existing disease waiting period', 'co-pay').

    Returns:
        Dictionary containing policy_id, query, and list of matched factual evidence items.
    """
    results = search_evidence_records(policy_id=policy_id, query=query)
    return {
        "policy_id": policy_id,
        "query": query,
        "results": results,
    }
