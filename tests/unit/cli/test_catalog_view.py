# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The catalog browser follows the write protocol and uses only installed definitions (c0234)."""

from __future__ import annotations

import hashlib
import socket
import subprocess
import sys
from pathlib import Path

import pytest
from _checkcli import run

from fenolite.catalog import list_entries
from fenolite.view.export import embedded


def test_catalog_view_is_offline_and_replays_exact_bytes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("catalog view attempted a network or external-tool operation")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    args = ("catalog", "view", "--out", "catalog.html", "--kind", "footprint", "--query", "0603")
    target = tmp_path / "catalog.html"
    code, refusal, error, _ = run(monkeypatch, tmp_path, *args)
    assert code == 4 and error["code"] == "FEN-4001" and not target.exists()
    code, planned, _, _ = run(monkeypatch, tmp_path, *args, "--dry-run")
    assert code == 0 and not target.exists()
    assert refusal["result"]["export"] == planned["result"]["export"]
    entries = list_entries(kind="footprint", query="0603")
    assert planned["result"]["count"] == len(entries)
    assert planned["result"]["counts"] == {"symbols": 0, "footprints": len(entries)}
    plan_id = planned["result"]["plan_id"]

    # Replay must consume the reviewed bytes, even if rendering cannot run anymore.
    monkeypatch.setattr("fenolite.view.catalog.catalog_page", forbidden)
    code, written, _, _ = run(monkeypatch, tmp_path, *args, "--confirm", "--plan", plan_id)
    assert code == 0
    content = target.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    assert digest == planned["result"]["export"]["sha256"] == written["receipt"]["written"][0]["sha256"]
    data = embedded(content.decode("utf-8"))
    assert data is not None and list(data["scenes"]) == ["catalog-footprint"]
    assert [item["lib_id"] for item in data["scenes"]["catalog-footprint"]["items"]] == [
        entry.lib_id for entry in entries
    ]
    assert sorted(path.name for path in tmp_path.iterdir()) == ["catalog.html"]


@pytest.mark.parametrize(
    "args",
    [
        ("view",),
        ("view", "Fenolite:Resistor", "--out", "catalog.html"),
        ("list", "--out", "catalog.html"),
        ("show", "Fenolite:Resistor", "--out", "catalog.html"),
    ],
)
def test_catalog_view_invalid_arguments_preserve_target(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, args: tuple[str, ...]
) -> None:
    target = tmp_path / "catalog.html"
    target.write_text("previous", encoding="utf-8")
    code, _, error, _ = run(monkeypatch, tmp_path, "catalog", *args, "--confirm")
    assert code == 2 and error["code"] == "FEN-2001"
    assert target.read_text(encoding="utf-8") == "previous"


def test_empty_view_refuses_but_empty_list_still_succeeds(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "catalog.html"
    target.write_text("previous", encoding="utf-8")
    code, reply, error, _ = run(
        monkeypatch,
        tmp_path,
        "catalog",
        "view",
        "--out",
        "catalog.html",
        "--query",
        "NO_MATCH_0212",
        "--confirm",
    )
    assert code == 3 and error["code"] == "FEN-3001" and "--query" in error["hint"]
    assert reply["receipt"] is None
    assert target.read_text(encoding="utf-8") == "previous"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["catalog.html"]
    code, reply, _, _ = run(monkeypatch, tmp_path, "catalog", "list", "--query", "NO_MATCH_0212")
    assert code == 0 and reply["result"]["entries"] == []


def test_list_and_show_do_not_import_catalog_viewer(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setitem(sys.modules, "fenolite.view.catalog", None)
    for args in (("list",), ("show", "Fenolite:Resistor")):
        code, reply, _, _ = run(monkeypatch, tmp_path, "catalog", *args)
        assert code == 0 and reply["receipt"] is None
    assert list(tmp_path.iterdir()) == []
