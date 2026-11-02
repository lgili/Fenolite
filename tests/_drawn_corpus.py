# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Value-free, strict source/lowered/native drawn census (c0276, task 7.2)."""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace

import _erc

from fenolite import __version__
from fenolite.backends.kicad import drawn as kdrawn
from fenolite.backends.kicad import parity_inputs, sch, symbol_contexts
from fenolite.backends.kicad.cli import KicadCli
from fenolite.core.errors import FenoliteError
from fenolite.core.ids import derived_id
from fenolite.importer.emit.sheets import Hierarchy, instances
from fenolite.importer.schematic import symbols
from fenolite.importer.source import Source
from fenolite.model.circuit import Circuit, Component, Net, Pin, PinRef
from fenolite.model.design import SCHEMA_VERSION, Design, DesignHeader
from fenolite.model.drawn_connect import DrawnNet, DrawnNetlist
from fenolite.model.library import FootprintDef

Element = tuple[str, str]


@dataclass(frozen=True)
class Input:
    id: str
    relative: str
    sha256: str


def partition_report(
    own: DrawnNetlist, references: Mapping[str, str], native: Mapping[str, set[Element]]
) -> dict[str, object]:
    """Compare full groups; native-only pins are never removed by an intersection."""

    def converted(members):
        return frozenset((references[path], pin) for path, pin in members)

    own_pins = converted(own.pins)
    ours = {converted(net.members) for net in own.nets}
    ours |= {converted((pin,)) for pin in own.open}
    groups = {
        name: frozenset(pin for pin in members if not pin[0].startswith("#"))
        for name, members in native.items()
    }
    groups = {name: group for name, group in groups.items() if group}
    native_pins = frozenset(pin for group in groups.values() for pin in group)
    theirs = set(groups.values()) | {frozenset((pin,)) for pin in own_pins - native_pins}
    native_names: dict[frozenset[Element], set[str]] = {}
    for name, group in groups.items():
        native_names.setdefault(group, set()).add(name)
    named = [(net.name, converted(net.members)) for net in own.nets if net.name]
    differences = sum(native_names.get(group) != {name} for name, group in named)
    return {
        "equal": ours == theirs,
        "drawn_pins": len(own_pins),
        "native_pins": len(native_pins),
        "native_only_pins": len(native_pins - own_pins),
        "drawn_unlisted_pins": len(own_pins - native_pins),
        "drawn_groups": len(ours),
        "native_groups": len(theirs),
        "only_drawn_groups": len(ours - theirs),
        "only_native_groups": len(theirs - ours),
        "names_compared": len(named),
        "name_differences": differences,
        "naming_equal": differences == 0,
        "naming_scope": "drawn-named-nets",
        "native_named_groups": len(native_names),
    }


def _issues(items: Sequence[object]) -> dict[str, int]:
    return dict(sorted(Counter(f"{item.severity}:{item.code}" for item in items).items()))


def _design(name: str, components: Sequence[Component] = (), nets: Sequence[Net] = ()) -> Design:
    return Design(
        header=DesignHeader(
            id=derived_id("dsn", "drawn-census", name),
            name=name,
            schema_version=SCHEMA_VERSION,
            fenolite_version=__version__,
        ),
        circuit=Circuit(components=tuple(components), nets=tuple(nets)),
    )


