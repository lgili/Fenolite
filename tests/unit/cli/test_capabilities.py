# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from fenolite.backends.kicad import cli as kicad_cli
from fenolite.cli import cmd_capabilities
from fenolite.cli.main import main


@pytest.fixture(autouse=True)
def _fresh_detection() -> Iterator[None]:
    cmd_capabilities.detect_tools.cache_clear()
    yield
    cmd_capabilities.detect_tools.cache_clear()


def _capabilities(capsys: pytest.CaptureFixture[str], *extra: str) -> dict[str, object]:
    assert main(["capabilities", "--json", *extra]) == 0
    return json.loads(capsys.readouterr().out)["result"]


def test_lists_itself_and_hidden_commands(capsys: pytest.CaptureFixture[str]) -> None:
    result = _capabilities(capsys, "--no-tools")
    commands = {c["name"]: c for c in result["commands"]}  # type: ignore[union-attr]
    assert commands["capabilities"] == {"name": "capabilities", "mutates": False,
                                        "schema": "fenolite.capabilities.v0", "hidden": False}  # fmt: skip
    assert commands["_echo"]["hidden"] is True and commands["_echo"]["mutates"] is True
    assert result["sends_data_offsite"] is False
    assert {router["name"] for router in result["routers"]} == {"direct", "freerouting", "kicadroutingtools"}
    # Freerouting is listed as sending data until its offline run is recorded (c0023); the tool as a whole
    # sends nothing, because that router runs only when named and only with --allow-offsite
    freerouting = next(router for router in result["routers"] if router["name"] == "freerouting")
    assert freerouting["sends_data_offsite"] is True and freerouting["builtin"] is True
    assert next(router for router in result["routers"] if router["name"] == "direct")["builtin"] is True
    assert set(result["extras"]) == {"dev", "geo", "kicad-ipc", "mcp", "oracles"}  # type: ignore[arg-type]


def test_missing_tools_are_null_not_fatal(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cmd_capabilities.shutil, "which", lambda _name: None)
    monkeypatch.setattr(kicad_cli, "MACOS_KICAD_CLI", Path("/nonexistent/kicad-cli"))
    monkeypatch.delenv("FENOLITE_KICAD_CLI", raising=False)
    tools = _capabilities(capsys)["tools"]
    assert tools == {"kicad-cli": None, "java": None, "docker": None}
