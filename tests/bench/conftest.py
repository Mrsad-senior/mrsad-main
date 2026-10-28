"""Shared fixtures for the Mirsad-Bench tests."""

from __future__ import annotations

import pytest
from bench.loader import load_suite


@pytest.fixture(scope="session")
def suite():
    return load_suite()
