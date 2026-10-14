# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Independent KiCad checks of Altium conversion (c0161), files confined to temporary folders."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fenolite.api import equivalent
from fenolite.backends.kicad.cli import KicadCli
from fenolite.convert import convert_project
from fenolite.convert.report import Explainer

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "tests/data/altium/blink/blink.PrjPcb"
SAMPLE_BOARD = ROOT / "tests/data/altium/routed/routed.PcbDoc"


def write(source: Path, folder: Path, target: int):
    conversion = convert_project(source, to="kicad", kicad_version=target, allow_lossy=True)
    for name, data in conversion.files.items():
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return conversion


def load(source: Path, cli: KicadCli) -> bool:
    with tempfile.TemporaryDirectory(prefix="fenolite-a2k-load-") as temp:
        folder = Path(temp)
        conversion = write(source, folder, cli.major())
        board = folder / conversion.read_back
        files = {name: folder / name for name in conversion.files if name != conversion.read_back}
        loaded = cli.load_board_svg(board, files=files)
        return loaded.ok and cli.drc(board, files=files).report is not None


def imported(source: Path, cli: KicadCli):
    with tempfile.TemporaryDirectory(prefix="fenolite-a2k-import-") as temp:
        folder = Path(temp)
        conversion = write(source, folder, 10)
        imported = cli.import_board(source)
        assert imported.board is not None, imported.run.stderr
        target = folder / "oracle.kicad_pcb"
        target.write_bytes(imported.board)
        from fenolite.backends.kicad import altium_import
        from fenolite.checks.equivalence import load_profiles, select_profile

        profiles = load_profiles(altium_import.exclusions_text())
        profile = select_profile(profiles, "kicad-import", cli.version())
        assert profile is not None
        result = equivalent(
            folder / conversion.read_back,
            target,
            level=5,
            profile=profile,
            frame="relative",
            ignore_refs=("",),
        )
        assert result.report is not None
        explainer = Explainer(conversion.source.design, conversion.report)
        return tuple(
            d for d in result.report.differences if explainer.explain(d.kind, d.where, d.a, d.b) is None
        )


def schematic(source: Path, cli: KicadCli):
    with tempfile.TemporaryDirectory(prefix="fenolite-a2k-sch-") as temp:
        folder = Path(temp)
        conversion = write(source, folder, cli.major())
        name = f"{conversion.design.header.name}.kicad_sch"
        if name not in conversion.files:
            assert conversion.report.row("schematic").lost
            return ()
        files = {key: folder / key for key in conversion.files if key != name}
        run = cli.export_netlist(folder / name, files=files)
        assert run.ok
        from dataclasses import replace

        from fenolite.api.sides import netlist_design
        from fenolite.backends.kicad.cli import NETLIST
        from fenolite.backends.kicad.netlist import read_netlist

        exported = read_netlist(run.outputs[NETLIST].decode())
        # H-K-SCH-UNCONNECTED: an open pin gets a synthetic net in
        # KiCad's export. It is not a conductive connection in the source.
        source_names = {net.name for net in conversion.design.circuit.nets}
        exported = replace(
            exported,
            nets=tuple(
                net
                for net in exported.nets
                if not (
                    net.name.startswith("unconnected-(")
                    and net.name not in source_names
                    and len(net.nodes) == 1
                )
            ),
        )
        actual = netlist_design(
            exported, "exported", dnp=frozenset(c.ref for c in exported.components if "dnp" in c.flags)
        )
        winners = {member: net.id for net in conversion.design.circuit.nets for member in net.members}
        expected_nets = tuple(
            replace(net, members=tuple(member for member in net.members if winners[member] == net.id))
            for net in conversion.design.circuit.nets
        )
        connected = {(m.component_id, m.pin) for net in expected_nets for m in net.members}
        parts = tuple(
            replace(c, pins=tuple(p for p in c.pins if (c.id, p.number) in connected))
            for c in conversion.design.circuit.components
        )
        expected = replace(
            conversion.design,
            board=None,
            circuit=replace(conversion.design.circuit, components=parts, nets=expected_nets),
        )
        independent = equivalent(expected, actual, level=2, ignore_refs=("",))
        assert independent.report is not None
        assert not independent.report.differences, independent.report.differences

        result = equivalent(replace(conversion.design, board=None), folder / name, level=2, ignore_refs=("",))
        assert result.report is not None
        # Export and ERC are independent checks; conversion is not a claim that a source is ERC clean.
        erc = cli.erc(folder / name, files=files)
        assert erc.report is not None
        assert not tuple(
            violation
            for violation in erc.report.violations
            if violation.severity == "error" and violation.type in ("pin_not_connected", "isolated_pin_label")
        ), erc.report.violations
        explainer = Explainer(conversion.source.design, conversion.report)
        return tuple(
            difference
            for difference in result.report.differences
            if explainer.explain(difference.kind, difference.where, difference.a, difference.b) is None
        )


def load_probe() -> str:
    from _probes import runner

    return "equal" if load(SAMPLE, runner()) else "not-equal"


def import_probe() -> str:
    from _probes import runner

    return "equal" if not imported(SAMPLE_BOARD, runner()) else "not-equal"


def schematic_probe() -> str:
    from _probes import runner

    return "equal" if not schematic(SAMPLE, runner()) else "not-equal"
