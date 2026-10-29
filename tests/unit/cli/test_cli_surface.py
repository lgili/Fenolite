# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The contract surface and its judge (capability cli-contract, "Contract surface", "Stability of the 1.x
contract", "Breaking changes of the surface"; change c0216)."""

from __future__ import annotations

import argparse
import copy
import dataclasses
import importlib.util
import json
import sys
from functools import cache
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from fenolite.cli.api import discover
from fenolite.cli.surface import GLOBAL, Surface, SurfaceChange, cli_surface, surface_changes

ROOT = Path(__file__).resolve().parents[3]
COMMITTED = ROOT / "docs" / "cli-surface.json"


def _tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("gen_cli_surface", ROOT / "tools" / "gen_cli_surface.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@cache
def _fresh() -> Surface:
    return cli_surface(discover())


def _data() -> dict[str, Any]:
    return copy.deepcopy(_fresh().to_json())


def _changes(before: dict[str, Any], after: dict[str, Any]) -> tuple[SurfaceChange, ...]:
    return surface_changes(Surface.from_json(before), Surface.from_json(after))


def _only(changes: tuple[SurfaceChange, ...]) -> SurfaceChange:
    assert len(changes) == 1, [str(c) for c in changes]
    return changes[0]


# ------------------------------------------------------------------------------------- the surface (1.1)


def test_committed_surface_is_fresh() -> None:
    assert COMMITTED.exists(), "docs/cli-surface.json missing: run tools/gen_cli_surface.py"
    committed = Surface.from_json(json.loads(COMMITTED.read_text(encoding="utf-8")))
    changes = surface_changes(committed, _fresh())
    assert not changes, "docs/cli-surface.json is stale: run tools/gen_cli_surface.py\n" + "\n".join(
        str(c) for c in changes
    )
    assert COMMITTED.read_text(encoding="utf-8") == _fresh().dumps()


def test_check_mode_passes() -> None:
    assert _tool().main(["--check"]) == 0


def test_check_mode_fails_on_a_stale_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                          capsys: pytest.CaptureFixture[str]) -> None:  # fmt: skip
    tool = _tool()
    stale = _data()
    del stale["commands"]["check"]["options"]["--exclude"]
    path = tmp_path / "cli-surface.json"
    path.write_text(json.dumps(stale), encoding="utf-8")
    monkeypatch.setattr(tool, "OUT", path)
    monkeypatch.setattr(tool, "ROOT", tmp_path)
    assert tool.main(["--check"]) == 1
    assert "added: check --exclude" in capsys.readouterr().err


def test_surface_drift_names_the_command_and_the_option() -> None:
    """Scenario "Surface drift detected": an option added to check without regenerating."""
    commands = discover()
    original = commands["check"]

    def register(parser: argparse.ArgumentParser) -> None:
        original.register(parser)
        parser.add_argument("--surface-probe", default=None)

    commands["check"] = dataclasses.replace(original, register=register)
    change = _only(surface_changes(_fresh(), cli_surface(commands)))
    assert (change.kind, change.path, change.breaking) == ("added", "check --surface-probe", False)


def test_hidden_command_left_out() -> None:
    """Scenario "Hidden command left out"."""
    data = _fresh().to_json()
    assert "_echo" not in data["commands"]
    visible = {name for name, command in discover().items() if not command.hidden}
    assert set(data["commands"]) == visible | {GLOBAL}


def test_surface_holds_the_registries() -> None:
    from fenolite.cli.errors import REGISTRY
    from fenolite.cli.exitcodes import ExitCode

    data = _fresh().to_json()
    assert data["contract"] == "v1"
    assert data["exit_codes"] == {code.name: int(code) for code in ExitCode}
    assert data["fen_codes"] == {code: int(spec.exit_code) for code, spec in REGISTRY.items()}
    assert data["issue_codes"]["kicad.drc.*"]["severities"]
    assert not set(data["issue_codes"]) & set(REGISTRY)
    assert {"--json", "--fields", "--seed", "--version"} <= set(data["commands"][GLOBAL]["options"])
    assert "--fields" not in data["commands"]["inspect"]["options"]
    assert data["commands"]["build"]["mutates"] is True
    assert "--dry-run" in data["commands"]["build"]["options"]
    assert data["commands"]["edit"]["exclusive"] == [
        {"options": ["--content-file", "--edits-file"], "required": True}
    ]
    assert data["commands"]["inspect"]["options"]["<file>"]["position"] == 0


