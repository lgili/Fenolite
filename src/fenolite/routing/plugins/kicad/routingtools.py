# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCadRoutingTools adapter. The external router runs as a subprocess; its file is never adopted."""

from __future__ import annotations

import dataclasses
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from fenolite.backends.kicad.pcb import read_board, source_info, write_board
from fenolite.backends.kicad.projectset import project_set
from fenolite.backends.kicad.triad import write_triad
from fenolite.backends.kicad.versions import DEFAULT_TARGET
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence
from fenolite.model.board import Arc, Track, Via
from fenolite.routing.merge import RoutingError, apply
from fenolite.routing.protocol import RouterStatus, RoutingJob, RoutingResult

PINNED_TAG = "v0.22.1"
EVIDENCE = Evidence(oracle="KiCadRoutingTools v0.22.1", hypotheses=("H-K-KRT-CLI", "H-K-KRT-ROUTE"))


def _mm(value: int) -> str:
    sign = "-" if value < 0 else ""
    whole, fraction = divmod(abs(value), 1_000_000)
    suffix = f"{fraction:06d}".rstrip("0")
    return f"{sign}{whole}" + (f".{suffix}" if suffix else "")


def _line(value: object, folder: Path | None = None) -> str:
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    line = str(value or "").splitlines()[0].strip() if value else ""
    if folder:
        line = line.replace(str(folder), "<run-dir>")
    return re.sub(r"[\x00-\x1f\x7f]", " ", line)[:300] or "no diagnostic output"


def _copper(design: object) -> tuple[Track | Arc | Via, ...]:
    board = getattr(design, "board", None)
    return () if board is None else (*board.tracks, *board.arcs, *board.vias)


