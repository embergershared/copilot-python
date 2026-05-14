"""Log the resolved fields of a settings object, redacting likely secrets."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:  # pragma: no cover - import only for static type-checking
    from pydantic_settings import BaseSettings as _BaseSettings  # noqa: F401

# Suffix patterns (case-insensitive substring match) that mark a field as
# likely-secret. Anything matching is logged as ``***`` regardless of value.
_SECRET_PATTERNS: tuple[str, ...] = (
    "_key",
    "_secret",
    "_password",
    "_token",
    "_connection_string",
    "_credential",
    "_apikey",
)

_REDACTED = "***"


class _ModelDumpable(Protocol):
    """Minimal protocol satisfied by pydantic and pydantic-settings models."""

    def model_dump(self) -> dict[str, Any]: ...


def _to_field_dict(settings: object) -> dict[str, Any]:
    """Return ``settings`` as a ``{field: value}`` dict, falling back to vars."""

    dump = getattr(settings, "model_dump", None)
    if callable(dump):
        result = dump()
        if isinstance(result, dict):
            return dict(result)
    return {k: v for k, v in vars(settings).items() if not k.startswith("_")}


def _is_secret_field(name: str, redact: tuple[str, ...]) -> bool:
    """Return True when ``name`` matches a built-in or user-supplied pattern."""

    lower = name.lower()
    if any(pattern in lower for pattern in _SECRET_PATTERNS):
        return True
    return any(needle and needle.lower() in lower for needle in redact)


def log_settings(
    settings: object,
    *,
    logger: logging.Logger | None = None,
    redact: Iterable[str] = (),
) -> None:
    """Log each field of ``settings`` as ``setting: key=<name> value=<value>``.

    Values whose field name matches a built-in secret suffix (``_key``,
    ``_secret``, ``_password``, ``_token``, ``_connection_string``,
    ``_credential``, ``_apikey``) or any user-supplied ``redact`` substring
    (case-insensitive) are emitted as ``***``. Accepts any object with a
    ``model_dump()`` method or, as a fallback, any plain object exposing
    public attributes via :func:`vars`.
    """

    sink = logger or logging.getLogger("emm_settings.snapshot")
    redact_tuple = tuple(redact)
    fields = _to_field_dict(settings)

    for name, value in fields.items():
        display = _REDACTED if _is_secret_field(name, redact_tuple) else value
        sink.info("setting: key=%s value=%s", name, display)