def test_experimental_items_are_marked() -> None:
    commands = _fresh().to_json()["commands"]
    build = commands["build"]["options"]
    assert build["--target"]["experimental_choices"] == ["altium"]
    assert build["--target"]["experimental"] is False
    assert build["--altium-pour"]["experimental"] is True
    assert build["--out"]["experimental"] is False
    issue_codes = _fresh().to_json()["issue_codes"]
    assert issue_codes["altium.copper-stack"]["experimental"] is True
    assert issue_codes["altium.import.bad-stack"]["experimental"] is False


def test_library_section() -> None:
    import fenolite.api
    import fenolite.dsl

    library = _fresh().to_json()["library"]
    assert set(library) == {"fenolite.api", "fenolite.dsl"}
    assert set(library["fenolite.api"]) == set(fenolite.api.__all__)
    assert set(library["fenolite.dsl"]) == set(fenolite.dsl.__all__)
    convert = library["fenolite.api"]["convert"]
    assert convert["kind"] == "function"
    assert convert["parameters"]["source"] == {
        "kind": "positional_or_keyword", "position": 0, "has_default": False, "default": None,
    }  # fmt: skip
    assert convert["parameters"]["name"]["has_default"] is True
    assert library["fenolite.api"]["Board"]["kind"] == "class"
    assert library["fenolite.dsl"]["select"]["kind"] == "module"
    assert "Select" in library["fenolite.dsl"]["select"]["names"]


# ----------------------------------------------------------------------------------------- the judge (1.2)


def test_a_removed_option_is_breaking() -> None:
    """Scenario "A removed option is breaking"."""
    before = _data()
    after = _data()
    del after["commands"]["inspect"]["options"]["--streams"]
    change = _only(_changes(before, after))
    assert (change.kind, change.path, change.breaking) == ("removed", "inspect --streams", True)


def test_an_experimental_option_may_change() -> None:
    """Scenario "An experimental option may change"."""
    before = _data()
    after = _data()
    option = after["commands"]["build"]["options"]["--altium-pour"]
    option["choices"] = [c for c in option["choices"] if c != "outline"]
    change = _only(_changes(before, after))
    assert (change.kind, change.path, change.breaking) == ("narrowed", "build --altium-pour outline", False)


def test_an_experimental_choice_may_go() -> None:
    before = _data()
    after = _data()
    option = after["commands"]["build"]["options"]["--target"]
    option["choices"] = ["kicad"]
    option["experimental_choices"] = []
    changes = _changes(before, after)
    assert [c.path for c in changes] == ["build --target altium", "build --target [experimental_choices]"]
    assert not any(c.breaking for c in changes)


def test_a_library_parameter_removed_is_breaking() -> None:
    """Scenario "A library parameter removed is breaking"."""
    before = _data()
    after = _data()
    del after["library"]["fenolite.api"]["convert"]["parameters"]["name"]
    change = _only(_changes(before, after))
    assert (change.kind, change.path, change.breaking) == ("removed", "fenolite.api.convert(name)", True)


def test_an_addition_is_not_breaking() -> None:
    """Scenario "An addition is not breaking"."""
    before = _data()
    after = _data()
    after["commands"]["analyze"]["options"]["--surface-probe"] = copy.deepcopy(
        before["commands"]["analyze"]["options"]["--net"]
    )
    change = _only(_changes(before, after))
    assert (change.kind, change.breaking) == ("added", False)


def test_unchanged_surface_has_no_change() -> None:
    assert _changes(_data(), _data()) == ()


@pytest.mark.parametrize(
    ("edit", "kind", "path"),
    [
        (lambda d: d["commands"]["check"]["options"]["--exclude"].update(default="x"), "default-changed",
         "check --exclude"),
        (lambda d: d["commands"]["check"]["options"]["--exclude"].update(type="int"), "type-changed",
         "check --exclude"),
        (lambda d: d["commands"]["check"]["options"]["--exclude"].update(required=True), "required-added",
         "check --exclude"),
        (lambda d: d["commands"]["check"]["options"].update({"--new": {**d["commands"]["check"]["options"][
            "--exclude"], "required": True}}), "required-added", "check --new"),
        (lambda d: d["commands"]["check"]["options"]["--exclude"].update(choices=["a"]), "narrowed",
         "check --exclude"),
        (lambda d: d["commands"][GLOBAL]["options"]["--format"].update(choices=["detailed"]), "narrowed",
         "* --format concise"),
        (lambda d: d["commands"].pop("fmt"), "removed", "fmt"),
        (lambda d: d["commands"]["fmt"].update(mutates=not d["commands"]["fmt"]["mutates"]), "type-changed",
         "fmt [mutates]"),
        (lambda d: d["exit_codes"].pop("LOSSY"), "removed", "exit:LOSSY"),
        (lambda d: d["fen_codes"].update({"FEN-2001": 3}), "type-changed", "FEN-2001"),
        (lambda d: d["issue_codes"].pop("kicad.drc.*"), "removed", "kicad.drc.*"),
        (lambda d: d["issue_codes"]["gate.unnamed"].update(severities=["error"]), "severity-raised",
         "gate.unnamed"),
        (lambda d: d["library"]["fenolite.api"].pop("trial"), "removed", "fenolite.api.trial"),
        (lambda d: d["library"]["fenolite.api"]["convert"]["parameters"].update(
            extra={"kind": "keyword_only", "position": 9, "has_default": False, "default": None}),
         "required-added", "fenolite.api.convert(extra)"),
        (lambda d: d["library"]["fenolite.api"]["convert"]["parameters"]["source"].update(
            kind="keyword_only"), "type-changed", "fenolite.api.convert(source)"),
        (lambda d: d["library"]["fenolite.api"]["Board"].update(kind="function"), "type-changed",
         "fenolite.api.Board"),
        (lambda d: d["library"]["fenolite.dsl"]["select"]["names"].pop("Select"), "removed",
         "fenolite.dsl.select.Select"),
    ],
)  # fmt: skip
def test_breaking_kinds(edit: Any, kind: str, path: str) -> None:
    before = _data()
    after = _data()
    edit(after)
    change = _only(_changes(before, after))
    assert (change.kind, change.path, change.breaking) == (kind, path, True)


