# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Visual tests of the viewer page (capability viewer-visual-tests, change c0191): the fixtures, their pages
and the browser harness, shared by ``tests/visual`` and ``tools/update_view_refs.py``.

Every fixture is a file authored for Fenolite (``tests/data/MANIFEST.toml``, ``origin = "authored"``) or
built here from Fenolite's own test data; its page is written by ``fenolite view PATH --export`` (a dry run,
then the confirmed plan). ``run`` hands jobs to ``tests/visual/harness.js`` in Node's Playwright, with
Chromium on the fonts of ``tests/visual/fonts.conf`` (DejaVu only), and returns its replies.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fenolite.cli.main as cli_main

ROOT = Path(__file__).resolve().parents[1]
VISUAL = ROOT / "tests" / "visual"
REFS = VISUAL / "refs"
HARNESS = VISUAL / "harness.js"
FONTS = VISUAL / "fonts.conf"
DATA = ROOT / "tests" / "data"
WIDTH, HEIGHT = 1100, 700
THRESHOLD = 2
"""A pixel differs when one of its channels differs by more than two levels (design, decision 2)."""
MAX_RATIO = 0.001
"""At most 0.1 % of the pixels may differ."""
BROWSER_HINT = (
    "Node with Playwright and its Chromium is needed: npm install playwright@1.63.0 and "
    "npx playwright install chromium (or set FENOLITE_PLAYWRIGHT to the package)"
)

JOB = """[OutputJobFile]
Version=1.0

[OutputGroup1]
Name=Docs
VariantName=[No Variations]
OutputMedium1=PDF
OutputMedium1_Type=Publish
OutputMedium2=Data
OutputMedium2_Type=GeneratedFiles
OutputType1=PCBDrawing
OutputName1=Assembly Drawing
OutputCategory1=Documentation
OutputDocumentPath1=board_Assembly.PCBDwf
OutputEnabled1=1
OutputEnabled1_OutputMedium1=1
OutputType2=BOM_PartType
OutputName2=Bill of Materials
OutputCategory2=Report
OutputDocumentPath2=[ActiveBOM Document]
OutputEnabled2=1
OutputEnabled2_OutputMedium2=1

[PublishSettings]
OutputBasePath1=Outputs\\
OutputPathMedia1=[Media Name]
OutputFileName1=board.PDF
OutputBasePath2=Outputs\\
OutputPathOutputer2=[Output Type]
"""


@dataclass(frozen=True)
class Fixture:
    """One scene kind: the file whose page is drawn, and the document of that page to open."""

    name: str
    source: str
    doc: str = ""
    scheme: str = "dark"
    """The interface theme the page is drawn in (c0268): Chromium's prefers-color-scheme."""
    script: str = ""
    """What the page does before its screenshot (c0269: select a net)."""


FIXTURES = (
    Fixture("kicad_board", "kicad/board/two_layer.kicad_pcb"),
    Fixture("kicad_board_light", "kicad/board/two_layer.kicad_pcb", scheme="light"),
    Fixture(
        "kicad_board_net", "kicad/board/two_layer.kicad_pcb", script='selectNetAt(S.nets.indexOf("GND"));'
    ),
    Fixture("altium_board", "altium/blink/blink.PcbDoc"),
    Fixture("altium_sheet", "altium/blink/blink.SchDoc"),
    Fixture("kicad_sheet", "kicad/parity/agree/blink.kicad_sch"),
    Fixture("footprint_library", "altium/blink/blink.PcbLib"),
    Fixture("symbol_library", "libs/Mini.kicad_sym"),
    Fixture("draftsman", "@draftsman"),
    Fixture("output_job", "@outjob"),
)
NAMES = tuple(f.name for f in FIXTURES)


