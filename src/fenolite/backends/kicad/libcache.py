# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Pins, tree hashes and stamps of the fetched official KiCad libraries (capability
kicad-library-resolution, "Library pins"; ``docs/formats/kicad/libraries.md``, "Library cache").

The official libraries are CC-BY-SA 4.0 as a collection, so they are fetched into a cache outside the
repository and never committed. ``data/libraries.toml`` pins each repository at a tag by commit, tree
hash and file count; ``tools/kicad_libs_fetch.py`` makes the cache, and a folder is usable when its stamp
equals its pin. This module imports only ``core`` and the standard library.
"""

# evidence: none, pins, hashes and stamps of the fetched libraries: no statement about a KiCad format or tool

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import cast

SCHEME = "fenolite-tree-1"
STAMP = ".fenolite-verified"
REPOS = ("kicad-footprints", "kicad-symbols")
CACHE_VARIABLE = "FENOLITE_LIBS_CACHE"
PINS_FILE = "fenolite/backends/kicad/data/libraries.toml"
SCHEMA = 1
_COMMIT = re.compile(r"[0-9a-f]{40}")
_TREE = re.compile(r"[0-9a-f]{64}")
_PIN_KEYS = ("tag", "major", "repo", "project", "commit", "tree", "files")
_STAMP_KEYS = ("scheme", "tag", "repo", "commit", "tree", "files")
_CHUNK = 1 << 20
MODEL_REPO = "kicad-packages3D"
"""The folder of the fetched 3D models below ``<cache>/<tag>/`` (capability kicad-library-resolution,
"3D model fetch"; change c0116)."""
MODEL_PROJECT = f"kicad/libraries/{MODEL_REPO}"
MODEL_STAMP = ".fenolite-models.json"
"""The stamp of a model folder: a JSON object, the path of each fetched file mapped to its SHA-256."""
_MODEL_KEYS = ("tag", "major", "project", "commit")


@dataclass(frozen=True, slots=True)
class LibraryPin:
    """One official library repository at one tag: its commit, and the tree hash and file count measured
    on a fetched tree."""

    tag: str
    major: int
    repo: str
    project: str
    commit: str
    tree: str
    files: int


@dataclass(frozen=True, slots=True)
class ModelPin:
    """The official 3D model repository at one tag: its commit. No tree hash and no file count: the
    models are fetched one file at a time, each checked against the SHA-256 that the files API gives."""

    tag: str
    major: int
    project: str
    commit: str


def _document(path: Path | None) -> tuple[dict[str, object], str]:
    if path is None:
        name = PINS_FILE
        text = resources.files("fenolite.backends.kicad").joinpath("data/libraries.toml").read_text("utf-8")
    else:
        name = str(path)
        text = path.read_text(encoding="utf-8")
    try:
        return tomllib.loads(text), name
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"{name}: not valid TOML: {exc}") from exc


def _fail(name: str, key: str, why: str) -> ValueError:
    return ValueError(f"{name}: {key}: {why}")


def archive_template(path: Path | None = None) -> str:
    """The download URL template of the pins file, with the fields ``{project}`` and ``{commit}``."""
    data, name = _document(path)
    template = data.get("archive")
    if not isinstance(template, str) or "{project}" not in template or "{commit}" not in template:
        raise _fail(name, "archive", "must be a URL template holding {project} and {commit}")
    return template


def load_pins(path: Path | None = None) -> tuple[LibraryPin, ...]:
    """The pins of ``path`` (default: the package's pins file), in file order; ``ValueError`` naming the
    file and the key for a file that breaks the rules of "Library pins"."""
    data, name = _document(path)
    if data.get("schema") != SCHEMA:
        raise _fail(name, "schema", f"must be {SCHEMA}")
    archive_template(path)
    listed = data.get("pin")
    if not isinstance(listed, list) or not listed:
        raise _fail(name, "pin", "must be a non-empty array of tables")
    pins: list[LibraryPin] = []
    for index, item in enumerate(cast(list[object], listed)):
        where = f"pin[{index}]"
        if not isinstance(item, dict):
            raise _fail(name, where, "must be a table")
        entry = cast(dict[str, object], item)
        missing = [key for key in _PIN_KEYS if key not in entry]
        extra = sorted(set(entry) - set(_PIN_KEYS))
        if missing or extra:
            raise _fail(name, f"{where}.{(missing or extra)[0]}", "missing key" if missing else "unknown key")
        tag, major, repo, project = entry["tag"], entry["major"], entry["repo"], entry["project"]
        commit, tree, files = entry["commit"], entry["tree"], entry["files"]
        if not isinstance(tag, str) or not tag:
            raise _fail(name, f"{where}.tag", "must be a non-empty string")
        if type(major) is not int or major <= 0:
            raise _fail(name, f"{where}.major", "must be a positive integer")
        if not isinstance(repo, str) or repo not in REPOS:
            raise _fail(name, f"{where}.repo", f"must be one of {', '.join(REPOS)}")
        if not isinstance(project, str) or project != f"kicad/libraries/{repo}":
            raise _fail(name, f"{where}.project", f"must be kicad/libraries/{repo}")
        if not isinstance(commit, str) or not _COMMIT.fullmatch(commit):
            raise _fail(name, f"{where}.commit", "must be 40 lowercase hex digits")
        if not isinstance(tree, str) or not _TREE.fullmatch(tree):
            raise _fail(name, f"{where}.tree", "must be 64 lowercase hex digits")
        if type(files) is not int or files <= 0:
            raise _fail(name, f"{where}.files", "must be a positive integer")
        pins.append(LibraryPin(tag, major, repo, project, commit, tree, files))
    seen: set[tuple[str, str]] = set()
    tags: dict[int, str] = {}
    for index, pin in enumerate(pins):
        if (pin.tag, pin.repo) in seen:
            raise _fail(name, f"pin[{index}].repo", f"{pin.repo} is pinned twice at tag {pin.tag}")
        seen.add((pin.tag, pin.repo))
        if tags.setdefault(pin.major, pin.tag) != pin.tag:
            raise _fail(name, f"pin[{index}].tag", f"major {pin.major} is pinned at two tags")
    return tuple(pins)


def load_model_pins(path: Path | None = None) -> tuple[ModelPin, ...]:
    """The ``[[models]]`` pins of ``path`` (default: the package's pins file), in file order: one per tag
    of the ``[[pin]]`` tables, with that tag's major. ``ValueError`` naming the file and the key for a
    table that breaks the rules of "3D model pins"."""
    data, name = _document(path)
    majors = {pin.tag: pin.major for pin in load_pins(path)}
    listed = data.get("models")
    if not isinstance(listed, list) or not listed:
        raise _fail(name, "models", "must be a non-empty array of tables")
    pins: list[ModelPin] = []
    for index, item in enumerate(cast(list[object], listed)):
        where = f"models[{index}]"
        if not isinstance(item, dict):
            raise _fail(name, where, "must be a table")
        entry = cast(dict[str, object], item)
        missing = [key for key in _MODEL_KEYS if key not in entry]
        extra = sorted(set(entry) - set(_MODEL_KEYS))
        if missing or extra:
            raise _fail(name, f"{where}.{(missing or extra)[0]}", "missing key" if missing else "unknown key")
        tag, major, project, commit = entry["tag"], entry["major"], entry["project"], entry["commit"]
        if not isinstance(tag, str) or tag not in majors:
            raise _fail(name, f"{where}.tag", "must be the tag of a [[pin]] table")
        if type(major) is not int or major != majors[tag]:
            raise _fail(name, f"{where}.major", f"must be {majors[tag]}, the major of tag {tag}")
        if project != MODEL_PROJECT:
            raise _fail(name, f"{where}.project", f"must be {MODEL_PROJECT}")
        if not isinstance(commit, str) or not _COMMIT.fullmatch(commit):
            raise _fail(name, f"{where}.commit", "must be 40 lowercase hex digits")
        if any(pin.tag == tag for pin in pins):
            raise _fail(name, f"{where}.tag", f"the models of tag {tag} are pinned twice")
        pins.append(ModelPin(tag, major, MODEL_PROJECT, commit))
    unpinned = sorted(set(majors) - {pin.tag for pin in pins})
    if unpinned:
        raise _fail(name, "models", f"tag {unpinned[0]} has no model pin")
    return tuple(pins)


def file_sha256(path: Path) -> str:
    """The SHA-256 of a file, read in 1 MiB pieces."""
    return _file_digest(path)[0]


def read_model_stamp(folder: Path) -> dict[str, str]:
    """The model stamp of ``folder`` (``<cache>/<tag>/kicad-packages3D``): the path of each fetched file
    below the folder mapped to its SHA-256. Empty when the stamp is missing or is not such an object."""
    try:
        data = json.loads((folder / MODEL_STAMP).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    found: dict[str, str] = {}
    for key, value in cast(dict[object, object], data).items():
        if isinstance(key, str) and isinstance(value, str) and _TREE.fullmatch(value):
            found[key] = value
    return found


def write_model_stamp(folder: Path, entries: Mapping[str, str]) -> None:
    """Write the model stamp of ``folder`` through a temporary file, so that a reader never sees half."""
    text = json.dumps(dict(sorted(entries.items())), indent=2) + "\n"
    target = folder / MODEL_STAMP
    partial = folder / (MODEL_STAMP + ".part")
    partial.write_text(text, encoding="utf-8", newline="\n")
    os.replace(partial, target)


def _file_digest(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def tree_hash(folder: Path) -> tuple[str, int]:
    """``(digest, files)`` of ``folder`` in the scheme ``fenolite-tree-1``.

    One line ``<sha256 hex> <size> <path>\\n`` per regular file, the stamp excluded, with POSIX paths
    relative to ``folder`` and the lines sorted by the UTF-8 bytes of the path. Times, permissions, empty
    folders and listing order do not count. A symlink or an entry that is neither a regular file nor a
    folder raises ``ValueError`` naming it.
    """
    lines: list[tuple[bytes, bytes]] = []
    pending = [folder]
    while pending:
        current = pending.pop()
        for entry in os.scandir(current):
            path = Path(entry.path)
            relative = path.relative_to(folder).as_posix()
            mode = entry.stat(follow_symlinks=False).st_mode
            if stat.S_ISLNK(mode):
                raise ValueError(f"{relative}: a symlink cannot be hashed")
            if stat.S_ISDIR(mode):
                pending.append(path)
            elif stat.S_ISREG(mode):
                if relative == STAMP:
                    continue
                digest, size = _file_digest(path)
                key = relative.encode("utf-8")
                lines.append((key, f"{digest} {size} ".encode("ascii") + key + b"\n"))
            else:
                raise ValueError(f"{relative}: neither a regular file nor a folder")
    total = hashlib.sha256()
    for _, line in sorted(lines):
        total.update(line)
    return total.hexdigest(), len(lines)


def read_stamp(folder: Path) -> dict[str, object] | None:
    """The stamp of ``folder`` as a dictionary, or ``None`` when it is missing or not a JSON object."""
    try:
        data = json.loads((folder / STAMP).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return cast(dict[str, object], data) if isinstance(data, dict) else None


def _stamp(pin: LibraryPin) -> dict[str, object]:
    return {
        "scheme": SCHEME,
        "tag": pin.tag,
        "repo": pin.repo,
        "commit": pin.commit,
        "tree": pin.tree,
        "files": pin.files,
    }


def stamp_matches(folder: Path, pin: LibraryPin) -> bool:
    """Whether the stamp of ``folder`` equals ``pin``: exactly the stamp keys, each with the pin's value."""
    found = read_stamp(folder)
    return found is not None and found == _stamp(pin) and tuple(sorted(found)) == tuple(sorted(_STAMP_KEYS))


def write_stamp(folder: Path, pin: LibraryPin) -> None:
    stamp = json.dumps(_stamp(pin), indent=2, sort_keys=True) + "\n"
    (folder / STAMP).write_text(stamp, encoding="utf-8", newline="\n")


def verified_folders(
    cache: Path, pins: Sequence[LibraryPin] | None = None
) -> tuple[tuple[LibraryPin, Path], ...]:
    """Each pin with its folder ``<cache>/<tag>/<repo>``, for the folders whose stamp equals their pin."""
    found: list[tuple[LibraryPin, Path]] = []
    for pin in load_pins() if pins is None else pins:
        folder = cache / pin.tag / pin.repo
        if stamp_matches(folder, pin):
            found.append((pin, folder))
    return tuple(found)


def default_cache_dir(env: Mapping[str, str] | None = None, home: Path | None = None) -> Path:
    """``FENOLITE_LIBS_CACHE`` when set, else ``~/.cache/fenolite/libs``: the location that the fetch tool
    and the tests use. The resolver never looks there by itself."""
    variables = os.environ if env is None else env
    named = variables.get(CACHE_VARIABLE)
    if named:
        return Path(named)
    return (Path.home() if home is None else home) / ".cache" / "fenolite" / "libs"


__all__ = [
    "CACHE_VARIABLE",
    "MODEL_PROJECT",
    "MODEL_REPO",
    "MODEL_STAMP",
    "REPOS",
    "SCHEME",
    "STAMP",
    "LibraryPin",
    "ModelPin",
    "archive_template",
    "default_cache_dir",
    "file_sha256",
    "load_model_pins",
    "load_pins",
    "read_model_stamp",
    "read_stamp",
    "write_model_stamp",
    "stamp_matches",
    "tree_hash",
    "verified_folders",
    "write_stamp",
]
