from pathlib import Path

import pytest
from prompt_model.model.prompt_validation_error import PromptErrorType
from prompt_model.service.validation.validate_prompt import find_errors_from_file

from .utils.validation_utils import assert_no_errors_from_string, assert_single_error_from_string

skipped_hierarchy_1: str = """# First Level
test test test

### Second Level"""

ok_skipped_heading_inside_code_block: str = """# real h1

  fake heading

  would-be-skip

  """

ok_skipped_heading_inside_indented_code: str = """# real h1

      # fake heading
      ### would-be-skip
  """


start_at_h2: str = """## First Level
test test test

### Second Level"""

empty_header: str = """# First
test test test
#
test test test"""

heading_in_list_item: str = """# heading
- first
- second
  # invalid
  test test test"""

heading_in_ordered_list_item: str = """# heading
1. first
2. second
   ## invalid
   test test test"""

heading_in_nested_list_item: str = """# heading
- outer
  - inner
    ### invalid
    test test test"""

empty_list_item_1: str = """# foo
test test test
- test test
- 
"""

empty_list_item_2: str = """# foo
test test test
1. test test
2. 
3. test test
"""

empty_list_item_3: str = """# foo
test test test

1. 
"""

non_empty_list_item_1: str = """# foo
test test test
1. 
"""

non_empty_list_item_2: str = """# foo
test test test
-
"""

sibling_lists_of_different_type_1: str = """# foo
- test
- tests
1. bar
2. blah"""

ok_siblings_lists_of_different_type_1: str = """# foo
- test
- tests

asdasflkajdfgdlkgjsdg

1. bar
2. blah"""

sibling_lists_of_different_type_2: str = """# foo
1. bar
2. blah
- test
- tests"""

sibling_lists_of_different_type_3: str = """# foo
- test
- tests

1. bar
2. blah"""

sibling_lists_of_different_type_4: str = """# foo
- outer
- inner ul
1. inner ol"""

ok_siblings_lists_of_different_type_2: str = """# foo
- test
- tests

some code

1. bar
2. blah"""


# ---------------------------------------------------------------------------
# Annotation fixtures — directive-container syntax (`::: examples` / `:::`,
# `::: example` accepted as singular alias, `::: guidance` / `:::`).
# ---------------------------------------------------------------------------

# --- Good: single annotation on a paragraph -------------------------------
ok_examples_on_paragraph: str = """# foo
some prose text
::: examples
A concrete example.
:::"""

ok_guidance_on_paragraph: str = """# foo
some prose text
::: guidance
Keep it brief.
:::"""

# --- Good: singular `example` accepted as alias ---------------------------
ok_singular_example_alias: str = """# foo
some prose text
::: example
Singular form is accepted.
:::"""

# --- Good: annotation body may itself be a list ---------------------------
ok_guidance_with_list_body: str = """# foo
some prose text
::: guidance
- be concise
- be creative
:::"""

# --- Good: one examples and one guidance on the same host ----------------
ok_one_of_each_kind_on_paragraph: str = """# foo
some prose text
::: examples
- first example
- second example
:::

::: guidance
- be concise
- be creative
:::"""

# --- Good: unknown `:::` names are not annotations, just paragraph text ---
ok_unknown_kind_is_not_annotation: str = """# foo
some prose
::: warning
not a recognized annotation kind
:::

::: foo
also not recognized
:::"""

# --- Good: annotation on a list item --------------------------------------
ok_annotation_on_list_item: str = """# foo
- thing one
  ::: example
  example for thing one
  :::
- thing two
  ::: guidance
  guidance for thing two
  :::"""

# --- Good: annotation on a nested list item -------------------------------
ok_annotation_on_nested_list_item: str = """# foo
- outer item
  - inner item
    ::: examples
    nested example
    :::"""

# --- Good: blank line between host paragraph and annotation ---------------
ok_blank_line_before_annotation: str = """# foo
prose text

::: examples
example here
:::"""

