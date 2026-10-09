# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The exclusion bench and the severity-key benches (change c0114; capability kicad-oracle, "Exclusion
facts are probed" and "Severity keys are probed"; ``H-K-DRC-EXCL``, ``H-K-PRO-SEV-KEYS``).

One board of ``_rulebench.Builder``, written for the running major: two 0.25 mm tracks 0.1 mm apart under
KiCad's ``Default`` class, and a lone via at a position that is no round number of micrometres, so that a
marker position moved by 1 nm is another position. The project files differ only in ``drc_exclusions`` or
in ``rule_severities``; each run is ``pcb drc`` on a copy, cached per project text. Every exclusion key is
built from the report of a first run with a ``{}`` project: the type, the first item's position in nm, and
the item uuids in report order, the nil uuid for a missing second item.
"""

from __future__ import annotations

import dataclasses
import json
import tempfile
from collections.abc import Callable, Mapping, Sequence
from functools import cache
from pathlib import Path

import _rulebench as rb

from fenolite.backends.base import NIL_UUID, DrcReport, DrcViolation
from fenolite.backends.kicad.cli import DrcRun, KicadCli
from fenolite.backends.kicad.pcb import write_board
from fenolite.backends.kicad.pro import SEVERITY_KEYS
from fenolite.backends.kicad.triad import write_triad
from fenolite.core.coords import Point
from fenolite.dsl import Design, to_model
from fenolite.model.design import Design as ModelDesign

Probes = dict[str, tuple[Callable[[], str], tuple[int, ...]]]
NAME = "bench"
BOARD, PROJECT = f"{NAME}.kicad_pcb", f"{NAME}.kicad_pro"
VIA_AT = Point(30_123_456, 20_654_321)
VIA_TYPE, CLEARANCE = "via_dangling", "clearance"
OTHER_UUID = "0c0114aa-0000-4000-8000-00000000c114"
"""A uuid that names no item of the bench."""
COMMENT = "test point"
BENCH_TYPES = ("clearance", "shorting_items", "solder_mask_bridge", "track_dangling", "via_dangling")
"""The checks that the severity bench of major 9 fires under a ``{}`` project; ``lib_footprint_issues`` joins
them when a footprint is on the board."""
UNKNOWN_KEYS = ("overlapping_pads", "fenolite_not_a_check")
"""Two keys outside the template of 10: one that most 9.0.9.1 demo projects hold, and an invented one."""


def runner() -> KicadCli:
    from _probes import runner as probes_runner  # _probes imports this module

    return probes_runner()


def running_target() -> int:
    return runner().major()


@cache
def bench() -> rb.Bench:
    made = rb.Builder()
    made.pair("close", "CLOSE_A", "CLOSE_B", gap=100_000)
    made.via("via", "TP", VIA_AT)
    return made.build()


@cache
def severity_bench() -> rb.Bench:
    """The exclusion bench with two placed footprints whose pads, on nets of their own, overlap by 0.1 mm:
    a short, a mask bridge and a library finding, so that the checks of ``BENCH_TYPES`` and
    ``lib_footprint_issues`` all have an entry under a ``{}`` project."""
    made = rb.Builder()
    made.pair("close", "CLOSE_A", "CLOSE_B", gap=100_000)
    made.via("via", "TP", VIA_AT)
    made.parts("pads", ("R1", "R2"), gap=-100_000, target=running_target())
    return made.build()


def project_text(
    *, exclusions: Sequence[object] | None = None, severities: Mapping[str, str] | None = None
) -> str:
    settings: dict[str, object] = {}
    if exclusions is not None:
        settings["drc_exclusions"] = list(exclusions)
    if severities is not None:
        settings["rule_severities"] = dict(severities)
    return json.dumps({"board": {"design_settings": settings}} if settings else {}, indent=2) + "\n"


@cache
def _board_text(which: str) -> str:
    design = (severity_bench() if which == "severity" else bench()).design
    return write_board(design, target=running_target()).text


@cache
def drc(project: str, which: str = "exclusion") -> DrcRun:
    """``pcb drc`` on the bench with ``project`` as its project file (one run per text)."""
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        (folder / BOARD).write_text(_board_text(which), encoding="utf-8")
        (folder / PROJECT).write_text(project, encoding="utf-8")
        return runner().drc(folder / BOARD, files={PROJECT: folder / PROJECT})


def report(project: str, which: str = "exclusion") -> DrcReport:
    found = drc(project, which).report
    assert found is not None, "pcb drc wrote no report"
    return found


def first() -> DrcReport:
    return report(project_text())


def _naming(found: DrcReport, kind: str, uuids: Sequence[str]) -> tuple[DrcViolation, ...]:
    wanted = set(uuids)
    return tuple(v for v in found.of_type(kind) if {item.uuid for item in v.items} & wanted)


def via_entries(found: DrcReport) -> tuple[DrcViolation, ...]:
    return _naming(found, VIA_TYPE, bench().uuids("via"))


def clearance_entries(found: DrcReport) -> tuple[DrcViolation, ...]:
    return rb.violations_between(found, bench().uuids("close_a"), bench().uuids("close_b"), CLEARANCE)


def key(entry: DrcViolation, *, dx: int = 0, uuids: Sequence[str] | None = None) -> str:
    """The stored key of ``entry``: ``<type>|<x>|<y>|<uuid>|<uuid>`` from its first item's position."""
    own = [item.uuid for item in entry.items]
    first_uuid, second_uuid = (uuids if uuids is not None else [*own, NIL_UUID, NIL_UUID])[:2]
    at = entry.items[0].position
    return f"{entry.type}|{at.x + dx}|{at.y}|{first_uuid}|{second_uuid}"


