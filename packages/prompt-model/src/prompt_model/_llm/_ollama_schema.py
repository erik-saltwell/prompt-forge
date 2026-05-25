"""Build an Ollama-compatible response_format from a Pydantic class.

Ollama's JSON-schema validator does not accept discriminated unions
(`oneOf` + `discriminator`) or unconstrained `anyOf` of object types.
We inline `$ref`s and replace any such subschema with a permissive
`{type: object}` placeholder. The response is still validated strictly
against the original Pydantic class on our side; structured-output
shape constraints lost in the wire schema are recovered by the actor's
prompt and the model's own lenient validators (e.g. `ActionBatch`'s
`_drop_invalid_actions`).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


def build_ollama_response_format(pydantic_cls: type[BaseModel]) -> dict[str, Any]:
    """Return a LiteLLM-compatible `response_format` dict for Ollama."""
    schema: dict[str, Any] = _flatten(_inline_refs(pydantic_cls.model_json_schema()))
    schema.pop("title", None)
    return {
        "type": "json_schema",
        "json_schema": {
            "name": pydantic_cls.__name__,
            "schema": schema,
            "strict": True,
        },
    }


def _inline_refs(raw: dict[str, Any]) -> dict[str, Any]:
    defs: dict[str, Any] = raw.pop("$defs", {})

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node and len(node) == 1:
                ref: str = node["$ref"]
                if ref.startswith("#/$defs/"):
                    return walk(defs.get(ref.split("/")[-1], {}))
            return {k: walk(v) for k, v in node.items()}
        if isinstance(node, list):
            return [walk(x) for x in node]
        return node

    inlined: Any = walk(raw)
    if not isinstance(inlined, dict):
        return {}
    return inlined


def _flatten(node: Any) -> Any:
    if isinstance(node, dict):
        if "discriminator" in node or "oneOf" in node or "anyOf" in node:
            return {"type": "object"}
        return {k: _flatten(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_flatten(x) for x in node]
    return node