def measure(
    folder: Path,
    root_file: str,
    inputs: Sequence[Input],
    cli: KicadCli,
    *,
    ident: str,
    major: int,
    native_version: str,
    code_commit: str = "",
) -> dict[str, object]:
    """Record actual stages without storing source names/values or accepting a refusal."""
    started = time.perf_counter()
    report: dict[str, object] = {
        "schema": "fenolite.drawn-census.v0",
        "id": ident,
        "code_commit": code_commit,
        "native_version": native_version,
        "major": major,
        "status": "refused",
        "inputs": [],
        "timings": {},
        "issues": {},
    }
    stage = "hash"
    timings: dict[str, float] = {}
    issues: dict[str, dict[str, int]] = {}
    try:
        measured = []
        for item in inputs:
            data = (folder / item.relative).read_bytes()
            actual = hashlib.sha256(data).hexdigest()
            measured.append({"id": item.id, "sha256": actual, "expected_sha256": item.sha256})
            if actual != item.sha256:
                report.update(
                    status="invalid-cache", inputs=measured, refusal={"stage": stage, "code": "sha256"}
                )
                return report
        report["inputs"] = measured
        stage = "read"
        sheets = parity_inputs.read_sheets(folder / root_file)
        root = sheets[root_file]
        report["formats"] = sorted({sch.source_info(sheet).version for sheet in sheets.values()})
        source = Source(
            name=Path(root_file).stem,
            backend="kicad",
            design=_design(Path(root_file).stem),
            board_text="",
            major=major,
            inputs=(),
            folder=folder,
            hierarchy=sheets,
        )
        native_parts = {p.ref: p for p in sch.hierarchy_components(folder / root_file, on_board_only=True)}
        stage = "source-symbols"
        library = symbols(source, target=major)
        hierarchy = Hierarchy(source)
        paths = {ref: "/".join(hierarchy.paths.get(ref, (ref,))) for ref in library.refs}
        references = {path: ref for ref, path in paths.items()}
        bindings = {ref: kdrawn.SymbolBinding(lib_id, ()) for ref, lib_id in library.refs.items()}
        stage = "extract"
        stamp = time.perf_counter()
        found = kdrawn.extract_with_pins(
            root,
            sheets,
            components=paths,
            root_file=root_file,
            symbol_defaults=bindings,
        )
        report["counts"] = {
            **kdrawn.drawn_counts(found.drawn),
            "sheets": len(found.drawn.sheets),
            "symbols": sum(len(s.symbols) for s in found.drawn.sheets),
            "powers": sum(len(s.powers) for s in found.drawn.sheets),
            "bus_entries": sum(len(s.bus_entries) for s in found.drawn.sheets),
            "sheet_refs": sum(len(s.sheet_refs) for s in found.drawn.sheets),
        }
        issues[stage] = _issues(found.issues)
        timings[stage] = round(time.perf_counter() - stamp, 6)
        stage = "resolve"
        stamp = time.perf_counter()
        temporary = _design(
            source.name,
            [
                Component(
                    id=derived_id("cmp", "drawn-census", ref),
                    ref=ref,
                    lib_symbol_ref=library.refs[ref],
                    properties={"fenolite.path": paths[ref]},
                )
                for ref in sorted(paths)
            ],
        )
        _, own, resolved_issues = kdrawn.resolve_sheets(
            root,
            sheets,
            circuit=temporary.circuit,
            name=source.name,
            root_file=root_file,
        )
        issues[stage] = _issues(resolved_issues)
        timings[stage] = round(time.perf_counter() - stamp, 6)
        files = {item.relative: (folder / item.relative).read_bytes() for item in inputs}
        stage = "native-original"
        stamp = time.perf_counter()
        native = _erc.netlist(cli, root_file, files)
        report["partition"] = partition_report(own, references, native)
        timings[stage] = round(time.perf_counter() - stamp, 6)
        component_by_path = {
            component.properties["fenolite.path"]: component for component in temporary.circuit.components
        }
        components = tuple(
            replace(
                component,
                value=native_parts[component.ref].value,
                lib_footprint_ref=native_parts[component.ref].footprint,
                pins=tuple(
                    Pin(id=derived_id("pin", "drawn-census", f"{component.ref}:{number}"), number=number)
                    for path, number in own.pins
                    if path == component.properties["fenolite.path"]
                ),
            )
            for component in temporary.circuit.components
        )
        nets = tuple(
            Net(
                id=derived_id("net", "drawn-census", str(index)),
                name=net.name,
                members=tuple(PinRef(component_by_path[path].id, number) for path, number in net.members),
            )
            for index, net in enumerate(own.nets)
        )
        design = _design(source.name, components, nets)
        excluded_bom = {
            ref
            for instance in instances(source, include_root=True)
            for symbol in sheets[instance.file].symbols
            if not symbol.in_bom
            if (ref := instance.refs.get(symbol.id)) is not None
        }
        parts = [
            SimpleNamespace(
                component=c,
                path=c.properties["fenolite.path"],
                symbol=library.definitions[library.refs[c.ref]].definition,
                parents=(),
                symbol_origin="project",
                footprint=FootprintDef(
                    id=derived_id("fpd", "drawn-census", c.ref),
                    library="Census",
                    name="UnusedGeometry",
                    flags=("exclude_from_bom",) if c.ref in excluded_bom else (),
                ),
            )
            for c in components
        ]
        definitions = {
            key: kdrawn.PowerSymbol(value.definition, (), "project")
            for key, value in library.definitions.items()
        }
        stage = "lower"
        stamp = time.perf_counter()
        contextual = symbol_contexts.from_source(library.contexts, found.drawn, root_file=root_file)
        lowered = kdrawn.lower_drawn(
            found.drawn,
            design,
            parts,
            name=source.name,
            target=major,
            allow_lossy=False,
            power_symbols=definitions,
            opaque_symbols=definitions,
            symbol_overrides=definitions,
            context_symbols=contextual,
        )
        issues[stage] = _issues(lowered.issues)
        timings[stage] = round(time.perf_counter() - stamp, 6)
        if any(item.severity == "error" for item in (*found.issues, *resolved_issues, *lowered.issues)):
            report["refusal"] = {"stage": stage, "code": "drawn-issues"}
            return report
        stage = "write"
        written = {root_file: sch.write_schematic(lowered.sheet, target=major, allow_lossy=False)}
        written.update(
            {
                name: sch.write_schematic(sheet, target=major, allow_lossy=False)
                for name, sheet in lowered.children.items()
            }
        )
        if contextual is not None:
            for name, sheet in {root_file: lowered.sheet, **lowered.children}.items():
                symbol_contexts.check_written(sheet, written[name].text, target=major)
            report["counts"]["contextual_definitions"] = len(contextual.symbols)
        issues[stage] = _issues([issue for result in written.values() for issue in result.issues])
        if any(issue.severity == "error" for result in written.values() for issue in result.issues):
            report["refusal"] = {"stage": stage, "code": "write-issues"}
            return report
        readback = {name: sch.read_schematic(result.text, file=name) for name, result in written.items()}
        stage = "resolve-lowered"
        _, lowered_own, lowered_issues = kdrawn.resolve_sheets(
            readback[root_file],
            readback,
            circuit=design.circuit,
            name=source.name,
            root_file=root_file,
        )
        issues[stage] = _issues(lowered_issues)
        report["lowered_partition"] = partition_report(lowered_own, references, native)
        stage = "native-lowered"
        stamp = time.perf_counter()
        lowered_native = _erc.netlist(cli, root_file, {name: value.text for name, value in written.items()})
        original_groups = {
            name: tuple(sorted(pin for pin in group if not pin[0].startswith("#")))
            for name, group in native.items()
        }
        native_pins = {pin for group in original_groups.values() for pin in group}
        all_pins = native_pins | {(references[path], pin) for path, pin in own.pins}
        original_netlist = DrawnNetlist(
            tuple(DrawnNet(name, group) for name, group in original_groups.items() if group),
            tuple(sorted(all_pins)),
            tuple(sorted(all_pins - native_pins)),
        )
        report["lowered_native_partition"] = partition_report(
            original_netlist,
            {ref: ref for ref, _ in all_pins},
            lowered_native,
        )
        timings[stage] = round(time.perf_counter() - stamp, 6)
        equal = all(
            report[key]["equal"] for key in ("partition", "lowered_partition", "lowered_native_partition")
        )
        report["status"] = (
            "equal" if equal and not any(i.severity == "error" for i in lowered_issues) else "differs"
        )
    except Exception as error:
        code = str(getattr(error, "code", ""))
        report["status"] = (
            "refused" if isinstance(error, (FenoliteError, ValueError, AssertionError)) else "internal-error"
        )
        report["refusal"] = {
            "stage": stage,
            "type": type(error).__name__,
            "code": code if re.fullmatch(r"[\w.-]{1,80}", code) else "",
        }
    finally:
        report["issues"] = issues
        report["timings"] = timings
        report["seconds"] = round(time.perf_counter() - started, 6)
    return report


def record(folder: Path, report: Mapping[str, object]) -> None:
    """One independent metadata file per test case, retained even when its assertion fails."""
    text = json.dumps(report, sort_keys=True, indent=2) + "\n"
    (folder / "drawn-census.json").write_text(text, encoding="utf-8")
    print("DRAWN_CENSUS " + json.dumps(report, sort_keys=True))
