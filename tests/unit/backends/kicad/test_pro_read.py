# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Project files read into the model (capability kicad-file-backend, "Project files are read into the
model" and "Project issue codes"; kicad-version-gating, "Project file versions"; change c0010)."""

from __future__ import annotations

import re
from pathlib import Path

import _netclass_bench as nb
import pytest
from _prodesigns import design, project, text

from fenolite.backends.kicad._json import JsonNumber
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.pro import (
    EVIDENCE,
    ISSUE_CODES,
    apply_project,
    pattern_matches,
    read_project,
)
from fenolite.backends.kicad.proerrors import ISSUE_CODES as LEAF_CODES
from fenolite.backends.kicad.triad import write_triad
from fenolite.backends.kicad.versions import VersionStatus
from fenolite.core.errors import ISSUE_CODE, FormatError, Issue
from fenolite.core.evidence import Level
from fenolite.core.ids import derived_id

ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / "src" / "fenolite" / "backends" / "kicad"
CODES: list[str] = []


def collect(found: list[Issue]) -> list[Issue]:
    CODES.extend(i.code for i in found)
    return found


def test_bench_project_read_back(tmp_path: Path) -> None:
    files = write_triad(nb.bench_design(target=10), name="bench", target=10)
    for name, body in files.items():
        (tmp_path / name).write_text(body, encoding="utf-8")
    board = read_board(tmp_path / "bench.kicad_pcb")
    found: list[Issue] = []
    info = read_project(tmp_path / "bench.kicad_pro", issues=found)
    applied = apply_project(board, info, issues=found)
    collect(found)
    assert [c.name for c in applied.circuit.netclasses] == ["Default", "HV"]
    hv = derived_id("cls", "kicad", "netclass:HV")
    by_name = {n.name: n.netclass_id for n in applied.circuit.nets}
    assert by_name["+3V3"] == hv and by_name["SIG1"] == hv
    for name in ("SIG10", "Net-(R1-Pad1)", "Net-R1-Pad1", "D[0]", "D0", "GND"):
        assert by_name[name] is None, name
    provenance = applied.circuit.netclasses[1].provenance
    assert provenance is not None and provenance.locator == "/net_settings/classes/1"
    assert provenance.evidence == EVIDENCE and EVIDENCE.level is Level.INFERRED
    assert applied.circuit.netclasses[1].clearance == 2_000_000


def test_wildcard_pattern() -> None:
    data = project(10)
    data["net_settings"]["netclass_patterns"] = [{"netclass": "HV", "pattern": "SW?_*"}]
    applied = apply_project(design({}, {"SW1_A": None, "SW10": None}), read_project(text(data)))
    by_name = {n.name: n.netclass_id for n in applied.circuit.nets}
    assert by_name["SW1_A"] == derived_id("cls", "kicad", "netclass:HV") and by_name["SW10"] is None


def test_patterns_read_as_wildcards_and_regular_expressions() -> None:
    cases = [("D[0]", "D0"), ("D[0]", "D[0]"), ("net*", "ne"), ("+3V3", "+3V3"), ("SIG1", "SIG10")]
    assert [pattern_matches(p, n) for p, n in cases] == [True, True, True, True, False]
    assert pattern_matches("IN+", "INN") and pattern_matches("Net-(R1-Pad1)", "Net-R1-Pad1")
    assert not pattern_matches("sig1", "SIG1")


def test_two_classes_for_one_net() -> None:
    data = project(10)
    classes = data["net_settings"]["classes"]
    pwr = dict(classes[1])
    pwr["name"] = "PWR"
    classes.append(pwr)
    classes[1]["priority"], classes[2]["priority"] = JsonNumber("0"), JsonNumber("1")
    data["net_settings"]["netclass_patterns"] = [
        {"netclass": "HV", "pattern": "+3V3"},
        {"netclass": "PWR", "pattern": "+*"},
    ]
    nets = design({}, {"+3V3": None})
    found: list[Issue] = []
    applied = apply_project(nets, read_project(text(data)), issues=found)
    collect(found)
    assert applied.circuit.nets[0].netclass_id == derived_id("cls", "kicad", "netclass:HV")
    (warning,) = [i for i in found if i.code == "kicad.project.multiple-classes"]
    assert "HV" in warning.message and "PWR" in warning.message
    classes[1]["priority"], classes[2]["priority"] = JsonNumber("1"), JsonNumber("0")
    swapped = apply_project(nets, read_project(text(data)))
    assert swapped.circuit.nets[0].netclass_id == derived_id("cls", "kicad", "netclass:PWR")


