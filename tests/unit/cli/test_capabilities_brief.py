# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The brief view and the command view of ``fenolite capabilities`` (capability cli-contract, "Brief
capabilities" and "Command view of capabilities"; change c0079)."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from _checkcli import hide_kicad, run

import fenolite
from fenolite.agent import guide
from fenolite.cli import cmd_capabilities
from fenolite.cli.api import discover
from fenolite.cli.describe import describe, global_arguments
from fenolite.routing.registry import routers

BRIEF_KEYS = [
    "fenolite_version",
    "commands",
    "targets",
    "tools",
    "routers",
    "guide",
    "starters",
    "sends_data_offsite",
]
BYTES_PER_COMMAND = 300
BYTES_FIXED = 2000


@pytest.fixture(autouse=True)
def _fresh_detection() -> Iterator[None]:
    cmd_capabilities.detect_tools.cache_clear()
    yield
    cmd_capabilities.detect_tools.cache_clear()


def _refuse(*args: object, **kwargs: object) -> None:
    raise AssertionError("capabilities started a subprocess")


def _no_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", _refuse)
    monkeypatch.setattr(subprocess, "Popen", _refuse)


def _result(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *args: str) -> dict[str, Any]:
    code, envelope, error, _ = run(monkeypatch, tmp_path, "capabilities", *args)
    assert code == 0, error
    return envelope["result"]