# --- Bad: empty annotation body (EmptyAnnotation) -------------------------
empty_examples_annotation: str = """# foo
some prose text
::: examples
:::"""
# Expected: EmptyAnnotation at line 3.

empty_guidance_annotation: str = """# foo
some prose text
::: guidance
:::"""
# Expected: EmptyAnnotation at line 3.

empty_annotation_on_list_item: str = """# foo
- thing one
  ::: examples
  :::"""
# Expected: EmptyAnnotation at line 3.

# --- Bad: orphan annotation (OrphanAnnotation) ----------------------------
orphan_annotation_at_document_start: str = """::: examples
foo
:::"""
# Expected: OrphanAnnotation at line 1.

orphan_annotation_after_heading: str = """# foo
::: examples
example
:::"""
# Expected: OrphanAnnotation at line 2.

orphan_annotation_in_section: str = """# foo
some prose

## subsection
::: examples
example
:::"""
# Expected: OrphanAnnotation at line 5.

# --- Bad: illegal host (IllegalAnnotationHost) ----------------------------
annotation_after_code_block: str = """# foo
```
code
```
::: examples
example
:::"""
# Expected: IllegalAnnotationHost at line 5.

annotation_after_blockquote: str = """# foo
> a quote
::: examples
example
:::"""
# Expected: IllegalAnnotationHost at line 3.

# --- Bad: heading inside annotation (HeadingInAnnotation) -----------------
heading_inside_annotation: str = """# foo
prose
::: examples
## inner heading
:::"""
# Expected: HeadingInAnnotation at line 4.

# --- Bad: more than one annotation block of the same kind on one host -----
duplicate_examples_on_paragraph: str = """# foo
some prose text
::: examples
First example.
:::

::: examples
Second example.
:::"""
# Expected: DuplicateAnnotationKind at line 7 (the second `::: examples`).

duplicate_guidance_on_list_item: str = """# foo
- thing one
  ::: guidance
  first guidance
  :::

  ::: guidance
  second guidance
  :::"""
# Expected: DuplicateAnnotationKind at line 7.

# `example` (singular) and `examples` (plural) are the same kind — two
# blocks using the alias still violate the rule.
duplicate_kind_via_alias: str = """# foo
some prose
::: examples
foo
:::

::: example
bar
:::"""
# Expected: DuplicateAnnotationKind at line 7.

# --- Bad: nested annotation (NestedAnnotation) ----------------------------
# Outer container uses four colons so the inner three-colon container nests
# rather than closing it (per markdown-it-container nesting rules).
nested_annotation: str = """# foo
prose
:::: examples
::: guidance
inner
:::
::::"""
# Expected: NestedAnnotation at line 4.


def test_find_errors_raises_file_not_found_error_when_filepath_does_not_exist(tmp_path: Path) -> None:
    filepath = tmp_path / "missing.md"

    with pytest.raises(FileNotFoundError):
        find_errors_from_file(filepath)


def test_find_errors_raises_is_a_directory_error_when_filepath_is_not_a_file(tmp_path: Path) -> None:
    with pytest.raises(IsADirectoryError):
        find_errors_from_file(tmp_path)


def test_empty_file() -> None:
    assert_single_error_from_string("", 0, PromptErrorType.EmptyFile)


def test_skipped_hierarchy() -> None:
    assert_single_error_from_string(skipped_hierarchy_1, 4, PromptErrorType.HeadingLevelSkip)
    assert_no_errors_from_string(ok_skipped_heading_inside_code_block)
    assert_no_errors_from_string(ok_skipped_heading_inside_indented_code)


def test_first_header_is_h1() -> None:
    assert_single_error_from_string(start_at_h2, 1, PromptErrorType.FirstHeadingNotH1)


def test_empty_header() -> None:
    assert_single_error_from_string(empty_header, 3, PromptErrorType.EmptyHeading)


