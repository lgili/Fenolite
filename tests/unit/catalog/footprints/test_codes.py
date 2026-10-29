# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``package.*`` codes (change c0260, decision 18)."""

from __future__ import annotations

import pytest

from fenolite.catalog.footprints.codes import ISSUE_CODES, issue, sort_issues
from fenolite.cli import explain


def test_codes_and_severities() -> None:
    assert dict(ISSUE_CODES) == {
        "package.dimensions-inconsistent": "error",
        "package.land-impossible": "error",
        "package.land-override": "info",
        "package.missing-bound": "error",
        "package.name-mismatch": "error",
        "package.no-goals": "error",
        "package.pads-clipped": "warning",
        "package.pin-count": "error",
    }


def test_every_code_is_explained() -> None:
    assert ("fenolite.catalog.footprints.codes", "ISSUE_CODES") in explain.TABLES
    for code in ISSUE_CODES:
        found = explain.explain(code)
        assert found is not None and found.see == "library", code


def test_issue_and_order() -> None:
    info = issue("package.land-override", "m", where="a")
    warning = issue("package.pads-clipped", "m", where="b")
    error = issue("package.no-goals", "m", where="c")
    assert (error.severity, warning.severity, info.severity) == ("error", "warning", "info")
    assert sort_issues([info, warning, error]) == (error, warning, info)
    with pytest.raises(ValueError, match="not a package issue code"):
        issue("library.drift", "m")
