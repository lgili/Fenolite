# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Vendored block imports, literal pins and static-record checks in builds (c0273)."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from types import ModuleType

import pytest
from _blockitems import VENDORED, get, project, release
from _checkcli import run
from _libdemo import no_network, unpublished_releases

from fenolite.cli._script import run_design_script
from fenolite.dsl.lock import read_lock


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    no_network(monkeypatch)
    unpublished_releases(monkeypatch)  # the demo releases call themselves 1.0.0
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))


@pytest.fixture
def ready(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    source = release(tmp_path / "one")
    work = project(tmp_path / "project")
    get(monkeypatch, work, source)
    return work


def test_vendored_block_is_pinned_twice_over(monkeypatch: pytest.MonkeyPatch, ready: Path) -> None:
    old = read_lock((ready / "design.lock").read_text(), file="design.lock")
    item_pin = dict(old.sections["library"]["block/Demo:led"])
    assert item_pin["version"] == "1.0.0"
    assert not (ready / "fenolite_library/__init__.py").exists()
    assert not (ready / "fenolite_library/blocks/__init__.py").exists()
    assert not (ready / "fenolite_library/blocks/Demo/__init__.py").exists()
    code, result, error, _ = run(monkeypatch, ready, "build", "design.py", "--out", "B", "--confirm")
    assert code == 0, (result, error)
    current = read_lock((ready / "design.lock").read_text(), file="design.lock")
    assert current.sections["blocks"] == {"led1": "Demo:led@1.0.0"}
    assert current.sections["library"]["block/Demo:led"] == item_pin
    assert "[block-packages]" not in (ready / "design.lock").read_text()
    assert "H-G-BLOCK-PACKAGES" in result["evidence"]["hypotheses"]
    assert run(monkeypatch, ready, "build", "design.py", "--out", "B", "--frozen", "--dry-run")[0] == 0
    assert not list((ready / VENDORED).rglob("__pycache__"))


def test_local_edit_warns_and_uses_code(monkeypatch: pytest.MonkeyPatch, ready: Path) -> None:
    source = ready / VENDORED / "__init__.py"
    source.write_text(source.read_text().replace('param("1k"', 'param("2k"'))
    code, result, error, _ = run(monkeypatch, ready, "build", "design.py", "--out", "B", "--confirm")
    assert code == 0, (result, error)
    assert any(i["code"] == "blocks.index-stale" and i["severity"] == "warning" for i in result["issues"])
    circuit = json.loads((ready / "B/.fenolite/circuit.json").read_text())
    assert circuit["components"][0]["value"] == "2k"


def test_missing_pinned_folder_fails_before_execution(monkeypatch: pytest.MonkeyPatch, ready: Path) -> None:
    shutil.rmtree(ready / VENDORED)
    script = ready / "design.py"
    script.write_text('from pathlib import Path\nPath("executed").write_text("bad")\n' + script.read_text())
    code, result, error, _ = run(monkeypatch, ready, "build", "design.py", "--out", "B", "--confirm")
    assert code == 6 and error["code"] == "FEN-6004"
    assert "get --locked design.py --dry-run" in error["hint"]
    assert not (ready / "executed").exists() and not (ready / "B").exists()


def test_project_local_namespace_is_restored(
    monkeypatch: pytest.MonkeyPatch, ready: Path, tmp_path: Path
) -> None:
    previous = ModuleType("fenolite_library")
    previous.__path__ = [str(tmp_path / "elsewhere")]
    monkeypatch.setitem(sys.modules, "fenolite_library", previous)
    first = run_design_script(ready / "design.py")
    assert first.design.parts["led1/R"].value == "1k"
    assert sys.modules["fenolite_library"] is previous
    assert not any(name.startswith("fenolite_library.") for name in sys.modules)
    source = ready / VENDORED / "__init__.py"
    source.write_text(source.read_text().replace('param("1k"', 'param("3k"'))
    second = run_design_script(ready / "design.py")
    assert second.design.parts["led1/R"].value == "3k"
    assert sys.modules["fenolite_library"] is previous


def test_two_projects_cannot_share_vendored_namespace_cache(
    monkeypatch: pytest.MonkeyPatch, ready: Path, tmp_path: Path
) -> None:
    other = project(tmp_path / "other")
    shutil.copytree(ready / "fenolite_library", other / "fenolite_library")
    source = other / VENDORED / "__init__.py"
    source.write_text(source.read_text().replace('param("1k"', 'param("4k"'))
    assert run_design_script(ready / "design.py").design.parts["led1/R"].value == "1k"
    assert run_design_script(other / "design.py").design.parts["led1/R"].value == "4k"
    assert not any(name == "fenolite_library" or name.startswith("fenolite_library.") for name in sys.modules)


def test_project_block_gets_no_item_pin(monkeypatch: pytest.MonkeyPatch, ready: Path) -> None:
    source = ready / VENDORED / "__init__.py"
    shutil.copy(source, ready / "own.py")
    (ready / "design.py").write_text(
        (ready / "design.py").read_text().replace("fenolite_library.blocks.Demo.led", "own")
    )
    (ready / "design.lock").unlink()
    shutil.rmtree(ready / "fenolite_library")
    code, result, error, _ = run(monkeypatch, ready, "build", "design.py", "--out", "B", "--confirm")
    assert code == 0, (result, error)
    current = read_lock((ready / "design.lock").read_text(), file="design.lock")
    assert current.sections["library"] == {} and current.sections["blocks"] == {"led1": "Demo:led@1.0.0"}


def test_review_binds_vendored_source(monkeypatch: pytest.MonkeyPatch, ready: Path) -> None:
    code, result, error, _ = run(monkeypatch, ready, "build", "design.py", "--out", "B", "--dry-run")
    assert code == 0, error
    source = ready / VENDORED / "__init__.py"
    source.write_text(source.read_text() + "\n# changed since review\n")
    code, _, error, _ = run(
        monkeypatch,
        ready,
        "build",
        "design.py",
        "--out",
        "B",
        "--confirm",
        "--plan",
        result["result"]["plan_id"],
    )
    assert code == 4 and error["code"] == "FEN-4002"


@pytest.mark.parametrize(
    "statement",
    [
        "from fenolite_library.blocks.Demo.led import led",
        "import fenolite_library.blocks.Demo.led as authored",
        "from fenolite_library.blocks.Demo import led",
    ],
)
def test_missing_unpinned_block_has_get_hint(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, statement: str
) -> None:
    (tmp_path / "design.py").write_text(statement + "\n")
    code, result, error, _ = run(monkeypatch, tmp_path, "build", "design.py", "--out", "B", "--confirm")
    assert code == 3 and error["code"] == "FEN-3004"
    assert "fenolite get block Demo:led --dry-run" in error["hint"]
    assert not (tmp_path / "B").exists() and not (tmp_path / "design.lock").exists()


def test_missing_unrelated_module_keeps_normal_script_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "design.py").write_text("import fenolite_unrelated_absent_module\n")
    code, result, error, _ = run(monkeypatch, tmp_path, "build", "design.py", "--out", "B", "--dry-run")
    assert code == 3 and error["code"] == "FEN-3004" and "fenolite get" not in error["hint"]