class KicadRoutingToolsRouter:
    """Run one tool process per net and lift only copper that did not exist in its input board."""

    name = "kicadroutingtools"
    description = "Routes nets with the external KiCadRoutingTools grid A* router."
    sends_data_offsite = False

    def __init__(
        self, path: str | Path | None = None, python: str | Path | None = None, timeout: float = 600
    ) -> None:
        raw_path = path or os.environ.get("FENOLITE_KRT")
        self.path = Path(raw_path).expanduser() if raw_path else None
        self.python = str(python or os.environ.get("FENOLITE_KRT_PYTHON") or shutil.which("python3") or "")
        self.timeout = timeout

    def available(self) -> RouterStatus:
        """Check required files and interpreter without launching the external tool."""
        if self.path is None:
            return RouterStatus(False, reason="set FENOLITE_KRT to the KiCadRoutingTools v0.22.1 checkout")
        route = self.path / "py_router" / "route.py"
        if not route.is_file():
            return RouterStatus(False, path=str(self.path), reason=f"missing {route}")
        if not (self.path / "rust_router" / "grid_router.so").is_file():
            return RouterStatus(
                False, path=str(self.path), reason="missing rust_router/grid_router.so; run build_router.py"
            )
        if not self.python or (not Path(self.python).is_file() and shutil.which(self.python) is None):
            return RouterStatus(
                False, path=str(self.path), reason="set FENOLITE_KRT_PYTHON to its Python interpreter"
            )
        version_file = self.path / "VERSION"
        version = version_file.read_text(encoding="utf-8").strip() if version_file.is_file() else "unknown"
        return RouterStatus(True, str(self.path), version)

    def route(self, job: RoutingJob) -> RoutingResult:
        """Route selected nets in a temporary project folder, returning proposed copper and issues."""
        status = self.available()
        if not status.available or self.path is None:
            return RoutingResult(
                unrouted=tuple(net.name for net in job.nets),
                issues=(Issue("route.tool-missing", "error", status.reason or "router unavailable"),),
                tool=self.name,
                tool_version=status.version or "",
                evidence=Evidence(),
            )
        issues: list[Issue] = []
        routed: list[str] = []
        unrouted: list[str] = []
        tracks: list[Track] = []
        arcs: list[Arc] = []
        vias: list[Via] = []
        logs: list[str] = []
        info = source_info(job.design)
        target = int(info.major) if info is not None and info.major is not None else DEFAULT_TARGET
        try:
            with tempfile.TemporaryDirectory(prefix="fenolite-route-") as name:
                folder = Path(name)
                stem = "fenolite-routing"
                for filename, contents in write_triad(job.design, name=stem, target=target).items():
                    (folder / filename).write_text(contents, encoding="utf-8")
                board_path = folder / f"{stem}.kicad_pcb"
                project_set(board_path)
                current = job.design
                for index, net in enumerate(job.nets):
                    board_text = write_board(current, target=target).text
                    board_path.write_text(board_text, encoding="utf-8")
                    baseline = read_board(board_text, file=board_path.name)
                    output_path = folder / f"routed-{index}.kicad_pcb"
                    args = [
                        self.python,
                        str(self.path / "py_router" / "route.py"),
                        str(board_path),
                        str(output_path),
                        "--nets",
                        net.name,
                        "--track-width",
                        _mm(net.width),
                        "--clearance",
                        _mm(net.clearance),
                        "--via-size",
                        _mm(net.via_diameter),
                        "--via-drill",
                        _mm(net.via_drill),
                    ]
                    for key, value in job.options.items():
                        args.extend((f"--{key}", value))
                    before = _copper(baseline)
                    old_ids = {item.id for item in before}
                    try:
                        run = subprocess.run(
                            args,
                            cwd=folder,
                            env={**os.environ, "LANG": "C", "LC_ALL": "C"},
                            capture_output=True,
                            text=True,
                            timeout=self.timeout,
                            check=False,
                        )
                    except subprocess.TimeoutExpired as exc:
                        issues.append(
                            Issue(
                                "route.tool-failed",
                                "error",
                                f"{net.name}: timeout: {_line(exc.stderr or exc.stdout, folder)}",
                                net.name,
                            )
                        )
                        unrouted.append(net.name)
                        continue
                    output_line = _line(run.stderr or run.stdout, folder)
                    if output_line != "no diagnostic output":
                        logs.append(output_line)
                    if run.returncode or not output_path.is_file():
                        why = f"exit {run.returncode}" if run.returncode else "output board missing"
                        issues.append(
                            Issue("route.tool-failed", "error", f"{net.name}: {why}: {output_line}", net.name)
                        )
                        unrouted.append(net.name)
                        continue
                    try:
                        result = read_board(output_path.read_text(encoding="utf-8"), file=output_path.name)
                    except Exception as exc:
                        issues.append(
                            Issue("route.tool-failed", "error", f"{net.name}: {_line(exc, folder)}", net.name)
                        )
                        unrouted.append(net.name)
                        continue
                    after = _copper(result)
                    new_copper = tuple(item for item in after if item.id not in old_ids)
                    absent = old_ids - {item.id for item in after}
                    issues.extend(
                        Issue(
                            "route.copper-removed",
                            "warning",
                            "router removed existing copper; preserved",
                            item_id,
                        )
                        for item_id in sorted(absent)
                    )
                    baseline_net_names = {entry.id: entry.name for entry in baseline.circuit.nets}
                    current_net_ids = {entry.name: entry.id for entry in current.circuit.nets}
                    lifted = tuple(
                        dataclasses.replace(
                            item,
                            net_id=current_net_ids.get(
                                baseline_net_names.get(item.net_id or "", ""), item.net_id
                            ),
                        )
                        for item in new_copper
                    )
                    delta = RoutingResult(
                        tracks=tuple(item for item in lifted if isinstance(item, Track)),
                        arcs=tuple(item for item in lifted if isinstance(item, Arc)),
                        vias=tuple(item for item in lifted if isinstance(item, Via)),
                    )
                    try:
                        current = apply(current, delta)
                    except RoutingError as exc:
                        issues.extend(exc.issues)
                        unrouted.append(net.name)
                        continue
                    net_copper = tuple(item for item in lifted if item.net_id == net.net_id)
                    if net_copper:
                        routed.append(net.name)
                        tracks.extend(item for item in net_copper if isinstance(item, Track))
                        arcs.extend(item for item in net_copper if isinstance(item, Arc))
                        vias.extend(item for item in net_copper if isinstance(item, Via))
                    else:
                        unrouted.append(net.name)
                if status.version != PINNED_TAG.removeprefix("v"):
                    issues.append(
                        Issue(
                            "route.tool-unpinned",
                            "warning",
                            f"expected {PINNED_TAG}, found {status.version}",
                            str(self.path),
                        )
                    )
                return RoutingResult(
                    tracks=tuple(tracks),
                    arcs=tuple(arcs),
                    vias=tuple(vias),
                    routed=tuple(routed),
                    unrouted=tuple(unrouted),
                    issues=tuple(issues),
                    tool=self.name,
                    tool_version=status.version,
                    log=tuple(logs[:20]),
                    evidence=dataclasses.replace(EVIDENCE, oracle=f"KiCadRoutingTools {status.version}"),
                )
        except Exception as exc:
            return RoutingResult(
                unrouted=tuple(net.name for net in job.nets),
                issues=(Issue("route.tool-failed", "error", _line(exc)),),
                tool=self.name,
                tool_version=status.version,
                log=(_line(exc),),
                evidence=Evidence(),
            )


__all__ = ["EVIDENCE", "PINNED_TAG", "KicadRoutingToolsRouter"]