def test_assignments_unknown_and_unread_entries() -> None:
    data = project(10)
    data["net_settings"]["netclass_assignments"] = {"A": "HV", "B": ["Nope"], "C": JsonNumber("3")}
    data["net_settings"]["netclass_patterns"] = [{"netclass": "Ghost", "pattern": "X"}, {"pattern": "Y"}]
    found: list[Issue] = []
    applied = apply_project(
        design({}, {"A": None, "X": None}), read_project(text(data), issues=found), issues=found
    )
    collect(found)
    by_name = {n.name: n.netclass_id for n in applied.circuit.nets}
    assert by_name["A"] == derived_id("cls", "kicad", "netclass:HV") and by_name["X"] is None
    assert sorted(i.code for i in found) == [
        "kicad.project.unknown-class",
        "kicad.project.unknown-class",
        "kicad.project.unread-entry",
        "kicad.project.unread-entry",
    ]


def test_inexact_value() -> None:
    data = project(10)
    data["net_settings"]["classes"][1]["clearance"] = JsonNumber("0.0000001")
    found: list[Issue] = []
    info = read_project(text(data), issues=found)
    collect(found)
    assert info.classes[1].clearance is None and [i.code for i in found] == ["kicad.project.inexact-value"]


def test_floors() -> None:
    info = read_project(text(project(10)))
    assert info.floors == {
        "clearance": 0,
        "track_width": 200_000,
        "via_diameter": 500_000,
        "via_drill": 300_000,
    }


def test_minimal_canary_project() -> None:
    info = read_project("{}")
    assert info.status is VersionStatus.SUPPORTED and (info.meta_version, info.net_settings_version) == (
        None,
        None,
    )
    assert info.major is None and info.classes == ()


def test_future_project_is_read_only() -> None:
    found: list[Issue] = []
    info = read_project('{"meta": {"version": 4}}', issues=found)
    collect(found)
    assert info.status is VersionStatus.FUTURE and [i.code for i in found] == ["kicad.version.future"]


def test_older_project_readable() -> None:
    info = read_project('{"meta": {"version": 2}}')
    assert info.status is VersionStatus.SUPPORTED and info.major is None


@pytest.mark.parametrize(
    ("source", "locator"),
    [
        ('{"meta": 1}', "/meta"),
        ('{"net_settings": {"classes": {}}}', "/net_settings/classes"),
        ('{"net_settings": {"classes": [1]}}', "/net_settings/classes/0"),
        ('{"net_settings": {"classes": [{"clearance": 1}]}}', "/net_settings/classes/0"),
        ('{"meta": {"version": 3.5}}', "/meta/version"),
    ],
)
def test_format_errors(source: str, locator: str) -> None:
    with pytest.raises(FormatError) as caught:
        read_project(source)
    assert caught.value.locator == locator


def test_codes() -> None:
    assert ISSUE_CODES is LEAF_CODES and len(ISSUE_CODES) == 14  # c0010 11, c0012 3
    assert all(ISSUE_CODE.match(code) for code in ISSUE_CODES)
    assert all(c in ISSUE_CODES or c.startswith("kicad.version.") for c in CODES)
    literals: set[str] = set()
    for path in SRC.glob("*.py"):
        literals |= set(re.findall(r'"(kicad\.project\.[a-z0-9-]+)"', path.read_text(encoding="utf-8")))
    assert literals == set(ISSUE_CODES)