def via_key(**kwargs: object) -> str:
    (entry,) = via_entries(first())
    return key(entry, **kwargs)  # type: ignore[arg-type]


def clearance_key(*, swapped: bool = False) -> str:
    (entry,) = clearance_entries(first())
    uuids = [item.uuid for item in entry.items]
    return key(entry, uuids=uuids[::-1] if swapped else uuids)


CASES: dict[str, Callable[[], str]] = {
    "pair": lambda: project_text(exclusions=[[via_key(), COMMENT]]),
    "plain": lambda: project_text(exclusions=[via_key()]),
    "moved": lambda: project_text(exclusions=[[via_key(dx=1), COMMENT]]),
    "stale": lambda: project_text(exclusions=[[via_key(uuids=[OTHER_UUID, NIL_UUID]), COMMENT]]),
    "first-position": lambda: project_text(exclusions=[[clearance_key(), "pair"]]),
    "reversed": lambda: project_text(exclusions=[[clearance_key(swapped=True), "pair"]]),
}


def excluded(case: str) -> tuple[DrcViolation, ...]:
    """The via's entries (the clearance pair's for the two clearance cases) of the run of ``case``."""
    found = report(CASES[case]())
    return clearance_entries(found) if case in ("first-position", "reversed") else via_entries(found)


def outcome(case: str) -> str:
    """``equal`` when the run of ``case`` gives what "Exclusion facts are probed" lists for it."""
    (before,) = clearance_entries(first()) if case in ("first-position", "reversed") else via_entries(first())
    entries = excluded(case)
    if len(entries) != 1:
        return "different"
    (entry,) = entries
    kept = entry.severity == before.severity and not before.excluded
    if case == "pair":
        ok = entry.excluded and kept and entry.comment == COMMENT
    elif case == "plain":
        ok = entry.excluded and kept and entry.comment == ""
    elif case == "moved":
        ok = not entry.excluded and kept
    elif case == "stale":
        named = [v for v in _entries(report(CASES[case]())) if OTHER_UUID in {i.uuid for i in v.items}]
        ok = not entry.excluded and kept and not named
    elif case == "first-position":
        ok = entry.excluded and kept
    else:
        ok = not entry.excluded and kept
    return "equal" if ok else "different"


def _entries(found: DrcReport) -> tuple[DrcViolation, ...]:
    return (*found.violations, *found.unconnected_items, *found.schematic_parity)


