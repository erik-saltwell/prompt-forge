from prompt_model.llm import LiteLLMConfig


def test_minimal_config_only_has_model() -> None:
    cfg: LiteLLMConfig = LiteLLMConfig(model="anthropic/claude-haiku-4-5")
    kwargs: dict[str, object] = cfg.to_completion_kwargs()
    assert kwargs == {"model": "anthropic/claude-haiku-4-5"}


def test_effort_maps_to_reasoning_effort() -> None:
    cfg: LiteLLMConfig = LiteLLMConfig(model="anthropic/claude-opus-4-7", effort="high")
    kwargs: dict[str, object] = cfg.to_completion_kwargs()
    assert kwargs["reasoning_effort"] == "high"
    assert "effort" not in kwargs


def test_typed_fields_and_extra_combine() -> None:
    cfg: LiteLLMConfig = LiteLLMConfig(
        model="openai/gpt-4o",
        temperature=0.2,
        max_tokens=1024,
        timeout=30.0,
        extra={"top_p": 0.9, "stop": ["END"]},
    )
    kwargs: dict[str, object] = cfg.to_completion_kwargs()
    assert kwargs == {
        "model": "openai/gpt-4o",
        "temperature": 0.2,
        "max_tokens": 1024,
        "timeout": 30.0,
        "top_p": 0.9,
        "stop": ["END"],
    }


def test_extra_overrides_typed_field_when_keys_collide() -> None:
    cfg: LiteLLMConfig = LiteLLMConfig(
        model="m",
        temperature=0.1,
        extra={"temperature": 0.9},
    )
    kwargs: dict[str, object] = cfg.to_completion_kwargs()
    assert kwargs["temperature"] == 0.9
