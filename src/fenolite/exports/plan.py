# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""One ``kicad-cli`` call per export kind, and the artefacts it wrote (capability manufacturing-exports,
"Export kinds and their arguments"; facts: ``docs/formats/kicad/cli.md``, "Exports and renders").

Each kind has one fixed way to be exported. ``--check-zones`` and ``--board-plot-params`` are never
passed: the first would refill zones in the copy, the second would make the files depend on settings
stored in the board, and either way the files would not show the board as it is.

Change c0116 adds the six document kinds (IPC-2581, ODB++, STEP, board PDF and DXF per layer, schematic
PDF). They have no preset table, so the preset callback never reaches them; the STEP run gets the 3D
model files that ``backends.kicad.models`` locates, and the schematic PDF the sheets of the copy set.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Literal

from fenolite.backends.kicad import models as kicad_models
from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.models import ModelPlan, ModelUse
from fenolite.core.errors import Issue
from fenolite.exports import documents
from fenolite.exports.codes import issue
from fenolite.model.board import Layer
from fenolite.model.design import Design

MAJORS = (9, 10)
GERBER_EXTRA_LAYERS = ("F.Mask", "B.Mask", "F.Paste", "B.Paste", "F.SilkS", "B.SilkS")
"""Non-copper layers exported when the board has them, in this order; ``Edge.Cuts`` comes last."""
OUTLINE_LAYER = "Edge.Cuts"
FAB_LAYERS = ("F.Fab", "B.Fab")
COURTYARD_LAYERS = ("F.CrtYd", "B.CrtYd")
SHOWN_NAMES: Mapping[str, str] = MappingProxyType(
    {
        "F.SilkS": "F.Silkscreen",
        "B.SilkS": "B.Silkscreen",
        "F.CrtYd": "F.Courtyard",
        "B.CrtYd": "B.Courtyard",
        "F.Adhes": "F.Adhesive",
        "B.Adhes": "B.Adhesive",
    }
)
"""The name KiCad shows for a layer, and uses in file names, when the board's table gives no user name."""
JOB_SUFFIX = "-job.gbrjob"
Repeat = Literal["bytes", "content", "none"]
"""What two exports of one board share: their bytes, their bytes without the date-bearing lines of
``VOLATILE_PREFIXES``, or nothing that a hash can compare."""
Source = Literal["board", "schematic"]
LAYER_KINDS = ("pdf", "dxf")
"""The document kinds that write one file per layer and take ``run_kind(…, layers=…)``."""


@dataclass(frozen=True, slots=True)
class Kind:
    """An export kind: its ``kicad-cli`` words and fixed options, where it writes, what two runs of one
    board share (``repeat``) and which design file it is made from (``source``)."""

    name: str
    words: tuple[str, ...]
    options: tuple[str, ...]
    folder: str
    file: str = ""
    """The output file below ``folder`` (``{stem}`` is the board's stem); empty for a folder output."""
    repeat: Repeat = "bytes"
    source: Source = "board"
    majors: tuple[int, ...] = MAJORS

    @property
    def repeatable(self) -> bool:
        """Whether two runs give the same bytes."""
        return self.repeat == "bytes"


KINDS: Mapping[str, Kind] = MappingProxyType(
    {
        "gerbers": Kind(
            "gerbers", ("pcb", "export", "gerbers"), ("--no-protel-ext",), "gerbers", repeat="content"
        ),
        "drill": Kind(
            "drill",
            ("pcb", "export", "drill"),
            ("--format", "excellon", "--excellon-units", "mm", "--excellon-separate-th")
            + ("--drill-origin", "absolute"),
            "drill",
            repeat="content",
        ),
        "pos": Kind(
            "pos",
            ("pcb", "export", "pos"),
            ("--format", "csv", "--units", "mm", "--side", "both"),
            "pos",
            "{stem}-pos.csv",
        ),
        "ipcd356": Kind("ipcd356", ("pcb", "export", "ipcd356"), (), "netlist", "{stem}.d356"),
        "ipc2581": Kind(
            "ipc2581",
            ("pcb", "export", "ipc2581"),
            ("--version", "C", "--units", "mm", "--precision", "6"),
            "ipc2581",
            "{stem}.xml",
            repeat="none",
        ),
        "odb": Kind(
            "odb",
            ("pcb", "export", "odb"),
            ("--compression", "zip", "--units", "mm"),
            "odb",
            "{stem}.zip",
            repeat="none",
        ),
        "step": Kind(
            "step", ("pcb", "export", "step"), ("--subst-models",), "3d", "{stem}.step", repeat="none"
        ),
        "pdf": Kind("pdf", ("pcb", "export", "pdf"), ("--mode-separate",), "pdf", repeat="content"),
        "dxf": Kind("dxf", ("pcb", "export", "dxf"), ("--mode-multi", "--output-units", "mm"), "dxf"),
        "sch-pdf": Kind(
            "sch-pdf",
            ("sch", "export", "pdf"),
            (),
            "schematic",
            "{stem}.pdf",
            repeat="content",
            source="schematic",
        ),
    }
)
"""The four fabrication kinds of v0.1 and the six document kinds of c0116, in the order they run."""
FAB_KINDS = ("gerbers", "drill", "pos", "ipcd356")
"""The kinds ``export --all`` selects, and the only ones an export preset reaches."""
DOCUMENT_KINDS = ("ipc2581", "odb", "step", "pdf", "dxf", "sch-pdf")
"""The document kinds: each is selected by its own flag and runs with one fixed argument list."""

