"""Opt-in protocol for Pydantic classes that have a hand-tuned Ollama variant.

The cloud path always sees the strict Pydantic class. For Ollama (whose schema
validator rejects discriminated unions), `_set_response_format` looks for
`__ollama_response_format__` on the class; if present, that variant is used
for the wire schema and the response is still parsed against the strict class.
Classes without the method fall back to a generic schema-flattening pass.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel


@runtime_checkable
class HasOllamaVariant(Protocol):
    """Implement to provide a hand-tuned Ollama wire schema.

    Returns the Pydantic class whose JSON schema will be sent to Ollama. The
    variant should be a permissive sibling of the strict class — same envelope
    fields, but any subschema Ollama can't validate (discriminated unions,
    deeply-nested `anyOf` of objects) replaced with open `dict[str, Any]` or
    similar.
    """

    @classmethod
    def __ollama_response_format__(cls) -> type[BaseModel]: ...
