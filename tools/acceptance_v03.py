# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Author, build and judge the v0.3 acceptance project (c0092), without assuming Altium ran.

The builds use Fenolite's library; independent checks use its CLI. --build-only is
the quick local proof. The complete run and its KiCad probe belong to CI.
"""

from __future__ import annotations

import argparse
import json
import runpy
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from fenolite import __version__  # noqa: E402
from fenolite.backends.kicad.libs import LibraryConfig, LibraryResolver  # noqa: E402
from fenolite.backends.kicad.triad import write_triad  # noqa: E402
from fenolite.cli.cmd_build import _catalog_definitions  # noqa: E402
from fenolite.dsl import to_model  # noqa: E402
from fenolite.dsl.convert import placements  # noqa: E402
from fenolite.dsl.intents import copper  # noqa: E402
from fenolite.lens.altium import build_altium  # noqa: E402
from fenolite.lens.build import build_design  # noqa: E402
from fenolite.templates import build_sheet, example_path, load_spec  # noqa: E402

NAME = "acceptance_v03"


def _write(folder: Path, files: dict[str, bytes]) -> None:
    for name, data in sorted(files.items()):
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def build(out: Path):
    """Build both targets from one authored circuit and layout; no external library or tool."""
    namespace = runpy.run_path(str(ROOT / "examples/acceptance_v03/design.py"))
    script = namespace["design"]
    model = to_model(script)
    footprints, symbols, _ = _catalog_definitions(
        model,
        {key: value.definition for key, value in script.footprints.items()},
        {key: value.definition for key, value in script.symbols.items()},
    )
    path = example_path("iso5457_generic")
    frame = build_sheet(load_spec(path.read_text(), file=path.name), base_dir=path.parent)
    resolver = LibraryResolver(LibraryConfig(project_dir=out, env={}, use_global_table=False))
    built = build_design(
        model,
        placements(script),
        name=NAME,
        copper=6,
        resolver=resolver,
        target=10,
        authored_footprints=footprints,
        authored_symbols=symbols,
        copper_intents=copper(script),
        drawing_sheet=frame,
    )
    errors = [issue.message for issue in built.issues if issue.severity == "error"]
    if errors or not built.files:
        raise ValueError("KiCad acceptance build refused: " + "; ".join(errors))
    layout = built.layout or built.design
    model = namespace["acceptance_model"](layout)
    model = replace(
        model,
        board=replace(
            model.board,
            outline=to_model(script).board.outline,
            graphics=tuple(graphic for graphic in model.board.graphics if graphic.layer != "Edge.Cuts"),
        ),
    )
    bodies = {fp.id: fp.bodies for fp in model.board.footprints}
    # The two public backends represent an NPTH differently: KiCad requires
    # a footprint; the Altium model writer accepts a standalone Board.holes item.
    kicad_model = replace(
        model,
        circuit=replace(layout.circuit, buses=model.circuit.buses),
        board=replace(
            model.board,
            holes=layout.board.holes,
            footprints=tuple(
                replace(fp, bodies=bodies.get(fp.id, fp.bodies)) for fp in layout.board.footprints
            ),
        ),
    )
    files = dict(built.files)
    files.update(
        {
            name: text.encode()
            for name, text in write_triad(
                kicad_model,
                name=NAME,
                target=10,
                schematic=True,
                allow_lossy=True,
                existing_project=files[f"{NAME}.kicad_pro"].decode(),
            ).items()
        }
    )
    _write(out / "kicad", files)
    requested = {path: request for path, request in placements(script).items() if path != "H1"}
    altium = build_altium(
        model,
        name=NAME,
        copper=6,
        sheets="modules",
        outjob=True,
        drawing_sheet=frame,
        authored_footprints=footprints,
        authored_symbols=symbols,
        bodies="extruded",
        placements=requested,
        placed=tuple(requested),
    )
    errors = [issue.message for issue in altium.issues if issue.severity == "error"]
    if errors or f"{NAME}.PcbDoc" not in altium.files or f"{NAME}.OutJob" not in altium.files:
        raise ValueError(
            "Altium acceptance build refused: "
            + "; ".join(
                errors
                or [issue.message for issue in altium.issues if issue.code == "altium.pcbdoc-not-written"]
            )
        )
    _write(out / "altium", dict(altium.files))
    return model, built, altium


def command(args: list[str], *, cwd: Path) -> dict[str, object]:
    """Record the actual exit code and JSON reply; a nonzero step is never reported as passing."""
    run = subprocess.run(
        [sys.executable, "-m", "fenolite", *args, "--json"],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        reply = json.loads(run.stdout) if run.stdout.strip() else json.loads(run.stderr)
    except (json.JSONDecodeError, ValueError):
        reply = {"message": run.stderr.strip()}
    return {"passed": run.returncode == 0, "exit_code": run.returncode, "reply": reply}


def run(out: Path, *, kicad_cli: str | None = None, build_only: bool = False) -> dict[str, object]:
    """A measured report. Kit evidence remains a separate real recorded run."""
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    model, _, altium = build(out)
    steps: dict[str, object] = {
        "build-kicad": {"passed": True},
        "build-altium": {"passed": True},
    }
    version = None
    if not build_only:
        from fenolite.backends.kicad.cli import cli_for

        if not kicad_cli:
            raise ValueError("a complete acceptance run requires --kicad-cli")
        version = cli_for(Path(kicad_cli)).version()
        # Existing registered conversion profile: 3 nm coordinates and 20 ppm
        # accumulated routed length, the triangle's measured rounding policy.
        from fenolite.convert import profiles_text

        (out / "profiles.toml").write_text(profiles_text())
        tool = ["--kicad-cli", kicad_cli]
        steps["check-kicad"] = command(["check", "kicad", *tool], cwd=out)
        steps["check-altium"] = command(["check", f"altium/{NAME}.PrjPcb"], cwd=out)
        steps["equivalent-targets"] = command(
            [
                "equivalent",
                f"kicad/{NAME}.kicad_pcb",
                f"altium/{NAME}.PcbDoc",
                "--level",
                "5",
                "--frame",
                "relative",
                "--ignore-ref",
                "",
                "--ignore-ref",
                "H1",
                "--exclusions",
                "profiles.toml",
                "--profile",
                "kicad-to-altium",
            ],
            cwd=out,
        )
        steps["roundtrip-altium"] = command(
            [
                "roundtrip",
                f"altium/{NAME}.PrjPcb",
                "--level",
                "rta3",
            ],
            cwd=out,
        )
        steps["independent-import"] = command(
            [
                "equivalent",
                f"altium/{NAME}.PcbDoc",
                "--against",
                "kicad-import",
                "--level",
                "5",
                "--frame",
                "relative",
                "--ignore-ref",
                "",
                *tool,
            ],
            cwd=out,
        )
    report: dict[str, object] = {
        "schema": "fenolite.acceptance-v03.v0",
        "fenolite_version": __version__,
        "kicad_version": version,
        "altium_version": None,
        "kit_run_id": None,
        "build_only": build_only,
        "steps": steps,
        "passed": not build_only and all(step["passed"] for step in steps.values()),
        "coverage": {
            "copper_layers": 6,
            "modules": [module.path for module in model.circuit.modules],
            "buses": len(model.circuit.buses),
            "bodies": sum(len(fp.bodies) for fp in model.board.footprints),
        },
        "build_issues": [issue.code for issue in altium.issues],
    }
    (out / "acceptance.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--kicad-cli")
    parser.add_argument("--build-only", action="store_true")
    args = parser.parse_args(argv)
    report = run(args.out, kicad_cli=args.kicad_cli, build_only=args.build_only)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if args.build_only or report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
