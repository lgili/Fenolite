# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A fake ``kicad-cli`` for hermetic tests of ``check``, ``doctor`` and the oracle (change c0013 Decision 19).

The fake is a launcher around a Python script (a ``#!/bin/sh`` script, or a ``.cmd`` file on Windows;
``_resources.fake_tool``). It answers
``version``, ``<words> --help`` from ``help_pages``, ``pcb drc``, ``pcb export ipcd356`` (the ``ipcd356``
text; without it, exit 3 and no export) and ``pcb upgrade --force`` (``upgrade="copy"`` re-saves the
board unchanged, ``"fail"`` exits 1; c0020), ``pcb import`` (``imported=<board text>`` writes it to the
``-o`` file with a JSON report and prints ``import_output``; without it, exit 0 and no file; c0045), and
``sch export bom`` (the ``bom`` text written to the ``-o`` file; without it, exit 3; c0064), and
the export and render commands of c0024
(``export_files``): an export whose ``-o`` names a folder or a file in a folder, as ``fenolite export``
asks for, while the netlist oracle of c0020 exports to the run folder itself. Without ``drc_report`` its
DRC report
holds no violation, plus the canary ``clearance`` pair when the board it got holds both canary tracks
and a rules file next to it holds the canary rule, as KiCad would report them. ``drc_report=""`` writes no
report and exits 3. Every call appends ``{"args", "files"}`` to ``<folder>/calls.jsonl``: the arguments
and the text of each board and rules file in the run folder. With ``log``, every board and rules file
of every run is also copied there as ``<call number>-<name>``. With ``drc_sequence``, the n-th ``pcb drc``
run writes the n-th report text, and the last one from then on.

Change c0062 adds ``sch erc``: with ``erc_report`` (a report text) the run writes it to the ``-o`` file and
exits 0; with ``erc_report=""`` it prints ``Failed to load schematic`` and exits 3 without a report; without
the argument it writes a report with one sheet ``/`` and no violation. ``erc_sequence`` gives the n-th
``sch erc`` run its own report text. Each call also records the text of every ``.kicad_sch`` of the run
folder under ``sheets``. ``parity`` is a list of DRC violations that a ``pcb drc`` run puts in
``schematic_parity`` only when it got ``--schematic-parity``; ``parity_fail`` makes such a run print
``parity_fail`` and exit 255 without a report, as KiCad does for a schematic it cannot load, and
``parity_note`` makes it print that line and still write its report.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

from _resources import fake_tool

from fenolite.backends.kicad.canary import CANARY_RULE_NAME, CANARY_UUIDS

