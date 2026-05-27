from __future__ import annotations

import logging
import math
import re
from typing import Any, cast

_logger: logging.Logger = logging.getLogger(__name__)

_SCORE_TOKENS: frozenset[str] = frozenset({"1", "2", "3", "4", "5"})
_NUMERIC_MASS_WARN_THRESHOLD: float = 0.9
LOGPROBS_COUNT: int = 5

# Matches the JSON `"score"` key followed by its colon and any inter-token whitespace, so the
# regex's `.end()` is the byte offset of the score value's first character. Using an exact
# `"score"` key (rather than substring) prevents matching unrelated occurrences of the word
# (e.g. inside an assessment string, or a hypothetical `score_breakdown` key).
_SCORE_KEY_RE: re.Pattern[str] = re.compile(r'"score"\s*:\s*')


def extract_weighted_score(response: Any) -> float | None:
    """Compute sum P(token_i) * int(token_i) over the score-token position.

    Returns `None` if the provider did not return logprobs, the score token cannot be
    located, or no numeric mass is present. Renormalises across {"1".."5"}; logs a
    warning if <90% of mass falls on numeric tokens.
    """
    try:
        choice: Any = response.choices[0]
        logprobs_obj: Any = getattr(choice, "logprobs", None)
        if logprobs_obj is None:
            return None
        content: Any = getattr(logprobs_obj, "content", None)
        if not content:
            return None
    except (AttributeError, IndexError, TypeError):
        return None

    score_position: Any = _find_score_token_position(content)
    if score_position is None:
        return None

    top: Any = getattr(score_position, "top_logprobs", None)
    if not top:
        return None

    numeric_mass: float = 0.0
    total_mass: float = 0.0
    weighted_sum: float = 0.0
    for entry in top:
        token: str = _strip_token(_attr(entry, "token"))
        logp: float | None = _attr(entry, "logprob")
        if logp is None:
            continue
        p: float = math.exp(logp)
        total_mass += p
        if token in _SCORE_TOKENS:
            numeric_mass += p
            weighted_sum += p * float(token)

    if numeric_mass <= 0.0:
        return None
    if total_mass > 0.0 and (numeric_mass / total_mass) < _NUMERIC_MASS_WARN_THRESHOLD:
        _logger.warning(
            "TemplatedLLM: only %.1f%% of top-%d probability mass at score token is numeric (1-5).",
            100.0 * numeric_mass / total_mass,
            LOGPROBS_COUNT,
        )
    return weighted_sum / numeric_mass


def _find_score_token_position(content: list[Any]) -> Any:
    """Locate the content entry whose token holds the JSON value of the `"score"` field.

    Strategy: reconstruct the full output text by concatenating every token, locate the
    `"score":` key with an exact regex, then find the token whose byte range contains the
    first character after the colon-plus-whitespace. The matched token's stripped form must
    be a digit in {1..5}; otherwise we return `None` (the caller falls back to the parsed
    integer score). This is tighter than substring-matching for `score` since it cannot
    false-trigger on the word appearing inside other keys or string values.
    """
    offsets: list[int] = []
    cursor: int = 0
    for entry in content:
        raw: str = _attr(entry, "token") or ""
        offsets.append(cursor)
        cursor += len(raw)
    full_text: str = "".join((_attr(e, "token") or "") for e in content)

    match: re.Match[str] | None = _SCORE_KEY_RE.search(full_text)
    if match is None:
        return None
    value_offset: int = match.end()

    for i, off in enumerate(offsets):
        raw = _attr(content[i], "token") or ""
        if off <= value_offset < off + len(raw):
            return content[i] if _strip_token(raw) in _SCORE_TOKENS else None
    return None


def _attr(obj: Any, name: str) -> Any:
    if isinstance(obj, dict):
        return cast(dict[str, Any], obj).get(name)
    return getattr(obj, name, None)


def _strip_token(token: str | None) -> str:
    if not token:
        return ""
    # Tokenizers may prefix with a leading space (e.g. " 4"). Strip whitespace + quotes.
    return token.strip().strip('"').strip("'")
