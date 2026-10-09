# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Probes of change c0116 (capability kicad-oracle, "Document exports are probed on both majors"): the
``export-files-*`` and ``export-repeat-*`` rows of the six document kinds, and ``export-models-*``,
``export-sheets-missing`` and ``export-pdf-page``.

The subjects are written for the test and nothing is downloaded: the four-copper created board, the
authored project of the running major, the authored hierarchy (``hier`` or ``hier_v9``), a two-copper
bench whose two footprints name the authored model ``tests/data/models/Fenolite.3dshapes/Box_2x1.step``,
and a bench whose outline leaves its A4 paper.

Three runs of one board are taken more than a second apart, so that a date written with a resolution of
one second differs between them.
"""

from __future__ import annotations

import re
import tempfile
import time
from collections.abc import Callable, Mapping
from functools import cache
from pathlib import Path

from _boards import created_board
from _models import BOX, BOX_REL, model_board, official, outline, two_copper
from _projects import authored_project, hierarchy_project

from fenolite.backends.kicad.cli import CliRun, KicadCli
from fenolite.backends.kicad.libs import LINUX_INSTALL, MACOS_INSTALL
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.backends.kicad.projectset import project_set
from fenolite.exports.manifest import content_sha256
from fenolite.exports.plan import DOCUMENT_KINDS, KindResult, arguments, dxf_layers, pdf_layers, run_kind

Probes = dict[str, tuple[Callable[[], str], tuple[int, ...]]]
RUNS = 3
PAUSE = 1.1
"""Seconds between two runs of one board: more than the one-second resolution of the dates written."""
REFS = ("U1", "U2")
WRL_REL = "Fenolite.3dshapes/Box_2x1.wrl"
INSTALL_REL = "Resistor_SMD.3dshapes/R_0603_1608Metric.step"
"""An official model that a KiCad install holds; read from the install only, never copied or committed."""
A4_LANDSCAPE = (841.9, 595.3)
"""A4 landscape in PDF points (297 x 210 mm at 72 per inch)."""
_PAGE = re.compile(rb"/Type\s*/Page\b(?!s)")
_MEDIABOX = re.compile(rb"/MediaBox\s*\[\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*\]")
_OCCURRENCE = re.compile(r"NEXT_ASSEMBLY_USAGE_OCCURRENCE\s*\(\s*'[^']*'\s*,\s*'([^']*)'")
_last_run = 0.0


def runner() -> KicadCli:
    from _probes import runner as probes_runner  # _probes imports this module

    return probes_runner()


@cache
def workspace() -> Path:
    return Path(tempfile.mkdtemp(prefix="fenolite-documents-"))


@cache
def boards() -> tuple[tuple[Path, dict[str, Path]], ...]:
    """``(board, the rest of its copy set)``: the four-copper created board and the authored project."""
    major = runner().major()
    four = workspace() / "four" / "four.kicad_pcb"
    four.parent.mkdir(parents=True, exist_ok=True)
    four.write_text(write_board(created_board(4), target=major).text, encoding="utf-8", newline="\n")
    root = authored_project(workspace(), major=major)
    project = project_set(root)
    others = {name: path for name, path in project.files.items() if name != project.board}
    return ((four, {}), (root / project.board, others))


@cache
def hierarchy(*, whole: bool = True) -> Path:
    """The authored two-sheet hierarchy as a project (root ``top.kicad_sch``); without its child sheet when
    ``whole`` is false."""
    major = runner().major()
    folder = "hier" if major >= 10 else "hier_v9"
    root = hierarchy_project(workspace() / ("hier" if whole else "hier-missing"), folder=folder, major=major)
    if not whole:
        (root / "child.kicad_sch").unlink()
    return root


def _paced() -> None:
    """Wait until ``PAUSE`` seconds after the previous export of this session."""
    global _last_run
    wait = _last_run + PAUSE - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last_run = time.monotonic()


@cache
def exported(kind: str, subject: int, attempt: int = 0) -> KindResult:
    """One export of ``kind``; ``attempt`` asks for another run. ``sch-pdf`` has one subject, the
    hierarchy; the five board kinds have the two boards."""
    cli = runner()
    _paced()
    if kind == "sch-pdf":
        board = hierarchy() / "top.kicad_pcb"
        project = project_set(board)
        others = {name: path for name, path in project.files.items() if name != project.board}
        return run_kind(cli, kind, board, others, major=cli.major())
    board, files = boards()[subject]
    return run_kind(cli, kind, board, files, major=cli.major(), design=read_board(board))


def subjects(kind: str) -> range:
    return range(1 if kind == "sch-pdf" else len(boards()))


def expected_files(kind: str, subject: int) -> set[str] | None:
    """The files of a single-file kind; ``None`` for the per-layer kinds, whose names KiCad derives."""
    stem = "top" if kind == "sch-pdf" else boards()[subject][0].stem
    single = {
        "ipc2581": f"ipc2581/{stem}.xml",
        "odb": f"odb/{stem}.zip",
        "step": f"3d/{stem}.step",
        "sch-pdf": f"schematic/{stem}.pdf",
    }
    return {single[kind]} if kind in single else None


def files_outcome(kind: str) -> str:
    """``equal`` when every subject gives exactly the expected files under the kind's folder: one named
    file, or for ``pdf`` and ``dxf`` one ``<stem>-<name>.<kind>`` per listed layer and nothing else."""
    for subject in subjects(kind):
        result = exported(kind, subject)
        if any(issue.severity == "error" for issue in result.issues):
            return "reject"
        paths = {a.path for a in result.artifacts}
        wanted = expected_files(kind, subject)
        if wanted is not None:
            if paths != wanted:
                return "different"
            continue
        board = boards()[subject][0]
        design = read_board(board)
        layers = pdf_layers(design) if kind == "pdf" else dxf_layers(design)
        named = all(Path(p).name.startswith(f"{board.stem}-") and p.endswith(f".{kind}") for p in paths)
        if not named or sorted(a.layer or "" for a in result.artifacts) != sorted(layers):
            return "different"
    return "equal"


def repeat_outcome(kind: str) -> str:
    """``equal`` when every file has one ``content_sha256`` over ``RUNS`` runs, ``different`` otherwise."""
    for subject in subjects(kind):
        runs = [exported(kind, subject, attempt) for attempt in range(RUNS)]
        if any(issue.severity == "error" for run in runs for issue in run.issues):
            return "reject"
        hashes = [{a.path: content_sha256(a.data, kind) for a in run.artifacts} for run in runs]
        if any(found != hashes[0] for found in hashes[1:]):
            return "different"
    return "equal"


def byte_equal(kind: str) -> bool:
    """Whether the ``RUNS`` runs of every subject are byte-equal for ``kind``."""
    return all(
        [a.data for a in exported(kind, subject, attempt).artifacts]
        == [a.data for a in exported(kind, subject).artifacts]
        for subject in subjects(kind)
        for attempt in range(1, RUNS)
    )


def unknown_lines(kind: str) -> list[bytes]:
    """For a kind with date lines, the start of every line that differs between two runs and is not one
    of them."""
    from fenolite.exports.plan import VOLATILE_PREFIXES

    found: list[bytes] = []
    prefixes = VOLATILE_PREFIXES[kind]
    for subject in subjects(kind):
        first = {a.path: a.data for a in exported(kind, subject).artifacts}
        second = {a.path: a.data for a in exported(kind, subject, 1).artifacts}
        for path in sorted(first):
            a, b = first[path].splitlines(), second.get(path, b"").splitlines()
            if len(a) != len(b):
                found.append(f"{path}: line count".encode())
                continue
            found += [
                x[:40] for x, y in zip(a, b, strict=True) if x != y and not x.lstrip().startswith(prefixes)
            ]
    return found


# --- models ---------------------------------------------------------------------------------------


@cache
def model_bench(path: str) -> Path:
    """A two-copper board whose footprints ``U1`` and ``U2`` both name the model ``path``."""
    folder = Path(tempfile.mkdtemp(prefix="bench-", dir=workspace()))
    board = folder / "bench.kicad_pcb"
    board.write_text(model_board({ref: [path] for ref in REFS}), encoding="utf-8", newline="\n")
    return board


def step_run(
    path: str, files: Mapping[str, Path], *, env: Mapping[str, str] | None, subst: bool = True
) -> CliRun:
    """``pcb export step`` on the bench of ``path`` with the given run files and environment."""
    board = model_bench(path)
    args = arguments("step", stem=board.stem)
    if not subst:
        args.remove("--subst-models")
    given = {board.name: board, **files}
    return runner().run([*args, board.name], files=given, env=env, folders=("3d",))


def bodies(run: CliRun) -> list[str]:
    """The references that the STEP of ``run`` holds a body for, sorted: its assembly occurrences named
    after a footprint of the bench."""
    text = run.outputs.get("3d/bench.step", b"").decode("latin-1")
    return sorted(name for name in _OCCURRENCE.findall(text) if name in REFS)


def variable() -> str:
    return f"KICAD{runner().major()}_3DMODEL_DIR"


def _empty_folder() -> dict[str, Path]:
    """A model folder that holds no model: one note, so that the folder exists in the run."""
    note = workspace() / "no-model.txt"
    note.write_text("no model here\n", encoding="utf-8")
    return {"3dmodels/README.txt": note}


def models_var_outcome() -> str:
    """``equal`` when the model named through ``KICAD<N>_3DMODEL_DIR=3dmodels`` gives one body per
    footprint that names it."""
    path = official(major=runner().major())
    run = step_run(path, {f"3dmodels/{BOX_REL}": BOX}, env={variable(): "3dmodels"})
    if run.returncode != 0:
        return "reject"
    return "equal" if bodies(run) == sorted(REFS) and "Could not add" not in run.stdout else "different"


def missing_lines(path: str) -> list[str]:
    return [
        line for ref in REFS for line in (f"Could not add 3D model for {ref}.", f"File not found: {path}")
    ]


def models_missing_outcome() -> str:
    """``equal`` when, with the variable naming a folder without the model, the run exits 0, writes the
    STEP without a body and prints the two lines of each footprint."""
    path = official(major=runner().major())
    run = step_run(path, _empty_folder(), env={variable(): "3dmodels"})
    if run.returncode != 0 or "3d/bench.step" not in run.outputs:
        return "different"
    printed = [line.strip() for line in run.stdout.splitlines()]
    whole = all(line in printed for line in missing_lines(path))
    return "equal" if whole and bodies(run) == [] else "different"


def models_subst_outcome() -> str:
    """``equal`` when a ``.wrl`` path whose file is present gives the bodies of its ``.step`` sibling with
    ``--subst-models``, and no body when only the sibling is present."""
    path = official(WRL_REL, runner().major())
    wrl = workspace() / "Box_2x1.wrl"
    wrl.write_text("#VRML V2.0 utf8\n", encoding="utf-8")
    env = {variable(): "3dmodels"}
    both = step_run(path, {f"3dmodels/{WRL_REL}": wrl, f"3dmodels/{BOX_REL}": BOX}, env=env)
    alone = step_run(path, {f"3dmodels/{BOX_REL}": BOX}, env=env)
    if both.returncode != 0 or alone.returncode != 0:
        return "reject"
    return "equal" if bodies(both) == sorted(REFS) and bodies(alone) == [] else "different"


def install_has_model() -> bool:
    return any((root / "3dmodels" / INSTALL_REL).is_file() for root in (MACOS_INSTALL, LINUX_INSTALL))


def models_install_bodies(major: int) -> list[str]:
    """The bodies of a STEP whose footprints name an official ``KICAD<major>_`` model, with no model
    variable in the run: what ``kicad-cli`` takes from its own install."""
    return bodies(step_run(official(INSTALL_REL, major), {}, env=None))


# --- sheets and page --------------------------------------------------------------------------------


def sheet_run(root: Path) -> CliRun:
    """``sch export pdf`` on every schematic and project file of ``root``."""
    files = {p.name: p for p in sorted(root.iterdir()) if p.suffix in (".kicad_sch", ".kicad_pro")}
    args = arguments("sch-pdf", stem="top")
    return runner().run([*args, "top.kicad_sch"], files=files, folders=("schematic",))


def pages(run: CliRun) -> int:
    return len(_PAGE.findall(run.outputs.get("schematic/top.pdf", b"")))


def sheets_outcome() -> str:
    """``present`` when the hierarchy without its child sheet still gives one page per sheet instance,
    exit 0 and no line other than ``Plotted to '…'`` and ``Done.``; ``absent`` when a page is missing or
    the run says so."""
    whole, cut = sheet_run(hierarchy()), sheet_run(hierarchy(whole=False))
    if whole.returncode != 0 or pages(whole) < 2:
        return "inconclusive"
    lines = [line.strip() for line in cut.stdout.splitlines() if line.strip()]
    silent = all(line.startswith("Plotted to '") or line == "Done." for line in lines)
    return "present" if cut.returncode == 0 and pages(cut) == pages(whole) and silent else "absent"


def page_box() -> tuple[float, float] | None:
    """Width and height of the ``/MediaBox`` of the ``Edge.Cuts`` PDF of a board whose outline, 158 x 179
    mm from (100, 100) mm, leaves its A4 paper."""
    board = workspace() / "page" / "page.kicad_pcb"
    board.parent.mkdir(parents=True, exist_ok=True)
    board.write_text(two_copper(outline(100, 100, 258, 279)), encoding="utf-8", newline="\n")
    args = ["pcb", "export", "pdf", "-o", "pdf/", "--mode-separate", "--layers", "Edge.Cuts", board.name]
    run = runner().run(args, files={board.name: board}, folders=("pdf",))
    match = _MEDIABOX.search(run.outputs.get("pdf/page-Edge_Cuts.pdf", b""))
    if run.returncode != 0 or match is None:
        return None
    x0, y0, x1, y1 = (float(value) for value in match.groups())
    return (x1 - x0, y1 - y0)


def page_outcome() -> str:
    """``equal`` when the page is A4 landscape although the outline reaches 279 mm on a page 210 mm high."""
    box = page_box()
    if box is None:
        return "reject"
    return "equal" if all(abs(a - b) < 1.0 for a, b in zip(box, A4_LANDSCAPE, strict=True)) else "different"


def document_probes() -> Probes:
    both = (9, 10)
    probes: Probes = {}
    for kind in DOCUMENT_KINDS:
        probes[f"export-files-{kind}"] = (lambda kind=kind: files_outcome(kind), both)
        probes[f"export-repeat-{kind}"] = (lambda kind=kind: repeat_outcome(kind), both)
    probes["export-models-var"] = (models_var_outcome, both)
    probes["export-models-missing"] = (models_missing_outcome, both)
    probes["export-models-subst"] = (models_subst_outcome, both)
    probes["export-sheets-missing"] = (sheets_outcome, both)
    probes["export-pdf-page"] = (page_outcome, both)
    return probes


__all__ = [
    "RUNS",
    "bodies",
    "byte_equal",
    "document_probes",
    "exported",
    "install_has_model",
    "missing_lines",
    "models_install_bodies",
    "page_box",
    "pages",
    "sheet_run",
    "step_run",
    "unknown_lines",
]