PROGRAM = """import json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
config = json.load(open(os.path.join(HERE, "config.json")))
args = sys.argv[1:]
files = {}
for name in sorted(os.listdir(".")):
    if name.endswith((".kicad_pcb", ".kicad_dru", ".kicad_pro")) and os.path.isfile(name):
        files[name] = open(name, encoding="utf-8", errors="replace").read()
sheets = {}
for folder, _, names in sorted(os.walk(".")):
    for name in sorted(names):
        if name.endswith(".kicad_sch"):
            path = os.path.normpath(os.path.join(folder, name)).replace(os.sep, "/")
            sheets[path] = open(path, encoding="utf-8", errors="replace").read()
with open(os.path.join(HERE, "calls.jsonl"), "a") as log:
    log.write(json.dumps({"args": args, "files": files, "sheets": sheets}) + "\\n")
if config["log"]:
    count = sum(1 for _ in open(os.path.join(HERE, "calls.jsonl")))
    for name, text in files.items():
        if name.endswith((".kicad_pcb", ".kicad_dru")):
            open(os.path.join(config["log"], f"{count}-{name}"), "w", newline="").write(text)
if args[:1] == ["version"]:
    print(config["version"])
    sys.exit(0)
if args and args[-1] == "--help":
    page = config["help_pages"].get(" ".join(args[:-1]))
    if page is None:
        print("Error: unknown command", file=sys.stderr)
        sys.exit(1)
    print(page)
    sys.exit(0)
time.sleep(config["sleep"])
for name in config["writes"]:
    open(name, "w", newline="").write("{}")
if args[:3] == ["pcb", "export", "ipcd356"] and "/" not in args[args.index("-o") + 1]:
    if config["ipcd356"] is None:
        print("Failed to load board", file=sys.stderr)
        sys.exit(3)
    open(args[args.index("-o") + 1], "w", newline="").write(config["ipcd356"])
    sys.exit(0)
if args[:2] == ["pcb", "upgrade"]:
    if config["upgrade"] == "fail":
        print("Failed to upgrade board", file=sys.stderr)
        sys.exit(1)
    board = args[-1]
    text = open(board, encoding="utf-8").read()
    open(board, "w", encoding="utf-8", newline="").write(text)
if args[:2] == ["pcb", "import"]:
    if config["imported"] is not None:
        open(args[args.index("-o") + 1], "w", encoding="utf-8", newline="").write(config["imported"])
        report = {"errors": [], "warnings": config["import_warnings"], "source_file": args[-1],
                  "source_format": "Altium Designer", "output_file": args[args.index("-o") + 1]}
        open(args[args.index("--report-file") + 1], "w", newline="").write(json.dumps(report))
        sys.stdout.write(config["import_output"])
    sys.exit(0)
if args[:2] == ["sch", "upgrade"]:
    sheet = args[-1]
    text = open(sheet, encoding="utf-8").read()
    open(sheet, "w", encoding="utf-8", newline="").write(text)
    sys.exit(0)
if args[:2] == ["sch", "erc"]:
    text = config["erc_report"]
    if config["erc_sequence"]:
        done = sum(1 for line in open(os.path.join(HERE, "calls.jsonl")) if '"sch", "erc"' in line)
        sequence = config["erc_sequence"]
        text = sequence[min(done, len(sequence)) - 1]
    if text == "":
        print("Failed to load schematic", file=sys.stderr)
        sys.exit(3)
    if text is None:
        text = json.dumps({"source": args[-1], "date": "2026-10-05", "kicad_version": config["version"],
                           "coordinate_units": "mm", "sheets": [
                               {"path": "/", "uuid_path": "/00000000-0000-4000-8000-000000000000",
                                "violations": []}]})
    open(args[args.index("-o") + 1], "w", newline="").write(text)
    sys.exit(0)
if args[:3] == ["sch", "export", "netlist"]:
    if config["netlist"] is None:
        print("Failed to load schematic", file=sys.stderr)
        sys.exit(3)
    open(args[args.index("-o") + 1], "w", encoding="utf-8", newline="").write(config["netlist"])
    sys.exit(0)
if args[:3] == ["sch", "export", "bom"]:
    if config["bom"] is None:
        print("Failed to load schematic", file=sys.stderr)
        sys.exit(3)
    open(args[args.index("-o") + 1], "w", encoding="utf-8", newline="").write(config["bom"])
    sys.exit(0)
kind = None
if args[:2] == ["pcb", "export"] and len(args) > 2:
    kind = args[2]
if args[:2] == ["pcb", "render"]:
    kind = "render"
if kind is not None and kind in config["export_files"]:
    out = args[args.index("-o") + 1]
    stem = os.path.splitext(os.path.basename(args[-1]))[0]
    folder = out if out.endswith("/") else os.path.dirname(out)
    if kind in config["export_fail"]:
        print("Failed to plot " + os.path.join(os.getcwd(), args[-1]), file=sys.stderr)
        sys.exit(1)
    if folder and not os.path.isdir(folder):
        print("Output folder is missing: " + folder, file=sys.stderr)
        sys.exit(1)
    wanted = config["export_files"][kind]
    for name, text in wanted.items():
        target = os.path.join(folder, name.replace("{stem}", stem)) if out.endswith("/") else out
        open(target, "w", encoding="latin-1", newline="").write(text)
    sys.exit(0)
if args[:2] == ["pcb", "drc"]:
    board = args[-1]
    asked = "--schematic-parity" in args
    if asked and config["parity_fail"]:
        print(config["parity_fail"], file=sys.stderr)
        sys.exit(255)
    if asked and config["parity_note"]:
        print(config["parity_note"], file=sys.stderr)
    if "--save-board" in args and config["refill_board"] is not None:
        open(board, "w", encoding="utf-8", newline="").write(config["refill_board"])
    if config["rewrite_input"] and "--save-board" not in args:
        open(board, "a", newline="").write("(rewritten)")
    if config["drc_sequence"]:
        done = sum(1 for line in open(os.path.join(HERE, "calls.jsonl")) if '"pcb", "drc"' in line)
        sequence = config["drc_sequence"]
        open(args[args.index("-o") + 1], "w", newline="").write(sequence[min(done, len(sequence)) - 1])
        sys.exit(0)
    if config["drc_report"] == "":
        print("Failed to load board", file=sys.stderr)
        sys.exit(3)
    if config["drc_report"] is not None:
        report = json.loads(config["drc_report"])
    else:
        uuids, rule = config["canary_uuids"], config["canary_rule"]
        text = files.get(os.path.basename(board), "")
        rules = "".join(v for k, v in files.items() if k.endswith(".kicad_dru"))
        violations = []
        if all(u in text for u in uuids) and rule in rules:
            items = [{"uuid": u, "description": "Track", "pos": {"x": 1, "y": 0}} for u in uuids]
            pair = {"type": "clearance", "description": "canary", "severity": "error", "items": items}
            violations.append(pair)
        report = {"source": board, "date": "2026-10-02", "kicad_version": config["version"],
                  "coordinate_units": "mm", "violations": violations, "unconnected_items": [],
                  "schematic_parity": []}
    if asked and config["parity"]:
        report["schematic_parity"] = config["parity"]
    open(args[args.index("-o") + 1], "w", newline="").write(json.dumps(report))
"""


