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
    {export!r}, {tests!r}
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
