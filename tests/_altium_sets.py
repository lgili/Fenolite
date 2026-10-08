# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The public Altium project sets as folders (the rows of one use ``altium-set:<nn>`` of the corpus
manifest), for the corpus tests that check a whole project (changes c0088 and c0090):
``test_altium_documents.py``, ``test_altium_copper.py`` and ``test_altium_rta3.py`` share them without
importing a test module. ``SETS`` is ``project_sets()``, made once."""

from __future__ import annotations

import shutil
import tomllib
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlparse

from _corpus import MANIFEST, CorpusItem, manifest_items, require


def project_sets() -> dict[str, list[CorpusItem]]:
    """Set name → its manifest rows, in name order."""
    found: dict[str, list[CorpusItem]] = {}
    for item in manifest_items("altium-import"):
        (name,) = [use for use in item.uses if use.startswith("altium-set:")]
        found.setdefault(name, []).append(item)
    return dict(sorted(found.items()))


SETS = project_sets()


def _in_repository() -> dict[str, PurePosixPath]:
    """Row id → the file's path inside its repository (the part of the URL after the pinned commit)."""
    rows = tomllib.loads(MANIFEST.read_text(encoding="utf-8")).get("file", [])
    out: dict[str, PurePosixPath] = {}
    for row in rows:
        path = unquote(urlparse(row["url"]).path)
        if f"/{row['ref']}/" in path:
            out[row["id"]] = PurePosixPath(path.split(f"/{row['ref']}/", 1)[1])
    return out


def lay_out(items: list[CorpusItem], folder: Path) -> Path:
    """Copy the files of one set under ``folder`` as they lie around their project file; returns the
    project's folder. A file outside the project file's folder is left out, as the project reader does."""
    places = _in_repository()
    (project,) = [item for item in items if "-prjpcb-" in item.id]
    base = places[project.id].parent
    for item in items:
        source = require(item)
        place = places[item.id]
        if base not in (place.parent, *place.parents):
            continue
        target = folder / place.relative_to(base)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    return folder


__all__ = ["SETS", "lay_out", "project_sets"]