def _png(width: int, height: int) -> str:
    """The first 24 bytes of a PNG of that size, as latin-1 text."""
    header = b"\x89PNG\r\n\x1a\n" + (13).to_bytes(4, "big") + b"IHDR"
    return (header + width.to_bytes(4, "big") + height.to_bytes(4, "big")).decode("latin-1")


GERBER = "%TF.GenerationSoftware,KiCad,Pcbnew,10.0.6*%\n%TF.CreationDate,2026-10-03T00:00:00+00:00*%\nM02*\n"
DRILL = "M48\n; DRILL file KiCad 10.0.6 date 2026-10-03T00:00:00+0000\nM30\n"
EXPORT_FILES: Mapping[str, Mapping[str, str]] = {
    "gerbers": {
        "{stem}-F_Cu.gbr": GERBER,
        "{stem}-Edge_Cuts.gbr": GERBER,
        "{stem}-job.gbrjob": '{\n  "Header": {\n    "CreationDate": "2026-10-03T00:00:00+00:00"\n  }\n}\n',
    },
    "drill": {"{stem}-PTH.drl": DRILL, "{stem}-NPTH.drl": DRILL},
    "pos": {"pos.csv": "Ref,Val,Package,PosX,PosY,Rot,Side\n"},
    "ipcd356": {"board.d356": "P  CODE 00\n999\n"},
    "svg": {"view.svg": '<svg xmlns="http://www.w3.org/2000/svg"/>\n'},
    "render": {"view.png": _png(320, 240)},
}
"""What the fake writes for each export kind when ``export_files`` is not given."""


EXAMPLE_NETLIST = (
    Path(__file__).resolve().parent / "data" / "kicad" / "netlist" / "export_10.net"
).read_text(encoding="utf-8")
"""The authored export that the fake writes for the examples of ``fenolite netlist`` (c0063); without a
``netlist`` argument the fake refuses the schematic."""


