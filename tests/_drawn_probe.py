# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Private c0276 probe records; only native I/O is shared by complete input identity."""

from __future__ import annotations

import hashlib
import json
import runpy
import shutil
import tempfile
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import _drawn
import _erc
from _buildhelp import LIBS, project
from _buildhelp import build as build_design_of

from fenolite.backends.kicad.cli import KicadCli
from fenolite.dsl import Design
from fenolite.lens.build import BuildOutput
from fenolite.lens.drawn import read_drawn
from fenolite.model.drawn_connect import DrawnNetlist

CASES = (*_drawn.NAMES, "example")
IDS = ("drawn-connect", "drawn-names", "drawn-bus", "drawn-repeat", "drawn-write")
CONNECTIVITY = frozenset(
    {
        "label_dangling",
        "wire_dangling",
        "bus_entry_needed",
        "bus_to_net_conflict",
        "net_not_bus_member",
        "hier_label_mismatch",
        "multiple_net_names",
        "unconnected_wire_endpoint",
        "global_label_dangling",
        "bus_definition_conflict",
        "similar_labels",
    }
)
Pin = tuple[str, str]
Partition = set[frozenset[Pin]]
Key = tuple[str, str, str, str]
_NETLIST: dict[Key, tuple[tuple[str, frozenset[Pin]], ...]] = {}
_ERC: dict[Key, tuple[int, str, str]] = {}


def build(name: str, target: int) -> BuildOutput:
    """Build the unchanged authored design in a disposable source folder, not its original."""
    with tempfile.TemporaryDirectory(prefix="fenolite-drawn-probe-") as tmp:
        source = Path(tmp) / "source"
        shutil.copytree(
            _drawn.folder(name), source, ignore=shutil.ignore_patterns("design.lock", "__pycache__")
        )
        project(source, {"Mini": str(LIBS / "Mini_v9.pretty")},
                {"Mini": str(LIBS / "Mini_v9.kicad_sym")})  # fmt: skip
        design = runpy.run_path(str(source / "design.py"))["design"]
        assert isinstance(design, Design)
        value = read_drawn((source / "schematic.toml").read_text("utf-8"), file="schematic.toml")
        return build_design_of(design, target, project_dir=source, drawn=value, drawn_file="schematic.toml")


def clear_native_cache() -> None:
    """Clear this test-session I/O cache; global probe cache semantics do not change."""
    _NETLIST.clear()
    _ERC.clear()


def _key(cli: KicadCli, root: str, files: Mapping[str, str | bytes], version: str) -> Key:
    total = hashlib.sha256()
    for name, value in sorted(files.items(), key=lambda item: item[0].encode("utf-8")):
        data = value.encode("utf-8") if isinstance(value, str) else value
        total.update(f"{hashlib.sha256(data).hexdigest()} {len(data)} ".encode("ascii"))
        total.update(name.encode("utf-8") + b"\n")
    return version, str(cli.path), root, total.hexdigest()


def native_netlist(
    cli: KicadCli, root: str, files: Mapping[str, str | bytes], *, version: str
) -> dict[str, set[Pin]]:
    key = _key(cli, root, files, version)
    if key not in _NETLIST:
        found = _erc.netlist(cli, root, files)
        _NETLIST[key] = tuple((name, frozenset(pins)) for name, pins in found.items())
    return {name: set(pins) for name, pins in _NETLIST[key]}


def erc_types(report: Any) -> Counter[str]:
    """Validate only the consumed report structure, not finding types or severities."""
    data = report.data
    if not isinstance(data, Mapping) or not isinstance(data.get("sheets"), list):
        raise ValueError("invalid ERC report sheets")
    for sheet in data["sheets"]:
        if not isinstance(sheet, Mapping) or not isinstance(sheet.get("violations"), list):
            raise ValueError("invalid ERC report violations")
        for violation in sheet["violations"]:
            if not isinstance(violation, Mapping) or not isinstance(violation.get("type"), str):
                raise ValueError("invalid ERC report violation type")
    return _erc.types(_erc.violations(report))


