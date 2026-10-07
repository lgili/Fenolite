# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The 3D model files that the footprints of a board name, and how a STEP export is given them
(capability manufacturing-exports, "STEP export with 3D models"; change c0116; facts:
``docs/formats/kicad/libraries.md``, "3D models").

``kicad-cli pcb export step`` leaves out a body whose model file it cannot find and still exits 0, and
the oracle runner removes every ``KICAD*`` variable. So Fenolite locates each model itself
(``LibraryResolver.locate_model``), copies the located files into the run and names their folder through
the run's own variables: the STEP then holds exactly the models that the result reports.

"Model" here means a 3D model *file* (STEP or VRML). The extruded ``bodies`` of a footprint definition
(change c0121) are not files and are not read here.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from types import MappingProxyType

from fenolite.backends.kicad import versions
from fenolite.backends.kicad.liberrors import lib_issue
from fenolite.backends.kicad.libs import MODEL_FOLDER, LibraryConfig, LibraryResolver, ModelLocation
from fenolite.backends.kicad.sexpr import AtomKind, Node, parse
from fenolite.core.errors import FormatError, Issue
from fenolite.core.evidence import Evidence, Level

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-EXPORT-MODELS",))
"""``INFERRED`` until ``H-K-EXPORT-MODELS`` holds on 9.0.x and 10.0.x: how ``kicad-cli`` finds a model
through ``KICAD<N>_3DMODEL_DIR`` and what it prints for one it does not find."""
MISSING = "missing"
IN_PLACE = "in-place"
SIBLING_SUFFIXES = (".step", ".stp")
"""The files ``--subst-models`` may take in place of a ``.wrl`` model: its siblings of these suffixes."""
_OFFICIAL = re.compile(r"^\$\{KICAD(\d+)_3DMODEL_DIR\}[/\\]")
_HEADER_VERSION = re.compile(rb"\(version\s+(\d+)\)")
_UNREAD = re.compile(r"Could not add 3D model for (.+?)\.\s*$", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class ModelRef:
    """One ``(model "<path>" …)`` of a footprint of a board: the footprint's reference and the path as
    written."""

    ref: str
    path: str


@dataclass(frozen=True, slots=True)
class ModelUse:
    """One distinct model path of a board: the source that holds its file (``missing`` when none does,
    ``in-place`` for a path KiCad reads where it is), the file's SHA-256 and size (``None`` when missing
    or in place) and the references that use it, sorted."""

    path: str
    source: str
    sha256: str | None
    bytes: int | None
    refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ModelPlan:
    """What a ``step`` run is given: ``files`` (name in the run folder → file), ``env`` (the model
    variables of the run), ``uses`` (one per distinct path, sorted by path) and the ``issues`` (one
    ``kicad.lib.missing-3d-model`` per path that no source holds)."""

    files: Mapping[str, Path] = field(default_factory=lambda: MappingProxyType({}))
    env: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))
    uses: tuple[ModelUse, ...] = ()
    issues: tuple[Issue, ...] = ()


def _reference(footprint: Node) -> str:
    for node in footprint.nodes("property"):
        atoms = node.atoms()
        if len(atoms) >= 2 and atoms[0].value == "Reference":
            return atoms[1].value
    for node in footprint.nodes("fp_text"):
        atoms = node.atoms()
        if len(atoms) >= 2 and atoms[0].value == "reference":
            return atoms[1].value
    return ""


def board_models(text: str) -> tuple[ModelRef, ...]:
    """One ``ModelRef`` per ``(model "<path>" …)`` child of each footprint of the board ``text``, in
    board order. A text that is no board gives none."""
    try:
        root = parse(text)
    except (FormatError, ValueError):
        return ()
    found: list[ModelRef] = []
    for footprint in (*root.nodes("footprint"), *root.nodes("module")):
        ref = _reference(footprint)
        for model in footprint.nodes("model"):
            atoms = model.atoms()
            if atoms and atoms[0].kind in (AtomKind.STRING, AtomKind.SYMBOL) and atoms[0].value:
                found.append(ModelRef(ref, atoms[0].value))
    return tuple(found)


def _digest(file: Path) -> tuple[str, int]:
    data = file.read_bytes()
    return hashlib.sha256(data).hexdigest(), len(data)


def _run_name(location: ModelLocation) -> str | None:
    """The name of a located file in the run folder; ``None`` for a file read in place."""
    if location.rel is None:
        return None
    official = _OFFICIAL.match(location.path) is not None
    return f"{MODEL_FOLDER}/{location.rel}" if official else location.rel