def fake_kicad_cli(
    folder: Path,
    *,
    version: str = "10.0.6",
    help_pages: Mapping[str, str] | None = None,
    drc_report: str | None = None,
    writes: Sequence[str] = (),
    rewrite_input: bool = False,
    sleep: float = 0.0,
    ipcd356: str | None = None,
    netlist: str | None = None,
    bom: str | None = None,
    upgrade: Literal["copy", "fail"] = "copy",
    log: Path | None = None,
    drc_sequence: Sequence[str] = (),
    refill_board: str | None = None,
    export_files: Mapping[str, Mapping[str, str]] | None = None,
    export_fail: Sequence[str] = (),
    imported: str | None = None,
    import_output: str = "",
    import_warnings: Sequence[str] = (),
    erc_report: str | None = None,
    erc_sequence: Sequence[str] = (),
    parity: Sequence[Mapping[str, Any]] = (),
    parity_fail: str = "",
    parity_note: str = "",
) -> Path:
    """An executable fake ``kicad-cli`` in ``folder`` (``help_pages`` keyed by the command words, ``""``
    for the root page).

    ``export_files`` maps an export kind (``gerbers``, ``drill``, ``pos``, ``ipcd356``, ``svg``, ``render``)
    to the files its run writes, name → text: under the ``-o`` folder when that argument ends with ``/``
    (``{stem}`` is the board's stem), else the first text at the ``-o`` path itself. The default is
    ``EXPORT_FILES``; a kind mapped to ``{}`` writes nothing, and a kind in ``export_fail`` exits 1."""
    folder.mkdir(parents=True, exist_ok=True)
    config = {
        "version": version,
        "help_pages": dict(help_pages or {}),
        "drc_report": drc_report,
        "writes": list(writes),
        "rewrite_input": rewrite_input,
        "sleep": sleep,
        "ipcd356": ipcd356,
        "netlist": netlist,
        "bom": bom,
        "upgrade": upgrade,
        "log": str(log) if log is not None else "",
        "drc_sequence": list(drc_sequence),
        "refill_board": refill_board,
        "canary_uuids": list(CANARY_UUIDS),
        "canary_rule": CANARY_RULE_NAME,
        "export_files": {
            k: dict(v) for k, v in (EXPORT_FILES if export_files is None else export_files).items()
        },
        "export_fail": list(export_fail),
        "imported": imported,
        "import_output": import_output,
        "import_warnings": list(import_warnings),
        "erc_report": erc_report,
        "erc_sequence": list(erc_sequence),
        "parity": [dict(entry) for entry in parity],
        "parity_fail": parity_fail,
        "parity_note": parity_note,
    }
    (folder / "config.json").write_text(json.dumps(config), encoding="utf-8")
    (folder / "fake.py").write_text(PROGRAM, encoding="utf-8")
    return fake_tool(folder / "kicad-cli", folder / "fake.py")


def calls(script: Path) -> list[dict[str, Any]]:
    """The calls the fake at ``script`` recorded, oldest first."""
    log = script.parent / "calls.jsonl"
    if not log.is_file():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]


def report_with(*violations: Mapping[str, Any]) -> str:
    """A DRC report text holding ``violations``."""
    return json.dumps({"source": "board.kicad_pcb", "date": "2026-10-02", "kicad_version": "10.0.6",
                       "coordinate_units": "mm", "violations": list(violations), "unconnected_items": [],
                       "schematic_parity": []})  # fmt: skip


def erc_report_with(*violations: Mapping[str, Any], sheets: Sequence[Mapping[str, Any]] = ()) -> str:
    """An ERC report text: ``violations`` on the root sheet ``/``, then the ``sheets`` given whole."""
    root = {"path": "/", "uuid_path": "/00000000-0000-4000-8000-000000000000", "violations": list(violations)}
    return json.dumps({"source": "board.kicad_sch", "date": "2026-10-05", "kicad_version": "10.0.6",
                       "coordinate_units": "mm", "sheets": [root, *sheets]})  # fmt: skip


def erc_entry(
    kind: str, uuid: str, *, severity: str = "error", x: float = 0.0, y: float = 0.0, description: str = "",
    excluded: bool | None = None,
) -> dict[str, Any]:  # fmt: skip
    """One violation of an ERC report with one item."""
    item = {"uuid": uuid, "description": "item", "pos": {"x": x, "y": y}}
    entry: dict[str, Any] = {
        "type": kind, "description": description or kind, "severity": severity, "items": [item]
    }  # fmt: skip
    if excluded is not None:
        entry["excluded"] = excluded
    return entry


__all__ = [
    "DRILL",
    "EXAMPLE_NETLIST",
    "EXPORT_FILES",
    "GERBER",
    "calls",
    "erc_entry",
    "erc_report_with",
    "fake_kicad_cli",
    "report_with",
]
