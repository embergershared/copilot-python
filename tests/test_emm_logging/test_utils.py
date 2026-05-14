"""Tests for emm_logging.utils — get_logger and timestamp_prefix."""

from __future__ import annotations

import logging
import re

from emm_logging import get_logger, timestamp_prefix


def test_get_logger_returns_logging_logger_instance() -> None:
    assert isinstance(get_logger("emm.test"), logging.Logger)


def test_get_logger_returns_named_logger() -> None:
    assert get_logger("emm.test").name == "emm.test"


def test_get_logger_is_idempotent() -> None:
    assert get_logger("emm.same") is get_logger("emm.same")


def test_get_logger_matches_stdlib_getlogger() -> None:
    """get_logger must be a thin wrapper — same logger object as stdlib."""
    assert get_logger("emm.parity") is logging.getLogger("emm.parity")


def test_timestamp_prefix_matches_expected_pattern() -> None:
    pattern = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{2}h\d{2}m\d{2}s\d{3}$")
    assert pattern.match(timestamp_prefix())


def test_timestamp_prefix_returns_str() -> None:
    assert isinstance(timestamp_prefix(), str)