VOLATILE_PREFIXES: Mapping[str, tuple[bytes, ...]] = MappingProxyType(
    {
        "gerbers": (b"%TF.CreationDate", b"G04 Created by KiCad", b'"CreationDate":'),
        "drill": (b"; DRILL file", b"; #@! TF.CreationDate"),
        "pos": (),
        "ipcd356": (),
        "ipc2581": (),
        "odb": (),
        "step": (),
        "pdf": (b"/CreationDate",),
        "dxf": (),
        "sch-pdf": (b"/CreationDate",),
    }
)
"""Per kind, the starts of the lines that carry the creation date (leading blanks ignored). A kind whose
``repeat`` is ``none`` has no prefix: its content hash is the hash of its bytes."""


@dataclass(frozen=True, slots=True)
class Artifact:
    """A file an export wrote: its path below the output folder, its kind, the layer of a Gerber or of a
    per-layer PDF or DXF, its bytes as KiCad wrote them, and whether two runs give the same bytes."""

    path: str
    kind: str
    layer: str | None
    data: bytes
    repeatable: bool


@dataclass(frozen=True, slots=True)
class KindResult:
    """One kind's run: its artefacts (sorted by path), its issues, the files the tool wrote outside the
    kind's output folder, and for ``step`` the 3D models of the board with their sources."""

    artifacts: tuple[Artifact, ...] = ()
    issues: tuple[Issue, ...] = ()
    tool_writes: tuple[str, ...] = ()
    models: tuple[ModelUse, ...] = ()


def _user_name(layer: Layer) -> str | None:
    ext = layer.ext.get("kicad")
    return None if ext is None else dict(ext.payload).get("user_name")


def gerber_layers(design: Design) -> tuple[str, ...]:
    """The layers a Gerber export plots: the copper layers in stack order, then the mask, paste and
    silkscreen pairs the board has, then ``Edge.Cuts``."""
    layers = design.board.layers if design.board is not None else ()
    copper = [layer.name for layer in sorted(layers, key=lambda la: la.ordinal) if layer.kind == "copper"]
    names = {layer.name for layer in layers}
    return (*copper, *(name for name in GERBER_EXTRA_LAYERS if name in names), OUTLINE_LAYER)


def _present(design: Design, names: Sequence[str]) -> tuple[str, ...]:
    found = {layer.name for layer in (design.board.layers if design.board is not None else ())}
    return tuple(name for name in names if name in found)


def pdf_layers(design: Design) -> tuple[str, ...]:
    """The layers a board PDF plots, one file each: those of ``gerber_layers`` with the fabrication pair
    the board has before ``Edge.Cuts``."""
    return (*gerber_layers(design)[:-1], *_present(design, FAB_LAYERS), OUTLINE_LAYER)


def dxf_layers(design: Design) -> tuple[str, ...]:
    """The layers a DXF export plots, one file each: ``Edge.Cuts``, then the fabrication and courtyard
    pairs the board has (the outline and the part outlines that an enclosure is drawn against)."""
    return (OUTLINE_LAYER, *_present(design, (*FAB_LAYERS, *COURTYARD_LAYERS)))


def layer_suffixes(design: Design) -> dict[str, str]:
    """File-name suffix → canonical layer name, through the canonical, user and shown names."""
    found: dict[str, str] = {}
    for layer in design.board.layers if design.board is not None else ():
        for name in (layer.name, _user_name(layer), SHOWN_NAMES.get(layer.name)):
            if name:
                found.setdefault(name.replace(".", "_"), layer.name)
    return found


def arguments(kind: str, *, stem: str, layers: Sequence[str] = ()) -> list[str]:
    """The ``kicad-cli`` arguments of ``kind`` without the input file name; the same on 9.0 and 10.0."""
    entry = KINDS[kind]
    out = f"{entry.folder}/{entry.file.format(stem=stem)}"
    args = [*entry.words, "-o", out, *entry.options]
    if kind == "gerbers" or kind in LAYER_KINDS:
        args += ["--layers", ",".join(layers)]
    if kind == "pdf":
        args += ["--common-layers", OUTLINE_LAYER, "--include-border-title"]
    return args


