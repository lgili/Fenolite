# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite template build SPEC --target kicad|altium --out OUT`` and ``fenolite template import SRC
--target kicad --out OUT`` (capability ``sheet-templates``, "Template build command", "Template build for
Altium" and "Template import command"; user guide ``docs/sheet-templates.md``).

``build`` turns a ``*.sheet.toml`` specification into a drawing sheet. ``import`` reads an Altium sheet
template (``.SchDot``, or the template graphics of a ``.SchDoc``, change c0046) into the neutral drawing
sheet; a loss is refused without ``--allow-lossy``. Both write one ``.kicad_wks``; ``build --target altium``
(change c0087) writes one ``.SchDot`` for one of the specification's sizes instead.

The action is a positional argument with two choices, not a nested sub-parser: the dispatcher adds the
global options, ``--dry-run`` and ``--confirm`` to this command's own parser, so they parse after
``build SPEC …``. The command runs no ``kicad-cli``; its evidence is ``INFERRED`` (``H-K-WKS-CORNER``, and
``H-A-RD-SHT-SAME`` for an import).
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any, cast

from fenolite.backends.altium import schdot
from fenolite.backends.altium.read.sheet import import_sheet
from fenolite.backends.kicad.versions import LossyWriteError
from fenolite.backends.kicad.wks import WRITE_EVIDENCE, write_drawing_sheet
from fenolite.cli.api import Command, Context, PlannedWrite, Result
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.model.presentation import (
    DrawingSheet,
    PaperSize,
    SheetText,
    SheetToken,
    TitleBlock,
    split_tokens,
)
from fenolite.templates import (
    SheetSpec,
    build_sheet,
    example_path,
    layout,
    load_spec,
    page_size,
    resolve_text,
)

HELP = (
    "build a drawing sheet from a *.sheet.toml specification, or import an Altium sheet template (writes OUT)"
)
TARGETS = ("kicad", "altium")
ALTIUM_TARGET = "altium"
"""``build`` writes an Altium sheet template (``.SchDot``) for this target (change c0087)."""
ACTIONS = ("build", "import")
ISO_PAPERS = ("A0", "A1", "A2", "A3", "A4", "A5")
"""The paper names KiCad shows as they are; any other page shows ``User``."""
IMPORT_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-A-RD-SHT-SAME", "H-K-WKS-CORNER"))
"""No second reader of an Altium schematic exists, and the command does not open the sheet in KiCad."""


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/sheet-templates.md for the format."
    parser.add_argument("action", choices=ACTIONS, help="build a specification, or import an Altium template")
    parser.add_argument(
        "spec",
        metavar="FILE",
        help="SPEC, the *.sheet.toml specification (build); SRC, the .SchDot or .SchDoc file (import)",
    )
    parser.add_argument("--target", required=True, choices=TARGETS, help="the backend to write for")
    parser.add_argument("-o", "--out", required=True, metavar="OUT", help="the drawing-sheet file to write")
    parser.add_argument(
        "--size",
        metavar="NAME",
        default=None,
        help=f"build --target {ALTIUM_TARGET}: the size of the template, one of the sizes the specification "
        "lists (default: the first); a usage error otherwise",
    )
    parser.add_argument(
        "--altium-format",
        choices=schdot.FORMS,
        default=None,
        help=f"build --target {ALTIUM_TARGET}: the form of the template, binary (default) or ascii; a usage "
        "error otherwise",
    )


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    spec_arg = Path(args.spec)
    path = spec_arg if spec_arg.is_absolute() else ctx.cwd / spec_arg
    try:
        data = path.read_bytes()
    except OSError as exc:
        message = f"cannot read {args.spec}: {exc.strerror or exc}"
        raise CliError("FEN-3001", message, where=str(args.spec)) from None
    to_altium = args.target == ALTIUM_TARGET
    if args.action == "import" and to_altium:
        raise CliError(
            "FEN-2001",
            f"import writes a .kicad_wks; --target {ALTIUM_TARGET} is a target of build",
            where="--target",
            hint="use --target kicad",
        )
    for option, value in (("--size", args.size), ("--altium-format", args.altium_format)):
        if value is not None and not (to_altium and args.action == "build"):
            raise CliError(
                "FEN-2001",
                f"{option} is an option of build --target {ALTIUM_TARGET}",
                where=option,
                hint=f"drop {option}, or build with --target {ALTIUM_TARGET}",
            )
    if args.action == "import":
        return _import(args, ctx, data)
    issues: list[Issue] = []
    spec = load_spec(data.decode("utf-8"), file=str(args.spec))
    sheet = build_sheet(spec, base_dir=path.parent, issues=issues)
    if to_altium:
        return _build_altium(args, ctx, spec, sheet, issues, data)
    written = write_drawing_sheet(sheet, target=ctx.kicad_target, allow_lossy=ctx.allow_lossy)
    issues += written.issues
    empty = TitleBlock()
    drawn: dict[str, Any] = {}
    for size in spec.sizes:
        width, height = page_size(spec, size)
        drawn[size] = _drawn(sheet, size, width, height, empty)
    result: dict[str, Any] = {
        "sheet": {
            "name": sheet.name,
            "sizes": list(spec.sizes),
            "items": len(sheet.items),
            "tokens": _sheet_tokens(sheet),
        },
        "target": args.target,
        "kicad_version": ctx.kicad_target,
        "drawn": drawn,
        "output": str(args.out),
    }
    return Result(
        result=result,
        issues=tuple(issues),
        evidence=WRITE_EVIDENCE,
        input=InputRef(
            path=str(args.spec),
            sha256=hashlib.sha256(data).hexdigest(),
            kind="sheet-toml",
            format_version=None,
        ),
        writes=(PlannedWrite(path=str(args.out), data=written.text.encode("utf-8"), kind="kicad_wks"),),
    )


def _build_altium(
    args: argparse.Namespace,
    ctx: Context,
    spec: SheetSpec,
    sheet: DrawingSheet,
    issues: list[Issue],
    data: bytes,
) -> Result:
    """The target ``altium`` of ``build`` (change c0087, "Template build for Altium"): the sheet drawn on
    one of the specification's sizes and written as a ``.SchDot`` in the binary or the ASCII form."""
    size = cast(PaperSize, args.size or spec.sizes[0])
    if size not in spec.sizes:
        raise CliError(
            "FEN-2001",
            f"--size {size}: the specification lists {', '.join(spec.sizes)}",
            where="--size",
            hint="name one of the listed sizes, or add the size to sheet.sizes",
        )
    width, height = page_size(spec, size)
    paper = size if size in ISO_PAPERS else "User"
    form = cast(schdot.TemplateForm, args.altium_format or schdot.FORMS[0])
    written = schdot.write_template(
        sheet, width=width, height=height, paper=paper, form=form, allow_lossy=ctx.allow_lossy
    )
    made = written.result
    result: dict[str, Any] = {
        "sheet": {
            "name": sheet.name,
            "sizes": list(spec.sizes),
            "items": len(sheet.items),
            "tokens": _sheet_tokens(sheet),
        },
        "target": args.target,
        "drawn": {size: _drawn(sheet, size, width, height, TitleBlock())},
        "altium": {
            "format": form,
            "size": size,
            "width": width,
            "height": height,
            "lines": made.lines,
            "texts": made.texts,
            "parameters": list(made.parameters),
            "strings": list(made.strings),
        },
        "output": str(args.out),
    }
    return Result(
        result=result,
        issues=(*issues, *written.issues),
        evidence=schdot.EVIDENCE,
        input=InputRef(
            path=str(args.spec),
            sha256=hashlib.sha256(data).hexdigest(),
            kind="sheet-toml",
            format_version=None,
        ),
        writes=(PlannedWrite(path=str(args.out), data=written.data, kind=schdot.SCHDOT_KIND),),
    )


def _import(args: argparse.Namespace, ctx: Context, data: bytes) -> Result:
    """The action ``import``: an Altium sheet template read into the neutral sheet and written as ``OUT``."""
    imported = import_sheet(data, file=str(args.spec), name=Path(args.spec).stem, allow_lossy=ctx.allow_lossy)
    sheet, source = imported.sheet, imported.source
    try:
        written = write_drawing_sheet(sheet, target=ctx.kicad_target, allow_lossy=ctx.allow_lossy)
    except LossyWriteError as refusal:
        refusal.issues = (*imported.issues, *refusal.issues)
        raise
    setup = sheet.setup
    width = source.width + setup.left_margin + setup.right_margin
    height = source.height + setup.top_margin + setup.bottom_margin
    result: dict[str, Any] = {
        "sheet": {"name": sheet.name, "items": len(sheet.items), "tokens": _sheet_tokens(sheet)},
        "source": {
            "form": source.form,
            "style": source.style,
            "paper": source.paper,
            "portrait": source.portrait,
            "width": source.width,
            "height": source.height,
        },
        "imported": {str(kind): count for kind, count in imported.imported.items()},
        "reported": list(imported.reported),
        "strings": dict(imported.strings),
        "parameters": list(imported.parameters),
        "target": args.target,
        "kicad_version": ctx.kicad_target,
        "drawn": {source.paper: _drawn(sheet, source.paper, width, height, TitleBlock())},
        "output": str(args.out),
    }
    return Result(
        result=result,
        issues=(*imported.issues, *written.issues),
        evidence=IMPORT_EVIDENCE,
        input=InputRef(
            path=str(args.spec),
            sha256=hashlib.sha256(data).hexdigest(),
            kind="altium-sheet",
            format_version=None,
        ),
        writes=(PlannedWrite(path=str(args.out), data=written.text.encode("utf-8"), kind="kicad_wks"),),
    )


def _drawn(sheet: DrawingSheet, size: str, width: int, height: int, block: TitleBlock) -> dict[str, Any]:
    """What ``layout`` predicts on a ``width`` by ``height`` page named ``size``."""
    lay = layout(sheet, width=width, height=height)
    paper = size if size in ISO_PAPERS else "User"
    texts = [resolve_text(t.text, block, paper=paper, filename="") for t in lay.texts]
    return {"texts": len(lay.texts), "lines": len(lay.lines), "resolved": texts}


def _sheet_tokens(sheet: DrawingSheet) -> list[str]:
    return sorted({t for i in sheet.items if isinstance(i, SheetText) for t in _tokens(i.text)})


def _tokens(text: str) -> list[str]:
    return [f"param:{p.name}" if p.param else p.name for p in split_tokens(text) if isinstance(p, SheetToken)]


_EXAMPLE = str(example_path("iso5457_generic"))
COMMAND = Command(
    name="template",
    help=HELP,
    mutates=True,
    register=_register,
    run=_run,
    example_args=("build", _EXAMPLE, "--target", "kicad", "--out", "fenolite-sheet.kicad_wks", "--dry-run"),
    mutation_example_args=("build", _EXAMPLE, "--target", "kicad", "--out", "fenolite-sheet.kicad_wks"),
)
