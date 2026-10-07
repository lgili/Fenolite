# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""What the Altium verification kit needs from the packages that ``fenolite.verify`` may not import
(``package-layering``): building a sample from its script, and judging a document that Altium saved.

``kit_sources`` builds the five samples of ``examples/kit/`` with the Altium lens and the sheet template of
group K8; ``judge_document`` reads a re-saved document with Fenolite's readers and compares it with the
kit's own. ``fenolite.verify.kit`` takes both as arguments (``docs/altium-kit.md``).

A sample script is a design script. It may also bind ``KIT``, a mapping with the keys ``sheets`` (``flat``
or ``modules``), ``forms`` (``binary``, ``ascii``), ``copper`` and ``planes`` (which replace the board's),
and ``drawing_sheet`` (the name of a shipped sheet example), and a function ``kit_model(model)`` that
returns the model with what the DSL cannot declare. The scripts are run in this process, as ``build`` runs
a design script: they are the repository's own.
"""

from __future__ import annotations

import runpy
import shutil
import tempfile
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import fenolite
from fenolite.backends import registry
from fenolite.backends.altium import schdot
from fenolite.backends.altium.read.cfb import open_compound
from fenolite.backends.altium.read.project import read_project
from fenolite.checks.documents import run_document_checks
from fenolite.checks.equivalence import compare_designs, max_level
from fenolite.cli._documents import find_documents
from fenolite.cli.cmd_build import _catalog_definitions  # pyright: ignore[reportPrivateUsage]
from fenolite.core.errors import FenoliteError, FormatError
from fenolite.core.io import sha256_bytes
from fenolite.dsl import Design, placements, to_model
from fenolite.lens.altium import build_altium
from fenolite.model.design import Design as ModelDesign
from fenolite.model.library import Library
from fenolite.templates import build_sheet, example_path, load_spec, page_size
from fenolite.verify.kit.manifest import KitSources, SampleFiles
from fenolite.verify.kit.steps import SAMPLES

SAMPLES_DIR = Path(fenolite.__file__).resolve().parents[2] / "examples" / "kit"
"""The sample scripts of a source checkout; an installed package holds none (``kit build --samples``)."""
SCRIPT = "design.py"
TEMPLATE = "iso5457_generic"
TEMPLATE_FILE = f"templates/{TEMPLATE}.SchDot"
"""The sheet template of group K8, built from the shipped specification when the kit is built: no
template file is kept in the repository."""
CACHE_PREFIX = ".fenolite/"
MAX_SHOWN = 6
KIT_PROFILE: Mapping[str, str] = {
    "unnamed-part": "a board item that the import reads as a part without a designator (a free hole) "
    "cannot be paired by reference, so level 1 reports it on any comparison, also of a file with itself; "
    "it is left out while both sides hold the same number of them",
}
"""The kit profile: what a comparison of a saved document leaves out, each with its cause. A difference
that no entry names fails its step; an entry is added only with the cause that a run showed."""
ModelEdit = Callable[[ModelDesign], ModelDesign]


def _drawing_sheet(name: str) -> Any:
    path = example_path(name)
    return build_sheet(load_spec(path.read_text(encoding="utf-8"), file=path.name), base_dir=path.parent)


def build_sample(script: Path, *, edit: ModelEdit | None = None) -> SampleFiles:
    """The sample of the script at ``script``, built for Altium. ``edit`` changes the model before the
    build (the tests' stand-in for what a tool did to a document). ``FormatError`` when the script binds no
    design or the build reports an error."""
    script = Path(script)
    if not script.is_file():
        raise FormatError(f"the sample script {script.parent.name}/{script.name} does not exist", file=SCRIPT)
    namespace = runpy.run_path(str(script))
    design = namespace.get("design")
    if not isinstance(design, Design):
        raise FormatError("the sample script binds no module-level 'design'", file=script.name)
    options = cast(Mapping[str, Any], namespace.get("KIT", {}))
    hook = namespace.get("kit_model")
    model = to_model(design)
    if callable(hook):
        model = cast(ModelDesign, hook(model))
    if edit is not None:
        model = edit(model)
    footprints, symbols, _builtin = _catalog_definitions(
        model,
        {key: fp.definition for key, fp in design.footprints.items()},
        {key: symbol.definition for key, symbol in design.symbols.items()},  # type: ignore[attr-defined]
    )
    requested = placements(design)
    sheet = _drawing_sheet(str(options["drawing_sheet"])) if "drawing_sheet" in options else None
    files: dict[str, bytes] = {}
    for form in cast(Sequence[str], options.get("forms", ("binary",))):
        built = build_altium(
            model,
            name=design.name,
            placed=tuple(requested),
            placements=requested,
            form=form,  # type: ignore[arg-type]
            sheets=options.get("sheets", "flat"),
            copper=int(options.get("copper", design.copper)),
            planes=dict(options.get("planes", design.planes)),
            outjob=True,
            drawing_sheet=sheet,
            authored_footprints=footprints,
            authored_symbols=symbols,
        )
        errors = [found.message for found in built.issues if found.severity == "error"]
        if errors or not built.files:
            raise FormatError(
                f"the sample {design.name} does not build: {'; '.join(errors) or 'no file'}", file=script.name
            )
        for path, data in built.files.items():
            if path.startswith(CACHE_PREFIX):
                continue
            if form == "binary":
                files[path] = data
            elif path.endswith(".SchDoc"):
                files[f"ascii/{path}"] = data
    return SampleFiles(design.name, sha256_bytes(script.read_bytes()), files)


def sheet_template() -> bytes:
    """The shipped generic drawing sheet as a binary Altium sheet template, on its first size."""
    path = example_path(TEMPLATE)
    spec = load_spec(path.read_text(encoding="utf-8"), file=path.name)
    sheet = build_sheet(spec, base_dir=path.parent)
    size = spec.sizes[0]
    width, height = page_size(spec, size)
    return schdot.write_template(sheet, width=width, height=height, paper=size).data


def kit_sources(samples_dir: Path | None = None) -> KitSources:
    """The built samples of ``samples_dir`` (the checkout's ``examples/kit`` by default) and the sheet
    template. ``FormatError`` when a sample script is missing or does not build."""
    folder = SAMPLES_DIR if samples_dir is None else Path(samples_dir)
    built: list[SampleFiles] = []
    for name in SAMPLES:
        sample = build_sample(folder / name / SCRIPT)
        if sample.name != name:
            raise FormatError(f"the script of the sample {name} names its design {sample.name}", file=SCRIPT)
        built.append(sample)
    return KitSources(tuple(built), {TEMPLATE_FILE: sheet_template()}, fenolite.__version__)


# --- judging a document that a tool saved ------------------------------------------------------------


def read_document(path: Path) -> object:
    """What the backend of ``path`` reads from it: a design or a library. ``FormatError`` when no backend
    reads the file."""
    backend = registry.for_path(path)
    if backend is None:
        raise FormatError(f"no backend reads {path.name}", file=path.name)
    return backend.read(path, issues=[]).content


def _project_documents(path: Path) -> list[str]:
    project = read_project(path.read_bytes(), file=path.name)
    return sorted(
        document.path.replace("\\", "/").rsplit("/", 1)[-1].casefold() for document in project.documents
    )


def _library(library: Library) -> dict[str, list[str]]:
    held: dict[str, list[str]] = {}
    for symbol in library.symbols:
        held[f"symbol {symbol.name}"] = sorted(f"{pin.number}:{pin.name}:{pin.unit}" for pin in symbol.pins)
    for footprint in library.footprints:
        held[f"footprint {footprint.name}"] = sorted(str(pad.number) for pad in footprint.pads)
    return held


def _differences(own: ModelDesign, saved: ModelDesign, level: int) -> list[str]:
    highest = max_level(own, saved)
    if highest < level:
        return [
            f"the kit's document is compared up to level {level}, and the saved one holds only what level "
            f"{highest} needs: footprints or copper are missing"
        ]
    report = compare_designs(own, saved, level=level)
    kept = [d for d in report.differences if not (d.kind == "ref-ambiguous" and not d.where and d.a == d.b)]
    found = [
        f"level {d.level} {d.kind} at {d.where}: the kit's document has {d.a or 'nothing'}, "
        f"the saved one {d.b or 'nothing'}"
        for d in kept[:MAX_SHOWN]
    ]
    if len(kept) > MAX_SHOWN:
        found.append(f"and {len(kept) - MAX_SHOWN} more difference(s)")
    return found


def _container(path: Path) -> list[str]:
    backend = registry.for_path(path)
    judge = getattr(backend, "container_roundtrip", None)
    if judge is None:
        return [f"no backend judges the container of {path.name}"]
    found: list[str] = []
    for level in ("RT-A0", "RT-A1"):
        verdict = judge(path, level)
        if verdict.judged and not verdict.passed:
            found.append(f"{level} fails on the saved file: {verdict.difference or verdict.reason}")
    return found


def poured_problems(design: ModelDesign) -> list[str]:
    """What the check ``poured`` finds on an imported board: no polygon at all, or polygons without a
    fill. The import gives a polygon the regions that Altium poured for it as its fills."""
    zones = () if design.board is None else design.board.zones
    if not zones:
        return ["the saved board holds no polygon"]
    bare = [zone.name or zone.id for zone in zones if not zone.fills]
    return [f"{len(bare)} of {len(zones)} polygon(s) hold no poured copper"] if bare else []


PLANTED_NETS = ("LED_A", "VIN")
"""The two nets of the one clearance violation that the sample ``routed`` plants (its rule of 1.5 mm
between them, ``examples/kit/routed/design.py``)."""
COPPER_STAGE = "copper.clearance"


def copper_problems(board: Path, *, repoured: bool) -> list[str]:
    """What the check ``copper.clearance`` finds on ``board``, a PCB document: the stage of that name of
    ``fenolite check`` must report the planted clearance violation between ``PLANTED_NETS`` and no other,
    and no short. With ``repoured`` the board must also leave no polygon out of the check: none unpoured,
    and none without a clearance to judge it by."""
    found = find_documents(board)
    if found is None:
        return [f"no backend checks {board.name}"]
    validator, documents = found
    report = run_document_checks(
        documents=documents, stages=(COPPER_STAGE,), model=None, built=False, validator=validator
    )
    if isinstance(report.read_error, FormatError):
        return [f"Fenolite cannot read the board: {report.read_error}"]
    stage = next((stage for stage in report.stages if stage.name == COPPER_STAGE), None)
    if stage is None or stage.status == "skipped":
        return [f"the copper check did not run: {stage.reason if stage else 'no stage'}"]
    problems: list[str] = []
    clearance = [issue for issue in report.issues if issue.code == "copper.clearance"]
    planted = [issue for issue in clearance if all(net in issue.message for net in PLANTED_NETS)]
    shorts = sum(1 for issue in report.issues if issue.code == "copper.short")
    if len(planted) != 1:
        problems.append(
            f"{len(planted)} clearance finding(s) between {' and '.join(PLANTED_NETS)}, not the one planted"
        )
    others = [issue for issue in clearance if issue not in planted]
    if others:
        problems.append(
            f"{len(others)} clearance finding(s) that the sample does not plant: {others[0].message}"
        )
    if shorts:
        problems.append(f"{shorts} short(s) between nets")
    if repoured:
        for code, what in (
            ("copper.item-unsupported", "polygon(s) without poured copper were left out"),
            ("copper.rules-incomplete", "polygon(s) have no clearance to be judged by"),
        ):
            left = [issue for issue in report.issues if issue.code == code]
            if left:
                problems.append(f"{what}: {left[0].message}")
    return problems


PARITY_STAGE = "parity"


def _parity_findings(folder: Path) -> Counter[tuple[str, str]] | None:
    """The findings of the stage ``parity`` on the project of ``folder`` as ``(code, message)`` counts, or
    ``None`` when the stage does not run there (a sample without a board, or without a schematic)."""
    found = find_documents(folder)
    if found is None:
        return None
    validator, documents = found
    report = run_document_checks(
        documents=documents, stages=(PARITY_STAGE,), model=None, built=False, validator=validator
    )
    if isinstance(report.read_error, FormatError):
        raise report.read_error
    stage = next((stage for stage in report.stages if stage.name == PARITY_STAGE), None)
    if stage is None or stage.status == "skipped":
        return None
    return Counter((issue.code, issue.message) for issue in report.issues)


def parity_problems(own: Path, saved: Path) -> list[str]:
    """What the check ``parity`` finds: the stage of that name on a copy of the sample's project in which
    ``saved`` takes the place of the kit's document of ``own``'s name, against the same stage on the kit's
    own project. The copy lives in a temporary folder and is removed; nothing of the kit is written. A
    sample whose own project gives no parity verdict (no board) is not judged."""
    sample = own.parent if list(own.parent.glob("*.PrjPcb")) else own.parent.parent
    mine = _parity_findings(sample)
    if mine is None:
        return []
    with tempfile.TemporaryDirectory() as scratch:
        copy = Path(scratch) / sample.name
        copy.mkdir()
        for path in sorted(sample.iterdir()):
            if path.is_file():
                shutil.copyfile(path, copy / path.name)
        shutil.copyfile(saved, copy / own.name)
        theirs = _parity_findings(copy)
    if theirs is None:
        return ["the parity of the project could not be judged with the saved document"]
    more, fewer = sorted((theirs - mine).elements()), sorted((mine - theirs).elements())
    problems = [f"{code} with the saved document only: {message}" for code, message in more[:MAX_SHOWN]]
    problems += [f"{code} with the kit's own document only: {message}" for code, message in fewer[:MAX_SHOWN]]
    if len(more) + len(fewer) > len(problems):
        problems.append(f"and {len(more) + len(fewer) - len(problems)} more parity difference(s)")
    return problems


DOCUMENT_KINDS: Mapping[str, str] = {
    "pcbdoc": "a PCB document",
    "pcblib": "a PCB library",
    "schlib": "a schematic library",
    "schdoc": "a schematic document",
    "project": "a project file",
}
"""What ``document_kind`` calls each kind of Altium file, as the reason of a failed step prints it."""


def document_kind(data: bytes) -> str | None:
    """What kind of Altium file ``data`` is, from its content and never from a file name: a compound file
    with a ``Board6`` storage is a PCB document, one with a ``Library`` storage a PCB library, one with a
    ``FileHeader`` stream a schematic library when it holds a storage per symbol and a schematic document
    (or sheet template) otherwise; text that starts with the schematic header is a schematic document in
    the ASCII form, and text with a ``[Design]`` section a project file. ``None`` for anything else."""
    if data.startswith(b"|HEADER="):
        return DOCUMENT_KINDS["schdoc"]
    try:
        streams = open_compound(data).streams()
    except FenoliteError:
        head = data[:4096].decode("latin-1").casefold()
        return DOCUMENT_KINDS["project"] if "[design]" in head and b"\x00" not in data[:4096] else None
    if "Board6/Data" in streams:
        return DOCUMENT_KINDS["pcbdoc"]
    if "Library/Data" in streams:
        return DOCUMENT_KINDS["pcblib"]
    if "FileHeader" not in streams:
        return None
    return DOCUMENT_KINDS["schlib" if any(name.endswith("/Data") for name in streams) else "schdoc"]


def kind_problems(own: Path, saved: Path) -> list[str]:
    """One message when the file a run left is of another kind of document than the kit's own, which the
    step wants: a schematic saved under the name of the board, a library under the name of a sheet. No
    message when either file is of no kind that ``document_kind`` knows: the checks then say what is
    wrong with it."""
    want, got = document_kind(own.read_bytes()), document_kind(saved.read_bytes())
    if want is None or got is None or want == got:
        return []
    return [
        f"the file is {got}, and the step wants {want}: save {own.name} of the sample, not another "
        "document of its project"
    ]


def judge_document(check: str, own: Path, saved: Path) -> list[str]:
    """What the machine check ``check`` of a kit step finds on ``saved``, the file a run left, against
    ``own``, the kit's document: one message per problem, none for a pass.

    ``resave``: RT-A0 and RT-A1 on the saved file, then its import against the import of the kit's own
    file, at the highest level of ``equivalent`` that the kit's file holds; a library is compared by its
    symbols with their pins and its footprints with their pads, a project file by its documents. The
    reference is Fenolite's reading of its own file, because the model of a build holds no placed footprint.
    ``netlist``: levels 1 and 2 only. ``poured``: every zone of the saved board holds a fill.
    ``parity``: ``parity_problems``.
    ``copper.clearance``: ``copper_problems`` on the saved board when the step leaves one (after a
    repour), else on the kit's own board (the step leaves Altium's report, which is archived as it is).
    """
    try:
        if not (check == COPPER_STAGE and saved.suffix.casefold() != ".pcbdoc"):
            other = kind_problems(own, saved)
            if other:
                return other
        if check == PARITY_STAGE:
            return parity_problems(own, saved)
        if check == COPPER_STAGE:
            if saved.suffix.casefold() == ".pcbdoc":
                return copper_problems(saved, repoured=True)
            return copper_problems(own, repoured=False)
        if check == "poured":
            return poured_problems(cast(ModelDesign, read_document(saved)))
        if own.suffix.casefold() == ".prjpcb":
            mine, theirs = _project_documents(own), _project_documents(saved)
            return [] if mine == theirs else [f"the project lists {', '.join(theirs)}, not {', '.join(mine)}"]
        found = _container(saved) if check == "resave" else []
        a, b = read_document(own), read_document(saved)
        if isinstance(a, Library):
            if not isinstance(b, Library):
                return [*found, "the saved file is not a library"]
            mine_lib, theirs_lib = _library(a), _library(b)
            names = sorted(set(mine_lib) | set(theirs_lib))
            found += [
                f"{name}: the kit's library has {mine_lib.get(name)}, the saved one {theirs_lib.get(name)}"
                for name in names
                if mine_lib.get(name) != theirs_lib.get(name)
            ][:MAX_SHOWN]
            return found
        if not isinstance(a, ModelDesign) or not isinstance(b, ModelDesign):
            return [*found, "the saved file is not a design"]
        level = 2 if check == "netlist" else max_level(a, a)
        return [*found, *_differences(a, b, level)]
    except FenoliteError as error:
        return [f"Fenolite cannot read the saved file: {error}"]


__all__ = [
    "DOCUMENT_KINDS",
    "KIT_PROFILE",
    "PLANTED_NETS",
    "SAMPLES_DIR",
    "TEMPLATE_FILE",
    "build_sample",
    "copper_problems",
    "document_kind",
    "judge_document",
    "kind_problems",
    "kit_sources",
    "parity_problems",
    "poured_problems",
    "read_document",
    "sheet_template",
]
