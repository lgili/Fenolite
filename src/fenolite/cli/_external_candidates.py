# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Explicit local adapter construction and scoped connectivity judge for c0368."""

from __future__ import annotations

import argparse
import hashlib
import shutil
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from fenolite.analysis.connectivity import connectivity
from fenolite.analysis.pour import PourCopper, rejoin
from fenolite.backends.base import BoardPad
from fenolite.cli.errors import CliError
from fenolite.model.design import Design
from fenolite.routing.budget import Budget
from fenolite.routing.external_candidates import SUPPORTED, Adapter
from fenolite.routing.plugins.kicad.routingtools import KicadRoutingToolsRouter
from fenolite.routing.plugins.specctra.freerouting import FreeroutingRouter
from fenolite.routing.protocol import JobSubject, RouterStatus


@dataclass(frozen=True, slots=True)
class Prepared:
    adapters: tuple[Adapter, ...] = ()
    paths: tuple[Path, ...] = ()
    hashes: tuple[str, ...] = ()

    def unchanged(self) -> bool:
        return self.hashes == tuple(_digest(path) for path in self.paths)


def _digest(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "missing"
    except OSError:
        return "unreadable"


def _cached(status: RouterStatus) -> Callable[[Budget], RouterStatus]:
    def ready(_budget: Budget) -> RouterStatus:
        return status

    return ready


def check(args: argparse.Namespace) -> None:
    requested: list[str] = getattr(args, "propose_with", [])
    if not requested:
        return
    if args.router != "octilinear" or not (args.propose or args.accept or args.reject):
        raise CliError(
            "FEN-2001", "--propose-with requires octilinear proposals or decisions", where="--propose-with"
        )
    if any(name not in SUPPORTED for name in requested):
        raise CliError(
            "FEN-2001", f"supported local candidate routers: {', '.join(SUPPORTED)}", where="--propose-with"
        )
    if len(set(requested)) > 1 and (args.router_path or args.router_python):
        raise CliError(
            "FEN-2001", "multiple --propose-with routers use their individual environment configuration"
        )
    if args.router_python and sorted(set(requested)) != ["kicadroutingtools"]:
        raise CliError("FEN-2001", "--router-python requires one --propose-with kicadroutingtools")
    if args.timeout is None:
        args.timeout = 900.0  # existing external adapters' default, for the whole proposal operation


def prepare(args: argparse.Namespace, budget: Budget) -> Prepared:
    adapters: list[Adapter] = []
    paths: list[Path] = []
    snapshots: dict[Path, str] = {}
    for name in sorted(set(getattr(args, "propose_with", []))):
        inputs: list[Path] = []
        if name == "kicadroutingtools":
            router = KicadRoutingToolsRouter(args.router_path, args.router_python)
            if router.path:
                inputs += [
                    router.path / "VERSION",
                    router.path / "py_router" / "route.py",
                    router.path / "rust_router" / "grid_router.so",
                ]
                inputs += [
                    p
                    for p in router.path.rglob("*")
                    if p.is_file()
                    and not any(part in {".git", ".venv", "__pycache__"} for part in p.parts)
                    and p.suffix in {".py", ".so", ".dll", ".pyd", ".dylib"}
                ]
            if executable := shutil.which(router.python):
                inputs.append(Path(executable))
            adapter = Adapter(name, "board", lambda _, router=router: router.available(), router.route)
        else:
            freerouter = FreeroutingRouter(args.router_path)
            if freerouter.jar is not None:
                inputs.append(freerouter.jar)
            if executable := shutil.which(freerouter.java):
                inputs.append(Path(executable))
            adapter = Adapter(name, "copper", freerouter.candidate_status, freerouter.route)
        inputs = sorted(set(inputs))
        # Paths themselves are not exported in provenance: only relative names plus byte hashes.
        hashes = tuple(_digest(path) for path in inputs)
        if "unreadable" in hashes:
            raise CliError("FEN-3001", "cannot fingerprint external tool inputs", where="--propose-with")
        for path, digest in zip(inputs, hashes, strict=True):
            if path in snapshots and snapshots[path] != digest:
                raise CliError("FEN-4002", "external tool inputs changed during preparation; review again")
            snapshots[path] = digest
        status = adapter.prepare(budget)
        if hashes != tuple(_digest(path) for path in inputs):
            raise CliError("FEN-4002", "external tool inputs changed during preflight; review again")
        if not status.available and budget.left() > 0:
            raise CliError("FEN-6001", status.reason or f"{name} unavailable", where="--propose-with")
        adapters.append(
            replace(
                adapter,
                prepare=_cached(status),
                dependencies=tuple(
                    f"{path.name}:{digest}" for path, digest in zip(inputs, hashes, strict=True)
                ),
            )
        )
        paths.extend(inputs)
    ordered = tuple(sorted(set(paths)))
    return Prepared(tuple(adapters), ordered, tuple(snapshots[path] for path in ordered))


def scope(
    before: Design, after: Design, subject: JobSubject, pads: tuple[BoardPad, ...], pour: PourCopper
) -> str:
    """Exactly the selected two original pad-containing components may merge.

    Reject unsupported/anonymous islands, extra disconnected copper and whole-net over-routing.
    Existing tracks inside a pad-containing component are supported; track-only endpoints are not.
    """
    if subject.a.kind != "pad" or subject.b.kind != "pad":
        return "external-scope-unsupported"
    a = connectivity(before, pads=pads, pour=pour).net(subject.net)
    b = connectivity(after, pads=pads, pour=rejoin(pour, after, pads=pads)).net(subject.net)
    if a is None or b is None or a.unsupported or b.unsupported or any(not part for part in a.pads):
        return "external-scope-unsupported"
    left = next((set(part) for part in a.pads if subject.a.name in part), set[str]())
    right = next((set(part) for part in a.pads if subject.b.name in part), set[str]())
    if not left or not right or left == right:
        return "external-scope-unsupported"
    expected = sorted(
        [tuple(sorted(left | right)), *(part for part in a.pads if set(part) not in (left, right))]
    )
    if sorted(b.pads) != expected or b.islands != len(expected) or a.islands - b.islands != 1:
        return "external-scope"
    return ""


def capability(router: object, status: RouterStatus | None = None) -> dict[str, Any] | None:
    supported = type(router) in (KicadRoutingToolsRouter, FreeroutingRouter)
    if not supported:
        return None
    container = isinstance(router, FreeroutingRouter) and bool(router.image)
    return {
        "supported": not container,
        "available": False if container else (status.available if status is not None else None),
        "projection": "copper" if isinstance(router, FreeroutingRouter) else "board",
        "scope": "ordinary pad-to-pad connection; exactly two original components merge",
        "arcs": False,
        "pairs": False,
        "groups": False,
        "local_only": True,
        "automatic_acceptance": False,
    }