def _first_line(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[0].replace("<tmp>/", "").replace("<tmp>", ".") if lines else ""


def _layer(path: str, stem: str, suffixes: Mapping[str, str]) -> str | None:
    name = Path(path).name
    if name.endswith(JOB_SUFFIX) or not name.startswith(f"{stem}-"):
        return None
    return suffixes.get(Path(name).stem[len(stem) + 1 :])


def _default_layers(kind: str, design: Design | None) -> tuple[str, ...]:
    if design is None:
        return ()
    if kind == "pdf":
        return pdf_layers(design)
    return dxf_layers(design) if kind == "dxf" else gerber_layers(design)


def _unread(plan: ModelPlan, output: str) -> list[Issue]:
    """One ``export.model-unread`` per reference that ``kicad-cli`` reports without a body although
    every model file of it was given."""
    located = kicad_models.located_refs(plan.uses)
    return [
        issue(
            "export.model-unread",
            f"kicad-cli could not add the 3D model of {ref}, although Fenolite gave it the file",
            where=ref,
            hint="run 'fenolite models' on the board to see the file, and open it in KiCad",
        )
        for ref in kicad_models.unread_refs(output)
        if ref in located
    ]


def run_kind(
    cli: KicadCli,
    kind: str,
    board: Path,
    files: Mapping[str, Path],
    *,
    major: int,
    design: Design | None = None,
    args: Callable[[str, str, Sequence[str]], Sequence[str]] | None = None,
    layers: Sequence[str] | None = None,
    models: ModelPlan | None = None,
) -> KindResult:
    """Export ``kind`` from a copy of ``board`` (``files`` are the rest of its copy set); ``design`` is the
    board's model, needed for the layers of a Gerber, PDF or DXF export. ``args(kind, stem, layers)``
    replaces the fixed arguments of a fabrication kind: it is how an export preset reaches the run
    (``exports.preset``), and it is never called for a document kind. ``layers`` replaces the layer list
    of ``pdf`` or ``dxf`` (``ValueError`` for any other kind). ``models`` is the model plan of a ``step``
    run; without it the plan is built from the board."""
    entry = KINDS[kind]
    if layers is not None and kind not in LAYER_KINDS:
        raise ValueError(f"the {kind} export takes no layer list")
    if major not in entry.majors:
        message = f"kicad-cli {major}.0 cannot export {kind}"
        return KindResult(issues=(issue("export.kind-unavailable", message, where=kind),))
    board = Path(board)
    stem = board.stem
    plotted = tuple(layers) if layers is not None else _default_layers(kind, design)
    if args is None or kind in DOCUMENT_KINDS:
        wanted = arguments(kind, stem=stem, layers=plotted)
    else:
        wanted = list(args(kind, stem, plotted))
    given: dict[str, Path] = {board.name: board, **{name: Path(path) for name, path in files.items()}}
    notes: list[Issue] = []
    subject = board.name
    plan: ModelPlan | None = None
    if kind == "sch-pdf":
        sheets = documents.schematic_files(board)
        if sheets.issues:
            return KindResult(issues=sheets.issues)
        subject = sheets.root
        given.setdefault(subject, board.parent / subject)
    elif kind == "step":
        plan = models if models is not None else kicad_models.board_plan(board, major=major)
        given.update({name: Path(path) for name, path in plan.files.items() if name not in given})
        notes += plan.issues
    elif kind == "pdf" and design is not None:
        page = documents.page_check(design)
        notes += [] if page is None else [page]
    uses = plan.uses if plan is not None else ()
    env = plan.env if plan is not None else None
    run = cli.run([*wanted, subject], files=given, env=env, folders=(entry.folder,))
    prefix = f"{entry.folder}/"
    produced = {name: data for name, data in run.outputs.items() if name.startswith(prefix)}
    tool_writes = tuple(sorted(name for name in run.outputs if name not in produced))
    if run.outcome == "timeout":
        failure = issue("export.failed", f"kicad-cli timed out after {cli.timeout:g} s", where=kind,
                        retryable=True)  # fmt: skip
        return KindResult(issues=(*notes, failure), tool_writes=tool_writes, models=uses)
    if run.returncode != 0 or not produced:
        detail = _first_line(run.stderr or run.stdout) or "kicad-cli wrote no file"
        failure = issue("export.failed", f"exit {run.returncode}: {detail}", where=kind)
        return KindResult(issues=(*notes, failure), tool_writes=tool_writes, models=uses)
    if plan is not None:
        notes += _unread(plan, f"{run.stdout}\n{run.stderr}")
    by_layer = kind == "gerbers" or kind in LAYER_KINDS
    suffixes = layer_suffixes(design) if design is not None and by_layer else {}
    artifacts = tuple(
        Artifact(name, kind, _layer(name, stem, suffixes), produced[name], entry.repeatable)
        for name in sorted(produced)
    )
    return KindResult(artifacts=artifacts, issues=tuple(notes), tool_writes=tool_writes, models=uses)


__all__ = [
    "DOCUMENT_KINDS",
    "FAB_KINDS",
    "GERBER_EXTRA_LAYERS",
    "JOB_SUFFIX",
    "KINDS",
    "LAYER_KINDS",
    "MAJORS",
    "SHOWN_NAMES",
    "VOLATILE_PREFIXES",
    "Artifact",
    "Kind",
    "KindResult",
    "Repeat",
    "arguments",
    "dxf_layers",
    "gerber_layers",
    "layer_suffixes",
    "pdf_layers",
    "run_kind",
]