def test_a_removed_field_is_breaking() -> None:
    before = _data()
    fields = before["library"]["fenolite.api"]["Board"]["fields"]
    assert fields, "Board has public fields"
    name = sorted(fields)[0]
    after = _data()
    del after["library"]["fenolite.api"]["Board"]["fields"][name]
    change = _only(_changes(before, after))
    assert (change.kind, change.path, change.breaking) == ("removed", f"fenolite.api.Board.{name}", True)


@pytest.mark.parametrize(
    ("edit", "kind"),
    [
        (lambda d: d["issue_codes"]["gate.unnamed"].update(severities=["info"]), "severity-lowered"),
        (lambda d: d["commands"]["check"]["options"]["--exclude"].update(required=False), None),
        (lambda d: d["library"]["fenolite.api"]["convert"]["parameters"].update(
            extra={"kind": "keyword_only", "position": 9, "has_default": True, "default": 1}), "added"),
        (lambda d: d["library"]["fenolite.api"]["convert"]["parameters"]["name"].update(default="x"),
         "default-changed"),
        (lambda d: d["issue_codes"].update({"probe.new": {"severities": ["error"], "experimental": False,
                                                          "deprecated": None}}), "added"),
        (lambda d: d["commands"][GLOBAL]["options"]["--format"]["choices"].append("wide"), "added"),
    ],
)  # fmt: skip
def test_non_breaking_kinds(edit: Any, kind: str | None) -> None:
    before = _data()
    after = _data()
    edit(after)
    changes = _changes(before, after)
    if kind is None:
        assert changes == ()
        return
    change = _only(changes)
    assert (change.kind, change.breaking) == (kind, False)


def test_a_deprecated_item_may_go() -> None:
    before = _data()
    before["commands"]["check"]["options"]["--exclude"]["deprecated"] = {"since": "1.1.0", "use": "--waive"}
    after = copy.deepcopy(before)
    del after["commands"]["check"]["options"]["--exclude"]
    change = _only(_changes(before, after))
    assert (change.kind, change.breaking) == ("removed", False)


def test_a_deprecated_command_may_go() -> None:
    before = _data()
    before["commands"]["fmt"]["deprecated"] = {"since": "1.1.0", "use": "edit"}
    after = copy.deepcopy(before)
    del after["commands"]["fmt"]
    change = _only(_changes(before, after))
    assert (change.kind, change.path, change.breaking) == ("removed", "fmt", False)


def test_an_experimental_issue_code_may_go() -> None:
    before = _data()
    after = _data()
    del after["issue_codes"]["altium.copper-stack"]
    change = _only(_changes(before, after))
    assert (change.kind, change.breaking) == ("removed", False)


def test_marking_an_item_experimental_is_breaking() -> None:
    before = _data()
    after = _data()
    after["commands"]["check"]["options"]["--exclude"]["experimental"] = True
    change = _only(_changes(before, after))
    assert change.breaking


def test_change_to_json() -> None:
    change = SurfaceChange("removed", "inspect --streams", {"type": "flag"}, None, True)
    assert change.to_json() == {
        "kind": "removed", "path": "inspect --streams", "before": {"type": "flag"}, "after": None,
        "breaking": True,
    }  # fmt: skip
    assert str(change).startswith("BREAKING removed: inspect --streams")


def test_surface_round_trips() -> None:
    surface = _fresh()
    again = Surface.from_json(json.loads(surface.dumps()))
    assert again.dumps() == surface.dumps()
