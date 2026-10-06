# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad's ERC and schematic parity reports for tests (change c0061): ``kicad-cli sch erc`` and
``pcb drc --schematic-parity`` run through ``KicadCli.run`` on copies, and their JSON reports as plain
dictionaries. Only key names that both 9.0.9 and 10.0.6 write are read. The product runner and its model
of the report belong to change c0062."""

from __future__ import annotations

import json
import tempfile
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fenolite.backends.kicad.cli import NETLIST, KicadCli
from fenolite.backends.kicad.sexpr import parse

ERC_REPORT = "erc.json"
PARITY_REPORT = "parity.json"


@dataclass(frozen=True)
class Report:
    """A report and the run that wrote it. ``returncode`` is ``None`` on a timeout; ``data`` is ``None``
    when the tool wrote no report (it did not load the input)."""

    returncode: int | None
    data: Mapping[str, Any] | None
    stderr: str = ""

    @property
    def loaded(self) -> bool:
        return self.data is not None


def tops(files: Mapping[str, str | bytes], folder: Path) -> dict[str, Path]:
    """``files`` (relative path → content) written under ``folder``: the top-level entries to copy."""
    out: dict[str, Path] = {}
    for rel, data in files.items():
        path = folder / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data.encode("utf-8") if isinstance(data, str) else data)
        top = rel.split("/", 1)[0]
        out[top] = folder / top
    return out


def _run(cli: KicadCli, args: list[str], files: Mapping[str, str | bytes], output: str) -> Report:
    with tempfile.TemporaryDirectory() as tmp:
        run = cli.run(args, files=tops(files, Path(tmp)))
    data = run.outputs.get(output)
    return Report(run.returncode, None if data is None else json.loads(data.decode("utf-8")), run.stderr)


def run_erc(
    cli: KicadCli, schematic: str, files: Mapping[str, str | bytes], *, exit_code: bool = False
) -> Report:
    """``sch erc --format json --severity-all`` on ``schematic``, one of ``files``. With ``exit_code`` the
    run also passes ``--exit-code-violations``, so ``returncode`` is 0 only without a violation."""
    extra = ["--exit-code-violations"] if exit_code else []
    args = ["sch", "erc", "--format", "json", "--severity-all", *extra, "-o", ERC_REPORT, schematic]
    return _run(cli, args, files, ERC_REPORT)


def run_parity(cli: KicadCli, board: str, files: Mapping[str, str | bytes]) -> Report:
    """``pcb drc --schematic-parity --format json --severity-all`` on ``board``, one of ``files``."""
    args = [
        "pcb", "drc", "--format", "json", "--severity-all", "--schematic-parity", "-o", PARITY_REPORT, board,
    ]  # fmt: skip
    return _run(cli, args, files, PARITY_REPORT)


def violations(report: Report) -> list[Mapping[str, Any]]:
    """Every violation of every sheet of an ERC report."""
    assert report.data is not None, f"no ERC report: {report.stderr.strip()}"
    return [v for sheet in report.data.get("sheets", []) for v in sheet.get("violations", [])]


def parity(report: Report) -> list[Mapping[str, Any]]:
    """The ``schematic_parity`` list of a DRC report."""
    assert report.data is not None, f"no DRC report: {report.stderr.strip()}"
    return list(report.data.get("schematic_parity", []))


def types(found: list[Mapping[str, Any]]) -> Counter[str]:
    return Counter(str(item.get("type", "")) for item in found)


def netlist(
    cli: KicadCli, schematic: str, files: Mapping[str, str | bytes]
) -> dict[str, set[tuple[str, str]]]:
    """The nets of ``sch export netlist``: name → the ``(reference, pin number)`` pairs on it."""
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        entries = tops(files, folder)
        others = {name: path for name, path in entries.items() if name != schematic}
        run = cli.export_netlist(folder / schematic, files=others)
    data = run.outputs.get(NETLIST)
    assert run.ok and data is not None, f"no netlist: {run.stderr.strip()}"
    found: dict[str, set[tuple[str, str]]] = {}
    nets = parse(data.decode("utf-8")).find("nets")
    for net in nets.nodes("net") if nets is not None else ():
        name = net.find("name")
        nodes = set()
        for node in net.nodes("node"):
            ref, pin = node.find("ref"), node.find("pin")
            assert ref is not None and pin is not None
            nodes.add((ref.atoms()[0].value, pin.atoms()[0].value))
        assert name is not None
        found.setdefault(name.atoms()[0].value, set()).update(nodes)
    return found


__all__ = [
    "ERC_REPORT",
    "PARITY_REPORT",
    "Report",
    "netlist",
    "parity",
    "run_erc",
    "run_parity",
    "tops",
    "types",
    "violations",
]
