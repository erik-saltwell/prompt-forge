from prompt_model.model import (
    Blockquote,
    CodeBlock,
    Document,
    List,
    ListItem,
    Paragraph,
    Section,
)
from prompt_model.service.parsing.parse_prompt import parse_from_string

from .utils.parsing_utils import assert_parses_to_shorthand, assert_trees_structurally_equal

# ---------------------------------------------------------------------------
# Leaf blocks
# ---------------------------------------------------------------------------

single_paragraph: str = """just some prose"""


def test_single_paragraph() -> None:
    assert_parses_to_shorthand(single_paragraph, "p")


two_paragraphs: str = """first para

second para"""


def test_two_paragraphs() -> None:
    assert_parses_to_shorthand(two_paragraphs, "p p")


single_code_block: str = """some prose

```python
print(1)
```"""


def test_single_code_block() -> None:
    assert_parses_to_shorthand(single_code_block, "p cb")


single_blockquote: str = """some prose

> a quote"""


def test_single_blockquote() -> None:
    assert_parses_to_shorthand(single_blockquote, "p bq")


single_table: str = """some prose

| a | b |
|---|---|
| 1 | 2 |"""


def test_single_table() -> None:
    assert_parses_to_shorthand(single_table, "p t")


# ---------------------------------------------------------------------------
# Section hierarchy
# ---------------------------------------------------------------------------

single_h1: str = """# Title"""


def test_single_h1() -> None:
    assert_parses_to_shorthand(single_h1, "h1")


h1_with_paragraph: str = """# Title
some prose"""


def test_h1_with_paragraph() -> None:
    assert_parses_to_shorthand(h1_with_paragraph, "h1 p")


nested_sections: str = """# A
intro

## B
sub

### C
deep

## D
back up"""


def test_nested_sections() -> None:
    assert_parses_to_shorthand(nested_sections, "h1 p h2 p h3 p h2 p")


# ---------------------------------------------------------------------------
# Lists
# ---------------------------------------------------------------------------

bullet_list: str = """# h
- one
- two"""


def test_bullet_list() -> None:
    assert_parses_to_shorthand(bullet_list, "h1 ul1 ul1")


ordered_list: str = """# h
1. one
2. two"""


def test_ordered_list() -> None:
    assert_parses_to_shorthand(ordered_list, "h1 ol1 ol1")


nested_bullet_list: str = """# h
- outer1
  - inner1
  - inner2
- outer2"""


def test_nested_bullet_list() -> None:
    assert_parses_to_shorthand(nested_bullet_list, "h1 ul1 ul2 ul2 ul1")


sibling_lists_different_type: str = """# h
- a
- b

some prose

1. c
2. d"""


def test_sibling_lists_different_type() -> None:
    assert_parses_to_shorthand(sibling_lists_different_type, "h1 ul1 ul1 p ol1 ol1")


# Ordered list nested inside a bullet list.
ordered_nested_in_bullet: str = """# h
- outer
  1. inner1
  2. inner2
- next outer"""


def test_ordered_nested_in_bullet() -> None:
    assert_parses_to_shorthand(ordered_nested_in_bullet, "h1 ul1 ol2 ol2 ul1")


# Bullet list nested inside an ordered list.
bullet_nested_in_ordered: str = """# h
1. outer
   - inner1
   - inner2
2. next outer"""


def test_bullet_nested_in_ordered() -> None:
    assert_parses_to_shorthand(bullet_nested_in_ordered, "h1 ol1 ul2 ul2 ol1")


# Three-level nesting alternating orderedness.
three_level_alternating: str = """# h
- a
  1. b
     - c
       1. d
     - e"""


def test_three_level_alternating() -> None:
    assert_parses_to_shorthand(three_level_alternating, "h1 ul1 ol2 ul3 ol4 ul3")


# A list directly under a heading (no intervening paragraph).
list_directly_under_heading: str = """# h
- only item"""


def test_list_directly_under_heading() -> None:
    assert_parses_to_shorthand(list_directly_under_heading, "h1 ul1")


