# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The committed bundle of the viewer page (change c0247; capability board-viewer, "Viewer page", "Viewer
sources" and "Committed viewer bundle"; capability licensing-and-notices, "NOTICE lists only real
derivations"). Runs without Node: ``manifest.json`` records the digests ``viewer/build.mjs`` computed, and
this file computes them again; the rebuild is ``tools/build_viewer.py --check`` in the ``viewer`` job."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

from fenolite.view.export import CSS_MARK, JS_MARK, page

ROOT = Path(__file__).resolve().parents[3]
VIEWER = ROOT / "viewer"
STATIC = ROOT / "src" / "fenolite" / "view" / "static"
SOURCE_FILES = ("build.mjs", "package.json", "package-lock.json", "tsconfig.json")
REBUILD = "the committed viewer bundle is not a build of viewer/src: run `make viewer` (Node 22) and commit"


def _text(path: Path) -> str:
    return path.read_bytes().decode("utf-8").replace("\r\n", "\n")


def sources_digest(viewer: Path) -> str:
    """``sourcesDigest()`` of ``viewer/build.mjs``: every file of ``src`` and the four build files, in path
    order, each as its path, NUL, its text with LF line ends, NUL."""
    files = sorted(
        [p.relative_to(viewer).as_posix() for p in (viewer / "src").rglob("*") if p.is_file()]
        + [*SOURCE_FILES]
    )
    digest = hashlib.sha256()
    for name in files:
        digest.update(name.encode() + b"\0" + _text(viewer / name).encode() + b"\0")
    return digest.hexdigest()


def _manifest() -> dict[str, object]:
    return json.loads(_text(STATIC / "manifest.json"))


def test_manifest_outputs() -> None:
    """Scenario "A stale bundle fails without Node": an output edited by hand."""
    outputs = _manifest()["outputs"]
    assert isinstance(outputs, dict)
    assert sorted(outputs) == ["page.html", "viewer.css", "viewer.js"]
    for name, digest in outputs.items():
        assert hashlib.sha256(_text(STATIC / name).encode()).hexdigest() == digest, f"{name}: {REBUILD}"


def test_manifest_sources() -> None:
    """Scenario "A stale bundle fails without Node": a source edited after the last build."""
    if not (VIEWER / "build.mjs").is_file():
        pytest.skip("viewer/ is not in this tree (an sdist carries the bundle, not its sources)")
    assert sources_digest(VIEWER) == _manifest()["sources"], REBUILD


def test_manifest_sees_an_edit(tmp_path: Path) -> None:
    """The digest changes with a source: a copy of ``viewer/`` with one module edited."""
    if not (VIEWER / "build.mjs").is_file():
        pytest.skip("viewer/ is not in this tree")
    copy = tmp_path / "viewer"
    for name in SOURCE_FILES:
        (copy / name).parent.mkdir(parents=True, exist_ok=True)
        (copy / name).write_bytes((VIEWER / name).read_bytes())
    for path in (VIEWER / "src").rglob("*"):
        if path.is_file():
            target = copy / path.relative_to(VIEWER)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())
    assert sources_digest(copy) == sources_digest(VIEWER)
    units = copy / "src" / "core" / "units.ts"
    units.write_text(units.read_text(encoding="utf-8").replace("0.0254", "0.025"), encoding="utf-8")
    assert sources_digest(copy) != sources_digest(VIEWER)


def test_assembled() -> None:
    """Scenario "The served page is the assembled page"."""
    html = page(live=True)
    css, js = _text(STATIC / "viewer.css"), _text(STATIC / "viewer.js")
    assert CSS_MARK not in html and JS_MARK not in html
    style = re.search(r"<style>\n(.*?)</style>", html, re.DOTALL)
    assert style is not None and css in style.group(1)
    *_, script = re.findall(r"<script>\n(.*?)</script>", html, re.DOTALL)
    assert script.startswith('"use strict";\nconst EMBED = /*__DATA__*/null;\nconst LIVE = true;\n')
    assert js in script


def test_no_early_end() -> None:
    """A bundle that held ``</script`` or ``</style`` would end its element in the page."""
    assert "</script" not in _text(STATIC / "viewer.js").lower()
    assert "</style" not in _text(STATIC / "viewer.css").lower()


def test_preact_panels() -> None:
    """Scenario "Panels render through Preact"."""
    js = _text(STATIC / "viewer.js")
    assert "\nvar preact=(()=>{" in js
    for name in ("buildDiffList", "buildMessages", "buildFindings", "buildNav"):
        start = js.index(f"\nfunction {name}(")
        body = js[start : js.index("\n}\n", start)]
        assert "preact.render(" in body, name


def test_notice() -> None:
    """Scenario "Bundled viewer code"."""
    notice = _text(ROOT / "NOTICE")
    assert notice.startswith("Fenolite — Copyright (c) 2026 Fenolite contributors\n")
    assert re.search(r"Preact [0-9.]+ .*MIT", notice, re.DOTALL), notice
    js = _text(STATIC / "viewer.js")
    head = js[: js.index("var preact=")]
    assert "Copyright (c) 2015-present Jason Miller" in head
    assert "Permission is hereby granted, free of charge" in head
    version = (
        json.loads(_text(VIEWER / "package.json"))["dependencies"]["preact"] if VIEWER.is_dir() else None
    )
    if version is not None:
        assert f"Preact {version}" in head and f"Preact {version}" in notice
