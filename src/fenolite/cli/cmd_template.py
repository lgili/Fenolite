# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite template build SPEC --target kicad --out OUT``: a ``*.sheet.toml`` specification built into a
drawing sheet (capability ``sheet-templates``, "Template build command"; user guide
``docs/sheet-templates.md``).

``build`` is a positional argument with a single choice, not a nested sub-parser: the dispatcher adds the
global options, ``--dry-run`` and ``--confirm`` to this command's own parser, so they parse after
``build SPEC …``. The command runs no ``kicad-cli``; its evidence is ``INFERRED`` (``H-K-WKS-CORNER``).
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any

from fenolite.backends.kicad.wks import WRITE_EVIDENCE, write_drawing_sheet
from fenolite.cli.api import Command, Context, PlannedWrite, Result
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.errors import Issue
from fenolite.model.presentation import SheetText, SheetToken, TitleBlock, split_tokens
from fenolite.templates import build_sheet, example_path, layout, load_spec, page_size, resolve_text

HELP = "build a drawing sheet from a *.sheet.toml specification (writes OUT)"
TARGETS = ("kicad",)


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/sheet-templates.md for the format."
    parser.add_argument("action", choices=("build",), help="the action: build")
    parser.add_argument("spec", metavar="SPEC", help="the *.sheet.toml specification")
    parser.add_argument("--target", required=True, choices=TARGETS, help="the backend to write for")
    parser.add_argument("-o", "--out", required=True, metavar="OUT", help="the drawing-sheet file to write")


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    spec_arg = Path(args.spec)
    path = spec_arg if spec_arg.is_absolute() else ctx.cwd / spec_arg
    try:
        data = path.read_bytes()
    except OSError as exc:
        message = f"cannot read {args.spec}: {exc.strerror or exc}"
        raise CliError("FEN-3001", message, where=str(args.spec)) from None
    issues: list[Issue] = []
    spec = load_spec(data.decode("utf-8"), file=str(args.spec))
    sheet = build_sheet(spec, base_dir=path.parent, issues=issues)
    written = write_drawing_sheet(sheet, target=ctx.kicad_target, allow_lossy=ctx.allow_lossy)
    issues += written.issues
    empty = TitleBlock()
    drawn: dict[str, Any] = {}
    for size in spec.sizes:
        width, height = page_size(spec, size)
        lay = layout(sheet, width=width, height=height)
        paper = size if size in ("A0", "A1", "A2", "A3", "A4", "A5") else "User"
        texts = [resolve_text(t.text, empty, paper=paper, filename="") for t in lay.texts]
        drawn[size] = {"texts": len(lay.texts), "lines": len(lay.lines), "resolved": texts}
    tokens = sorted({t for i in sheet.items if isinstance(i, SheetText) for t in _tokens(i.text)})
    result: dict[str, Any] = {
        "sheet": {"name": sheet.name, "sizes": list(spec.sizes), "items": len(sheet.items), "tokens": tokens},
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
