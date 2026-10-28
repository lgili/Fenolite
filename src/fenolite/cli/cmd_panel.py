# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite panel PANEL.py --out DIR --target {9,10,altium}``: several copies of one built board in one
panel (capability cli-contract, "Panel command"; ``docs/cli-contract.md``, "panel"; ``docs/panels.md``;
change c0173).

The command runs the panel script in-process (as ``build`` runs a design script), reads the board it names,
lays the panel out and checks it (``fenolite.panel``). An error finding plans no write: exit 5. Otherwise
every file of the panel is planned under ``DIR`` and written under ``--confirm``, all or none. A file that a
previous run wrote and that was edited since is refused (``panel.output-changed``) unless
``--discard-layout`` replaces it: ``.fenolite/<name>.panel-written.json`` records what was written.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import fenolite
from fenolite.cli._manifest import joined
from fenolite.cli._script import DesignScriptError, run_panel_script
from fenolite.cli.api import Command, Context, PlannedWrite, Result, depends_on
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence
from fenolite.geometry.errors import BackendUnavailable
from fenolite.panel import build as panel_build
from fenolite.panel.build import PanelOutput

HELP = "write a panel of copies of one built board"
TARGETS = ("9", "10", "altium")
ALTIUM_FORMS = ("auto", "embedded", "flat")
POURS = ("computed", "outline")
"""The values of ``--altium-pour`` (change c0215), as for ``build``."""
RECORD = ".fenolite/{name}.panel-written.json"
EVIDENCE_KICAD = panel_build.EVIDENCE
"""A KiCad panel board: loaded, drilled and net-checked by kicad-cli 9.0.9 and 10.0.6 (task 4.2)."""
EVIDENCE_FLAT = panel_build.EVIDENCE_FLAT
"""A flattened Altium panel: imported by kicad-cli 10.0.6 at the KiCad panel's places (task 6.2)."""
EXAMPLE_PANEL = str(Path(fenolite.__file__).resolve().parents[2] / "tests/data/panels/tabs.py")
EXAMPLE_OUT = "fenolite-panel"
KINDS = {
    ".kicad_pcb": "kicad_pcb",
    ".kicad_pro": "kicad_pro",
    ".kicad_dru": "kicad_dru",
    ".kicad_mod": "kicad_mod",
    ".json": "json",
    ".pcbdoc": "altium_pcbdoc",
    ".prjpcb": "altium_prjpcb",
}


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/cli-contract.md, 'panel'."
    parser.add_argument("panel", metavar="PANEL.py", help="the panel script (run in-process)")
    parser.add_argument("--out", required=True, metavar="DIR", help="the output folder")
    parser.add_argument("--target", required=True, choices=TARGETS, help="KiCad major or altium")
    parser.add_argument(
        "--altium-panel",
        choices=ALTIUM_FORMS,
        help="the Altium form (default auto)",
    )
    parser.add_argument(
        "--altium-pour",
        choices=POURS,
        help="with --target altium: computed pours the polygons with Altium's rules (default, "
        "experimental; needs the geo extra, without which the default writes the outline with a warning), "
        "outline writes them unpoured",
    )
    parser.add_argument("--discard-layout", action="store_true", help="replace files edited since")


def _absolute(given: str, ctx: Context) -> Path:
    path = Path(given)
    return Path(os.path.abspath(path if path.is_absolute() else ctx.cwd / path))


def _kind(name: str) -> str:
    if name == "fp-lib-table":
        return "fp_lib_table"
    return KINDS.get(Path(name).suffix.lower(), "file")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _edited(out: Path, name: str, files: dict[str, bytes]) -> list[Issue]:
    """``panel.output-changed`` for each file a previous run wrote and that differs from what it wrote."""
    record = out / RECORD.format(name=name)
    if not record.is_file():
        return []
    try:
        written: dict[str, str] = json.loads(record.read_text(encoding="utf-8")).get("files", {})
    except (OSError, ValueError):
        return []
    found: list[Issue] = []
    for key in sorted(files):
        path = out / key
        if key in written and path.is_file() and _sha(path.read_bytes()) != written[key]:
            found.append(
                Issue(
                    "panel.output-changed",
                    "error",
                    f"{key} was changed since the last run; nothing is replaced",
                    where=key,
                    hint="run again with --discard-layout to replace it (a .bak copy is kept)",
                )
            )
    return found