# A list item with a code block as a block child (the code block is silently
# skipped in shorthand — it's a list-item block child, out of scope per spec).
list_item_with_code_block_child: str = """# h
- run this:
  ```bash
  echo hi
  ```
- then this"""


def test_list_item_with_code_block_child() -> None:
    assert_parses_to_shorthand(list_item_with_code_block_child, "h1 ul1 ul1")


# A list item with a second paragraph (extra paragraph is silently skipped
# in shorthand for the same reason — list-item block children are out of
# scope; nested *lists* are the only block children shorthand emits).
list_item_with_second_paragraph: str = """# h
- first para of item one

  second para of item one
- item two"""


def test_list_item_with_second_paragraph() -> None:
    assert_parses_to_shorthand(list_item_with_second_paragraph, "h1 ul1 ul1")


# Same-type sibling lists separated by prose still form two distinct lists
# (the paragraph is the separator, mirroring the mixed-type case).
same_type_sibling_lists_separated_by_prose: str = """# h
- a
- b

separator

- c
- d"""


def test_same_type_sibling_lists_separated_by_prose() -> None:
    assert_parses_to_shorthand(same_type_sibling_lists_separated_by_prose, "h1 ul1 ul1 p ul1 ul1")


# Pop back to outer depth then re-nest — verifies depth tracking resets.
list_pop_then_renest: str = """# h
- a
  - a1
- b
  - b1
  - b2"""


def test_list_pop_then_renest() -> None:
    assert_parses_to_shorthand(list_pop_then_renest, "h1 ul1 ul2 ul1 ul2 ul2")


# ---------------------------------------------------------------------------
# Annotations
# ---------------------------------------------------------------------------

paragraph_with_example: str = """# h
some prose
::: examples
an example
:::"""


def test_paragraph_with_example() -> None:
    assert_parses_to_shorthand(paragraph_with_example, "h1 p e")


paragraph_with_guidance: str = """# h
some prose
::: guidance
be concise
:::"""


def test_paragraph_with_guidance() -> None:
    assert_parses_to_shorthand(paragraph_with_guidance, "h1 p g")


paragraph_with_both: str = """# h
some prose
::: examples
ex
:::

::: guidance
g
:::"""


def test_paragraph_with_both_annotations() -> None:
    assert_parses_to_shorthand(paragraph_with_both, "h1 p e g")


list_item_with_example: str = """# h
- item one
  ::: examples
  ex
  :::
- item two"""


def test_list_item_with_example() -> None:
    assert_parses_to_shorthand(list_item_with_example, "h1 ul1 e ul1")


nested_list_item_with_guidance: str = """# h
- outer
  - inner
    ::: guidance
    g
    :::"""


def test_nested_list_item_with_guidance() -> None:
    assert_parses_to_shorthand(nested_list_item_with_guidance, "h1 ul1 ul2 g")


# Source-order guidance-before-examples must still emit `e` before `g` (per
# the "e always before g" rule baked into tree_to_shorthand).
paragraph_guidance_before_example: str = """# h
some prose
::: guidance
be brief
:::

::: examples
short one
:::"""


def test_paragraph_guidance_before_example() -> None:
    assert_parses_to_shorthand(paragraph_guidance_before_example, "h1 p e g")


# A list item carrying both an example and a guidance block.
list_item_with_both_annotations: str = """# h
- item one
  ::: examples
  ex
  :::

  ::: guidance
  g
  :::
- item two"""


def test_list_item_with_both_annotations() -> None:
    assert_parses_to_shorthand(list_item_with_both_annotations, "h1 ul1 e g ul1")


# Multiple sibling list items, each with its own annotation.
multiple_list_items_with_annotations: str = """# h
- first
  ::: examples
  ex1
  :::
- second
  ::: guidance
  g2
  :::
- third"""


def test_multiple_list_items_with_annotations() -> None:
    assert_parses_to_shorthand(multiple_list_items_with_annotations, "h1 ul1 e ul1 g ul1")


# Singular `::: example` alias parses to the same kind as `::: examples`.
paragraph_with_singular_example_alias: str = """# h
some prose
::: example
singular alias
:::"""


