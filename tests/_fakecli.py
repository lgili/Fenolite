# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A fake ``kicad-cli`` for hermetic tests of ``check``, ``doctor`` and the oracle (change c0013 Decision 19).

The fake is a ``#!/bin/sh`` wrapper around a Python script, as in c0009's runner tests. It answers
``version``, ``<words> --help`` from ``help_pages`` and ``pcb drc``. Without ``drc_report`` its DRC report
holds no violation, plus the canary ``clearance`` pair when the board it got holds both canary tracks
and a rules file next to it holds the canary rule, as KiCad would report them. ``drc_report=""`` writes no
report and exits 3. Every call appends ``{"args", "files"}`` to ``<folder>/calls.jsonl``: the arguments
and the text of each board and rules file in the run folder.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from fenolite.backends.kicad.canary import CANARY_RULE_NAME, CANARY_UUIDS

PROGRAM = """import json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
config = json.load(open(os.path.join(HERE, "config.json")))
args = sys.argv[1:]
files = {}
for name in sorted(os.listdir(".")):
    if name.endswith((".kicad_pcb", ".kicad_dru", ".kicad_pro")) and os.path.isfile(name):
        files[name] = open(name, encoding="utf-8", errors="replace").read()
with open(os.path.join(HERE, "calls.jsonl"), "a") as log:
    log.write(json.dumps({"args": args, "files": files}) + "\\n")
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
    open(name, "w").write("{}")
if args[:2] == ["pcb", "drc"]:
    board = args[-1]
    if config["rewrite_input"]:
        open(board, "a").write("(rewritten)")
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
    open(args[args.index("-o") + 1], "w").write(json.dumps(report))
"""


def fake_kicad_cli(
    folder: Path,
    *,
    version: str = "10.0.6",
    help_pages: Mapping[str, str] | None = None,
    drc_report: str | None = None,
    writes: Sequence[str] = (),
    rewrite_input: bool = False,
    sleep: float = 0.0,
) -> Path:
    """An executable fake ``kicad-cli`` in ``folder`` (``help_pages`` keyed by the command words, ``""``
    for the root page)."""
    folder.mkdir(parents=True, exist_ok=True)
    config = {
        "version": version,
        "help_pages": dict(help_pages or {}),
        "drc_report": drc_report,
        "writes": list(writes),
        "rewrite_input": rewrite_input,
        "sleep": sleep,
        "canary_uuids": list(CANARY_UUIDS),
        "canary_rule": CANARY_RULE_NAME,
    }
    (folder / "config.json").write_text(json.dumps(config), encoding="utf-8")
    (folder / "fake.py").write_text(PROGRAM, encoding="utf-8")
    script = folder / "kicad-cli"
    script.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{folder / "fake.py"}" "$@"\n', encoding="utf-8")
    script.chmod(0o755)
    return script


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


__all__ = ["calls", "fake_kicad_cli", "report_with"]
