# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Probe outcomes per ``kicad-cli`` version (c0017 Decision 20; capability kicad-oracle, "Probe results
per kicad-cli version").

``PROBES`` maps a probe id to its function and the majors it runs on. ``run(probe_id)`` runs a probe
once per session; oracle tests assert on its outcome, and ``tests/kicad/test_probe_results.py``
compares every outcome of the running major with ``docs/evidence/kicad/probes/<version>.json``
(``FENOLITE_PROBES_WRITE=1`` writes that file instead).
"""

from __future__ import annotations

import dataclasses
import json
import os
import re
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import _acceptance
import _arccases
import _asmcases
import _bench
import _benches
import _bodycases
import _buildcases
import _checkcases
import _copperparity
import _creepbench
import _doccases
import _drccases
import _erccases
import _exportcases
import _fieldbench
import _fieldprobe
import _fillcases
import _followcases
import _fpwrite
import _framecases
import _gencases
import _hiercases
import _kindcases
import _layercases
import _layertables
import _lenscases
import _libtables
import _limitsbench
import _lockbench
import _mincases
import _netcases
import _netlistcases
import _offsetbench
import _openbench
import _paircases
import _paritycases
import _pcbxcases
import _placecases
import _procases
import _renamecases
import _routetriangle
import _rta3oracle
import _rulecases
import _schcases
import _sheetcases
import _stackbench
import _triad
import _vendorcases
import _zonebench
import pytest
from _boards import FIXTURE, created_board
from _resources import kicad_cli

from fenolite.backends.kicad import drc as drcmod
from fenolite.backends.kicad.cli import DRC_REPORT, KicadCli
from fenolite.backends.kicad.embed import place_footprint
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.mod import read_footprint
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.core.coords import Point
from fenolite.model.circuit import Circuit, Component
from fenolite.model.design import Design

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "docs" / "evidence" / "kicad" / "probes"
DIMENSION = ROOT / "tests" / "data" / "kicad" / "board" / "dimension.kicad_pcb"
WRITE_VARIABLE = "FENOLITE_PROBES_WRITE"
OUTCOMES = frozenset({"load", "reject", "present", "absent", "equal", "different", "inconclusive", "timeout"})
GENERATOR_VERSIONS = {"absent": None, "9.0": "9.0", "10.0": "10.0", "fenolite-x": "fenolite-x"}


@dataclass(frozen=True)
class Probe:
    function: Callable[[], str]
    majors: tuple[int, ...]


@cache
def runner() -> KicadCli:
    path = kicad_cli()
    assert path is not None  # the needs_kicad marker skips before this is reached
    return KicadCli(Path(path), timeout=600)


@cache
def version() -> str:
    """The first line of ``kicad-cli version``, restricted to ``[0-9A-Za-z.+-]``."""
    return re.sub(r"[^0-9A-Za-z.+-]", "", runner().version())


def major() -> int:
    return runner().major()


# -- loads


def load(text: str) -> str:
    """``load`` when ``pcb export svg`` exits 0 with its output, ``reject`` otherwise."""
    with tempfile.TemporaryDirectory() as tmp:
        board = Path(tmp) / "board.kicad_pcb"
        board.write_text(text, encoding="utf-8")
        board.with_suffix(".kicad_pro").write_text(_triad.PROJECT, encoding="utf-8")
        args = ["pcb", "export", "svg", "-l", "Edge.Cuts", "--mode-single", "-o", "out.svg", board.name]
        run = runner().run(args, files={board.name: board, **_triad.project(board)})
    if run.outcome == "timeout":
        return "timeout"
    return "load" if run.returncode == 0 and "out.svg" in run.outputs else "reject"


@cache
def triad_text(target: int) -> str:
    return write_board(_triad.triad(target), target=target).text


def genver(target: int, value: str | None) -> str:
    """The triad text for ``target`` with ``generator_version`` set to ``value`` (removed for None)."""
    text = triad_text(target)
    line = f'\t(generator_version "{target}.0")\n'
    assert line in text
    return text.replace(line, "" if value is None else f'\t(generator_version "{value}")\n')


def lossy_design() -> Design:
    """``Mini_R_0603`` of ``Mini.pretty`` (10.0) placed as ``R1`` on a created board."""
    defn = read_footprint(_triad.LIBS / "Mini.pretty" / "Mini_R_0603.kicad_mod", library="Mini")
    r1 = Component(id="cmp_00000000-0000-4000-8000-000000000001", ref="R1", value="1k")
    placed = place_footprint(defn, component=r1, at=Point(10_000_000, 10_000_000), key="R1")
    design = Design.new("lossy", seed=0)
    assert design.board is not None
    board = dataclasses.replace(design.board, layers=created_layers(2), footprints=(placed,))
    return dataclasses.replace(design, circuit=Circuit(components=(r1,)), board=board)


def lossy_text() -> str:
    """The lossy design written for target 9 with ``allow_lossy``."""
    return write_board(lossy_design(), target=9, allow_lossy=True).text


def dimension_text(target: int) -> str:
    return write_board(read_board(DIMENSION), target=target).text


# -- DRC


@cache
def drc_case(name: str) -> tuple[str, drcmod.DrcReport | None, bytes | None]:
    """``(outcome, report, raw report)`` of one bench board; the outcome is ``timeout``, ``reject`` (no
    report) or ``load``."""
    target = major()
    if name == "bench":
        design, table = _bench.bench(target), True
    elif name == "missing-table":
        design, table = _bench.control(target), False
    elif name == "exact":
        design, table = _bench.control(target), True
    elif name == "triad":
        design, table = _triad.triad(target), False
    else:
        design, table = _bench.control(target, _bench.CONTROLS[name]), True
    with tempfile.TemporaryDirectory() as tmp:
        board, files = _bench.write(design, target, Path(tmp), table=table)
        run = runner().drc(board, files=files)
    if run.run.outcome == "timeout":
        return "timeout", None, None
    if run.report is None:
        return "reject", None, None
    return "load", run.report, run.run.outputs.get(DRC_REPORT)


def libdrc(name: str) -> str:
    """Library parity outcomes; every one is ``inconclusive`` when the missing-table control is silent."""
    if name != "missing-table" and libdrc("missing-table") != "present":
        return "inconclusive"
    outcome, report, _ = drc_case(name)
    if report is None:
        return outcome
    if name == "missing-table":
        return "present" if report.of_type(drcmod.LIB_FOOTPRINT_ISSUES) else "inconclusive"
    found = len(report.of_type(drcmod.LIB_FOOTPRINT_MISMATCH))
    if name in ("bench", "exact"):
        return "absent" if found == 0 else "present"
    return {0: "absent", 1: "present"}.get(found, "different")


def ignored_checks() -> str:
    outcome, _, raw = drc_case("triad")
    if raw is None:
        return outcome
    return "present" if "ignored_checks" in json.loads(raw) else "absent"


def _probes() -> dict[str, Probe]:
    both = (9, 10)
    probes: dict[str, Probe] = {
        "pcb-write-triad-9": Probe(lambda: load(triad_text(9)), both),
        "pcb-write-triad-10": Probe(lambda: load(triad_text(10)), both),
        "pcb-write-heads-9": Probe(lambda: load(write_board(created_board(4), target=9).text), both),
        "pcb-write-heads-10": Probe(lambda: load(write_board(created_board(4), target=10).text), both),
        "pcb-write-two-layer-9": Probe(lambda: load(write_board(read_board(FIXTURE), target=9).text), both),
        "pcb-write-two-layer-10": Probe(lambda: load(write_board(read_board(FIXTURE), target=10).text), both),
        "pcb-write-lossy-9": Probe(lambda: load(lossy_text()), both),
        "pcb-write-dimension-9": Probe(lambda: load(dimension_text(9)), both),
        "pcb-write-dimension-10": Probe(lambda: load(dimension_text(10)), both),
        "pcb-drc-ignored-checks": Probe(ignored_checks, both),
    }
    for label, value in GENERATOR_VERSIONS.items():
        probes[f"pcb-genver-9-{label}"] = Probe(lambda value=value: load(genver(9, value)), both)
        probes[f"pcb-genver-10-{label}"] = Probe(lambda value=value: load(genver(10, value)), (10,))
    for name in ("bench", "exact", "missing-table", *_bench.CONTROLS):
        probes[f"pcb-libdrc-{name}"] = Probe(lambda name=name: libdrc(name), both)
    probes.update(fp_write_probes())
    # the level-5 triangle on the routed sample (c0089); `pcb import` exists from 10.0 only
    probes["equiv-l5-triangle"] = Probe(_routetriangle.outcome, (10,))
    # KiCad's importer on the rewrite of an own PCB document (c0090, RT-A3)
    probes["altium-rta3-kicad"] = Probe(_rta3oracle.outcome, (10,))
    for pid, (function, majors) in {
        **_rulecases.dru_probes(),
        **_procases.pro_probes(),
        **_buildcases.build_probes(),
        **_mincases.min_probes(),
        **_vendorcases.vendor_probes(),
        **_lenscases.lens_probes(),
        **_renamecases.rename_probes(),
        **_followcases.followup_probes(),
        **_exportcases.export_probes(),
        **_doccases.document_probes(),  # change c0116
        **_framecases.frame_probes(),
        **_fieldprobe.field_probes(),
        **_fieldbench.bench_probes(),
        **_zonebench.zone_probes(),
        **_benches.copper_probes(),
        **_copperparity.parity_probes(),
        **_fillcases.fill_probes(),
        **_placecases.place_probes(),
        **_creepbench.creepage_probes(),
        **_offsetbench.offset_probes(),
        **_arccases.arc_probes(),
        **_kindcases.kind_probes(),
        **_paircases.pair_probes(),
        **_openbench.open_probes(),
        **_lockbench.lock_probes(),
    }.items():
        probes[pid] = Probe(function, majors)  # type: ignore[arg-type]
    for pid, (function, majors) in _sheetcases.wks_probes().items():
        probes[pid] = Probe(function, majors)
    for pid, (function, majors) in _acceptance.accept_probes().items():
        probes[pid] = Probe(function, majors)  # type: ignore[arg-type]
    for pid, (function, majors) in _checkcases.check_probes().items():
        probes[pid] = Probe(function, majors)
    probes.update(libtable_probes())
    for pid, (function, majors) in _drccases.drc_probes().items():
        probes[pid] = Probe(function, majors)
    for pid, (function, majors) in _netcases.net_probes().items():
        probes[pid] = Probe(function, majors)
    for pid, (function, majors) in _asmcases.assembly_probes().items():
        probes[pid] = Probe(function, majors)
    for pid, (function, majors) in _schcases.sch_probes().items():
        probes[pid] = Probe(function, majors)
    for pid, (function, majors) in _gencases.gen_probes().items():
        probes[pid] = Probe(function, majors)
    for pid, (function, majors) in _netlistcases.netlist_probes().items():
        probes[pid] = Probe(function, majors)
    for pid, (function, majors) in _erccases.erc_probes().items():
        probes[pid] = Probe(function, majors)
    for pid, (function, majors) in _paritycases.parity_probes().items():
        probes[pid] = Probe(function, majors)
    for pid, (function, majors) in _hiercases.hier_probes().items():
        probes[pid] = Probe(function, majors)
    for pid, (function, majors) in _pcbxcases.pcbx_probes().items():  # change c0085
        probes[pid] = Probe(function, majors)
    for pid, (function, majors) in _bodycases.body_probes().items():  # change c0121
        probes[pid] = Probe(function, majors)
    for pid, (function, majors) in _limitsbench.limit_probes().items():  # change c0141
        probes[pid] = Probe(function, majors)
    for pid, (function, majors) in {  # change c0100
        **_layertables.table_probes(),
        **_layercases.layer_probes(),
    }.items():
        probes[pid] = Probe(function, majors)  # type: ignore[arg-type]
    for pid, (function, majors) in _stackbench.stackup_probes(runner).items():  # change c0101
        probes[pid] = Probe(function, majors)
    return probes


# -- written footprint libraries (c0018)


def _loaded(folder: str, target: int, allow_lossy: bool = False) -> str:
    return "load" if _fpwrite.mini(runner(), folder, target, allow_lossy).loaded else "reject"


def _reread(folder: str, target: int) -> str:
    result = _fpwrite.mini(runner(), folder, target)
    return "equal" if _fpwrite.equal_after_upgrade(result, _fpwrite.definitions(folder)) else "different"


def libtable_probes() -> dict[str, Probe]:
    """The ``pcb-libtable-*`` probes (c0021): every one is ``inconclusive`` when the missing-table control is
    silent, because a library check that reports nothing proves nothing (``H-K-LIB-DRC``)."""

    def guarded(function: Callable[[], str]) -> Callable[[], str]:
        return lambda: function() if libdrc("missing-table") == "present" else "inconclusive"

    return {pid: Probe(guarded(function), (9, 10)) for pid, function in _libtables.probes(runner).items()}


def fp_write_probes() -> dict[str, Probe]:
    both = (9, 10)
    return {
        "fp-write-mini-10": Probe(lambda: _loaded("Mini.pretty", 10), (10,)),
        "fp-write-mini-10-reread": Probe(lambda: _reread("Mini.pretty", 10), (10,)),
        "fp-write-mini-v9-9": Probe(lambda: _loaded("Mini_v9.pretty", 9), both),
        "fp-write-mini-v9-9-reread": Probe(lambda: _reread("Mini_v9.pretty", 9), both),
        "fp-write-mini-lossy-9": Probe(lambda: _loaded("Mini.pretty", 9, True), both),
        "fp-write-escapes-9": Probe(
            lambda: "equal" if _fpwrite.escapes_equal(runner()) else "different", both
        ),
    }


PROBES: dict[str, Probe] = _probes()


@cache
def run(probe_id: str) -> str:
    """The outcome of ``probe_id`` on the running ``kicad-cli`` (memoised per session)."""
    outcome = PROBES[probe_id].function()
    if outcome not in OUTCOMES:
        raise ValueError(f"probe {probe_id} returned {outcome!r}, not one of {sorted(OUTCOMES)}")
    return outcome


def outcomes(running: int) -> dict[str, str]:
    """Every probe of the running major and its outcome."""
    return {pid: run(pid) for pid, probe in sorted(PROBES.items()) if running in probe.majors}


def results_path(name: str, folder: Path = RESULTS) -> Path:
    return folder / f"{name}.json"


def verify(name: str, found: Mapping[str, str], folder: Path = RESULTS) -> None:
    """Compare ``found`` with the results file of version ``name``, or write it with
    ``FENOLITE_PROBES_WRITE=1``; fail on drift or on a missing file."""
    path = results_path(name, folder)
    if os.environ.get(WRITE_VARIABLE) == "1":
        folder.mkdir(parents=True, exist_ok=True)
        data = {"version": name, "probes": dict(sorted(found.items()))}
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return
    if not path.is_file():
        pytest.fail(
            f"no probe results for kicad-cli {name}: "
            f"run the probes with {WRITE_VARIABLE}=1 and commit {path.name}",
            pytrace=False,
        )
    recorded: dict[str, str] = json.loads(path.read_text(encoding="utf-8"))["probes"]
    drift = [
        f"{pid}: recorded {recorded.get(pid)!r}, now {found.get(pid)!r}"
        for pid in sorted(set(recorded) | set(found))
        if recorded.get(pid) != found.get(pid)
    ]
    if drift:
        pytest.fail(f"probe outcomes drifted for kicad-cli {name}:\n" + "\n".join(drift), pytrace=False)


__all__ = ["OUTCOMES", "PROBES", "Probe", "outcomes", "run", "verify", "version"]
