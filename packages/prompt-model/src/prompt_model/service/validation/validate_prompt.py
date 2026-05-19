from __future__ import annotations

from pathlib import Path

from markdown_it import MarkdownIt
from mdit_py_plugins.container import container_plugin

from ..._protocols.prompt_validator import MarkdownTokenList, PromptValidator
from ...model.prompt_validation_error import PromptError
from ._rules.annotation_content_is_paragraphs_or_ul import AnnotationContentIsParagraphsOrUL
from ._rules.annotation_host_is_valid import AnnotationHostIsValid
from ._rules.first_heading_is_h1 import FirstHeadingIsH1
from ._rules.markdown_not_empty import MarkdownNotEmpty
from ._rules.no_duplicate_annotation_kind import NoDuplicateAnnotationKind
from ._rules.no_empty_annotation import NoEmptyAnnotation
from ._rules.no_empty_heading import NoEmptyHeading
from ._rules.no_empty_list_item import NoEmptyListItem
from ._rules.no_heading_in_annotation import NoHeadingInAnnotation
from ._rules.no_heading_in_list_item import NoHeadingInListItem
from ._rules.no_heading_level_skip import NoHeadingLevelSkip
from ._rules.no_mixed_list_type_siblings import NoMixedListTypeSiblings
from ._rules.no_nested_annotation import NoNestedAnnotation
from ._rules.no_nested_list_in_annotation import NoNestedListInAnnotation
from ._rules.no_orphan_annotation import NoOrphanAnnotation


def _build_parser() -> MarkdownIt:
    parser = MarkdownIt("commonmark").enable("table")
    for name in ("example", "examples", "guidance"):
        parser = parser.use(container_plugin, name)
    return parser


_PARSER = _build_parser()


def _load_validators() -> list[PromptValidator]:
    return [
        MarkdownNotEmpty(),
        FirstHeadingIsH1(),
        NoHeadingLevelSkip(),
        NoEmptyHeading(),
        NoHeadingInListItem(),
        NoEmptyListItem(),
        NoMixedListTypeSiblings(),
        NoEmptyAnnotation(),
        NoOrphanAnnotation(),
        AnnotationHostIsValid(),
        NoHeadingInAnnotation(),
        NoNestedAnnotation(),
        NoDuplicateAnnotationKind(),
        AnnotationContentIsParagraphsOrUL(),
        NoNestedListInAnnotation(),
    ]


def _load_tokens(markdown_text: str) -> MarkdownTokenList:
    return _PARSER.parse(markdown_text)


def find_errors_from_file(filepath: Path) -> list[PromptError]:
    if not filepath.exists():
        raise FileNotFoundError(filepath)
    if not filepath.is_file():
        raise IsADirectoryError(filepath)
    markdown_text: str = filepath.read_text()
    return find_errors_from_string(markdown_text)


def find_errors_from_string(markdown_text: str) -> list[PromptError]:
    results: list[PromptError] = []
    validators: list[PromptValidator] = _load_validators()
    tokens: MarkdownTokenList = _load_tokens(markdown_text)
    for validator in validators:
        results.extend(validator.find_errors(tokens))

    return results
