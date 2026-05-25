from __future__ import annotations

import hashlib

from .._prompt import Document


def candidate_id_of(doc: Document) -> str:
    """Short stable id for a candidate, derived from its prompt markdown."""
    digest: str = hashlib.sha1(doc.to_markdown().encode("utf-8")).hexdigest()
    return f"cand_{digest[:10]}"
