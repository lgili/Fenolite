# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Nexar readiness stays closed before any credentials or transport are read."""

import pytest

from fenolite.pick.query import parse_query
from fenolite.suppliers import credentials
from fenolite.suppliers.errors import CredentialsMissing
from fenolite.suppliers.nexar import Nexar


def test_unverified_source_cannot_request(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object) -> None:
        raise AssertionError("readiness must be checked first")

    monkeypatch.setattr(credentials, "lookup", forbidden)
    plugin = Nexar()
    with pytest.raises(CredentialsMissing, match="unverified|verified"):
        plugin.lookup(parse_query("capacitor(100nF)"), timestamp="2026-11-01T00:00:00Z")
    assert not plugin.available() and plugin.policy.cache == "none" and plugin.policy.persist == ()
