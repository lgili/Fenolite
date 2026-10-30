# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Unexpressed items need consent (capability board-to-code, "Unexpressed items need consent")."""

from __future__ import annotations

from pathlib import Path

from _importcode import grouped, imported


def test_group_refused_without_consent(tmp_path: Path) -> None:
    reply = imported(tmp_path, grouped(tmp_path))
    assert reply.exit_code == 7
    assert reply.error is not None and reply.error["code"] == "FEN-7001"
    issues = (reply.envelope or {})["issues"]
    assert [(i["code"], i["where"]) for i in issues] == [("import.item-unexpressed", "group")]
    assert not (tmp_path / "out").exists()


def test_group_reported_with_consent(tmp_path: Path) -> None:
    reply = imported(tmp_path, grouped(tmp_path), "--allow-lossy")
    assert reply.exit_code == 0, reply.error
    assert reply.result["unexpressed"] == [{"kind": "group", "count": 1, "examples": ["group"]}]
    (found,) = [i for i in (reply.envelope or {})["issues"] if i["code"] == "import.item-unexpressed"]
    assert found["where"] == "group" and "1 item(s) of kind group" in found["message"]
    assert reply.result["equivalence"]["equivalent"] is True