def native_erc(cli: KicadCli, root: str, files: Mapping[str, str | bytes], *, version: str) -> Any:
    key = _key(cli, root, files, version)
    if key in _ERC:
        code, data, stderr = _ERC[key]
        return _erc.Report(code, json.loads(data), stderr)
    found = _erc.run_erc(cli, root, files)
    # Retain only complete successful tool I/O, never a failed/absent report.
    # run_erc does not request --exit-code-violations: native findings still return0.
    if found.returncode == 0 and found.loaded:
        erc_types(found)  # Invalid/missing structures never fill the I/O cache.
        _ERC[key] = found.returncode, json.dumps(found.data), found.stderr
    return found


def refs(output: Any) -> dict[str, str]:
    circuit = output.design.circuit
    return {c.properties["fenolite.path"]: c.ref for c in circuit.components}


def partition(netlist: DrawnNetlist, references: dict[str, str]) -> Partition:
    groups = {frozenset((references[p], n) for p, n in net.members) for net in netlist.nets}
    return groups | {frozenset({(references[p], n)}) for p, n in netlist.open}


def kicad_partition(nets: dict[str, set[Pin]], pins: set[Pin]) -> Partition:
    # Exactly the existing authored-fixture physical domain, including the
    # singletons that native netlists legitimately omit. A lost CONNECTED pin
    # still breaks its multi-pin group, even though it becomes a singleton.
    groups = {frozenset(nodes & pins) for nodes in nets.values()} - {frozenset()}
    seen = {pin for group in groups for pin in group}
    return groups | {frozenset({pin}) for pin in pins - seen}


@dataclass(frozen=True)
class Observation:
    ours: Partition
    theirs: Partition
    differing_names: Mapping[str, str | None]


def observe(name: str, target: int, cli: KicadCli, *, version: str) -> Observation:
    output = build(name, target)
    _, netlist, _ = _drawn.resolved(output)
    references = refs(output)
    pins = {(references[p], n) for p, n in netlist.pins}
    exported = native_netlist(cli, _drawn.root_name(output), dict(output.files), version=version)
    ours, theirs = partition(netlist, references), kicad_partition(exported, pins)
    names = {
        net.name: frozenset((references[p], n) for p, n in net.members) for net in netlist.nets if net.name
    }
    kicad_names = {frozenset(nodes & pins): net for net, nodes in exported.items()}
    differing = {
        name: kicad_names.get(group) for name, group in names.items() if kicad_names.get(group) != name
    }
    return Observation(ours, theirs, differing)


def drawn_probes(
    runner: Callable[[], KicadCli], version: Callable[[], str]
) -> dict[str, tuple[Callable[[], str], tuple[int, ...]]]:
    """Register functions lazily; no tool is executed by registration/import."""

    def measured(kind: str, cases: tuple[str, ...]) -> str:
        tool, actual = runner(), version()
        target = int(actual.split(".", 1)[0])
        for name in cases:
            if kind == "write":
                output = build(name, target)
                report = native_erc(tool, _drawn.root_name(output), dict(output.files), version=actual)
                if report.returncode != 0 or not report.loaded or set(erc_types(report)) & CONNECTIVITY:
                    return "different"
            else:
                found = observe(name, target, tool, version=actual)
                if found.differing_names if kind == "names" else found.ours != found.theirs:
                    return "different"
        return "equal"

    return {
        "drawn-connect": (lambda: measured("connect", CASES), (9, 10)),
        "drawn-names": (lambda: measured("names", CASES), (9, 10)),
        "drawn-bus": (lambda: measured("connect", ("bus", "full")), (9, 10)),
        "drawn-repeat": (lambda: measured("connect", ("repeat",)), (9, 10)),
        "drawn-write": (lambda: measured("write", CASES), (9, 10)),
    }
