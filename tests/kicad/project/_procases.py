# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Net-class oracle runs (c0010 Decision 14): each case builds the bench set with ``write_triad``,
changes it as the case says, runs ``pcb drc`` once per session through ``KicadCli`` on a temporary
copy, and is judged by ``_netclass_bench.judge``. The ``pro-*`` probes of ``_probes.PROBES`` record the
outcomes."""

from __future__ import annotations

import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import _netclass_bench as nb

from fenolite.backends.base import DrcReport
from fenolite.backends.kicad import _json
from fenolite.backends.kicad._json import JsonNumber
from fenolite.backends.kicad.cli import CliRun, KicadCli
from fenolite.backends.kicad.triad import write_triad
from fenolite.model.design import Design

PROJECT = "bench.kicad_pro"
PRL = "bench.kicad_prl"


def runner() -> KicadCli:
    from _probes import runner as probes_runner  # _probes imports this module

    return probes_runner()


@dataclass(frozen=True)
class Run:
    design: Design
    report: DrcReport | None
    run: CliRun


def _files(design: Design, target: int) -> dict[str, str]:
    return write_triad(design, name="bench", target=target)


def drc(design: Design, files: Mapping[str, str], *, project: bool = True) -> Run:
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        for name, text in files.items():
            (folder / name).write_text(text, encoding="utf-8")
        extra = {n: folder / n for n in files if n != "bench.kicad_pcb" and (project or n != PROJECT)}
        result = runner().drc(folder / "bench.kicad_pcb", files=extra)
    return Run(design, result.report, result.run)


def _edit(files: Mapping[str, str], change: object) -> dict[str, str]:
    data = _json.loads(files[PROJECT])
    change(data)  # type: ignore[operator]
    return {**files, PROJECT: _json.dumps(data)}


@cache
def full(target: int) -> Run:
    design = nb.bench_design(target=target)
    return drc(design, _files(design, target))


@cache
def case(name: str, target: int) -> Run:
    """The run behind one case (``decoys`` shares the ``patterns`` run, ``anchor`` the ``full`` run)."""
    design = nb.bench_design(target=target)
    files = _files(design, target)
    if name in ("full", "anchor", "minimal"):
        if name != "minimal":
            return full(target)
        return drc(
            design, _edit(files, lambda d: [d.pop(k) for k in list(d) if k not in ("meta", "net_settings")])
        )
    if name == "noproject":
        return drc(design, files, project=False)
    if name == "noclass":
        plain = nb.bench_design(target=target, hv_clearance=None)
        return drc(plain, _files(plain, target))
    if name in ("patterns", "decoys"):
        entries = [{"netclass": "HV", "pattern": p} for p in nb.RAW_PATTERNS]
        return drc(design, _edit(files, lambda d: d["net_settings"]["netclass_patterns"].extend(entries)))
    if name in ("floor-template", "floor-raised"):
        low = nb.bench_design(target=target, hv_clearance=500_000)
        low_files = _files(low, target)
        if name == "floor-template":
            return drc(low, low_files)

        def raised(data: dict[str, object]) -> None:
            data["board"]["design_settings"]["rules"]["min_clearance"] = JsonNumber("1.5")  # type: ignore[index]

        return drc(low, _edit(low_files, raised))
    raise KeyError(name)


def outcome(name: str, target: int) -> str:
    result = case(name, target)
    reference = full(target).report if name == "minimal" else None
    return nb.judge(result.report, case=name, design=result.design, reference=reference)


# -- project files under kicad-cli runs


@cache
def file_runs() -> dict[str, CliRun]:
    """``pcb drc`` and ``pcb export svg`` on the target-9 set, each on its own copy."""
    design = nb.bench_design(target=9)
    files = _files(design, 9)
    out: dict[str, CliRun] = {"drc": drc(design, files).run}
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        for name, text in files.items():
            (folder / name).write_text(text, encoding="utf-8")
        args = [
            "pcb",
            "export",
            "svg",
            "-l",
            "Edge.Cuts",
            "--mode-single",
            "-o",
            "out.svg",
            "bench.kicad_pcb",
        ]
        out["export"] = runner().run(args, files={n: folder / n for n in files})
    return out


def pro_probes() -> dict[str, tuple[object, tuple[int, ...]]]:
    """``probe id → (function, majors)``: target-10 cases on major 10, target-9 cases on both."""
    probes: dict[str, tuple[object, tuple[int, ...]]] = {}
    for target, majors in ((10, (10,)), (9, (9, 10))):
        for name in nb.CASES:
            probes[f"pro-{name}-t{target}"] = (lambda name=name, target=target: outcome(name, target), majors)
    for run_name in ("drc", "export"):
        probes[f"pro-file-{run_name}"] = (
            lambda run_name=run_name: "different" if PROJECT in file_runs()[run_name].outputs else "equal",
            (9, 10),
        )
        probes[f"pro-prl-{run_name}"] = (
            lambda run_name=run_name: "present" if PRL in file_runs()[run_name].outputs else "absent",
            (9, 10),
        )
    return probes


__all__ = ["PRL", "PROJECT", "Run", "case", "file_runs", "full", "outcome", "pro_probes"]
