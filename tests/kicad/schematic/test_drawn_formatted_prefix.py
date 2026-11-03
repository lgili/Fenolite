# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Original native Mini controls preserve formatted prefix identity and all pins (c0343)."""

import hashlib

import _bus_scope
import _drawn_corpus
import _erc
import _probes
import pytest

from fenolite.backends.kicad import drawn, sch

pytestmark = pytest.mark.needs_kicad
PREFIXES = ("BUS_{A}", "BUS^{A}", "~{BUS}", "BUS_{A}^{B}~{C}", "BUS_{A^{B}}")


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("matching", [False, True])
def test_native_formatted_prefixes_preserve_literal_members_and_complete_partition(
    prefix: str, matching: bool
) -> None:
    value = _bus_scope.formatted_prefix(prefix, child_prefix=None if matching else "PLAIN")
    file, files, refs = _bus_scope.native_drawing(value, _probes.major())
    source_hashes = {path: hashlib.sha256(data).hexdigest() for path, data in files.items()}
    root = sch.read_schematic(files[file].decode(), file=file)
    children = {
        path: sch.read_schematic(data.decode(), file=path)
        for path, data in files.items()
        if path.endswith(".kicad_sch") and path != file
    }
    _, own, issues = drawn.resolve_sheets(
        root,
        children,
        circuit=_bus_scope.base(_probes.major()).design.circuit,
        name="formatted-prefix",
        root_file=file,
    )
    native = _erc.netlist(_probes.runner(), file, files)
    report = _drawn_corpus.partition_report(own, refs, native)
    for index in range(4):
        assert (
            any({("U1", str(17 + index)), (f"R{10 + index}", "1")} <= group for group in native.values())
            is matching
        )
    assert report["drawn_pins"] == report["native_pins"] == 40
    assert report["equal"], report
    if matching:
        assert not issues
        assert {f"/{prefix}.D{index}" for index in range(4)} <= set(native)
    assert source_hashes == {path: hashlib.sha256(data).hexdigest() for path, data in files.items()}
    print(f"{_probes.runner().version()} {prefix} matching={matching}: {report}")


@pytest.mark.parametrize("prefix", ["BROKEN{D", "BUS_{A}{D"])
def test_native_malformed_group_does_not_fall_through_as_a_vector(prefix: str) -> None:
    value = _bus_scope.vector_prefix(prefix)
    file, files, refs = _bus_scope.native_drawing(value, _probes.major())
    root = sch.read_schematic(files[file].decode(), file=file)
    children = {
        path: sch.read_schematic(data.decode(), file=path)
        for path, data in files.items()
        if path.endswith(".kicad_sch") and path != file
    }
    _, own, issues = drawn.resolve_sheets(
        root,
        children,
        circuit=_bus_scope.base(_probes.major()).design.circuit,
        name="malformed-prefix",
        root_file=file,
    )
    native = _erc.netlist(_probes.runner(), file, files)
    report = _drawn_corpus.partition_report(own, refs, native)
    assert (
        report["drawn_pins"]
        == report["native_pins"]
        == report["drawn_groups"]
        == report["native_groups"]
        == 40
    )
    assert report["equal"] and issues
    print(f"{_probes.runner().version()} malformed {prefix}: {report}")


@pytest.mark.parametrize("prefix", PREFIXES)
def test_native_formatting_alone_does_not_declare_the_scalar_members(prefix: str) -> None:
    value = _bus_scope.formatted_prefix(prefix, group=False)
    file, files, refs = _bus_scope.native_drawing(value, _probes.major())
    root = sch.read_schematic(files[file].decode(), file=file)
    children = {
        path: sch.read_schematic(data.decode(), file=path)
        for path, data in files.items()
        if path.endswith(".kicad_sch") and path != file
    }
    _, own, _issues = drawn.resolve_sheets(
        root,
        children,
        circuit=_bus_scope.base(_probes.major()).design.circuit,
        name="format-only",
        root_file=file,
    )
    native = _erc.netlist(_probes.runner(), file, files)
    report = _drawn_corpus.partition_report(own, refs, native)
    assert report["drawn_pins"] == report["native_pins"] == 40
    assert report["drawn_groups"] == report["native_groups"] == 40
    assert report["equal"], report