def test_no_heading_in_list_item() -> None:
    assert_single_error_from_string(heading_in_list_item, 4, PromptErrorType.HeadingInListItem)
    assert_single_error_from_string(heading_in_ordered_list_item, 4, PromptErrorType.HeadingInListItem)
    assert_single_error_from_string(heading_in_nested_list_item, 4, PromptErrorType.HeadingInListItem)


def test_no_empty_list_item() -> None:
    assert_single_error_from_string(empty_list_item_1, 4, PromptErrorType.EmptyListItem)
    assert_single_error_from_string(empty_list_item_2, 4, PromptErrorType.EmptyListItem)
    assert_single_error_from_string(empty_list_item_3, 4, PromptErrorType.EmptyListItem)
    assert_no_errors_from_string(non_empty_list_item_1)
    assert_no_errors_from_string(non_empty_list_item_2)


def test_sibling_lists_of_different_type() -> None:
    assert_single_error_from_string(sibling_lists_of_different_type_1, 4, PromptErrorType.MixedListTypeSiblings)
    assert_single_error_from_string(sibling_lists_of_different_type_2, 4, PromptErrorType.MixedListTypeSiblings)
    assert_single_error_from_string(sibling_lists_of_different_type_3, 5, PromptErrorType.MixedListTypeSiblings)
    assert_single_error_from_string(sibling_lists_of_different_type_4, 4, PromptErrorType.MixedListTypeSiblings)
    assert_no_errors_from_string(ok_siblings_lists_of_different_type_1)
    assert_no_errors_from_string(ok_siblings_lists_of_different_type_2)


def test_ok_annotations() -> None:
    assert_no_errors_from_string(ok_examples_on_paragraph)
    assert_no_errors_from_string(ok_guidance_on_paragraph)
    assert_no_errors_from_string(ok_singular_example_alias)
    assert_no_errors_from_string(ok_guidance_with_list_body)
    assert_no_errors_from_string(ok_one_of_each_kind_on_paragraph)
    assert_no_errors_from_string(ok_annotation_on_list_item)
    assert_no_errors_from_string(ok_annotation_on_nested_list_item)
    assert_no_errors_from_string(ok_blank_line_before_annotation)
    assert_no_errors_from_string(ok_unknown_kind_is_not_annotation)


def test_empty_annotation() -> None:
    assert_single_error_from_string(empty_examples_annotation, 3, PromptErrorType.EmptyAnnotation)
    assert_single_error_from_string(empty_guidance_annotation, 3, PromptErrorType.EmptyAnnotation)
    assert_single_error_from_string(empty_annotation_on_list_item, 3, PromptErrorType.EmptyAnnotation)


def test_orphan_annotation() -> None:
    assert_single_error_from_string(orphan_annotation_at_document_start, 1, PromptErrorType.OrphanAnnotation)
    assert_single_error_from_string(orphan_annotation_after_heading, 2, PromptErrorType.OrphanAnnotation)
    assert_single_error_from_string(orphan_annotation_in_section, 5, PromptErrorType.OrphanAnnotation)


def test_illegal_annotation_host() -> None:
    assert_single_error_from_string(annotation_after_code_block, 5, PromptErrorType.IllegalAnnotationHost)
    assert_single_error_from_string(annotation_after_blockquote, 3, PromptErrorType.IllegalAnnotationHost)


def test_heading_in_annotation() -> None:
    assert_single_error_from_string(heading_inside_annotation, 4, PromptErrorType.HeadingInAnnotation)


def test_nested_annotation() -> None:
    assert_single_error_from_string(nested_annotation, 4, PromptErrorType.NestedAnnotation)


def test_duplicate_annotation_kind() -> None:
    assert_single_error_from_string(duplicate_examples_on_paragraph, 7, PromptErrorType.DuplicateAnnotationKind)
    assert_single_error_from_string(duplicate_guidance_on_list_item, 7, PromptErrorType.DuplicateAnnotationKind)
    assert_single_error_from_string(duplicate_kind_via_alias, 7, PromptErrorType.DuplicateAnnotationKind)
