# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Backend protocol, read results and the registry (capability backend-protocol, change c0009)."""

from __future__ import annotations

import ast
import builtins
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from fenolite.backends import registry
from fenolite.backends.base import CapabilityReport, ReadResult
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.core.errors import Issue
from fenolite.model.library import Library

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "src" / "fenolite" / "backends" / "base.py"
MINI_R = ROOT / "tests" / "data" / "libs" / "Mini.pretty" / "Mini_R_0603.kicad_mod"
MINI_SYM = ROOT / "tests" / "data" / "libs" / "Mini.kicad_sym"


@pytest.fixture
def fresh_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(registry, "_BACKENDS", {})
    monkeypatch.setattr(registry, "_loaded", False)


def base_import_problems(source: str) -> list[str]:
    """Imports of ``backends/base.py`` other than the standard library, ``core`` and ``model``."""
    problems: list[str] = []
    for node in ast.walk(ast.parse(source)):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        for name in names:
            top = name.split(".")[0]
            if top == "fenolite":
                if not name.startswith(("fenolite.core", "fenolite.model")):
                    problems.append(f"{name}: base imports only core and model")
            elif top not in sys.stdlib_module_names and top != "__future__":
                problems.append(f"{name}: base imports only core and model")
    return problems


def test_base_imports() -> None:
    assert base_import_problems(BASE.read_text(encoding="utf-8")) == []


def test_base_imports_detects_a_backend() -> None:
    text = BASE.read_text(encoding="utf-8") + "\nimport fenolite.backends.kicad\n"
    problems = base_import_problems(text)
    assert problems == ["fenolite.backends.kicad: base imports only core and model"]


def test_builtin_backend_in_a_fresh_interpreter() -> None:
    code = "from fenolite.backends import registry; print([b.name for b in registry.all_backends()])"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout
    assert out.strip() == "['kicad']"


def test_registry_module_imports_no_backend() -> None:
    code = (
        "import sys, fenolite.backends.registry, fenolite.cli.main; "
        "print(sorted(m for m in sys.modules if m.startswith('fenolite.backends.kicad')))"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout
    assert out.strip() == "[]"


@pytest.mark.usefixtures("fresh_registry")
def test_duplicate_registration() -> None:
    with pytest.raises(ValueError, match="kicad"):
        registry.register(KicadBackend())


@pytest.mark.usefixtures("fresh_registry")
def test_unknown_backend_names_the_known_ones() -> None:
    with pytest.raises(KeyError, match="kicad"):
        registry.get("nope")


@pytest.mark.usefixtures("fresh_registry")
def test_backend_for_a_path() -> None:
    assert registry.for_path(Path("a.kicad_pcb")) is registry.get("kicad")
    assert registry.for_path(Path("a.txt")) is None


class _Fake:
    name = "aaa"

    def detect(self, path: Path) -> bool:
        return path.suffix == ".kicad_pcb"

    def read(self, path: Path, *, issues: list[Issue] | None = None) -> ReadResult:
        raise NotImplementedError

    def capabilities(self) -> CapabilityReport:
        return CapabilityReport("aaa", ())


@pytest.mark.usefixtures("fresh_registry")
def test_backends_sorted_and_first_detecting_wins() -> None:
    fake = _Fake()
    registry.register(fake)
    assert [b.name for b in registry.all_backends()] == ["aaa", "kicad"]
    assert registry.for_path(Path("x.kicad_pcb")) is fake
    assert registry.for_path(Path("x.kicad_mod")) is registry.get("kicad")


def test_detection_by_name_opens_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    folder = tmp_path / "Lib.kicad_symdir"
    folder.mkdir()

    def refuse(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("detect opened a file")

    monkeypatch.setattr(builtins, "open", refuse)
    monkeypatch.setattr(Path, "open", refuse)
    backend = KicadBackend()
    paths = [Path("a.kicad_pcb"), Path("a.kicad_mod"), Path("a.kicad_sym"), folder, Path("a.txt")]
    assert [backend.detect(p) for p in paths] == [True, True, True, True, False]


def test_footprint_read_through_the_backend() -> None:
    issues: list[Issue] = []
    result = KicadBackend().read(MINI_R, issues=issues)
    assert isinstance(result.content, Library)
    assert [f.name for f in result.content.footprints] == ["Mini_R_0603"]
    assert result.evidence.level.value == "INFERRED"
    assert list(result.issues) == issues
    with pytest.raises(TypeError):
        _ = result.design


def test_symbol_library_read_through_the_backend() -> None:
    result = KicadBackend().read(MINI_SYM)
    assert isinstance(result.content, Library)
    assert result.content.name == "Mini" and result.content.symbols


def test_kicad_capability_report() -> None:
    """The write fields of c0017 replace c0009's pre-writer values (write kinds empty, no targets)."""
    report = KicadBackend().capabilities().to_json()
    assert "kicad_pcb" in report.pop("write_kinds")
    assert report == {
        "name": "kicad",
        "read_kinds": ["kicad_pcb", "kicad_mod", "kicad_sym"],
        "targets": [9, 10],
        "default_target": 10,
        "downgrade": "unsupported",
        "operations": ["detect", "read", "write"],
        "evidence": {"level": "INFERRED", "oracle": None, "hypotheses": ["H-K-PCB-READ", "H-K-PCB-WRITE"]},
    }
    assert "lower" not in report["operations"] and "validate" not in report["operations"]
    json.dumps(report)


def test_board_read_through_the_backend() -> None:
    board = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
    issues: list[Issue] = []
    result = KicadBackend().read(board, issues=issues)
    assert result.design.board is not None and len(result.design.board.footprints) == 2
    assert not [i for i in result.issues if i.severity == "error"]
    assert result.evidence.level.value == "INFERRED"
    validation = result.design.validate()
    assert result.issues == (*issues, *validation)


def test_capability_invariants() -> None:
    """Every listed operation is implemented, and a backend that writes nothing says so."""
    for backend in registry.all_backends():
        report = backend.capabilities()
        assert {"detect", "read"} <= set(report.operations), backend.name
        for operation in report.operations:
            assert callable(getattr(backend, operation, None)), f"{backend.name} lists {operation!r}"
        if not report.write_kinds:
            assert "write" not in report.operations and report.targets == () and report.default_target is None
        else:
            assert "write" in report.operations and report.default_target in report.targets
            assert list(report.targets) == sorted(report.targets)
        assert report.downgrade == "unsupported" or report.write_kinds
