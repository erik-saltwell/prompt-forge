# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

This is a `uv` workspace. All commands run from the repo root.

```bash
uv sync                              # install / sync dependencies
uv run pytest                        # run all tests (~600, completes in <1s)
uv run pytest packages/prompt-model/tests/actions/test_move_node.py::test_name
uv run pytest -k "substring"         # filter by test-name substring
uv run ruff format                   # apply formatting
uv run ruff check --fix              # lint with auto-fix
uv run ty check packages apps        # type-check (uses `ty`, not mypy/pyright)
```

Pre-commit hooks run `ruff format --check`, `ruff check --fix`, and `ty check` on each commit; `pytest` runs on push. Don't bypass them.

## Workspace Layout

- `packages/prompt-model/` — the core library. All real code lives here.
- `apps/prompt-model-check/` — CLI stub, currently a hello-world; depends on `prompt-model` via workspace source.

## important files with design information
- @docs/prompt-model.md — markdown-to-tree parser, node types, ID scheme.  The core data model.
- @docs/prompt-actions.md — the action vocabulary of prompt changes that the actor requests.
- @docs/prompt-serialization.md — rules about how data are sent-to and read-from llm calls
- @docs/critic-metric-interface.md — Metric protocol and MetricResult schema
- @docs/public-facade.md — public import surface: optimize_prompt entry point, OptimizerConfig, OptimizeResult, progress events, module layout
- @docs/actor-module.md — Actor module design: per-bucket fan-out, RedactionStrategy, revise() contract, structural pass orchestration
- @research/sculpt_paper.md - the sculpt paper i am basing this optimizer off of

## Conventions

- **Python 3.12.** Use PEP 695 `type` statements, structural pattern matching, and modern type-hints (no `from __future__ import annotations` necessary, but it's used liberally).
- **Library code uses relative imports**, tests use absolute imports.
- **Underscore-prefixed modules and folders are private** (`_cleaners/`, `_rules/`, `_walk.py`, `_subtree.py`). Don't import them from outside their immediate parent.
- **Line length 140.**
- **type hints everywhere** Use type hints on all function parameters, all function return types and all local variable declarations that are not simple primitives (str, float, int...)

## Testing

Tests are **fixture-driven**: most cases live as asset files (markdown, JSON) under `tests/.../assets/`, auto-discovered by pytest-collection logic in the test modules. See `docs/test-infra.md` for the shorthand grammar used to declare expected tree structures and for the mode-per-directory convention for action fixtures. Tree comparisons in tests are **structural-only** — IDs are not asserted unless explicitly tested.

## Style Guidelines - be brief

- Provide **concise, focused responses** to user questions.
- Lead with the main answer; **skip non-essential context** and filler preamble.
- Use **bullet points** or numbered lists for multiple items, and keep bullets short.
- Avoid repeating the user’s question or saying “As an AI model” unless needed.
- If a very brief reply is appropriate, stop after the key points. (Longer explanations can come in later steps if requested.)
