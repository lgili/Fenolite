# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Via protection through ``fenolite build`` (capabilities design-dsl, "Via protection defaults in the
DSL", and layout-lens, "Via protection defaults across rebuilds"; change c0112). Each test builds a blink
variant into ``tmp_path`` in-process, edits the result as KiCad would (by token edit), and builds again."""

from __future__ import annotations

import io
import json
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest
from _buildhelp import blink, build, codes
from _preserve_help import rebuild

import fenolite.cli.main as cli_main
from fenolite.backends.kicad import via_protection as vp
from fenolite.backends.kicad.copper import is_copper_uuid
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.sexpr import Node, dumps, parse, parse_fragment
from fenolite.dsl import protect, via_protection_locked
from fenolite.model.board import ViaProtection

ROOT = Path(__file__).resolve().parents[3]
BLINK_DIR = ROOT / "examples" / "blink_2layer"
IMPORT = "from fenolite.dsl import protect\n"
VIA = 'design.via("{key}", mm({x}), mm(26), net=gnd, diameter=mm(0.8), drill=mm(0.4){more})\n'
TENTED = "(tenting (front yes) (back yes))"
OPEN = "(tenting (front no) (back no))"
RESAVED = (
    f"{TENTED} (covering (front no) (back no)) (plugging (front no) (back no)) (capping no) (filling no)"
)


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def via_line(key: str, x: int, protection: str = "") -> str:
    return VIA.format(key=key, x=x, more=f", protection={protection}" if protection else "")


class Project:
    """A copy of the blink whose script gains ``append``, built into ``out`` in-process."""

    def __init__(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, append: str = "", target: int = 10
    ) -> None:
        self.monkeypatch = monkeypatch
        self.target = target
        root = tmp_path / f"repo-{target}"
        shutil.copytree(BLINK_DIR, root / "examples" / "blink_2layer")
        shutil.copytree(ROOT / "tests" / "data" / "libs", root / "tests" / "data" / "libs")
        self.script = root / "examples" / "blink_2layer" / "design.py"
        self.plain = self.script.read_text(encoding="utf-8")
        self.out = tmp_path / f"out-{target}"
        self.set_script(append)

    def set_script(self, append: str) -> None:
        self.script.write_text(self.plain + (IMPORT + append if append else ""), encoding="utf-8")

    def build(self, *flags: str) -> tuple[int, dict[str, object], str]:
        out, err = io.StringIO(), io.StringIO()
        self.monkeypatch.setattr("sys.stdout", out)
        self.monkeypatch.setattr("sys.stderr", err)
        args = ["--kicad-version", str(self.target), "build", str(self.script), "--out", str(self.out)]
        code = cli_main.main([*args, *flags, "--json"])
        return code, json.loads(out.getvalue()) if out.getvalue() else {}, err.getvalue()

    def confirm(self) -> dict[str, object]:
        code, env, err = self.build("--confirm")
        assert code == 0, err
        return env

    @property
    def board(self) -> Path:
        return self.out / "blink.kicad_pcb"

    @property
    def text(self) -> str:
        return self.board.read_text(encoding="utf-8")

    def setup(self) -> Node:
        found = parse(self.text).find("setup")
        assert found is not None
        return found

    def edit_setup(self, change: Callable[[Node], Node]) -> None:
        root = parse(self.text)
        new = change(self.setup())
        children = [new if isinstance(c, Node) and c.name == "setup" else c for c in root.children]
        self.board.write_text(dumps(root.with_children(children)), encoding="utf-8")

    def files(self) -> dict[str, bytes]:
        return {
            p.relative_to(self.out).as_posix(): p.read_bytes()
            for p in sorted(self.out.rglob("*"))
            if p.is_file() and not p.name.endswith(".bak")
        }


def via_codes(env: dict[str, object]) -> list[dict[str, str]]:
    return [i for i in env["issues"] if i["code"].startswith("kicad.via.")]  # type: ignore[union-attr, index]


def children(node: Node) -> list[str]:
    return [dumps(c, style="compact") for c in node.children]


def fragment(text: str) -> Node:
    found = parse_fragment(text)
    assert isinstance(found, Node)
    return found


def with_tenting(setup: Node, text: str) -> Node:
    new = fragment(text)
    return setup.with_children(
        new if isinstance(c, Node) and c.name == "tenting" else c for c in setup.children
    )


def planned_board(env: dict[str, object], project: Project) -> str:
    """The board a ``--dry-run`` plans: built again with ``--confirm`` into the same folder."""
    del env
    project.confirm()
    return project.text


# --- the script's default ------------------------------------------------------------------------------


@pytest.mark.parametrize("target", [9, 10])
def test_a_design_without_a_default_writes_no_protection(target: int) -> None:
    """Without ``via_protection()`` and without ``protection=`` the board holds no protection child; the
    bytes of every built file are pinned by the golden and determinism tests of the build."""
    output = build(blink(), target)
    assert via_protection_locked(blink()) is False
    root = parse(output.files["blink.kicad_pcb"].decode("utf-8"))
    setup = root.find("setup")
    assert setup is not None and children(setup) == ["(pad_to_mask_clearance 0)"]
    assert b'"via_protection"' not in output.files[".fenolite/board.json"]
    assert b'"protection"' not in output.files[".fenolite/board.json"]
    assert not [c for c in codes(output) if c.startswith("kicad.via.")]
    again = rebuild(blink(), output.files["blink.kicad_pcb"].decode("utf-8"), target)
    assert dict(again.files) == dict(output.files)


@pytest.mark.parametrize("target", [9, 10])
def test_built_for_both_targets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: int) -> None:
    script = "design.via_protection(protect(tenting=False))\n" + via_line("tp1", 8, "protect(tenting=True)")
    project = Project(tmp_path, monkeypatch, script, target)
    code, env, err = project.build("--dry-run")
    assert code == 0, err
    assert via_codes(env) == []
    design = read_board(planned_board(env, project))
    assert design.board is not None
    default = design.board.via_protection
    assert default is not None and (default.tenting_front, default.tenting_back) == (False, False)
    (via,) = [v for v in design.board.vias if is_copper_uuid(v.native_ids.get("kicad", ""))]
    assert (via.protection.tenting_front, via.protection.tenting_back) == (True, True)
    expected = (
        ["(pad_to_mask_clearance 0)", "(tenting none)"]
        if target == 9
        else ["(pad_to_mask_clearance 0)", OPEN, "(covering (front no) (back no))",
              "(plugging (front no) (back no))", "(capping no)", "(filling no)"]
    )  # fmt: skip
    assert children(project.setup()) == expected
    first = project.files()
    assert via_codes(project.confirm()) == [] and project.files() == first


def test_a_10_feature_for_target_9(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = Project(tmp_path, monkeypatch, via_line("tp1", 8, "protect(filling=True)"), target=9)
    code, env, err = project.build("--confirm")
    assert code == 7 and json.loads(err)["code"] == "FEN-7001"
    assert "kicad.board.via-protection-too-new" in err or "kicad.board.via-protection-too-new" in [
        i["code"]
        for i in env.get("issues", [])  # type: ignore[union-attr]
    ]
    assert not project.board.exists()
    code, _, err = project.build("--allow-lossy", "--confirm")
    assert code == 7 and not project.board.exists()
    ten = Project(tmp_path, monkeypatch, via_line("tp1", 8, "protect(filling=True)"), target=10)
    assert "(filling yes)" in dumps(parse(ten.confirm() and ten.text), style="compact")


def test_a_default_that_no_file_carries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    script = "design.via_protection(protect(plugging=True))\n" + via_line("tp1", 8) + via_line("tp2", 12)
    project = Project(tmp_path, monkeypatch, script)
    code, env, err = project.build("--dry-run")
    assert code == 0, err
    (issue,) = via_codes(env)
    assert issue["code"] == "kicad.via.protection-not-exported" and issue["severity"] == "info"
    assert "plugging_front" in issue["message"] and "plugging_back" in issue["message"]
    assert "2 via(s)" in issue["message"] and "10.0.6" in issue["message"]
    assert "protection=" in issue["hint"]
    # a via that carries the value itself is not counted
    project.set_script(
        "design.via_protection(protect(plugging=True))\n"
        + via_line("tp1", 8, "protect(plugging=True)")
        + via_line("tp2", 12)
    )
    (issue,) = via_codes(project.build("--dry-run")[1])
    assert "1 via(s)" in issue["message"]
    project.set_script("design.via_protection(protect(tenting=False))\n" + via_line("tp1", 8))
    assert via_codes(project.build("--dry-run")[1]) == []


# --- across rebuilds ------------------------------------------------------------------------------------


def test_an_edit_in_kicad_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = Project(tmp_path, monkeypatch, "design.via_protection(protect(tenting=True))\n")
    project.confirm()
    assert children(project.setup())[1] == TENTED
    project.edit_setup(lambda setup: with_tenting(setup, OPEN))
    env = project.confirm()
    assert children(project.setup())[1] == OPEN
    (issue,) = via_codes(env)
    assert issue["code"] == "kicad.via.protection-overridden" and issue["severity"] == "info"
    assert "tenting_front" in issue["message"] and "--discard-layout" in issue["hint"]
    assert "True" in issue["message"] and "False" in issue["message"]


def test_a_locked_default_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = Project(tmp_path, monkeypatch, "design.via_protection(protect(tenting=True))\n")
    project.confirm()
    project.edit_setup(lambda setup: with_tenting(setup, OPEN))
    project.set_script("design.via_protection(protect(tenting=True), locked=True)\n")
    env = project.confirm()
    assert children(project.setup())[1] == TENTED
    (issue,) = via_codes(env)
    assert issue["code"] == "kicad.via.protection-forced" and issue["severity"] == "warning"
    assert "tenting_front" in issue["message"]
    first = project.files()
    again = project.confirm()
    assert via_codes(again) == [] and project.files() == first


def test_a_default_added_to_a_built_board(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = Project(tmp_path, monkeypatch)
    project.confirm()
    before = project.setup()
    assert children(before) == ["(pad_to_mask_clearance 0)"]
    project.set_script('design.via_protection(protect(tenting="front"))\n')
    env = project.confirm()
    setup = project.setup()
    assert [c.name for c in setup.nodes()] == ["pad_to_mask_clearance", *vp.SETUP_ORDER]
    assert children(setup)[1] == "(tenting (front yes) (back no))"
    assert [c for c in setup.children if not (isinstance(c, Node) and c.name in vp.FEATURE_FIELDS)] == list(
        before.children
    )
    assert via_codes(env) == []


def test_equal_in_effect(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = Project(tmp_path, monkeypatch)
    project.confirm()
    project.edit_setup(
        lambda setup: setup.with_children([*setup.children, *fragment(f"(x {RESAVED})").children])
    )
    edited = project.setup()
    assert read_board(project.text).board.via_protection == vp.KICAD_DEFAULT  # type: ignore[union-attr]
    project.set_script("design.via_protection(protect(tenting=True))\n")
    env = project.confirm()
    assert via_codes(env) == []
    assert project.setup() == edited


def test_a_board_default_is_kept_without_a_script_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = Project(tmp_path, monkeypatch, "design.via_protection(protect(tenting=False))\n")
    project.confirm()
    kept = project.setup()
    project.set_script("")
    env = project.confirm()
    assert project.setup() == kept and via_codes(env) == []
    assert read_board(project.text).board.via_protection == ViaProtection(  # type: ignore[union-attr]
        False, False, False, False, False, False, False, False
    )


def test_the_build_function_takes_the_lock() -> None:
    """``build_design(lock_via_protection=)`` decides against an existing board; without it the board's
    default is kept."""
    scripted = blink()
    scripted.via_protection(protect(tenting=True), locked=True)
    assert via_protection_locked(scripted) is True
    first = build(scripted, 10)
    text = first.files["blink.kicad_pcb"].decode("utf-8")
    assert TENTED.replace(" ", "") in "".join(text.split())
    opened = text.replace("(front yes)\n\t\t\t(back yes)", "(front no)\n\t\t\t(back no)", 1)
    assert opened != text
    kept = rebuild(scripted, opened, 10)
    assert [c for c in codes(kept) if c.startswith("kicad.via.")] == ["kicad.via.protection-overridden"]
