# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""One ``kicad-cli`` call per export kind, and the artefacts it wrote (capability manufacturing-exports,
"Export kinds and their arguments"; facts: ``docs/formats/kicad/cli.md``, "Exports and renders").

Each kind has one fixed way to be exported. ``--check-zones`` and ``--board-plot-params`` are never
passed: the first would refill zones in the copy, the second would make the files depend on settings
stored in the board, and either way the files would not show the board as it is.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from fenolite.backends.kicad.cli import KicadCli
from fenolite.core.errors import Issue
from fenolite.exports.codes import issue
from fenolite.model.board import Layer
from fenolite.model.design import Design

MAJORS = (9, 10)
GERBER_EXTRA_LAYERS = ("F.Mask", "B.Mask", "F.Paste", "B.Paste", "F.SilkS", "B.SilkS")
"""Non-copper layers exported when the board has them, in this order; ``Edge.Cuts`` comes last."""
OUTLINE_LAYER = "Edge.Cuts"
SHOWN_NAMES: Mapping[str, str] = MappingProxyType({"F.SilkS": "F.Silkscreen", "B.SilkS": "B.Silkscreen"})
"""The name KiCad shows for a layer, and uses in file names, when the board's table gives no user name."""
JOB_SUFFIX = "-job.gbrjob"


@dataclass(frozen=True, slots=True)
class Kind:
    """An export kind: its ``kicad-cli`` words and fixed options, where it writes, and whether two runs
    give the same bytes."""

    name: str
    words: tuple[str, ...]
    options: tuple[str, ...]
    folder: str
    file: str = ""
    """The output file below ``folder`` (``{stem}`` is the board's stem); empty for a folder output."""
    repeatable: bool = True
    majors: tuple[int, ...] = MAJORS


KINDS: Mapping[str, Kind] = MappingProxyType(
    {
        "gerbers": Kind(
            "gerbers", ("pcb", "export", "gerbers"), ("--no-protel-ext",), "gerbers", repeatable=False
        ),
        "drill": Kind(
            "drill",
            ("pcb", "export", "drill"),
            ("--format", "excellon", "--excellon-units", "mm", "--excellon-separate-th")
            + ("--drill-origin", "absolute"),
            "drill",
            repeatable=False,
        ),
        "pos": Kind(
            "pos",
            ("pcb", "export", "pos"),
            ("--format", "csv", "--units", "mm", "--side", "both"),
            "pos",
            "{stem}-pos.csv",
        ),
        "ipcd356": Kind("ipcd356", ("pcb", "export", "ipcd356"), (), "netlist", "{stem}.d356"),
    }
)
"""The four kinds of v0.1, in the order they run."""

VOLATILE_PREFIXES: Mapping[str, tuple[bytes, ...]] = MappingProxyType(
    {
        "gerbers": (b"%TF.CreationDate", b"G04 Created by KiCad", b'"CreationDate":'),
        "drill": (b"; DRILL file", b"; #@! TF.CreationDate"),
        "pos": (),
        "ipcd356": (),
    }
)
"""Per kind, the starts of the lines that carry the creation date (leading blanks ignored)."""


@dataclass(frozen=True, slots=True)
class Artifact:
    """A file an export wrote: its path below the output folder, its kind, the layer of a Gerber, its
    bytes as KiCad wrote them, and whether two runs give the same bytes."""

    path: str
    kind: str
    layer: str | None
    data: bytes
    repeatable: bool


@dataclass(frozen=True, slots=True)
class KindResult:
    """One kind's run: its artefacts (sorted by path), its issues, and the files the tool wrote outside
    the kind's output folder."""

    artifacts: tuple[Artifact, ...] = ()
    issues: tuple[Issue, ...] = ()
    tool_writes: tuple[str, ...] = ()


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


def layer_suffixes(design: Design) -> dict[str, str]:
    """File-name suffix → canonical layer name, through the canonical, user and shown names."""
    found: dict[str, str] = {}
    for layer in design.board.layers if design.board is not None else ():
        for name in (layer.name, _user_name(layer), SHOWN_NAMES.get(layer.name)):
            if name:
                found.setdefault(name.replace(".", "_"), layer.name)
    return found


def arguments(kind: str, *, stem: str, layers: Sequence[str] = ()) -> list[str]:
    """The ``kicad-cli`` arguments of ``kind`` without the board name; the same on 9.0 and 10.0."""
    entry = KINDS[kind]
    out = f"{entry.folder}/{entry.file.format(stem=stem)}"
    args = [*entry.words, "-o", out, *entry.options]
    if kind == "gerbers":
        args += ["--layers", ",".join(layers)]
    return args


def _first_line(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[0].replace("<tmp>/", "").replace("<tmp>", ".") if lines else ""


def _layer(path: str, stem: str, suffixes: Mapping[str, str]) -> str | None:
    name = Path(path).name
    if name.endswith(JOB_SUFFIX) or not name.startswith(f"{stem}-"):
        return None
    return suffixes.get(Path(name).stem[len(stem) + 1 :])


def run_kind(
    cli: KicadCli,
    kind: str,
    board: Path,
    files: Mapping[str, Path],
    *,
    major: int,
    design: Design | None = None,
) -> KindResult:
    """Export ``kind`` from a copy of ``board`` (``files`` are the rest of its copy set); ``design`` is the
    board's model, needed for the layers of a Gerber export."""
    entry = KINDS[kind]
    if major not in entry.majors:
        message = f"kicad-cli {major}.0 cannot export {kind}"
        return KindResult(issues=(issue("export.kind-unavailable", message, where=kind),))
    stem = Path(board).stem
    layers = gerber_layers(design) if design is not None else ()
    run = cli.export(arguments(kind, stem=stem, layers=layers), board, files=files, out=entry.folder)
    prefix = f"{entry.folder}/"
    produced = {name: data for name, data in run.outputs.items() if name.startswith(prefix)}
    tool_writes = tuple(sorted(name for name in run.outputs if name not in produced))
    if run.outcome == "timeout":
        failure = issue("export.failed", f"kicad-cli timed out after {cli.timeout:g} s", where=kind,
                        retryable=True)  # fmt: skip
        return KindResult(issues=(failure,), tool_writes=tool_writes)
    if run.returncode != 0 or not produced:
        detail = _first_line(run.stderr or run.stdout) or "kicad-cli wrote no file"
        failure = issue("export.failed", f"exit {run.returncode}: {detail}", where=kind)
        return KindResult(issues=(failure,), tool_writes=tool_writes)
    suffixes = layer_suffixes(design) if design is not None and kind == "gerbers" else {}
    artifacts = tuple(
        Artifact(name, kind, _layer(name, stem, suffixes), produced[name], entry.repeatable)
        for name in sorted(produced)
    )
    return KindResult(artifacts=artifacts, tool_writes=tool_writes)


__all__ = [
    "GERBER_EXTRA_LAYERS",
    "JOB_SUFFIX",
    "KINDS",
    "MAJORS",
    "VOLATILE_PREFIXES",
    "Artifact",
    "Kind",
    "KindResult",
    "arguments",
    "gerber_layers",
    "layer_suffixes",
    "run_kind",
]
