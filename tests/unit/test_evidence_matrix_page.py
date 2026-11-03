# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The generated evidence matrix page (capability verification-evidence, "Generated evidence matrix
page"; change c0067)."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType

import pytest

from fenolite.backends import matrix
from fenolite.backends.base import MatrixRow, VersionEvidence
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
    assert titles == ["Operations", "Matrix", "Write graduation", "Hypotheses", "Modules"]
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
        expected = rows[ident].level_text.replace("|", chr(92) + "|")
        if rows[ident].refuted:
            expected += " (refuted)"
        assert f"| `{ident}` | {expected} |" in text, ident


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


def test_graduation_section_names_actual_missing_hypotheses() -> None:
    from fenolite.backends.altium.claims import MATRIX
    from fenolite.verify.evidence import is_release_evidence

    register = {row.id: row for row in load_register(REGISTER)}
    text = _section(PAGE.read_text(encoding="utf-8"), "Write graduation")
    for row in MATRIX:
        if row.write is None:
            continue
        (line,) = [line for line in text.splitlines() if line.startswith(f"| `{row.kind}` |")]
        for ident in row.write.hypotheses:
            if not is_release_evidence(register[ident]):
                assert ident + " is not release-verified" in line
        assert "own-readback test is not declared" not in line
    assert "no supporting committed kit run" not in text, "known recorded runs must be used"


def test_graduation_rendering_uses_injected_proof_context() -> None:
    from fenolite.backends.base import GraduationRun
    from fenolite.verify.hypotheses import HypothesisRow

    ident = "H-A-ACC-KIT"
    run_id = "2026-10-13-12345678"
    register = [
        HypothesisRow(
            ident,
            "altium",
            "test",
            Level.ALTIUM_VERIFIED_KIT,
            f"ALTIUM-VERIFIED(kit; AD 26.5; 2026-10-13; {run_id})",
            "test",
            "pass",
            "pass",
            "2026-10-13",
        )
    ]
    row = MatrixRow(
        "altium",
        "altium_schlib",
        write=Evidence(Level.INFERRED, hypotheses=(ident,)),
        experimental=("write",),
    )
    run = GraduationRun(run_id, frozenset({ident}), frozenset(), True)
    context = {"own_readbacks": {row.kind: "proof"}, "suite_tests": {"proof"}}
    assert "| `altium_schlib` | none |" in _tool().render([row], [], register, runs=[run], **context)
    text = _tool().render([row], [], register, runs=[], **context)
    assert f"no supporting committed kit run {run_id}" in text
    from dataclasses import replace

    text = _tool().render(
        [row], [], register, runs=[replace(run, stale_hypotheses=frozenset({ident}))], **context
    )
    assert f"kit run {run_id} is stale" in text


def test_versioned_conformance_artifacts_are_deterministic_and_current() -> None:
    tool = _tool()
    rows = matrix.rows()
    text = tool.render_conformance_json(rows)
    assert text == tool.render_conformance_json(tuple(reversed(rows)))
    assert tool.CONFORMANCE_JSON.read_text(encoding="utf-8") == text
    assert tool.CONFORMANCE_PAGE.read_text(encoding="utf-8") == tool.render_conformance(rows)
    data = json.loads(text)
    assert data["schema"] == "fenolite.conformance.v1"
    for entry in data["rows"]:
        assert list(entry) == ["backend", "kind", "operation", "version", "tool", "level", "source"]
    dsn = next(entry for entry in data["rows"] if entry["kind"] == "specctra_dsn")
    assert dsn["version"] is dsn["tool"] is dsn["source"] is None and dsn["level"] == "INFERRED"
    assert str(ROOT) not in text and "\r" not in text


def test_missing_conformance_source_fails_check_without_writing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    scope = VersionEvidence("20260206", "kicad-cli 10.0.6", Level.INFERRED, "tests/kicad/test_missing.py")
    row = MatrixRow(
        "kicad",
        "kicad_pcb",
        read=Evidence(Level.INFERRED, hypotheses=("H-K-PCB-READ",)),
        versions={"read": (scope,)},
    )
    tool = _tool()
    before = {path: path.read_bytes() for path in (PAGE, tool.CONFORMANCE_JSON, tool.CONFORMANCE_PAGE)}
    monkeypatch.setattr(matrix, "rows", lambda: (row,))
    assert tool.main(["--check"]) == 1
    message = capsys.readouterr().err
    assert "kicad/kicad_pcb/read" in message and "tests/kicad/test_missing.py" in message
    assert before == {path: path.read_bytes() for path in before}


@pytest.mark.parametrize(
    "source", ["tests/../outside.py", "tests/test_missing.py", "../test_outside.py", "tests\\test_missing.py"]
)
def test_conformance_test_sources_cannot_escape_or_name_missing_files(tmp_path: Path, source: str) -> None:
    scope = VersionEvidence("1", "authored test", Level.INFERRED, source)
    row = MatrixRow(
        "x", "kind", read=Evidence(Level.INFERRED, hypotheses=("H-G-MODEL-OWN",)), versions={"read": (scope,)}
    )
    assert _tool().source_problems([row], repository=tmp_path)


def test_conformance_native_sources_require_current_nonsynthetic_passing_records() -> None:
    from dataclasses import replace

    from fenolite.verify.kit.manifest import Kit
    from fenolite.verify.kit.record import load_records

    rows = [row for row in matrix.rows() if row.backend == "altium" and row.kind == "altium_schdoc_ascii"]
    register = load_register(REGISTER)
    records = load_records(ROOT)
    empty_kit = Kit("0" * 64, {}, {}, {}, (), "0" * 64)
    problems = _tool().source_problems(rows, register=register, records=records, kit=empty_kit)
    assert len(problems) == 1 and "no current passing native observation" in problems[0]
    modified = [{**record, "synthetic": True} for record in records]
    problems = _tool().source_problems(rows, register=register, records=modified, kit=empty_kit)
    assert len(problems) == 1 and "synthetic" in problems[0]
    scope = rows[0].versions["write"][0]
    missing = replace(scope, source="2026-11-01-00000000")
    bad = replace(rows[0], versions={"write": (missing,)})
    assert (
        "no validated recorded run"
        in _tool().source_problems([bad], register=register, records=records, kit=empty_kit)[0]
    )


@pytest.mark.parametrize("alteration", ["version", "tool", "missing", "failed"])
def test_native_scope_refuses_mismatched_or_failed_record(alteration: str) -> None:
    from dataclasses import replace

    from fenolite.verify.kit.manifest import Kit
    from fenolite.verify.kit.record import load_records

    row = next(row for row in matrix.rows() if row.backend == "altium" and row.kind == "altium_schdoc_ascii")
    scope = row.versions["write"][0]
    if alteration == "version":
        scope = replace(scope, version="AD 0.0")
    elif alteration == "tool":
        scope = replace(scope, tool="unrecorded tool")
    records = load_records(ROOT)
    if alteration == "missing":
        records = []
    elif alteration == "failed":
        records = [
            {**record, "hypotheses": [{**item, "outcome": "fail"} for item in record["hypotheses"]]}
            for record in records
        ]
    candidate = replace(row, versions={"write": (scope,)})
    problems = _tool().source_problems(
        [candidate],
        register=load_register(REGISTER),
        records=records,
        kit=Kit("0" * 64, {}, {}, {}, (), "0" * 64),
    )
    assert problems and "altium/altium_schdoc_ascii/write" in problems[0]