def test_paragraph_with_singular_example_alias() -> None:
    assert_parses_to_shorthand(paragraph_with_singular_example_alias, "h1 p e")


# Annotation body is itself a bullet list — body structure is collapsed to
# the annotation's text; the host still carries a single annotation block.
annotation_body_is_list: str = """# h
some prose
::: guidance
- be concise
- be creative
:::"""


def test_annotation_body_is_list() -> None:
    assert_parses_to_shorthand(annotation_body_is_list, "h1 p g")


# Two sibling paragraphs in the same section, each with its own annotation.
sibling_paragraphs_each_annotated: str = """# h
first para
::: examples
ex
:::

second para
::: guidance
g
:::"""


def test_sibling_paragraphs_each_annotated() -> None:
    assert_parses_to_shorthand(sibling_paragraphs_each_annotated, "h1 p e p g")


# Annotation on a deeply nested list item (depth 3).
deeply_nested_list_item_annotated: str = """# h
- a
  - b
    - c
      ::: examples
      deep example
      :::"""


def test_deeply_nested_list_item_annotated() -> None:
    assert_parses_to_shorthand(deeply_nested_list_item_annotated, "h1 ul1 ul2 ul3 e")


# Annotation on a paragraph inside a sub-section.
annotation_on_paragraph_in_subsection: str = """# top
intro

## sub
sub prose
::: guidance
g
:::"""


def test_annotation_on_paragraph_in_subsection() -> None:
    assert_parses_to_shorthand(annotation_on_paragraph_in_subsection, "h1 p h2 p g")


# ---------------------------------------------------------------------------
# Combined
# ---------------------------------------------------------------------------

sample_combined_markdown: str = """# foo
test test test
test test

## bar
- aaa
- bbb
  - ccc
    - ddd
  - eee
- fff

test test test
## gum
```block
asdasd a
sdasd
asdasda asdasd asdasd
```"""


def test_sample_combined_markdown() -> None:
    assert_parses_to_shorthand(sample_combined_markdown, "h1 p h2 ul1 ul1 ul2 ul3 ul2 ul1 p h2 cb")


heading_hierarchy_no_skips_ends_shallow: str = """# Top
intro

## A
prose

### A1
detail

## B
back up"""


def test_heading_hierarchy_no_skips_ends_shallow() -> None:
    sh = "h1 p h2 p h3 p h2 p"
    assert_parses_to_shorthand(heading_hierarchy_no_skips_ends_shallow, sh)


nested_lists_list_item_with_block_code_child: str = """# Recipe
- gather ingredients
- run this:
```bash
make dinner
- enjoy"""


def test_nested_lists_list_item_with_block_code_child() -> None:
    sh = "h1 ul1 ul1 cb"
    assert_parses_to_shorthand(nested_lists_list_item_with_block_code_child, sh)


paragraph_with_examples_and_guidance_block: str = """# Style
write concise prose

::: examples
"the cat sat"
:::
::: guidance
prefer short sentences
:::"""


def test_paragraph_with_examples_and_guidance_block() -> None:
    sh = "h1 p e g"
    assert_parses_to_shorthand(paragraph_with_examples_and_guidance_block, sh)


paragraph_with_examples_and_guidance_block_reversed: str = """# Style
write concise prose
::: guidance
prefer short sentences
:::
::: examples
"the cat sat"
:::"""


def test_paragraph_with_examples_and_guidance_block_reversed() -> None:
    sh = "h1 p e g"
    assert_parses_to_shorthand(paragraph_with_examples_and_guidance_block_reversed, sh)


annotations_on_nested_lest_with_list_in_annotation: str = """# Tips
- general advice
- specific tip
    ::: examples
    - first concrete case
    - second concrete case
    :::
- next general
"""


def test_annotations_on_nested_lest_with_list_in_annotation() -> None:
    sh = "h1 ul1 ul1 e ul1"
    assert_parses_to_shorthand(annotations_on_nested_lest_with_list_in_annotation, sh)


annotations_on_nested_ordered_list_with_list_in_annotation: str = """# Tips
1. general advice
1. specific tip
    ::: examples
    1. first concrete case
    1. second concrete case
    :::
1. next general
"""