def test_brief_view(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Brief view"."""
    _no_subprocess(monkeypatch)
    for router in routers().values():
        monkeypatch.setattr(type(router), "available", _refuse)
    result = _result(monkeypatch, tmp_path, "--brief", "--no-tools")
    assert list(result) == BRIEF_KEYS
    assert result["fenolite_version"] == fenolite.__version__
    commands = {entry["name"]: entry for entry in result["commands"]}
    public = sorted(name for name, command in discover().items() if not command.hidden)
    assert list(commands) == public and "_echo" not in commands
    assert all(list(entry) == ["name", "summary", "mutates"] for entry in result["commands"])
    assert all(entry["summary"] == discover()[name].help for name, entry in commands.items())
    assert commands["build"]["summary"] and commands["build"]["mutates"] is True
    assert commands["check"]["mutates"] is False
    assert result["targets"] == {"build": ["altium", "kicad"], "kicad": [9, 10], "default": 10}
    assert result["tools"] == {} and result["sends_data_offsite"] is False
    assert [r["name"] for r in result["routers"]] == sorted(routers())
    assert all(list(r) == ["name", "available", "reason"] for r in result["routers"])
    assert all(r["available"] is None and r["reason"] is None for r in result["routers"])
    assert "direct" in [r["name"] for r in result["routers"]]
    assert result["guide"][0]["topic"] == "start"
    assert result["guide"] == [
        {"topic": p.topic, "title": p.title, "summary": p.summary} for p in guide.pages()
    ]
    assert result["starters"] == [{"name": s.name, "summary": s.summary} for s in guide.starters()]
    assert "blink" in [s["name"] for s in result["starters"]]


def test_brief_targets_come_from_the_build_parser() -> None:
    target = next(a for a in describe(discover()["build"]).arguments if "--target" in a.flags)
    assert list(target.choices or ()) == ["altium", "kicad"]


def test_brief_routers_availability(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Router availability": no Freerouting jar, no ``FENOLITE_KRT``, no tool on the path."""
    hide_kicad(monkeypatch, tmp_path)
    for name in ("FENOLITE_FREEROUTING_JAR", "FENOLITE_FREEROUTING_IMAGE", "FENOLITE_KRT", "FENOLITE_JAVA"):
        monkeypatch.delenv(name, raising=False)
    from fenolite.routing import registry

    monkeypatch.setattr(registry, "_BUILTINS", {})
    monkeypatch.setattr(registry, "_loaded", False)  # the routers read their environment when they load
    _no_subprocess(monkeypatch)
    result = _result(monkeypatch, tmp_path, "--brief")
    found = {r["name"]: r for r in result["routers"]}
    assert found["direct"] == {"name": "direct", "available": True, "reason": None}
    assert found["freerouting"]["available"] is False and found["freerouting"]["reason"]
    assert result["tools"] == {"kicad-cli": None, "java": None, "docker": None}


def test_brief_tools_equal_the_default_view(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        cmd_capabilities, "detect_tools", lambda: {"kicad-cli": {"path": "x", "version": "10.0.6"}}
    )
    brief = _result(monkeypatch, tmp_path, "--brief")
    default = _result(monkeypatch, tmp_path)
    assert brief["tools"] == default["tools"] == {"kicad-cli": {"path": "x", "version": "10.0.6"}}
    assert brief["sends_data_offsite"] == default["sends_data_offsite"]


def test_brief_size(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Size bound"."""
    result = _result(monkeypatch, tmp_path, "--brief", "--no-tools")
    size = len(json.dumps(result, ensure_ascii=False).encode("utf-8"))
    assert size < BYTES_PER_COMMAND * len(result["commands"]) + BYTES_FIXED, size
    assert not {"backends", "experimental", "extras", "matrix"} & set(result)
    text = json.dumps(result)
    assert "experimental" not in text and "VERIFIED" not in text and "INFERRED" not in text
    default = _result(monkeypatch, tmp_path, "--no-tools")
    assert size < len(json.dumps(default, ensure_ascii=False).encode("utf-8"))


def test_default_view_is_unchanged(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Default view unchanged"; ``global_flags`` and ``mutation_flags`` came with change c0120."""
    result = _result(monkeypatch, tmp_path, "--no-tools")
    assert list(result) == [
        "fenolite_version", "commands", "global_flags", "mutation_flags", "backends", "experimental",
        "matrix", "extras", "tools", "routers", "sends_data_offsite",
    ]  # fmt: skip
    assert all("summary" not in entry and "arguments" not in entry for entry in result["commands"])
    assert all(set(r) == {"name", "description", "sends_data_offsite", "builtin"} for r in result["routers"])
    assert result["backends"] and result["experimental"] and result["matrix"]


def test_brief_excludes_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, _, error, _ = run(monkeypatch, tmp_path, "capabilities", "--brief", "--command", "route")
    assert code == 2 and error["code"] == "FEN-2001"


def test_brief_with_fields_and_concise(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fields = _result(monkeypatch, tmp_path, "--brief", "--no-tools", "--fields", "targets.build,starters")
    assert fields == {"targets": {"build": ["altium", "kicad"]}, "starters": fields["starters"]}
    plain = _result(monkeypatch, tmp_path, "--brief", "--no-tools")
    concise = _result(monkeypatch, tmp_path, "--brief", "--no-tools", "--format", "concise")
    assert concise.pop("issues_summary") == []
    assert concise == plain


def test_command_view(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "One command"."""
    _no_subprocess(monkeypatch)
    for extra in ((), ("--no-tools",)):
        result = _result(monkeypatch, tmp_path, "--command", "route", *extra)
        assert list(result) == ["command", "global_arguments"]
        command = result["command"]
        assert command["name"] == "route" and command["mutates"] is True
        assert "--router" in [flag for argument in command["arguments"] for flag in argument["flags"]]
        assert "--fields" in [flag for argument in result["global_arguments"] for flag in argument["flags"]]
        assert result["global_arguments"] == [argument.to_json() for argument in global_arguments()]
        described = describe(discover()["route"]).to_json()
        default = next(
            c for c in _result(monkeypatch, tmp_path, "--no-tools")["commands"] if c["name"] == "route"
        )
        assert command == default | {key: described[key] for key in ("summary", "usage", "arguments")}


def test_command_view_keeps_paging_keys_and_describes_a_hidden_command(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    echo = _result(monkeypatch, tmp_path, "--command", "_echo")["command"]
    assert echo["hidden"] is True and echo["paged"] == "issues" and echo["summary"] == ""
    assert "--text-body" in [flag for argument in echo["arguments"] for flag in argument["flags"]]


def test_command_view_unknown_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Unknown command"."""
    code, envelope, error, _ = run(monkeypatch, tmp_path, "capabilities", "--command", "rout")
    assert code == 2 and envelope["ok"] is False and error["code"] == "FEN-2001"
    named = error["hint"].split(": ", 1)[1].split(", ")
    assert named[0] == "route" and len(named) == 3 and "_echo" not in named
