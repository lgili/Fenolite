# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Supplier discovery reads registered static metadata, never credentials or provider code."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from _checkcli import run

from fenolite.pick.propose import suppliers
from fenolite.pick.supplier_policy import capabilities


def test_suppliers_are_listed_offline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FENOLITE_MOUSER_API_KEY", "AUTHORED-DISCOVERY-CANARY")
    for brief in ((), ("--brief",)):
        code, env, error, raw = run(monkeypatch, tmp_path, "capabilities", "--no-tools", *brief)
        assert code == 0, error
        entries = env["result"]["suppliers"]
        assert [e["name"] for e in entries] == ["digikey", "farnell", "mouser", "nexar"]
        assert all(not e["available"] and not e["ready"] for e in entries)
        assert next(e for e in entries if e["name"] == "mouser")["credential_env_present"]
        assert "AUTHORED-DISCOVERY-CANARY" not in raw and env["result"]["sends_data_offsite"] is False


def test_discovery_does_not_read_credential_values(monkeypatch: pytest.MonkeyPatch) -> None:
    original = type(os.environ).__getitem__

    def guarded(self: object, key: str) -> str:
        if key.startswith("FENOLITE_MOUSER_"):
            raise AssertionError("discovery read a credential value")
        return original(self, key)

    monkeypatch.setattr(type(os.environ), "__getitem__", guarded)
    assert capabilities(suppliers())