def test_annotations_on_nested_ordered_list_with_list_in_annotation() -> None:
    sh = "h1 ol1 ol1 e ol1"
    assert_parses_to_shorthand(annotations_on_nested_ordered_list_with_list_in_annotation, sh)


sibling_lists_of_diff_types_sep_by_prose: str = """# Choices
prefer these:

- option one
- option two

avoid these:

1. anti-pattern A
2. anti-pattern B
"""


def test_sibling_lists_of_diff_types_sep_by_prose() -> None:
    sh = "h1 p ul1 ul1 p ol1 ol1"
    assert_parses_to_shorthand(sibling_lists_of_diff_types_sep_by_prose, sh)


# ---------------------------------------------------------------------------
# Text content (structural equality — shorthand doesn't check text)
# ---------------------------------------------------------------------------

text_in_heading_and_paragraph: str = """# The Title
some intro text"""


def test_text_in_heading_and_paragraph() -> None:
    expected = Document(
        children=[
            Section(level=1, text="The Title", children=[Paragraph(text="some intro text")]),
        ],
    )
    assert_trees_structurally_equal(parse_from_string(text_in_heading_and_paragraph), expected)


text_in_list_items: str = """# h
- first item
- second item"""


def test_text_in_list_items() -> None:
    expected = Document(
        children=[
            Section(
                level=1,
                text="h",
                children=[
                    List(
                        ordered=False,
                        children=[ListItem(text="first item"), ListItem(text="second item")],
                    )
                ],
            )
        ],
    )
    assert_trees_structurally_equal(parse_from_string(text_in_list_items), expected)


text_in_code_block_preserves_info_and_body: str = """# h
```python
x = 1
y = 2
```"""


def test_text_in_code_block_preserves_info_and_body() -> None:
    doc = parse_from_string(text_in_code_block_preserves_info_and_body)
    section = doc.children[0]
    assert isinstance(section, Section)
    cb = section.children[0]
    assert isinstance(cb, CodeBlock)
    assert cb.info == "python"
    assert cb.text == "x = 1\ny = 2\n"


text_in_annotation_body: str = """# h
some prose
::: examples
this is the body
:::"""


def test_text_in_annotation_body() -> None:
    doc = parse_from_string(text_in_annotation_body)
    section = doc.children[0]
    assert isinstance(section, Section)
    para = section.children[0]
    assert isinstance(para, Paragraph)
    assert para.example is not None
    assert para.example.text == "this is the body"


# ---------------------------------------------------------------------------
# ID assignment (Phase 5)
# ---------------------------------------------------------------------------

ids_top_level: str = """# a
para1

# b
para2"""


def test_ids_top_level_are_1_based() -> None:
    doc = parse_from_string(ids_top_level)
    assert doc.children[0].id == "1"
    assert doc.children[1].id == "2"


def test_document_has_no_id() -> None:
    doc = parse_from_string("just prose")
    assert not hasattr(doc, "id") or doc.id is None  # type: ignore[attr-defined]


ids_nested: str = """# a
intro

## b
sub prose"""


def test_ids_nested() -> None:
    doc = parse_from_string(ids_nested)
    section_a = doc.children[0]
    assert isinstance(section_a, Section)
    assert section_a.id == "1"
    assert section_a.children[0].id == "1.1"  # Paragraph "intro"
    assert section_a.children[1].id == "1.2"  # Section b
    section_b = section_a.children[1]
    assert isinstance(section_b, Section)
    assert section_b.children[0].id == "1.2.1"  # Paragraph "sub prose"


ids_list_has_own_segment: str = """# h
- one
- two"""


def test_ids_list_has_own_segment() -> None:
    doc = parse_from_string(ids_list_has_own_segment)
    section = doc.children[0]
    assert isinstance(section, Section)
    lst = section.children[0]
    assert isinstance(lst, List)
    assert lst.id == "1.1"
    assert lst.children[0].id == "1.1.1"
    assert lst.children[1].id == "1.1.2"


ids_sibling_lists_dont_collide: str = """# h
- a
- b

prose

1. c
2. d"""