def browser_missing() -> str | None:
    """Why the harness cannot run here, or ``None`` when Node and Playwright are found."""
    node = shutil.which("node")
    if node is None:
        return "node is not installed. " + BROWSER_HINT
    package = os.environ.get("FENOLITE_PLAYWRIGHT", "playwright")
    probe = subprocess.run(
        [node, "-e", f"require({json.dumps(package)})"], capture_output=True, text=True, timeout=60
    )
    return None if probe.returncode == 0 else "Playwright is not found. " + BROWSER_HINT


def _source(fixture: Fixture, folder: Path) -> Path:
    if fixture.source == "@draftsman":
        from _draftsman import DOCUMENT, stored  # the authored drawing of the c0180 tests

        path = folder / "board_Assembly.PCBDwf"
        path.write_bytes(stored(DOCUMENT))
        return path
    if fixture.source == "@outjob":
        path = folder / "Docs.OutJob"
        path.write_text(JOB, encoding="utf-8")
        return path
    return DATA / fixture.source


def _cli(*args: str) -> dict[str, Any]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = cli_main.main(list(args))
    if code != 0:
        raise RuntimeError(f"fenolite {' '.join(args)} exited {code}")
    return json.loads(out.getvalue())


def export(path: Path, page: Path, *extra: str) -> Path:
    """The page ``fenolite view PATH --export`` writes for ``path``: a dry run, then its confirmed plan."""
    base = ["view", str(path), *extra, "--export", str(page), "--cache", "off", "--json"]
    plan = _cli(*base, "--dry-run")["result"]["plan_id"]
    _cli(*base, "--confirm", "--plan", plan)
    return page


def pages(folder: Path) -> dict[str, Path]:
    """The page of every fixture, written into ``folder``, by fixture name."""
    folder.mkdir(parents=True, exist_ok=True)
    out: dict[str, Path] = {}
    for fixture in FIXTURES:
        source = _source(fixture, folder)
        out[fixture.name] = export(source, folder / f"{fixture.name}.html")
    blink = folder / "blink"
    shutil.copytree(DATA / "altium" / "blink", blink, dirs_exist_ok=True)
    out["blink_project"] = export(
        blink / "blink.PrjPcb", folder / "blink_project.html", "--doc", "blink.PcbDoc"
    )
    return out


def job(
    name: str, page: Path, out: Path, *, script: str = "", ref: Path | None = None, **extra: Any
) -> dict[str, Any]:
    """A screenshot job of the harness: ``ref`` defaults to the committed reference of ``name``; a fixture's
    interface theme is its ``scheme`` (c0268)."""
    fixture = next((f for f in FIXTURES if f.name == name), None)
    scheme = fixture.scheme if fixture is not None else "dark"
    script = script or (fixture.script if fixture is not None else "")
    return {
        "name": name,
        "page": str(page),
        "width": WIDTH,
        "height": HEIGHT,
        "script": script,
        "shot": str(out / f"{name}.png"),
        "ref": str(ref if ref is not None else REFS / f"{name}.png"),
        "diff": str(out / f"{name}.diff.png"),
        "threshold": THRESHOLD,
        "max_ratio": MAX_RATIO,
        "scheme": scheme,
    } | extra


def run(jobs: list[dict[str, Any]], folder: Path) -> list[dict[str, Any]]:
    """The harness's replies to ``jobs``, run in one Chromium with the fonts of ``fonts.conf``."""
    spec = folder / "jobs.json"
    spec.write_text(json.dumps(jobs), encoding="utf-8")
    env = dict(os.environ, FONTCONFIG_FILE=str(FONTS))
    node = shutil.which("node") or "node"
    done = subprocess.run(
        [node, str(HARNESS), str(spec)], capture_output=True, text=True, timeout=600, env=env, check=False
    )
    if done.returncode != 0:
        raise RuntimeError(f"the harness failed: {done.stderr.strip()[-2000:]}")
    return json.loads(done.stdout.strip().splitlines()[-1])


__all__ = ["FIXTURES", "MAX_RATIO", "NAMES", "REFS", "browser_missing", "export", "job", "pages", "run"]
