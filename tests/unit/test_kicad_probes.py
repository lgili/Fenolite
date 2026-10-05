# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The probe results file: write, compare and missing-file modes with a fake probe (capability
kicad-oracle, "Probe results per kicad-cli version"; change c0017). No ``kicad-cli`` is run."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parents[1]
FAKE = """
import sys
sys.path[:0] = [
    {kicad!r}, {board!r}, {rules!r}, {project!r}, {build!r}, {sheets!r}, {check!r}, {lens!r},
    {export!r}, {frame!r}, {zones!r}, {copper!r}, {fill!r}, {place!r}, {analysis!r}, {assembly!r},
    {export!r}, {frame!r}, {zones!r}, {copper!r}, {fill!r}, {place!r}, {analysis!r}, {schematic!r},
    {followups!r}, {tests!r}
]
from pathlib import Path
import _probes

FOLDER = Path({folder!r})


def test_fake(monkeypatch):
    probes = {{
        "fake-probe": _probes.Probe(lambda: "load", (10,)),
        "nine-only": _probes.Probe(lambda: "reject", (9,)),
    }}
    monkeypatch.setattr(_probes, "PROBES", probes)
    _probes.run.cache_clear()
    found = _probes.outcomes(10)
    _probes.run.cache_clear()
    assert found == {{"fake-probe": "load"}}
    _probes.verify("1.2.3", found, FOLDER)
"""


@pytest.fixture
def fake(pytester: pytest.Pytester, tmp_path: Path) -> Path:
    folder = tmp_path / "probes"
    source = FAKE.format(
        kicad=str(TESTS / "kicad"),
        board=str(TESTS / "kicad" / "board"),
        rules=str(TESTS / "kicad" / "rules"),
        project=str(TESTS / "kicad" / "project"),
        build=str(TESTS / "kicad" / "build"),
        sheets=str(TESTS / "kicad" / "sheets"),
        check=str(TESTS / "kicad" / "check"),
        lens=str(TESTS / "kicad" / "lens"),
        export=str(TESTS / "kicad" / "export"),
        frame=str(TESTS / "kicad" / "frame"),
        zones=str(TESTS / "kicad" / "zones"),
        copper=str(TESTS / "kicad" / "copper"),
        fill=str(TESTS / "kicad" / "fill"),
        place=str(TESTS / "kicad" / "place"),
        analysis=str(TESTS / "kicad" / "analysis"),
        assembly=str(TESTS / "kicad" / "assembly"),
        schematic=str(TESTS / "kicad" / "schematic"),
        followups=str(TESTS / "kicad" / "followups"),
        tests=str(TESTS),
        folder=str(folder),
    )
    pytester.makepyfile(test_fake=source)
    return folder


def test_missing_results_file(pytester: pytest.Pytester, fake: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FENOLITE_PROBES_WRITE", raising=False)
    result = pytester.runpytest("-p", "no:cacheprovider")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*no probe results for kicad-cli 1.2.3*FENOLITE_PROBES_WRITE=1*"])


def test_results_written_then_compared(
    pytester: pytest.Pytester, fake: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FENOLITE_PROBES_WRITE", "1")
    pytester.runpytest("-p", "no:cacheprovider").assert_outcomes(passed=1)
    data = json.loads((fake / "1.2.3.json").read_text(encoding="utf-8"))
    assert data == {"version": "1.2.3", "probes": {"fake-probe": "load"}}
    monkeypatch.delenv("FENOLITE_PROBES_WRITE")
    pytester.runpytest("-p", "no:cacheprovider").assert_outcomes(passed=1)


def test_drift_detected(pytester: pytest.Pytester, fake: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FENOLITE_PROBES_WRITE", raising=False)
    fake.mkdir(parents=True)
    (fake / "1.2.3.json").write_text(json.dumps({"version": "1.2.3", "probes": {"fake-probe": "reject"}}))
    result = pytester.runpytest("-p", "no:cacheprovider")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*fake-probe: recorded 'reject', now 'load'*"])


# -- the library table probes (c0021): the outcome rule and the registered ids, without kicad-cli


def _kicad_paths() -> None:
    import sys

    root = TESTS / "kicad"
    subfolders = sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith("_"))
    for folder in (str(root), *(str(p) for p in subfolders)):
        if folder not in sys.path:
            sys.path.insert(0, folder)


def _report(issues: int, mismatches: int, other: int = 0):  # type: ignore[no-untyped-def]
    from fenolite.backends.base import DrcReport, DrcViolation

    violations = (
        *(DrcViolation("lib_footprint_issues", "d", "warning") for _ in range(issues)),
        *(DrcViolation("lib_footprint_mismatch", "d", "warning") for _ in range(mismatches)),
        *(DrcViolation("clearance", "d", "error") for _ in range(other)),
    )
    return DrcReport("b.kicad_pcb", "", "10.0.6", "mm", violations=violations)


@pytest.mark.parametrize(
    ("issues", "mismatches", "wanted"),
    [(0, 1, "absent"), (1, 0, "present"), (2, 0, "present"), (0, 0, "different"), (1, 1, "different"),
     (0, 2, "different")],
)  # fmt: skip
def test_libtable_outcome_rule(issues: int, mismatches: int, wanted: str) -> None:
    _kicad_paths()
    import _libtables

    assert _libtables.outcome(_report(issues, mismatches, other=3)) == wanted
    assert _libtables.outcome(None) == "reject" and _libtables.outcome(None, timed_out=True) == "timeout"


def test_libtable_probes_are_registered() -> None:
    _kicad_paths()
    import _libtables
    import _probes

    ids = [_libtables.probe_id(layout) for layout in _libtables.LAYOUTS]
    assert len(ids) == 13 and all(i.startswith("pcb-libtable-") for i in ids)
    for pid in ids:
        assert _probes.PROBES[pid].majors == (9, 10), pid
    assert "pcb-libdrc-missing-table" in _probes.PROBES  # the guard of every library table probe


def test_libtable_rows_follow_the_major() -> None:
    _kicad_paths()
    import _libtables

    ten = _libtables.table(
        _libtables.row("Sub", "${KIPRJMOD}/sub/fp-lib-table", major=10, kind="Table"), major=10
    )
    assert "(version 7)" in ten and '(type "Table")' in ten and '(name "Sub")' in ten
    nine = _libtables.table(_libtables.row("Mini", "Mini_v9.pretty", major=9), major=9)
    assert "(version" not in nine and "(name Mini)(type KiCad)(uri Mini_v9.pretty)" in nine