def test_ids_sibling_lists_dont_collide() -> None:
    doc = parse_from_string(ids_sibling_lists_dont_collide)
    section = doc.children[0]
    assert isinstance(section, Section)
    first_list = section.children[0]
    second_list = section.children[2]
    assert isinstance(first_list, List)
    assert isinstance(second_list, List)
    assert first_list.id == "1.1"
    assert second_list.id == "1.3"
    assert first_list.children[0].id == "1.1.1"
    assert second_list.children[0].id == "1.3.1"


ids_annotations_per_kind: str = """# h
prose
::: examples
ex
:::

::: guidance
g
:::"""


def test_ids_annotations_per_kind() -> None:
    doc = parse_from_string(ids_annotations_per_kind)
    section = doc.children[0]
    assert isinstance(section, Section)
    para = section.children[0]
    assert isinstance(para, Paragraph)
    assert para.id == "1.1"
    assert para.example is not None
    assert para.example.id == "1.1.e1"
    assert para.guidance is not None
    assert para.guidance.id == "1.1.g1"


# ---------------------------------------------------------------------------
# Inline markup preservation
#
# Inline elements (bold, italic, links, code spans) are NOT separate nodes —
# they are part of the host block's text. The raw source markup is preserved
# verbatim so authors and the actor LLM can convey emphasis to the target LLM.
# ---------------------------------------------------------------------------

inline_bold_and_italic_preserved: str = """# h
this has **bold** and *italic* text"""


def test_inline_bold_and_italic_preserved() -> None:
    doc = parse_from_string(inline_bold_and_italic_preserved)
    section = doc.children[0]
    assert isinstance(section, Section)
    para = section.children[0]
    assert isinstance(para, Paragraph)
    assert para.text == "this has **bold** and *italic* text"


inline_code_and_link_preserved: str = """# h
see `parse_from_string` in [the docs](http://example.com)"""


def test_inline_code_and_link_preserved() -> None:
    doc = parse_from_string(inline_code_and_link_preserved)
    section = doc.children[0]
    assert isinstance(section, Section)
    para = section.children[0]
    assert isinstance(para, Paragraph)
    assert para.text == "see `parse_from_string` in [the docs](http://example.com)"


inline_in_heading_preserved: str = """# **Bold** title with *emphasis*
body"""


def test_inline_in_heading_preserved() -> None:
    doc = parse_from_string(inline_in_heading_preserved)
    section = doc.children[0]
    assert isinstance(section, Section)
    assert section.text == "**Bold** title with *emphasis*"


# ---------------------------------------------------------------------------
# CodeBlock variants
# ---------------------------------------------------------------------------

code_block_fence_no_info: str = """# h
```
plain code
```"""


def test_code_block_fence_no_info() -> None:
    doc = parse_from_string(code_block_fence_no_info)
    section = doc.children[0]
    assert isinstance(section, Section)
    cb = section.children[0]
    assert isinstance(cb, CodeBlock)
    assert cb.info == ""
    assert cb.text == "plain code\n"


code_block_indented: str = """# h
some prose

    indented code line 1
    indented code line 2"""


def test_code_block_indented() -> None:
    doc = parse_from_string(code_block_indented)
    section = doc.children[0]
    assert isinstance(section, Section)
    cb = section.children[1]
    assert isinstance(cb, CodeBlock)
    assert cb.info == ""
    assert "indented code line 1" in cb.text
    assert "indented code line 2" in cb.text


# ---------------------------------------------------------------------------
# Blockquote multi-block collapse
# ---------------------------------------------------------------------------

blockquote_multi_paragraph: str = """# h
> first paragraph
>
> second paragraph"""


def test_blockquote_multi_paragraph_collapses_to_text() -> None:
    doc = parse_from_string(blockquote_multi_paragraph)
    section = doc.children[0]
    assert isinstance(section, Section)
    bq = section.children[0]
    assert isinstance(bq, Blockquote)
    assert "first paragraph" in bq.text
    assert "second paragraph" in bq.text


blockquote_with_list: str = """# h
> intro line
> - bullet one
> - bullet two"""


