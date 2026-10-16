# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Build and check the authored Altium v0.3 acceptance tree; JSON results stay explicit.

--prepare-only builds files and verifies scope without launching KiCad. Full runs
perform readback checks, RT-A3 and the level-5 triangle through the existing CLI.
"""

from __future__ import annotations

import argparse
import json
import os
import runpy
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

import fenolite  # noqa: E402
from fenolite.backends import registry  # noqa: E402
from fenolite.backends.altium import lower, pcbdoc, project, rulemap, schdot  # noqa: E402
from fenolite.backends.altium.read.pcb import read_pcbdoc  # noqa: E402
from fenolite.backends.kicad import altium_import, pcb  # noqa: E402
from fenolite.backends.kicad.cli import cli_for  # noqa: E402
from fenolite.checks.equivalence import load_profiles, select_profile  # noqa: E402
from fenolite.core.ids import derived_id  # noqa: E402
from fenolite.dsl import mm  # noqa: E402
from fenolite.dsl.holes import hole_footprint  # noqa: E402
from fenolite.model import canonical  # noqa: E402
from fenolite.model.board import FootprintInstance  # noqa: E402
from fenolite.model.circuit import Component  # noqa: E402
from fenolite.model.design import Design  # noqa: E402
from fenolite.templates import build_sheet, load_spec  # noqa: E402

EXAMPLE = ROOT / "examples" / "acceptance_v03"
NAME = "acceptance_v03"
SEED = "92"
TIMESTAMP = "2026-10-14T00:00:00Z"


def command(args: list[str], folder: Path, stage: str) -> dict[str, Any]:
    """Run one CLI stage and retain its raw envelope only in the generated folder."""
    result = subprocess.run(
        [sys.executable, "-m", "fenolite", *args, "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
        timeout=300,
    )
    (folder / f"{stage}.stdout.json").write_text(result.stdout, encoding="utf-8")
    (folder / f"{stage}.stderr.json").write_text(result.stderr, encoding="utf-8")
    payload = result.stdout if result.returncode == 0 else result.stderr
    try:
        body = json.loads(payload)
    except json.JSONDecodeError as error:
        raise ValueError(f"{stage} returned no JSON envelope") from error
    return {"name": stage, "passed": result.returncode == 0, "exit_code": result.returncode, "reply": body}


def build(folder: Path, target: str) -> dict[str, Any]:
    args = [
        "build",
        str(EXAMPLE / "design.py"),
        "--out",
        str(folder / target),
        "--target",
        target,
        "--seed",
        SEED,
        "--timestamp",
        TIMESTAMP,
    ]
    args += ["--kicad-version", "10"] if target == "kicad" else ["--altium-sheets", "modules"]
    reviewed = command([*args, "--dry-run"], folder, f"build-{target}-plan")
    if not reviewed["passed"]:
        return reviewed
    plan = reviewed["reply"]["result"]["plan_id"]
    return command([*args, "--confirm", "--plan", plan], folder, f"build-{target}")


def add_bus(folder: Path) -> None:
    """Author the neutral-model bus and regenerate the Altium schematic through its writer.

    The board geometry is emitted with the free hole through the existing writers. The DSL cannot declare
    an arbitrary ranged bus; this authored model addition is shared by both caches.
    """
    namespace = runpy.run_path(str(EXAMPLE / "design.py"))
    models: dict[str, Design] = {}
    for target in ("kicad", "altium"):
        path = folder / target / ".fenolite"
        models[target] = namespace["acceptance_model"](canonical.load_dir(path))
        canonical.dump_dir(models[target], path)
    # A free mechanical hole belongs to the neutral board, not to its circuit.
    source = models["kicad"]
    hole = source.board.holes[0]
    land = hole_footprint(mm(2))
    component = Component(
        id=derived_id("cmp", "acceptance", "hole"), ref="", path="free-hole", lib_footprint_ref=land.lib_id
    )
    footprint = FootprintInstance(
        id=derived_id("fp", "acceptance", "hole"),
        component_id=component.id,
        lib_ref=land.lib_id,
        position=hole.position,
        pads=land.definition.pads,
    )
    models["kicad"] = replace(
        source,
        circuit=replace(source.circuit, components=(*source.circuit.components, component)),
        board=replace(source.board, holes=(), footprints=(*source.board.footprints, footprint)),
    )
    canonical.dump_dir(models["kicad"], folder / "kicad" / ".fenolite")
    board = pcb.write_board(models["kicad"], target=10)
    (folder / "kicad" / f"{NAME}.kicad_pcb").write_text(board.text, encoding="utf-8", newline="\n")
    findings = []
    lowered = lower.from_design(models["altium"], bodies="extruded", issues=findings)
    if any(item.severity == "error" or item.where in lower.LOSS_KINDS for item in findings):
        raise ValueError("acceptance board lowering omitted a required item")
    if lowered.pcb is None:
        raise ValueError("acceptance model lowered without a PCB")
    (folder / "altium" / f"{NAME}.PcbDoc").write_bytes(
        pcbdoc.write_pcbdoc(lowered.pcb, filename=f"{NAME}.PcbDoc")
    )
    template = EXAMPLE / "acceptance.sheet.toml"
    drawing = build_sheet(
        load_spec(template.read_text(encoding="utf-8"), file=template.name), base_dir=EXAMPLE
    )
    frame = schdot.sheet_frame(drawing, width=297_000_000, height=210_000_000, paper="A4").frame
    frames = {path.name: frame for path in (folder / "altium").glob("*.SchDoc")}
    files = project.write_project(
        models["altium"], name=NAME, project=False, sheets="modules", form="binary", frames=frames
    )
    for name, data in files.items():
        (folder / "altium" / name).write_bytes(data)


def inventory(folder: Path) -> dict[str, bool]:
    path = folder / "altium" / f"{NAME}.PrjPcb"
    backend = registry.for_path(path)
    if backend is None:
        raise ValueError("acceptance project has no reader")
    model = backend.read(path).design
    authored = canonical.load_dir(folder / "altium" / ".fenolite")
    board = model.board
    exact = {row.neutral for row in rulemap.TABLE if row.exact}
    kicad = pcb.read_board(folder / "kicad" / f"{NAME}.kicad_pcb")
    # since change c0168 the Altium import gives a free pad whose copper is its hole as a board hole
    native_holes = sorted(
        [pad.drill for fp in board.footprints for pad in fp.pads if pad.kind == "np_thru_hole"]
        + [hole.drill for hole in board.holes if not hole.plated]
    )
    kicad_holes = sorted(
        pad.drill for fp in kicad.board.footprints for pad in fp.pads if pad.kind == "np_thru_hole"
    )
    profile = select_profile(
        load_profiles(altium_import.exclusions_text(), file=altium_import.EXCLUSIONS_FILE),
        altium_import.PROFILE,
        "10.0",
    )
    if profile is None:
        raise ValueError("acceptance has no committed KiCad-10 triangle profile")
    matching_hole = len(native_holes) == len(kicad_holes) == 1 and all(
        drill is not None and abs(drill - 2_000_000) <= profile.tolerance_nm
        for drill in (*native_holes, *kicad_holes)
    )
    return {
        "six_copper_layers": len([layer for layer in board.layers if layer.kind == "copper"]) == 6,
        "blind_and_buried_vias": {"blind", "buried"} <= {via.via_type for via in board.vias},
        "board_texts": bool(board.texts),
        "keepout": bool(board.keepouts)
        or any(
            region.properties.get("V7_LAYER") == "KEEPOUT"
            for region in read_pcbdoc((folder / "altium" / f"{NAME}.PcbDoc").read_bytes()).regions
        ),
        "non_plated_hole": matching_hole,
        "bodies": any(fp.bodies for fp in board.footprints),
        "polygons": bool(board.zones),
        "every_exact_rule": exact <= {rule.kind for rule in model.rules.rules},
        "two_level_module_tree": any(module.path.count("/") >= 1 for module in model.circuit.modules),
        "bus": bool(model.circuit.buses),
        "outjob": (folder / "altium" / f"{NAME}.OutJob").is_file(),
        "drawing_sheet": authored.board.sheet is not None and authored.board.sheet.drawing_sheet is not None,
    }


def run(
    folder: Path,
    *,
    prepare_only: bool = False,
    kicad_cli: str | None = None,
    altium_version: str | None = None,
    kit_run_id: str | None = None,
) -> dict[str, Any]:
    """Use a new output folder; never replace a previous acceptance result."""
    folder = folder.resolve()
    folder.mkdir(parents=True, exist_ok=False)
    summary: dict[str, Any] = {
        "schema": "fenolite.acceptance-v03.v0",
        "versions": {"fenolite": fenolite.__version__, "kicad": None, "altium": altium_version},
        "kit_run_id": kit_run_id,
        "mode": "prepare" if prepare_only else "full",
        "steps": [],
    }
    steps = summary["steps"]
    try:
        for target in ("kicad", "altium"):
            result = build(folder, target)
            steps.append({key: result[key] for key in ("name", "passed", "exit_code")})
            if not result["passed"]:
                return summary
        add_bus(folder)
        summary["scope"] = inventory(folder)
        steps.append({"name": "written-scope", "passed": all(summary["scope"].values())})
        if prepare_only or not steps[-1]["passed"]:
            return summary
        cli_path = kicad_cli or os.environ.get("FENOLITE_KICAD_CLI") or shutil.which("kicad-cli")
        if not cli_path:
            steps.append({"name": "kicad-import", "passed": False, "reason": "kicad-cli missing"})
            return summary
        cli = cli_for(Path(cli_path), timeout=300)
        summary["versions"]["kicad"] = cli.version()
        board = folder / "kicad" / f"{NAME}.kicad_pcb"
        document = folder / "altium" / f"{NAME}.PcbDoc"
        project_file = folder / "altium" / f"{NAME}.PrjPcb"
        exclusions = folder / "import-exclusions.toml"
        exclusions.write_text(altium_import.exclusions_text(), encoding="utf-8")
        cases = [
            ("check-kicad", ["check", str(board), "--stages", "model.validate,roundtrip"]),
            ("check-altium", ["check", str(project_file), "--stages", "model.validate,roundtrip.rta1"]),
            (
                "equivalent-targets",
                [
                    "equivalent",
                    str(board),
                    str(document),
                    "--level",
                    "5",
                    "--frame",
                    "relative",
                    "--ignore-ref",
                    "",
                    "--ignore-ref",
                    "[*]",
                    "--exclusions",
                    str(exclusions),
                    "--profile",
                    altium_import.PROFILE,
                ],
            ),
            ("roundtrip-project", ["roundtrip", str(project_file), "--level", "rta3"]),
        ]
        for stage, args in cases:
            result = command(args, folder, stage)
            steps.append({key: result[key] for key in ("name", "passed", "exit_code")})
        imported = cli.import_board(document)
        import_passed = imported.board is not None and imported.run.returncode == 0
        steps.append({"name": "kicad-import", "passed": import_passed})
        if import_passed:
            converted = folder / "imported.kicad_pcb"
            converted.write_bytes(imported.board)
            exclusions = folder / "import-exclusions.toml"
            exclusions.write_text(altium_import.exclusions_text(), encoding="utf-8")
            result = command(
                [
                    "equivalent",
                    str(board),
                    str(converted),
                    "--level",
                    "5",
                    "--exclusions",
                    str(exclusions),
                    "--profile",
                    altium_import.PROFILE,
                    "--ignore-ref",
                    "",
                    "--ignore-ref",
                    "[*]",
                ],
                folder,
                "equivalent-import",
            )
            steps.append({key: result[key] for key in ("name", "passed", "exit_code")})
        return summary
    except Exception as error:
        steps.append({"name": "execution-error", "passed": False, "error_type": type(error).__name__})
        raise
    finally:
        summary["passed"] = bool(steps) and all(step["passed"] for step in steps)
        summary["acceptance_complete"] = (
            summary["passed"]
            and not prepare_only
            and any(step["name"] == "equivalent-import" for step in steps)
        )
        (folder / "summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--kicad-cli")
    parser.add_argument("--altium-version")
    parser.add_argument("--kit-run-id")
    args = parser.parse_args(argv)
    result = run(
        args.out,
        prepare_only=args.prepare_only,
        kicad_cli=args.kicad_cli,
        altium_version=args.altium_version,
        kit_run_id=args.kit_run_id,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
