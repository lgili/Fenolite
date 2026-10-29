# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The role mode of the octilinear router (change c0244; capability routing, "Role routes in a routing job"
and the requirements after it; ``docs/routing.md``, "Role mode")."""

from __future__ import annotations

from fenolite.routing.codes import ISSUE_CODES

ROLE_CODES = {
    "route.role-unrouted": "warning",
    "route.role-refused": "warning",
    "route.role-unconfirmed": "info",
    "route.role-kept": "info",
    "route.role-placement": "info",
    "route.role-none": "info",
}


def test_role_codes() -> None:
    """Scenario "Codes explained" of "Role route codes" (the codes' part; ``test_explain_cmd`` checks the
    entries and the documented rows)."""
    assert {code: ISSUE_CODES[code] for code in ROLE_CODES} == ROLE_CODES