def _record(name: str, files: dict[str, bytes]) -> bytes:
    data = {"panel": name, "files": {key: _sha(value) for key, value in sorted(files.items())}}
    return (json.dumps(data, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _summary(output: PanelOutput, target: str) -> dict[str, Any]:
    laid = output.layout
    rows = sum(len({h.x if t.axis == "y" else h.y for h in t.holes}) for t in laid.tabs)
    return {
        "target": target,
        "form": output.form,
        "rows": laid.rows,
        "cols": laid.cols,
        "copies": len(laid.copies),
        "rotation": laid.rotation,
        "size": {"w": laid.size.w, "h": laid.size.h},
        "unused": {"w": laid.unused.w, "h": laid.unused.h},
        "separations": dict(sorted(laid.methods.items())),
        "items": {
            "tabs": len(laid.tabs),
            "mouse_bite_rows": rows,
            "mouse_bite_holes": sum(len(t.holes) for t in laid.tabs),
            "score_lines": len(laid.score_lines),
            "fiducials": len(laid.fiducials),
            "tooling_holes": len(laid.tooling_holes),
        },
        "score_layer": output.score_layer,
        **({"pour": _pour(output)} if output.form == "flat" else {}),
    }


def _pour(output: PanelOutput) -> dict[str, Any]:
    """``panel.pour`` of a flattened Altium panel (change c0215), as ``result.pcb.pour`` of a build."""
    summary = output.pour.pour if output.pour is not None else None
    if summary is None:
        return {"mode": "outline", "poured": 0, "unpoured": {}, "evidence": None, "hypotheses": []}
    return {"mode": "computed", **summary.to_json()}


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    script = _absolute(args.panel, ctx)
    if not script.is_file():
        raise CliError("FEN-3001", f"{script.name} does not exist", where=script.name)
    if args.altium_panel is not None and args.target != "altium":
        raise CliError(
            "FEN-2001",
            "--altium-panel is for --target altium",
            where="--altium-panel",
            hint="drop --altium-panel",
        )
    if args.altium_pour is not None and args.target != "altium":
        raise CliError(
            "FEN-2001",
            "--altium-pour is for --target altium",
            where="--altium-pour",
            hint="drop --altium-pour",
        )
    try:
        run = run_panel_script(script)
    except DesignScriptError:
        raise
    dsl = run.panel
    source = (script.parent / dsl.board).resolve()
    if not source.is_file():
        raise CliError(
            "FEN-3001", f"the board {dsl.board} named by the panel does not exist", where=dsl.board
        )
    if dsl.backend == "altium" and args.target != "altium":
        raise CliError(
            "FEN-2001",
            f"{dsl.board} is an Altium document: a KiCad panel needs a .kicad_pcb",
            where="--target",
            hint="name the board built for KiCad, or use --target altium",
        )
    model = dsl.to_model()
    if model.array.mirrored and not (args.target == "altium" and args.altium_panel == "embedded"):
        raise CliError(
            "FEN-7001",
            "mirror=True is Altium's Mirrored property of an Embedded Board Array; no other form holds it",
            where="grid",
            hint="drop mirror=True",
        )
    out = _absolute(args.out, ctx)
    output = _output(model, source, args)
    issues: list[Issue] = [*output.issues, *output.notes]
    files = dict(output.files)
    if files and not args.discard_layout:
        issues += _edited(out, model.name, files)
    refused = any(i.severity == "error" for i in issues)
    writes: tuple[PlannedWrite, ...] = ()
    if not refused:
        files[RECORD.format(name=model.name)] = _record(model.name, files)
        writes = tuple(
            PlannedWrite(path=joined(args.out, key), data=data, kind=_kind(key))
            for key, data in sorted(files.items())
        )
    result: dict[str, Any] = {
        "name": model.name,
        "board": dsl.board,
        "out": args.out,
        "panel": _summary(output, args.target),
        "files": [{"name": key, "bytes": len(value)} for key, value in sorted(files.items())]
        if not refused
        else [],
        "script_output": run.output,
    }
    return Result(
        result=result,
        issues=tuple(issues),
        evidence=_evidence(output),
        input=InputRef(
            path=script.name, sha256=_sha(script.read_bytes()), kind="fenolite-panel", format_version=None
        ),
        writes=writes,
        depends=depends_on(ctx.cwd, script, source),
    )


def _output(model: Any, source: Path, args: argparse.Namespace) -> PanelOutput:
    from fenolite.backends.altium.pcbdoc import EMBEDDED_ARRAYS
    from fenolite.panel.build import altium_panel, kicad_panel

    if args.target == "altium":
        if args.altium_panel == "embedded" and (not EMBEDDED_ARRAYS or source.suffix.lower() != ".pcbdoc"):
            reason = (
                "the Embedded Board Array waits on the maintainer's kit (pcbdoc.EMBEDDED_ARRAYS is off)"
                if not EMBEDDED_ARRAYS
                else "an Embedded Board Array references a .PcbDoc, and the board is a .kicad_pcb"
            )
            raise CliError("FEN-7001", reason, where="--altium-panel", hint="use --altium-panel flat")
        try:
            return altium_panel(model, source, pour=args.altium_pour)
        except BackendUnavailable as error:
            raise CliError(
                "FEN-6001",
                "--altium-pour computed needs the geo extra, which is not installed",
                where="--altium-pour",
                hint="pip install 'fenolite[geo]', or use --altium-pour outline",
            ) from error
    try:
        return kicad_panel(model, source, target=int(args.target))
    except ValueError as error:
        from fenolite.panel.kicad import PanelWriteError

        if isinstance(error, PanelWriteError):
            raise CliError(
                "FEN-2001", str(error), where="--target", hint="build the board for that KiCad major"
            ) from error
        raise


def _evidence(output: PanelOutput) -> Evidence:
    if output.form == "kicad":
        return EVIDENCE_KICAD
    summary = output.pour.pour if output.pour is not None else None
    if summary is not None and summary.poured:
        return Evidence.combine(EVIDENCE_FLAT, summary.evidence)
    return EVIDENCE_FLAT


COMMAND = Command(
    name="panel",
    help=HELP,
    mutates=True,
    register=_register,
    run=_run,
    example_args=(EXAMPLE_PANEL, "--out", EXAMPLE_OUT, "--target", "10", "--dry-run"),
    mutation_example_args=(EXAMPLE_PANEL, "--out", EXAMPLE_OUT, "--target", "10"),
)
