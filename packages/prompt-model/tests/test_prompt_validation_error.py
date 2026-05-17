from prompt_model.model.prompt_validation_error import PromptError, PromptErrorType


def _error(
    line: int,
    error_type: PromptErrorType = PromptErrorType.EmptyFile,
    error_message: str = "message",
) -> PromptError:
    return PromptError(line=line, error_type=error_type, error_message=error_message)


def test_equality_uses_line_and_error_type() -> None:
    assert _error(1, error_message="first") == _error(1, error_message="second")
    assert _error(1) != _error(2)


def test_hashing_uses_line_and_error_type() -> None:
    errors = {
        _error(1, error_message="first"),
        _error(1, error_message="second"),
        _error(2),
    }

    assert len(errors) == 2


def test_comparison_operators_use_line_and_error_type() -> None:
    first = _error(1)
    second = _error(2)
    third = _error(3)

    assert first < second
    assert second < third
    assert first <= _error(1, error_message="different message")
    assert third > second
    assert third >= _error(3, error_message="different message")


def test_sorting_uses_line_and_error_type() -> None:
    errors = [_error(3), _error(2), _error(1)]

    assert sorted(errors) == [_error(1), _error(2), _error(3)]
