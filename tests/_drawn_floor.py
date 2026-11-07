# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Strict electrical copy-upgrade evidence, separate from original support (c0347)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping

from fenolite.backends.kicad import sch
from fenolite.backends.kicad.sexpr import parse_bytes
from fenolite.backends.kicad.versions import (
    FileKind,
    UnsupportedFormatError,
    VersionStatus,
    inspect,
)

Element = tuple[str, str]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def original_refusal(data: bytes) -> dict[str, object]:
    """Only a checked schematic TOO_OLD header and the exact reader guard qualify."""
    info = inspect(parse_bytes(data))
    if info.kind != FileKind.SCHEMATIC or info.status != VersionStatus.TOO_OLD:
        raise ValueError("not a schematic reader-floor boundary")
    try:
        sch.read_schematic(data.decode("utf-8"))
    except UnsupportedFormatError as error:
        return {
            "status": "refused",
            "expectation": "original-reader-floor",
            "format": info.version,
            "input_sha256": digest(data),
            "refusal": {"stage": "read", "type": type(error).__name__, "code": error.cli_code},
        }
    raise AssertionError("original below-floor schematic was read without refusal")


def signature(graph: Mapping[str, set[Element]]) -> dict[str, object]:
    """All exported elements and names contribute; no intersection or pin filtering."""
    named = {name: sorted(members) for name, members in sorted(graph.items())}
    partitions = sorted(sorted(members) for members in graph.values())
    pins = sorted({element for members in graph.values() for element in members})

    def hashed(value: object) -> str:
        return digest(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8"))

    return {
        "pins": len(pins),
        "groups": len(graph),
        "pins_sha256": hashed(pins),
        "partition_sha256": hashed(partitions),
        "named_sha256": hashed(named),
    }


def bridge_equal(first: Mapping[str, object], second: Mapping[str, object]) -> bool:
    keys = {"pins", "groups", "pins_sha256", "partition_sha256", "named_sha256"}
    return keys <= first.keys() and keys <= second.keys() and all(first[k] == second[k] for k in keys)


def census_equal(report: Mapping[str, object]) -> bool:
    """Partition equality alone never certifies the stricter upgraded naming bridge."""
    if report.get("status") != "equal":
        return False
    for key in ("partition", "lowered_partition", "lowered_native_partition"):
        comparison = report.get(key)
        if not isinstance(comparison, dict) or not comparison.get("equal"):
            return False
        if comparison.get("naming_equal") is not True or comparison.get("name_differences") != 0:
            return False
        if comparison.get("native_only_pins") != 0 or comparison.get("drawn_unlisted_pins") != 0:
            return False
    return True


def authored_original() -> tuple[str, dict[str, bytes]]:
    """Named Mini pin islands carry an old header; they do not imitate legacy grammar."""
    import _drawn

    from fenolite.backends.kicad.sexpr import Node, dumps, parse
    from fenolite.core.ids import derived_id
    from fenolite.model.schematic import NetLabel, SchematicSheet

    output = _drawn.build("flat", 9)
    root = _drawn.root_name(output)
    files = dict(output.files)
    tree = parse(files[root].decode("utf-8"))
    positions = _drawn.pins(_drawn.drawn("flat"), "flat")
    labels = tuple(
        NetLabel(
            id=derived_id("lbl", "floor-control", str(index)),
            kind="local",
            name=f"AUTH_{index}",
            position=pin.at,
        )
        for index, pin in enumerate(
            pin for key, pins in positions.items() if key[1] == "symbol" for pin in pins
        )
    )
    shell = SchematicSheet(id=derived_id("sch", "floor-control", "labels"), name="labels", labels=labels)
    fragments = parse(sch.write_schematic(shell, target=9).text)
    children = []
    for child in tree.children:
        if isinstance(child, Node):
            if child.name in {
                "wire",
                "junction",
                "no_connect",
                "label",
                "global_label",
                "hierarchical_label",
            }:
                continue
            if child.name == "symbol" and any(
                prop.atoms()[0].value == "Reference" and prop.atoms()[1].value.startswith("#")
                for prop in child.nodes("property")
            ):
                continue
        children.append(child)
    children.extend(node for node in fragments.children if isinstance(node, Node) and node.name == "label")
    tree = tree.with_children(tuple(children))
    old = tree.find("version")
    assert old is not None
    version = old.with_children((parse("(version 20230121)").children[0],))
    files[root] = dumps(
        tree.with_children(tuple(version if node is old else node for node in tree.children))
    ).encode()
    return root, files


def probe(folder, root_file, target_file, inputs, cli, *, ident, major, code_commit, manifest_sha256):
    """Measure one checked original owner; upgraded bytes never replace its identity."""
    import dataclasses
    import tempfile
    from pathlib import Path

    import _erc
    from _drawn_corpus import Input, measure

    from fenolite.importer.upgrade import upgrader

    original = {item.relative: (folder / item.relative).read_bytes() for item in inputs}
    actual = {name: digest(data) for name, data in original.items()}
    report = {
        "schema": "fenolite.drawn-floor.v0",
        "id": ident,
        "code_commit": code_commit,
        "manifest_sha256": manifest_sha256,
        "major": major,
        "native_version": cli.version(),
        "inputs": [dataclasses.asdict(item) for item in inputs],
        "status": "partial",
    }
    try:
        if any(actual[item.relative] != item.sha256 for item in inputs):
            raise ValueError("original-input-digest")
        report["original"] = original_refusal(original[target_file])
        graph = _erc.netlist(cli, root_file, original)
        report["original_native"] = signature(graph)
        if major == 9:
            report.update(status="original/refused", upgrade_capability=False)
            return report
        if major != 10:
            raise ValueError("unsupported-native-major")
        report["upgrade_capability"] = True
        with tempfile.TemporaryDirectory() as temporary:
            copy = Path(temporary)
            for name, data in original.items():
                destination = copy / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
            upgraded_files = dict(original)
            upgrades = []
            for name, data in original.items():
                if not name.endswith(".kicad_sch"):
                    continue
                old = inspect(parse_bytes(data))
                if old.status != VersionStatus.TOO_OLD:
                    continue
                after, receipt = upgrader(cli.path)(copy / name, FileKind.SCHEMATIC)
                new = inspect(parse_bytes(after))
                if (
                    receipt.sha256_before != actual[name]
                    or receipt.sha256_after != digest(after)
                    or receipt.from_version != old.version
                    or receipt.to_version != new.version
                    or receipt.tool != "kicad-cli"
                    or receipt.tool_version != cli.version()
                    or new.kind != FileKind.SCHEMATIC
                    or new.status != VersionStatus.SUPPORTED
                ):
                    raise ValueError("upgrade-provenance")
                upgraded_files[name] = after
                upgrades.append({**dataclasses.asdict(receipt), "relative": name})
            report["upgrades"] = upgrades
            if not upgrades:
                raise ValueError("missing-upgrade-output")
            if actual != {name: digest((copy / name).read_bytes()) for name in original}:
                raise ValueError("copy-upgrader-modified-input")
            upgraded_graph = _erc.netlist(cli, root_file, upgraded_files)
            report["upgraded_native"] = signature(upgraded_graph)
            report["upgrade_bridge_equal"] = bridge_equal(
                report["original_native"], report["upgraded_native"]
            )
            for name, data in upgraded_files.items():
                (copy / name).write_bytes(data)
            updated = tuple(
                Input(item.id, item.relative, digest(upgraded_files[item.relative])) for item in inputs
            )
            census = measure(
                copy,
                root_file,
                updated,
                cli,
                ident=ident,
                major=major,
                native_version=cli.version(),
                code_commit=code_commit,
            )
            report["upgraded_census"] = census
            if report["upgrade_bridge_equal"] and census_equal(census):
                report["status"] = "upgraded/equal"
    except Exception as error:
        report["failure"] = {"type": type(error).__name__}
    finally:
        report["originals_unchanged"] = actual == {
            name: digest((folder / name).read_bytes()) for name in original
        }
        if not report["originals_unchanged"]:
            report["status"] = "partial"
    return report
