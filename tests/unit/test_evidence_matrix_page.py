# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The generated evidence matrix page (capability verification-evidence, "Generated evidence matrix
page"; change c0067)."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType

import pytest

from fenolite.backends import matrix
from fenolite.backends.base import MatrixRow
from fenolite.backends.matrix import ModuleClaim
from fenolite.core.evidence import Evidence, Level
from fenolite.verify import load_register

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "docs" / "evidence" / "matrix.md"
REGISTER = ROOT / "docs" / "hypotheses.md"


def _tool() -> ModuleType:
    name = "fenolite_gen_evidence_matrix"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / "gen_evidence_matrix.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _section(text: str, title: str) -> str:
    start = text.index(f"\n## {title}\n")
    end = text.find("\n## ", start + 1)
    return text[start : end if end != -1 else len(text)]


def test_committed_page_is_current(capsys: pytest.CaptureFixture[str]) -> None:
    """Fails when a declaration, a matrix row or the level text of a named id changed without the page."""
    before = PAGE.read_bytes()
    assert _tool().main(["--check"]) == 0, capsys.readouterr().err
    assert PAGE.read_bytes() == before
    assert b"\r" not in before and before.endswith(b"\n")


def test_stale_page_is_reported(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    text = PAGE.read_text(encoding="utf-8")
    changed = text.replace(
        "| kicad | `kicad_pcb` | INFERRED |", "| kicad | `kicad_pcb` | KICAD-VERIFIED |", 1
    )
    assert changed != text
    page = tmp_path / "matrix.md"
    page.write_bytes(changed.encode("utf-8"))
    assert _tool().main(["--check", "--page", str(page)]) == 1
    message = capsys.readouterr().err
    assert "docs/evidence/matrix.md" in message and "tools/gen_evidence_matrix.py" in message
    assert page.read_bytes() == changed.encode("utf-8"), "--check writes nothing"
    missing = tmp_path / "absent.md"
    assert _tool().main(["--check", "--page", str(missing)]) == 1 and not missing.exists()


def test_rendering_is_repeatable(tmp_path: Path) -> None:
    first, second = _tool().render(), _tool().render()
    assert first == second
    assert not re.search(r"\b20\d\d-\d\d-\d\d\b", _section(first, "Matrix") + _section(first, "Modules"))
    assert not re.search(r"(^|[\s(`'\"])/[A-Za-z]", first), "no absolute path"
    assert str(ROOT) not in first and "\r" not in first
    page = tmp_path / "matrix.md"
    assert _tool().main(["--page", str(page)]) == 0
    assert page.read_bytes() == first.encode("utf-8")


def test_page_order_and_matrix_lines() -> None:
    text = PAGE.read_text(encoding="utf-8")
    assert text.startswith("# Evidence matrix\n")
    head = text[: text.index("\n## ")]
    assert "tools/gen_evidence_matrix.py" in head and "Do not edit by" in head
    titles = re.findall(r"^## (.+)$", text, re.M)
    assert titles == ["Operations", "Matrix", "Hypotheses", "Modules"]
    for name, _ in _tool().MEANINGS:
        assert f"| `{name}` |" in _section(text, "Operations")
    table = _section(text, "Matrix")
    for row in matrix.rows():
        (line,) = [ln for ln in table.splitlines() if ln.startswith(f"| {row.backend} | `{row.kind}` |")]
        for ident in row.verified_by():
            assert f"`{ident}`" in line
    symbols = next(ln for ln in table.splitlines() if "`kicad_sym`" in ln)
    assert "UNVERIFIED (experimental)" in symbols
    assert "| — |" in next(ln for ln in table.splitlines() if "`specctra_dsn`" in ln)


def test_register_level_shown_next_to_the_id() -> None:
    rows = {row.id: row for row in load_register(REGISTER)}
    text = _section(PAGE.read_text(encoding="utf-8"), "Hypotheses")
    wanted = rows["H-K-PCB-WRITE"].level_text
    assert "(" in wanted, "the level text names the KiCad versions it was checked on"
    assert text.count("| `H-K-PCB-WRITE` |") == 1
    assert f"| `H-K-PCB-WRITE` | {wanted} |" in text
    named = sorted({ident for row in matrix.rows() for ident in row.verified_by()})
    listed = re.findall(r"^\| `(H-[AGK]-[A-Z0-9-]+)` \|", text, re.M)
    assert listed == named
    for ident in named:
        assert f"| `{ident}` | {rows[ident].level_text.replace('|', chr(92) + '|')} |" in text, ident


def test_module_without_a_claim_is_visible() -> None:
    row = MatrixRow("demo", "demo_kind", read=Evidence(Level.INFERRED, hypotheses=("H-K-PCB-READ",)))
    claims = [
        ModuleClaim("fenolite.backends.demo", "errors", none="error classes only"),
        ModuleClaim("fenolite.backends.demo", "helper", see=("reader",)),
        ModuleClaim("fenolite.backends.demo", "reader", constants=(("EVIDENCE", row.read or Evidence()),)),
    ]
    text = _tool().render([row], claims, load_register(REGISTER))
    modules = _section(text, "Modules")
    assert "| `errors` | none: error classes only |" in modules
    assert "| `helper` | see `reader` |" in modules
    assert "| `reader` | `EVIDENCE` INFERRED: `H-K-PCB-READ` |" in modules
    assert "| demo | `demo_kind` | — | INFERRED | — | — | — | `H-K-PCB-READ` |" in _section(text, "Matrix")


def test_page_lists_every_live_module() -> None:
    modules = _section(PAGE.read_text(encoding="utf-8"), "Modules")
    for package in matrix.packages():
        assert f"### `{package}`" in modules
        part = modules[modules.index(f"### `{package}`") :]
        part = part[: part.find("\n### ", 1) if part.find("\n### ", 1) != -1 else len(part)]
        for claim in matrix.module_claims(package):
            assert f"| `{claim.module}` |" in part, (package, claim.module)
            if claim.none:
                assert f"none: {claim.none}" in part


def test_readme_names_the_page_and_its_generator() -> None:
    text = (ROOT / "docs" / "evidence" / "README.md").read_text(encoding="utf-8")
    assert "matrix.md" in text and "tools/gen_evidence_matrix.py" in text
    assert "gen_evidence_matrix.py" in (ROOT / "tools" / "README.md").read_text(encoding="utf-8")