def project_unchanged() -> str:
    """``equal`` when no run of the bench created or changed the project file of its copy."""
    runs = [drc(project_text()), *(drc(make()) for make in CASES.values())]
    return "equal" if all(PROJECT not in run.run.outputs for run in runs) else "different"


# --- severity keys --------------------------------------------------------------------------------


def all_ignored(target: int, *more: str) -> str:
    return project_text(severities=dict.fromkeys((*sorted(SEVERITY_KEYS[target]), *more), "ignore"))


def ignored_checks(project: str) -> tuple[str, ...]:
    """The ``key`` of each member of the report's ``ignored_checks`` (absent on 9.0.9: ``()``)."""
    return report(project, "severity").ignored_checks


def keys_ten() -> str:
    """``equal`` when 10.0.6 lists exactly ``SEVERITY_KEYS[10]`` as ignored and no entry remains."""
    project = all_ignored(10, *UNKNOWN_KEYS)
    left = _entries(report(project, "severity"))
    return "equal" if set(ignored_checks(project)) == set(SEVERITY_KEYS[10]) and not left else "different"


def bench_types(found: DrcReport) -> set[str]:
    return {v.type for v in _entries(found)} & {*BENCH_TYPES, "lib_footprint_issues"}


def keys_nine() -> str:
    """``absent`` when the bench, whose control run fires every type of ``BENCH_TYPES`` and
    ``lib_footprint_issues``, has no entry of them once every key of ``SEVERITY_KEYS[9]`` is ``ignore``;
    ``inconclusive`` when the control does not fire them all."""
    control = bench_types(report(project_text(), "severity"))
    if control != {*BENCH_TYPES, "lib_footprint_issues"}:
        return "inconclusive"
    return "absent" if not bench_types(report(all_ignored(9), "severity")) else "present"


# --- a script's severity ---------------------------------------------------------------------------


def _with_script_severity(design: ModelDesign) -> ModelDesign:
    script = Design("sev")
    script.rules.severity("kicad.drc.via-dangling", "error")
    rules = to_model(script).rules
    assert rules is not None and design.rules is not None
    return dataclasses.replace(design, rules=dataclasses.replace(design.rules, severities=rules.severities))


@cache
def triad_report(with_severity: bool) -> DrcReport:
    design = bench().design
    if with_severity:
        design = _with_script_severity(design)
    files = write_triad(design, name=NAME, target=running_target())
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        for name, text in files.items():
            (folder / name).write_text(text, encoding="utf-8")
        extra = {name: folder / name for name in files if name != BOARD}
        found = runner().drc(folder / BOARD, files=extra).report
    assert found is not None
    return found


def script_severity() -> str:
    """``equal`` when the via's ``via_dangling`` entry is an ``error`` in the project written from a design
    with ``design.rules.severity("kicad.drc.via-dangling", "error")`` and a ``warning`` without the call."""
    with_call = [entry.severity for entry in via_entries(triad_report(True))]
    without = [entry.severity for entry in via_entries(triad_report(False))]
    return "equal" if with_call == ["error"] and without == ["warning"] else "different"


def exclusion_probes() -> Probes:
    both = (9, 10)
    probes: Probes = {f"drc-excl-{case}": (lambda case=case: outcome(case), both) for case in CASES}
    probes["drc-excl-project-unchanged"] = (project_unchanged, both)
    probes["pro-sev-keys-10"] = (keys_ten, (10,))
    probes["pro-sev-keys-9-bench"] = (keys_nine, (9,))
    probes["pro-sev-script"] = (script_severity, both)
    return probes


__all__ = [
    "BENCH_TYPES",
    "BOARD",
    "CASES",
    "COMMENT",
    "PROJECT",
    "UNKNOWN_KEYS",
    "all_ignored",
    "bench",
    "bench_types",
    "clearance_entries",
    "clearance_key",
    "drc",
    "excluded",
    "exclusion_probes",
    "first",
    "ignored_checks",
    "key",
    "keys_nine",
    "keys_ten",
    "outcome",
    "project_text",
    "project_unchanged",
    "report",
    "script_severity",
    "severity_bench",
    "triad_report",
    "via_entries",
    "via_key",
]
