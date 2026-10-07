# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite init`` and the starter projects it writes (capability cli-contract, "Init command";
capability agent-guide, "Starter projects"; change c0079)."""

from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path

import pytest
from _checkcli import hide_kicad, run

from fenolite.agent import guide

STARTERS = [starter.name for starter in guide.starters()]
LIB_ID = re.compile(r"^[A-Za-z0-9_.+-]+:[A-Za-z0-9_.+-]+$")
CATALOG = "Fenolite:"


def catalog_problems(script: str) -> list[str]:
    """Why a starter's script breaks the catalog rule: an empty list when it starts with the CC0 line,
    binds ``design`` at module level, places every part and names only ``Fenolite:`` lib ids."""
    problems: list[str] = []
    if script.split("\n", 1)[0] != guide.STARTER_HEADER:
        problems.append(f"the first line is not {guide.STARTER_HEADER!r}")
    tree = ast.parse(script)
    bound = {
        target.id
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    if "design" not in bound:
        problems.append("no module-level 'design'")
    parts: set[str] = set()
    placed: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and LIB_ID.match(node.value):
            if not node.value.startswith(CATALOG):
                problems.append(f"names the lib id {node.value}, which is not of the built-in catalog")
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            called = node.value.func
            if isinstance(called, ast.Name) and called.id == "Part":
                parts |= {target.id for target in node.targets if isinstance(target, ast.Name)}
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "place":
            if isinstance(node.func.value, ast.Name):
                placed.add(node.func.value.id)
    problems += [f"the part {name} is not placed" for name in sorted(parts - placed)]
    if not parts:
        problems.append("no part")
    return problems


def _refuse(*args: object, **kwargs: object) -> None:
    raise AssertionError("a starter test started a subprocess")


def _hermetic(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    hide_kicad(monkeypatch, tmp_path)
    monkeypatch.setattr(subprocess, "run", _refuse)
    monkeypatch.setattr(subprocess, "Popen", _refuse)
    work = tmp_path / "work"
    work.mkdir()
    return work


def _write_starter(work: Path, name: str) -> None:
    folder = work / name
    folder.mkdir()
    for file, data in guide.render_starter(name, name).items():
        (folder / file).write_bytes(data)


@pytest.mark.parametrize("name", STARTERS)
def test_starter_follows_the_catalog_rule(name: str) -> None:
    for file, data in guide.render_starter(name, name).items():
        assert catalog_problems(data.decode("utf-8")) == [], file


def test_starter_that_names_a_library_part_is_refused() -> None:
    """Scenario "Starter that names a library part is refused by the test"."""
    script = guide.render_starter("blink", "blink")["design.py"].decode("utf-8")
    assert '"Fenolite:Resistor"' in script
    assert catalog_problems(script.replace('"Fenolite:Resistor"', '"Device:R"')) == [
        "names the lib id Device:R, which is not of the built-in catalog"
    ]
    unplaced = catalog_problems(script.replace("r1.place(", "r1.field("))
    assert unplaced == ["the part r1 is not placed"]
    assert catalog_problems(script.replace("design = Design", "board = Design").replace("design.", "board."))
    assert catalog_problems(script.replace("CC0-1.0", "MIT", 1))


@pytest.mark.parametrize("target", ["9", "10"])
@pytest.mark.parametrize("name", STARTERS)
def test_starter_builds_without_a_tool(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, name: str, target: str
) -> None:
    """The hermetic proof of "Starter projects": no library table, no subprocess."""
    work = _hermetic(monkeypatch, tmp_path)
    _write_starter(work, name)
    args = (f"{name}/design.py", "--out", f"{name}/build", "--kicad-version", target)
    code, envelope, error, _ = run(monkeypatch, work, "build", *args, "--confirm")
    assert code == 0, error
    assert [issue for issue in envelope["issues"] if issue["severity"] == "error"] == []
    libraries = envelope["result"]["libraries"]
    assert libraries and set(libraries.values()) == {"builtin"}
    assert all(lib_id.startswith(CATALOG) for lib_id in libraries)
    assert envelope["result"]["staged"] == []
    assert (work / name / "build" / f"{name}.kicad_pcb").is_file()


@pytest.mark.parametrize("target", ["9", "10"])
def test_starter_blink_routes_and_checks_without_a_tool(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, target: str
) -> None:
    """Scenario "Blink builds and routes without a tool"."""
    work = _hermetic(monkeypatch, tmp_path)
    _write_starter(work, "blink")
    version = ("--kicad-version", target)
    code, _, error, _ = run(
        monkeypatch, work, "build", "blink/design.py", "--out", "blink/build", *version, "--confirm"
    )
    assert code == 0, error
    code, envelope, error, _ = run(
        monkeypatch, work, "route", "blink/build", "--router", "direct", *version, "--confirm"
    )
    assert code == 0, error
    assert sorted(envelope["result"]["routed"]) == ["GND", "LED_A", "VIN"]
    assert envelope["result"]["unrouted"] == []
    code, envelope, error, _ = run(
        monkeypatch, work, "check", "blink/build", "--stages", "model.validate,copper.clearance", *version
    )
    assert code == 0, (error, envelope["issues"])
    assert [(stage["name"], stage["status"]) for stage in envelope["result"]["stages"]] == [
        ("model.validate", "ok"),
        ("copper.clearance", "ok"),
    ]
    summary = envelope["result"]["stages"][1]["summary"]
    assert summary["items"] == {"pad": 6, "track": 3} and summary["shorts"] == 0


def test_starter_blink_is_the_described_board() -> None:
    script = guide.render_starter("blink", "blink")["design.py"].decode("utf-8")
    assert "design.board(mm(30), mm(20))" in script and "design.rules.minimum(" in script
    assert len(re.findall(r"^connect\(", script, re.MULTILINE)) == 3
    assert len(re.findall(r"= Part\(", script)) == 3


# --- the command (capability cli-contract, "Init command") -------------------------------------------


def test_new_project(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "New project"."""
    import shlex

    from fenolite.cli.api import discover
    from fenolite.cli.main import build_parser

    work = _hermetic(monkeypatch, tmp_path)
    code, envelope, error, _ = run(monkeypatch, work, "init", "board", "--confirm")
    assert code == 0, error
    script = (work / "board" / "design.py").read_text(encoding="utf-8")
    assert script.startswith("# SPDX-License-Identifier: CC0-1.0\n") and 'Design("board")' in script
    assert script.encode("utf-8") == guide.render_starter("blink", "board")["design.py"]
    result = envelope["result"]
    assert list(result) == ["starter", "name", "design", "next"]
    assert (result["starter"], result["name"], result["design"]) == ("blink", "board", "board/design.py")
    assert result["next"] == [
        "fenolite build board/design.py --out board/build --dry-run --json",
        "fenolite build board/design.py --out board/build --confirm --json",
    ]
    assert [w["path"] for w in envelope["receipt"]["written"]] == ["board/design.py"]
    parser = build_parser(discover())
    for line in result["next"]:
        words = shlex.split(line)
        assert words[0] == "fenolite"
        parsed = parser.parse_args(words[1:])
        assert parsed.command == "build" and parsed.out == "board/build"
    words = shlex.split(result["next"][0])
    code, built, error, _ = run(monkeypatch, work, *[w for w in words[1:] if w != "--json"])
    assert code == 0, error
    assert "board/build/board.kicad_pcb" in [Path(p).as_posix() for p in built["result"]["files"]]
    assert not (work / "board" / "build").exists()


