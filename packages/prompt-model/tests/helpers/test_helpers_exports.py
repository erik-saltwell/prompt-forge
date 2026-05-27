from __future__ import annotations

from prompt_model._llm.call import acomplete as private_acomplete
from prompt_model._llm.call import complete as private_complete
from prompt_model.helpers import acomplete, complete


def test_helpers_export_completion_functions() -> None:
    assert acomplete is private_acomplete
    assert complete is private_complete
