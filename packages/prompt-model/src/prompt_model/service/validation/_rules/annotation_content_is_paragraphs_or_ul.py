from __future__ import annotations

from ...._protocols.prompt_validator import MarkdownTokenList, PromptValidator
from ....model.prompt_validation_error import PromptError, PromptErrorType
from ._annotation_helpers import (
    annotation_name,
    find_matching_close,
    is_annotation_open,
)


class AnnotationContentIsParagraphsOrUL(PromptValidator):
    """Body of `::: examples` / `::: guidance` must be either:
    - one or more paragraphs (parser collapses them into one Annotation), or
    - a single flat bullet list (one Annotation per item).

    Anything else — code blocks, blockquotes, tables, ordered lists, a paragraph
    mixed with a list, multiple bullet lists — is rejected. Headings and nested
    annotations are covered by separate rules and not re-flagged here.
    """

    def find_errors(self, tokens: MarkdownTokenList | None) -> list[PromptError]:
        if not tokens:
            return []

        errors: list[PromptError] = []
        for i, token in enumerate(tokens):
            if not is_annotation_open(token):
                continue
            close_i = find_matching_close(tokens, i)
            if close_i == -1:
                continue
            errors.extend(self._check_one_directive(tokens, i, close_i))
        return errors

    def _check_one_directive(self, tokens: MarkdownTokenList, open_i: int, close_i: int) -> list[PromptError]:
        child_level = tokens[open_i].level + 1
        children = _direct_children(tokens, open_i, close_i, child_level)
        errors: list[PromptError] = []

        bullet_count = sum(1 for kind, _ in children if kind == "bullet_list")
        paragraph_count = sum(1 for kind, _ in children if kind == "paragraph")

        for kind, line in children:
            if kind == "paragraph":
                # paragraph mixed with a bullet list is an error; flag the
                # paragraph(s) when both forms appear.
                if bullet_count > 0:
                    errors.append(
                        _err(
                            line,
                            "Annotation body cannot mix paragraphs with a list; use one form or the other.",
                        )
                    )
                continue
            if kind == "bullet_list":
                if paragraph_count > 0:
                    # The paragraph case already flagged it; don't double-report.
                    continue
                if bullet_count > 1:
                    errors.append(
                        _err(
                            line,
                            "Annotation body must contain at most one bullet list.",
                        )
                    )
                continue
            if kind == "heading" or kind.startswith("container_"):
                # Covered by NoHeadingInAnnotation / NoNestedAnnotation.
                continue
            errors.append(
                _err(
                    line,
                    f"Annotation body must be paragraphs or a single bullet list; '{kind}' is not allowed.",
                )
            )
        return errors


def _direct_children(tokens: MarkdownTokenList, open_i: int, close_i: int, child_level: int) -> list[tuple[str, int]]:
    """Return (kind, 1-based line) for each direct child block of the directive."""
    out: list[tuple[str, int]] = []
    for j in range(open_i + 1, close_i):
        t = tokens[j]
        if t.level != child_level:
            continue
        kind: str | None
        if t.nesting == 1:
            kind = _block_open_kind(t.type)
        elif t.nesting == 0 and t.type != "inline":
            kind = t.type
        else:
            kind = None
        if kind is None:
            continue
        # Nested annotation containers come through as container_<name>_open;
        # collapse to a stable "container_..." marker so the caller can skip them.
        if annotation_name(t) is not None:
            kind = "container_annotation"
        line = (t.map[0] + 1) if t.map else 0
        out.append((kind, line))
    return out


def _block_open_kind(token_type: str) -> str | None:
    if not token_type.endswith("_open"):
        return None
    return token_type[: -len("_open")]


def _err(line: int, message: str) -> PromptError:
    return PromptError(
        line=line,
        error_type=PromptErrorType.IllegalAnnotationContent,
        error_message=message,
    )
