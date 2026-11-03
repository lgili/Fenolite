# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Original Mini native-project inputs and actual reviewed command replay (c0351)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import _drawn
from _buildhelp import build as build_design

from fenolite.api import run
from fenolite.dsl import copper, mm

STAMP = "2026-11-01T00:00:00Z"
SETTINGS = {
    "intersheets_ref_show": True,
    "intersheets_ref_own_page": True,
    "intersheets_ref_short": True,
    "intersheets_ref_prefix": "AUTH[",
    "intersheets_ref_suffix": "]",
}


def snapshot(folder: Path) -> dict[str, str]:
    return {
        path.relative_to(folder).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in folder.rglob("*")
        if path.is_file()
    }


def authored(folder: Path, target: int = 10) -> Path:
    folder.mkdir()
    design = _drawn.design("full")
    design.track(
        "project_template_probe",
        (mm(35), mm(25)),
        (mm(37), mm(25)),
        width=mm("0.25"),
        net=next(iter(design.nets.values())),
    )
    design.via(
        "project_template_annulus",
        (mm(10), mm(10)),
        net=next(iter(design.nets.values())),
        diameter=mm("0.6"),
        drill=mm("0.4"),
        free=True,
    )
    output = build_design(
        design,
        target,
        project_dir=_drawn.folder("full"),
        drawn=_drawn.drawn("full"),
        drawn_file="schematic.toml",
        copper_intents=copper(design),
    )
    assert output.files and not [issue for issue in output.issues if issue.severity == "error"]
    for name, data in output.files.items():
        if name.startswith(".fenolite/"):
            continue
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    path = next(folder.glob("*.kicad_pro"))
    project = json.loads(path.read_text())
    project.setdefault("schematic", {}).setdefault("drawing", {}).update(SETTINGS)
    project["board"]["design_settings"]["rules"]["min_via_annular_width"] = 0.19
    path.write_text(json.dumps(project, sort_keys=True, indent=2) + "\n")
    return path


def imported(base: Path, source: Path, *, out: str = "code", target: int = 10) -> Path:
    args = ("import", str(source), "--to", "python", "--out", out, "--kicad-version", str(target))
    planned = run(*args, "--dry-run", cwd=base, timestamp=STAMP)
    assert planned.exit_code == 0, planned.error
    assert planned.result["unexpressed"] == []
    assert not (base / out).exists()
    confirmed = run(*args, "--confirm", "--plan", planned.result["plan_id"], cwd=base, timestamp=STAMP)
    assert confirmed.exit_code == 0, confirmed.error
    return base / out


def built(base: Path, code: Path, *, out: str = "rebuilt", target: int = 10) -> Path:
    args = ("build", str(code / "design.py"), "--out", out, "--kicad-version", str(target))
    planned = run(*args, "--dry-run", cwd=base, timestamp=STAMP)
    assert planned.exit_code == 0, planned.error
    confirmed = run(*args, "--confirm", "--plan", planned.result["plan_id"], cwd=base, timestamp=STAMP)
    assert confirmed.exit_code == 0, confirmed.error
    return next((base / out).glob("*.kicad_pro"))
