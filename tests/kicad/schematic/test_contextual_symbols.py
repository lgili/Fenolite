# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Native load, effective component/BOM defaults and complete owned snapshots (c0327)."""

from __future__ import annotations

import csv
import hashlib
import io
import tomllib
from pathlib import Path

import _drawn_corpus as census
import pytest
from _contextual_symbols import NATIVE_ID, ROOT_FILE, project
from _contextual_symbols import source as source_input
from _probes import runner

from fenolite.api import run
from fenolite.backends.kicad.cli import BOM, NETLIST
from fenolite.backends.kicad.netlist import read_netlist
from fenolite.backends.kicad.sexpr import dumps, parse
from fenolite.backends.kicad.versions import inspect
from fenolite.importer.schematic import symbols

pytestmark = pytest.mark.needs_kicad
STAMP = "2026-11-02T00:00:00Z"


def files(folder: Path) -> dict[str, bytes]:
    return {p.relative_to(folder).as_posix(): p.read_bytes() for p in folder.rglob("*") if p.is_file()}


def native(cli, root: Path):
    others = {path.name: path for path in root.parent.iterdir() if path.name != root.name}
    netlist = cli.export_netlist(root, files=others)
    assert netlist.ok and NETLIST in netlist.outputs, netlist.stderr
    bom = cli.export_bom(
        root, fields=("Reference", "Value", "Footprint", "Description", "Datasheet"), files=others
    )
    assert bom.ok and BOM in bom.outputs, bom.stderr
    return read_netlist(netlist.outputs[NETLIST].decode("utf-8")), list(
        csv.reader(io.StringIO(bom.outputs[BOM].decode("utf-8-sig")))
    )


def test_native_component_defaults_bom_and_all_nine_levels_remain_equal(tmp_path: Path) -> None:
    cli = runner()
    # The versioned native drawings are KiCad 9. Build their matching board,
    # independently of which installed CLI is judging their preservation.
    original = project(tmp_path / "original", 9)
    before = files(original.parent)
    source_target = inspect(parse(original.with_suffix(".kicad_sch").read_text(encoding="utf-8"))).major
    assert source_target == 9  # The owned native snapshots are authored in KiCad 9 format.
    source, source_bom = native(cli, original.with_suffix(".kicad_sch"))
    imported = run(
        "import",
        str(original),
        "--to",
        "python",
        "--out",
        "code",
        "--kicad-version",
        str(source_target),
        "--confirm",
        cwd=tmp_path,
        timestamp=STAMP,
    )
    assert imported.exit_code == 0, (imported.error, (imported.envelope or {}).get("issues"))
    built = run(
        "build",
        "code/design.py",
        "--out",
        "built",
        "--kicad-version",
        str(source_target),
        "--confirm",
        cwd=tmp_path,
        timestamp=STAMP,
    )
    assert built.exit_code == 0, (built.error, (built.envelope or {}).get("issues"))
    actual, actual_bom = native(cli, tmp_path / "built" / ROOT_FILE)
    assert source.components == actual.components
    assert source.nets == actual.nets
    assert source_bom == actual_bom and len(source_bom) > 1
    index = tomllib.loads((tmp_path / "code/symbol-contexts.toml").read_text(encoding="utf-8"))
    for row in index["symbol"]:
        file = row["input"]
        first = parse(before[file].decode("utf-8")).find("lib_symbols")
        second = parse((tmp_path / "built" / file).read_text(encoding="utf-8")).find("lib_symbols")
        assert first is not None and second is not None
        expected = next(s for s in first.nodes("symbol") if s.atoms()[0].value == row["native_id"])
        written = next(s for s in second.nodes("symbol") if s.atoms()[0].value == row["native_id"])
        assert expected.nodes("property") == written.nodes("property")
    proof = run(
        "verify-source",
        "code/design.py",
        "--against",
        str(original.parent),
        "--kicad-version",
        str(source_target),
        cwd=tmp_path,
        timestamp=STAMP,
    )
    assert proof.exit_code == 0, (proof.error, proof.result.get("differences"))
    assert {str(row["level"]): row["status"] for row in proof.result["levels"]} == {
        **{str(level): "equal" for level in range(1, 9)},
        "S": "equal",
    }
    assert next(row for row in proof.result["levels"] if row["level"] == 5)["compared"] > 0
    assert files(original.parent) == before
    print(f"native {cli.version()}: 4 components, {len(source_bom) - 1} BOM rows; all nine levels equal")


def test_context_census_keeps_every_full_snapshot_and_native_partition(tmp_path: Path) -> None:
    cli = runner()
    original = project(tmp_path / "original", cli.major())
    inputs = [
        census.Input(
            p.name, p.relative_to(original.parent).as_posix(), hashlib.sha256(p.read_bytes()).hexdigest()
        )
        for p in original.parent.rglob("*")
        if p.suffix in (".kicad_sch", ".kicad_pro")
    ]
    report = census.measure(
        original.parent,
        ROOT_FILE,
        inputs,
        cli,
        ident="authored-contextual-symbols",
        major=cli.major(),
        native_version=cli.version(),
    )
    assert report["status"] == "equal", report
    assert report["counts"]["contextual_definitions"] == 4
    assert all(report[key]["equal"] for key in ("partition", "lowered_partition", "lowered_native_partition"))
    assert report["partition"]["drawn_pins"] == 8
    assert report["partition"]["drawn_groups"] == 5
    indexed = symbols(source_input(original.parent), target=cli.major()).contexts
    assert len(indexed) == 4
    assert len({dumps(v.node) for (file, lib_id), v in indexed.items() if lib_id == NATIVE_ID}) == 2
    print(
        f"native {cli.version()}: 8 pins / 5 groups, 4 complete contextual definitions, all partitions equal"
    )