def _shown(path: str) -> str:
    """``path`` as the commands report it: as written, or only the file name of an absolute path, so
    that no result holds a folder of the machine."""
    plain = path.replace("\\", "/")
    if plain.startswith("/") or re.match(r"^[A-Za-z]:/", plain):
        return PurePosixPath(plain).name
    return path


def model_majors(paths: Iterable[str]) -> tuple[int, ...]:
    """Every N of a ``${KICAD<N>_3DMODEL_DIR}`` that ``paths`` name, sorted."""
    return tuple(sorted({int(m.group(1)) for m in map(_OFFICIAL.match, paths) if m is not None}))


def plan_models(refs: Iterable[ModelRef], resolver: LibraryResolver) -> ModelPlan:
    """Locate each distinct path of ``refs`` once and plan the run: a located official model as
    ``3dmodels/<rel>`` (a ``.wrl`` with its STEP siblings of the same source), a located project model
    under its own relative path, and ``KICAD<N>_3DMODEL_DIR=3dmodels`` for every N that a path names,
    located or not, so that ``kicad-cli`` never reads a model that is not reported here."""
    users: dict[str, set[str]] = {}
    for ref in refs:
        users.setdefault(ref.path, set()).add(ref.ref)
    files: dict[str, Path] = {}
    uses: list[ModelUse] = []
    issues: list[Issue] = []
    for path in sorted(users):
        named = tuple(sorted(ref for ref in users[path] if ref))
        location = resolver.locate_model(path)
        shown = _shown(path)
        if location is None:
            parts = ", ".join(named) or "a footprint without reference"
            issues.append(
                lib_issue(
                    "kicad.lib.missing-3d-model",
                    f"3D model {shown} of {parts} was not found: its body is left out of the STEP",
                    where=shown,
                    hint="run 'fenolite models' on the board to see the sources tried, or vendor the "
                    "model into the project's 3dmodels folder",
                )
            )
            uses.append(ModelUse(shown, MISSING, None, None, named))
            continue
        name = _run_name(location)
        if name is None:
            uses.append(ModelUse(shown, IN_PLACE, None, None, named))
            continue
        sha, size = _digest(location.file)
        files[name] = location.file
        uses.append(ModelUse(shown, location.source, sha, size, named))
        if location.file.suffix.lower() == ".wrl":
            for suffix in SIBLING_SUFFIXES:
                sibling = location.file.with_suffix(suffix)
                if sibling.is_file():
                    files[PurePosixPath(name).with_suffix(suffix).as_posix()] = sibling
    env = {f"KICAD{major}_3DMODEL_DIR": MODEL_FOLDER for major in model_majors(users)}
    uses.sort(key=lambda use: use.path)
    return ModelPlan(MappingProxyType(files), MappingProxyType(env), tuple(uses), tuple(issues))


def board_plan(board: Path, *, major: int = versions.DEFAULT_TARGET) -> ModelPlan:
    """The model plan of the board file ``board``, located as the ``step`` export kind locates it: a
    resolver with the board's folder as project folder, the major of the board's format as target
    (``major`` when the header gives none) and KiCad's configured path variables read."""
    board = Path(board)
    data = board.read_bytes()
    header = _HEADER_VERSION.search(data[:4096])
    found = versions.major_for(versions.FileKind.BOARD, int(header.group(1))) if header else None
    config = LibraryConfig(target_major=found or major, project_dir=board.parent, read_common=True)
    return plan_models(board_models(data.decode("utf-8", "replace")), LibraryResolver(config))


def unread_refs(stdout: str) -> tuple[str, ...]:
    """The references of the lines ``Could not add 3D model for <ref>.`` of a STEP run's output, in
    order, each once."""
    return tuple(dict.fromkeys(match.group(1).strip() for match in _UNREAD.finditer(stdout)))


def located_refs(uses: Iterable[ModelUse]) -> frozenset[str]:
    """The references whose model paths were all located."""
    seen: dict[str, bool] = {}
    for use in uses:
        for ref in use.refs:
            seen[ref] = seen.get(ref, True) and use.source != MISSING
    return frozenset(ref for ref, whole in seen.items() if whole)


def use_dict(use: ModelUse) -> dict[str, object]:
    """One ``ModelUse`` as the commands report it (``result.models``)."""
    return {
        "path": use.path,
        "source": use.source,
        "sha256": use.sha256,
        "bytes": use.bytes,
        "refs": list(use.refs),
    }


__all__ = [
    "EVIDENCE",
    "IN_PLACE",
    "MISSING",
    "MODEL_FOLDER",
    "ModelPlan",
    "ModelRef",
    "ModelUse",
    "board_models",
    "board_plan",
    "located_refs",
    "model_majors",
    "plan_models",
    "unread_refs",
    "use_dict",
]