def test_init_plans_before_it_writes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, envelope, _, _ = run(monkeypatch, tmp_path, "init", "blink", "--dry-run")
    assert code == 0 and [p["path"] for p in envelope["result"]["plan"]] == ["blink/design.py"]
    assert envelope["result"]["plan"][0]["kind"] == "starter" and list(tmp_path.iterdir()) == []
    code, _, error, _ = run(monkeypatch, tmp_path, "init", "blink")
    assert code == 4 and error["code"] == "FEN-4001" and list(tmp_path.iterdir()) == []


def test_existing_script_is_kept(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Existing script is kept"."""
    (tmp_path / "board").mkdir()
    mine = b"# my own script\n"
    (tmp_path / "board" / "design.py").write_bytes(mine)
    code, _, error, _ = run(monkeypatch, tmp_path, "init", "board", "--confirm")
    assert code == 2 and error["code"] == "FEN-2001" and "--force" in error["hint"]
    assert (tmp_path / "board" / "design.py").read_bytes() == mine
    assert sorted(p.name for p in (tmp_path / "board").iterdir()) == ["design.py"]
    code, envelope, error, _ = run(monkeypatch, tmp_path, "init", "board", "--force", "--confirm")
    assert code == 0, error
    assert (tmp_path / "board" / "design.py").read_bytes() == guide.render_starter("blink", "board")[
        "design.py"
    ]
    assert (tmp_path / "board" / "design.py.bak").read_bytes() == mine
    assert envelope["receipt"]["backup"] == ["board/design.py.bak"]


def test_name_that_is_not_a_design_name(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Name that is not a design name"."""
    code, _, error, _ = run(monkeypatch, tmp_path, "init", "my board", "--dry-run")
    assert code == 2 and error["code"] == "FEN-2001" and "--name" in error["hint"]
    code, _, error, _ = run(monkeypatch, tmp_path, "init", "board", "--name", ".x", "--dry-run")
    assert code == 2 and "--name" in error["hint"]
    code, envelope, error, _ = run(
        monkeypatch, tmp_path, "init", "my board", "--name", "my_board", "--dry-run"
    )
    assert code == 0, error
    assert envelope["result"]["name"] == "my_board" and envelope["result"]["design"] == "my board/design.py"
    assert envelope["result"]["next"][0] == (
        "fenolite build 'my board/design.py' --out 'my board/build' --dry-run --json"
    )
    assert list(tmp_path.iterdir()) == []


def test_name_defaults_to_the_last_part_of_the_folder(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    code, envelope, _, _ = run(monkeypatch, tmp_path, "init", "boards/first.v2", "--dry-run")
    assert code == 0 and envelope["result"]["name"] == "first.v2"
    assert envelope["result"]["design"] == "boards/first.v2/design.py"
    (tmp_path / "here-1").mkdir()
    code, envelope, _, _ = run(monkeypatch, tmp_path / "here-1", "init", ".", "--dry-run")
    assert code == 0 and envelope["result"]["name"] == "here-1"
    assert envelope["result"]["design"] == "design.py"


def test_unknown_starter(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, _, error, _ = run(monkeypatch, tmp_path, "init", "board", "--starter", "nope", "--dry-run")
    assert code == 2 and error["code"] == "FEN-2001" and "blink" in error["hint"]


def test_init_declaration() -> None:
    from fenolite.cli.cmd_init import COMMAND, DEFAULT_STARTER

    assert COMMAND.example_args == ("proj", "--dry-run") and COMMAND.mutation_example_args == ("proj",)
    assert COMMAND.mutates is True and DEFAULT_STARTER == "blink"
