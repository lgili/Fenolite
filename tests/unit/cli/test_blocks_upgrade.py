# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Reviewed lock-only block upgrades with real authored releases and circuit differences (c0273)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from _blockitems import VENDORED, get, project, release
from _checkcli import run
from _libdemo import files_of, no_network, unpublished_releases

from fenolite.cli import cmd_build
from fenolite.cli._blocks_upgrade import _circuit_diff
from fenolite.dsl.lock import lock_text, make_lock, read_lock
from fenolite.model.circuit import Circuit, Component


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    no_network(monkeypatch)
    unpublished_releases(monkeypatch)  # the demo releases call themselves 1.0.0
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))


@pytest.fixture
def upgraded_code(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    initial = release(tmp_path / "old")
    work = project(tmp_path / "project")
    get(monkeypatch, work, initial)
    code, result, error, _ = run(monkeypatch, work, "build", "design.py", "--out", "B", "--confirm")
    assert code == 0, (result, error)
    newer = release(tmp_path / "new", version="1.1.0", resistance="2k")
    get(monkeypatch, work, newer)
    return work


def test_planned_upgrade_and_build_after_confirmation(
    monkeypatch: pytest.MonkeyPatch, upgraded_code: Path
) -> None:
    work = upgraded_code
    before = files_of(work)
    old = read_lock((work / "design.lock").read_text(), file="design.lock")
    code, result, error, _ = run(monkeypatch, work, "blocks", "upgrade", "design.py", "--dry-run")
    assert code == 0, (result, error)
    (row,) = result["result"]["upgrades"]
    assert (row["path"], row["id"], row["before"], row["after"], row["step"]) == (
        "led1",
        "Demo:led",
        "1.0.0",
        "1.1.0",
        "minor",
    )
    assert row["record"]["id"] == "Demo:led" and row["deprecated"] is None
    assert result["result"]["plan"][0]["path"] == "design.lock"
    assert [w["kind"] for w in result["result"]["plan"]] == ["lock"]
    assert files_of(work) == before
    code, result, error, _ = run(
        monkeypatch,
        work,
        "blocks",
        "upgrade",
        "design.py",
        "--confirm",
        "--plan",
        result["result"]["plan_id"],
    )
    assert code == 0, error
    assert [w["path"] for w in result["receipt"]["written"]] == ["design.lock"]
    current = read_lock((work / "design.lock").read_text(), file="design.lock")
    assert current.sections["blocks"]["led1"] == "Demo:led@1.1.0"
    for name in ("refs", "picks", "pins", "library"):
        assert current.sections[name] == old.sections[name]
    assert files_of(work / "B") == {k[2:]: v for k, v in before.items() if k.startswith("B/")}
    code, result, error, _ = run(monkeypatch, work, "build", "design.py", "--out", "B", "--dry-run")
    assert code == 0, (result, error)
    assert not any(i["code"] == "lock.block-version" for i in result["issues"])


@pytest.mark.parametrize("separators", ["native", "windows"])
def test_circuit_difference_shown(
    monkeypatch: pytest.MonkeyPatch, upgraded_code: Path, separators: str
) -> None:
    if separators == "windows":
        original = cmd_build._built

        def windows_paths(*args, **kwargs):
            validated = original(*args, **kwargs)
            return replace(
                validated,
                writes=tuple(replace(w, path=w.path.replace("/", "\\")) for w in validated.writes),
            )

        monkeypatch.setattr(cmd_build, "_built", windows_paths)
    code, result, error, _ = run(
        monkeypatch, upgraded_code, "blocks", "upgrade", "design.py", "--out", "B", "--dry-run"
    )
    assert code == 0, (result, error)
    (row,) = result["result"]["upgrades"]
    (change,) = row["circuit"]
    assert (change["path"], change["change"]) == ("led1/R", "changed")
    assert change["before"]["value"] == "1k" and change["after"]["value"] == "2k"


@pytest.mark.parametrize("changed", ["code", "record", "baseline", "lock"])
def test_review_binds_inputs(monkeypatch: pytest.MonkeyPatch, upgraded_code: Path, changed: str) -> None:
    work = upgraded_code
    code, result, error, _ = run(
        monkeypatch, work, "blocks", "upgrade", "design.py", "--out", "B", "--dry-run"
    )
    assert code == 0, (result, error)
    path = {
        "code": work / VENDORED / "__init__.py",
        "record": work / VENDORED / "block.json",
        "baseline": work / "B/.fenolite/circuit.json",
        "lock": work / "design.lock",
    }[changed]
    path.write_text(path.read_text() + "\n")
    code, result, error, _ = run(
        monkeypatch,
        work,
        "blocks",
        "upgrade",
        "design.py",
        "--out",
        "B",
        "--confirm",
        "--plan",
        result["result"]["plan_id"],
    )
    assert code == 4 and error["code"] == "FEN-4002"
    assert "Demo:led@1.0.0" in (work / "design.lock").read_text()


def test_confirmation_does_not_run_script_again(monkeypatch: pytest.MonkeyPatch, upgraded_code: Path) -> None:
    work = upgraded_code
    script = work / "design.py"
    script.write_text(
        'from pathlib import Path\np = Path("counter")\n'
        'p.write_text(str(int(p.read_text()) + 1) if p.exists() else "1")\n' + script.read_text()
    )
    code, result, error, _ = run(monkeypatch, work, "blocks", "upgrade", "design.py", "--dry-run")
    assert code == 0, error
    assert (work / "counter").read_text() == "1"
    code, result, error, _ = run(
        monkeypatch,
        work,
        "blocks",
        "upgrade",
        "design.py",
        "--confirm",
        "--plan",
        result["result"]["plan_id"],
    )
    assert code == 0, error
    assert (work / "counter").read_text() == "1"


def test_major_step_is_explicit(monkeypatch: pytest.MonkeyPatch, upgraded_code: Path) -> None:
    work = upgraded_code
    lock = read_lock((work / "design.lock").read_text(), file="design.lock")
    before = lock_text(make_lock(lock.design, {**lock.sections, "blocks": {"led1": "Demo:led@0.9.0"}}))
    (work / "design.lock").write_text(before)
    code, result, error, _ = run(monkeypatch, work, "blocks", "upgrade", "design.py", "--confirm")
    assert code == 5, error
    assert result["result"]["upgrades"][0]["step"] == "major"
    assert any(i["code"] == "blocks.upgrade-major" for i in result["issues"])
    assert (work / "design.lock").read_text() == before
    code, result, error, _ = run(
        monkeypatch, work, "blocks", "upgrade", "design.py", "--allow-major", "--confirm"
    )
    assert code == 0, (result, error)


def test_selection_preserves_unselected_versions(
    monkeypatch: pytest.MonkeyPatch, upgraded_code: Path
) -> None:
    work = upgraded_code
    script = work / "design.py"
    script.write_text(
        script.read_text()
        + """
from fenolite.dsl import block
@block(id="Demo:other", version="1.1.0", summary="authored empty control", licence="CC0-1.0")
def other(b):
    pass
design.use(other, "other")
"""
    )
    lock = read_lock((work / "design.lock").read_text(), file="design.lock")
    (work / "design.lock").write_text(
        lock_text(
            make_lock(
                lock.design,
                {**lock.sections, "blocks": {**lock.sections["blocks"], "other": "Demo:other@1.0.0"}},
            )
        )
    )
    code, result, error, _ = run(
        monkeypatch, work, "blocks", "upgrade", "design.py", "--block", "Demo:led", "--confirm"
    )
    assert code == 0, (result, error)
    assert [row["id"] for row in result["result"]["upgrades"]] == ["Demo:led"]
    current = read_lock((work / "design.lock").read_text(), file="design.lock")
    assert current.sections["blocks"] == {"led1": "Demo:led@1.1.0", "other": "Demo:other@1.0.0"}


def test_error_under_new_code_plans_nothing(monkeypatch: pytest.MonkeyPatch, upgraded_code: Path) -> None:
    work = upgraded_code
    script = work / "design.py"
    script.write_text(script.read_text() + '\nraise RuntimeError("authored failed upgrade")\n')
    before = (work / "design.lock").read_bytes()
    code, result, error, _ = run(monkeypatch, work, "blocks", "upgrade", "design.py", "--confirm")
    assert code == 3 and error["code"] == "FEN-3004"
    assert (work / "design.lock").read_bytes() == before


def test_frozen_and_unknown_selector_are_refused(
    monkeypatch: pytest.MonkeyPatch, upgraded_code: Path
) -> None:
    assert run(monkeypatch, upgraded_code, "blocks", "upgrade", "design.py", "--frozen")[0] == 2
    code, result, error, _ = run(
        monkeypatch, upgraded_code, "blocks", "upgrade", "design.py", "--block", "Demo:absent"
    )
    assert code == 2 and error["code"] == "FEN-2001"


def test_no_changed_versions_is_a_noop(monkeypatch: pytest.MonkeyPatch, upgraded_code: Path) -> None:
    work = upgraded_code
    assert run(monkeypatch, work, "blocks", "upgrade", "design.py", "--confirm")[0] == 0
    before = files_of(work)
    code, result, error, _ = run(monkeypatch, work, "blocks", "upgrade", "design.py", "--dry-run")
    assert code == 0, error
    assert result["result"]["upgrades"] == [] and files_of(work) == before


@pytest.mark.parametrize("before,after,step", [("1.0.0", "1.0.1", "patch"), ("1.2.0", "1.1.0", "downgrade")])
def test_patch_and_downgrade_steps(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, before: str, after: str, step: str
) -> None:
    work = project(tmp_path / "project")
    get(monkeypatch, work, release(tmp_path / "old", version=before))
    assert run(monkeypatch, work, "build", "design.py", "--out", "B", "--confirm")[0] == 0
    get(monkeypatch, work, release(tmp_path / "new", version=after))
    code, result, error, _ = run(monkeypatch, work, "blocks", "upgrade", "design.py", "--dry-run")
    assert code == 0, (result, error)
    assert result["result"]["upgrades"][0]["step"] == step


def test_circuit_diff_names_added_removed_and_changed_parts() -> None:
    def part(n: int, path: str, value: str) -> Component:
        return Component(
            id=f"cmp_00000000-0000-4000-8000-{n:012d}",
            ref=f"R{n}",
            value=value,
            properties={"fenolite.path": path},
        )

    before = Circuit(
        components=(part(1, "led1/R", "1k"), part(2, "led1/gone", "old"), part(3, "other/R", "unchanged"))
    )
    after = Circuit(
        components=(part(1, "led1/R", "2k"), part(4, "led1/new", "new"), part(3, "other/R", "unchanged"))
    )
    rows = _circuit_diff(before, after, "led1")
    assert [(row["path"], row["change"]) for row in rows] == [
        ("led1/R", "changed"),
        ("led1/gone", "removed"),
        ("led1/new", "added"),
    ]


def test_upgrade_records_are_captured_inside_script_import_scope(
    monkeypatch: pytest.MonkeyPatch, upgraded_code: Path
) -> None:
    source = upgraded_code / VENDORED / "__init__.py"
    source.write_text(
        source.read_text().replace("    positive =", "    from . import helper\n    positive =")
    )
    (source.parent / "helper.py").write_text("# Authored for this regression test.\nVALUE = 1\n")
    code, result, error, _ = run(monkeypatch, upgraded_code, "blocks", "upgrade", "design.py", "--dry-run")
    assert code == 0, (result, error)
    record = result["result"]["upgrades"][0]["record"]
    assert record["elaboration"] is None
    assert [port["name"] for port in record["ports"]] == ["NEG", "POS"]