def test_blockquote_with_list_collapses_to_text() -> None:
    doc = parse_from_string(blockquote_with_list)
    section = doc.children[0]
    assert isinstance(section, Section)
    bq = section.children[0]
    assert isinstance(bq, Blockquote)
    assert "intro line" in bq.text
    assert "bullet one" in bq.text
    assert "bullet two" in bq.text


# ---------------------------------------------------------------------------
# Annotation body content
# ---------------------------------------------------------------------------

annotation_body_plain_paragraph: str = """# h
prose
::: examples
single paragraph body
:::"""


def test_annotation_body_plain_paragraph() -> None:
    doc = parse_from_string(annotation_body_plain_paragraph)
    section = doc.children[0]
    assert isinstance(section, Section)
    para = section.children[0]
    assert isinstance(para, Paragraph)
    assert para.example is not None
    assert para.example.text == "single paragraph body"


annotation_body_list: str = """# h
prose
::: guidance
- first
- second
- third
:::"""


def test_annotation_body_list_collapses_to_text() -> None:
    doc = parse_from_string(annotation_body_list)
    section = doc.children[0]
    assert isinstance(section, Section)
    para = section.children[0]
    assert isinstance(para, Paragraph)
    assert para.guidance is not None
    body = para.guidance.text
    assert "first" in body
    assert "second" in body
    assert "third" in body


annotation_body_multi_paragraph: str = """# h
prose
::: examples
first paragraph

second paragraph
:::"""


def test_annotation_body_multi_paragraph() -> None:
    doc = parse_from_string(annotation_body_multi_paragraph)
    section = doc.children[0]
    assert isinstance(section, Section)
    para = section.children[0]
    assert isinstance(para, Paragraph)
    assert para.example is not None
    body = para.example.text
    assert "first paragraph" in body
    assert "second paragraph" in body


# ---------------------------------------------------------------------------
# Section-stack edges
# ---------------------------------------------------------------------------

multiple_sibling_h1s: str = """# first
a

# second
b

# third
c"""


def test_multiple_sibling_h1s() -> None:
    assert_parses_to_shorthand(multiple_sibling_h1s, "h1 p h1 p h1 p")
    doc = parse_from_string(multiple_sibling_h1s)
    assert len(doc.children) == 3
    assert all(isinstance(c, Section) and c.level == 1 for c in doc.children)


pop_multiple_levels_at_once: str = """# a
intro

## b
sub

### c
deep

# d
back to top"""


def test_pop_multiple_levels_at_once() -> None:
    assert_parses_to_shorthand(pop_multiple_levels_at_once, "h1 p h2 p h3 p h1 p")
    doc = parse_from_string(pop_multiple_levels_at_once)
    # Two sibling h1s at the root
    assert len(doc.children) == 2
    section_a, section_d = doc.children
    assert isinstance(section_a, Section)
    assert isinstance(section_d, Section)
    assert section_a.text == "a"
    assert section_d.text == "d"
    # Section d has no children (the deep sections are inside a)
    assert len(section_d.children) == 1  # just the "back to top" paragraph


empty_sections_chain: str = """# a
## b
### c
body finally"""


def test_empty_sections_chain() -> None:
    assert_parses_to_shorthand(empty_sections_chain, "h1 h2 h3 p")


successive_headings_no_body: str = """# a
# b
# c"""


def test_successive_headings_no_body() -> None:
    assert_parses_to_shorthand(successive_headings_no_body, "h1 h1 h1")
    doc = parse_from_string(successive_headings_no_body)
    assert len(doc.children) == 3
    for section in doc.children:
        assert isinstance(section, Section)
        assert len(section.children) == 0


# ---------------------------------------------------------------------------
# Heading-less documents
# ---------------------------------------------------------------------------

heading_less_list_only: str = """- one
- two
- three"""


def test_heading_less_list_only() -> None:
    assert_parses_to_shorthand(heading_less_list_only, "ul1 ul1 ul1")
    doc = parse_from_string(heading_less_list_only)
    assert len(doc.children) == 1
    lst = doc.children[0]
    assert isinstance(lst, List)
    assert lst.id == "1"
    assert lst.children[0].id == "1.1"
