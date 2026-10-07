# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite export PATH --out DIR``: fabrication files through ``kicad-cli``, on a copy of the project
(capability manufacturing-exports; ``docs/cli-contract.md``, "export"; user guide ``docs/exports.md``).

``--altium-rul`` (change c0084) writes the project's rules as an Altium rule file. It runs no tool, so it
alone needs no ``kicad-cli``; it is not one of the kinds of ``--all``.

``kicad-cli`` only sees the copy set of ``projectset.project_set``, so the project folder never changes.
Every file the tool wrote becomes a planned write under ``DIR``; when a kind fails, nothing is planned,
so a folder never holds a partial set.

Change c0116 adds the six document kinds (``--ipc2581``, ``--odb``, ``--step``, ``--pdf``, ``--dxf``,
``--sch-pdf``). Each is selected by its own flag, ``--all`` keeps the four fabrication kinds, and no
preset reaches a document kind. ``result.repeat`` says which hashes compare between two exports, and
``result.models`` lists the 3D model files a STEP was given.

Change c0117 adds the two drawing kinds (``--fab-drawing``, ``--assembly-drawing``) and ``--drawing-spec``.
They are KiCad's: ``kicad-cli`` plots them from copies of the board that hold Fenolite's tables, and this
module only reads the specification, finds the drawing sheet and what it takes of a page (through
``templates.layout``, which ``exports`` may not import), and describes the pages in ``result.drawings``.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
from pathlib import Path
from typing import Any

import fenolite
from fenolite.backends import registry
from fenolite.backends.kicad import models as kicad_models
from fenolite.backends.kicad import pro as kicad_pro
from fenolite.backends.kicad import wks
from fenolite.backends.kicad.projectset import project_set, resolve_board
from fenolite.cli._examples import EXAMPLE_BOARD
from fenolite.cli._kicadtool import DEFAULT_TIMEOUT, board_format, preflight
from fenolite.cli._manifest import joined, merged_write
from fenolite.cli.api import Command, Context, PlannedWrite, Result, depends_on
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.errors import FenoliteError, FormatError, Issue
from fenolite.core.evidence import Evidence
from fenolite.core.units import Nm
from fenolite.exports import DOCUMENTS_EVIDENCE, EVIDENCE, altium_rul, drawing_spec, drawings, manifest
from fenolite.exports import preset as presets
from fenolite.exports.codes import issue as export_issue
from fenolite.exports.drawing_layout import Obstacles
from fenolite.exports.plan import DOCUMENT_KINDS, FAB_KINDS, KINDS, Artifact, run_kind, stackup_note
from fenolite.model.presentation import DrawingSheet

HELP = "export fabrication files through kicad-cli on a copy of the project (writes under DIR)"
RESULT_KEYS = ("path", "kind", "layer", "bytes", "sha256", "content_sha256")
"""The keys of one artefact in ``result.artifacts``; the manifest holds more (``docs/exports.md``)."""


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/exports.md."
    parser.add_argument("path", metavar="PATH", help="a .kicad_pcb, a .kicad_pro or a project folder")
    parser.add_argument("-o", "--out", required=True, metavar="DIR", help="the folder to write under")
    parser.add_argument("--gerbers", action="store_true", help="Gerber files and the job file")
    parser.add_argument("--drill", action="store_true", help="Excellon drill files (PTH and NPTH)")
    parser.add_argument("--pos", action="store_true", help="component positions (CSV, mm)")
    parser.add_argument("--ipcd356", action="store_true", help="IPC-D-356 netlist")
    parser.add_argument("--ipc2581", action="store_true", help="IPC-2581 (version C, mm), one XML file")
    parser.add_argument("--odb", action="store_true", help="ODB++, one zip file")
    parser.add_argument("--step", action="store_true", help="STEP model with the 3D models Fenolite locates")
    parser.add_argument("--pdf", action="store_true", help="board PDF, one file per layer")
    parser.add_argument("--dxf", action="store_true", help="DXF (mm), one file per mechanical layer")
    parser.add_argument(
        "--sch-pdf", dest="sch_pdf", action="store_true", help="schematic PDF, every sheet of the hierarchy"
    )
    parser.add_argument(
        "--all", action="store_true", help="the four fabrication kinds (Gerbers, drill, positions, netlist)"
    )
    parser.add_argument(
        "--altium-rul",
        dest="altium_rul",
        action="store_true",
        help="the project's rules as an Altium rule file (no tool runs; not part of --all)",
    )
    parser.add_argument(
        "--fab-drawing",
        dest="fab_drawing",
        action="store_true",
        help="a fabrication drawing (PDF) with KiCad's drill maps and report (not part of --all)",
    )
    parser.add_argument(
        "--assembly-drawing",
        dest="assembly_drawing",
        action="store_true",
        help="assembly drawings (PDF), top and bottom (not part of --all)",
    )
    parser.add_argument(
        "--drawing-spec",
        dest="drawing_spec",
        metavar="FILE",
        default=None,
        help="a TOML file of paper, sheet, tables, notes and assembly options for the drawing kinds",
    )
    parser.add_argument(
        "--manifest", action="store_true", help=f"also add the files to {manifest.FILE_NAME} in DIR"
    )
    parser.add_argument(
        "--preset",
        metavar="FILE",
        default=None,
        help="a TOML file of your fabrication options for the Gerber, drill and position exports",
    )
    parser.add_argument("--kicad-cli", dest="kicad_cli", metavar="PATH", help="the kicad-cli to run")
    parser.add_argument(
        "--timeout", type=float, default=DEFAULT_TIMEOUT, metavar="SECONDS", help="per kicad-cli run (300)"
    )


def _preset(given: str | None, cwd: Path) -> tuple[presets.Preset | None, dict[str, str] | None]:
    """The preset of ``--preset`` and ``result.preset`` (its name as given and its SHA-256), read before
    any run."""
    if given is None:
        return None, None
    path = Path(given) if Path(given).is_absolute() else cwd / given
    try:
        data = path.read_bytes()
    except OSError as error:
        message = f"cannot read the preset {given}: {error.strerror or error}"
        raise CliError("FEN-3001", message, where=str(given)) from None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise FormatError(f"not UTF-8 text: {error}", file=Path(given).name) from error
    preset = presets.read_preset(text, file=Path(given).name)
    return preset, {"file": str(given), "sha256": hashlib.sha256(data).hexdigest()}


preset_file = _preset
"""The same reading for ``build --altium-outjob-preset`` (change c0087)."""


def _rule_file(board: Path, issues: list[Issue]) -> altium_rul.RuleFileExport | None:
    """The rule file of the rules file beside ``board``. Without that file, or when no rule of it has an
    exact Altium form, one ``export.failed`` is added and nothing is written."""
    from fenolite.backends.kicad.dru import read_rules

    source = board.with_suffix(".kicad_dru")
    try:
        text = source.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        message = f"{source.name} cannot be read: the rules of the project are in that file"
        issues.append(export_issue("export.failed", message, where=altium_rul.KIND))
        return None
    found = altium_rul.export_rules(read_rules(text, file=source.name).rules, stem=board.stem)
    if not found.data:
        reasons = ", ".join(f"{item['kind']} ({item['reason']})" for item in found.not_lowered)
        message = "no rule of the project has an exact Altium form" + (f": {reasons}" if reasons else "")
        issues.append(export_issue("export.failed", message, where=altium_rul.KIND))
    return found


def _drawing_spec(given: str | None, cwd: Path) -> tuple[drawing_spec.DrawingSpec, Path]:
    """The specification of ``--drawing-spec`` and the folder its paths are relative to; ``DEFAULT``
    without the option. It is read before any tool runs."""
    if given is None:
        return drawing_spec.DEFAULT, cwd
    path = Path(given) if Path(given).is_absolute() else cwd / given
    try:
        data = path.read_bytes()
    except OSError as error:
        message = f"cannot read the drawing specification {given}: {error.strerror or error}"
        raise CliError("FEN-3001", message, where=str(given)) from None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise FormatError(f"not UTF-8 text: {error}", file=Path(given).name) from error
    return drawing_spec.read_spec(text, file=Path(given).name), path.parent


def _sheet_obstacles(sheet: DrawingSheet, width: Nm, height: Nm) -> Obstacles:
    """What a known drawing sheet takes of a page: the page less the sheet's margins, and the boxes of
    the lines and texts that ``templates.layout`` predicts. A text's justification is not predicted, so
    its box reaches the text's bound to both sides of its anchor."""
    from fenolite.exports.drawing_tables import text_width
    from fenolite.templates import layout

    setup = sheet.setup
    margin = (setup.left_margin, setup.top_margin, width - setup.right_margin, height - setup.bottom_margin)
    drawn = layout(sheet, width=width, height=height)
    boxes = [
        (min(line.x1, line.x2), min(line.y1, line.y2), max(line.x1, line.x2), max(line.y1, line.y2))
        for line in drawn.lines
    ]
    for text in drawn.texts:
        reach = text_width(text.text, text.size[0])
        boxes.append((text.x - reach, text.y - text.size[1], text.x + reach, text.y + text.size[1]))
    return Obstacles(margin, tuple(boxes))


def _known_sheet(sheet: DrawingSheet, source: str, data: bytes | None) -> drawings.Sheet:
    return drawings.Sheet(source, lambda width, height: _sheet_obstacles(sheet, width, height), data)


def _drawing_sheet(
    spec: drawing_spec.DrawingSpec, base: Path, board: Path, major: int, issues: list[Issue]
) -> drawings.Sheet | None:
    """The sheet of the drawing pages: the specification's, else the one the project names, else
    KiCad's default. ``None`` with one ``drawing.sheet-unread`` when it cannot be read or built."""
    named = spec.page.drawing_sheet
    try:
        if named.endswith(".sheet.toml"):
            from fenolite.templates import build_sheet, load_spec

            path = Path(named) if Path(named).is_absolute() else base / named
            problems: list[Issue] = []
            sheet = build_sheet(load_spec(path), base_dir=path.parent, issues=problems)
            written = wks.write_drawing_sheet(sheet, target=major)
            if any(found.severity == "error" for found in (*problems, *written.issues)):
                raise ValueError("the sheet template does not build")
            return _known_sheet(sheet, "spec", written.text.encode("utf-8"))
        if named:
            path = Path(named) if Path(named).is_absolute() else base / named
            data = path.read_bytes()
            sheet = wks.read_drawing_sheet(data.decode("utf-8"), file=path.name)
            return _known_sheet(sheet, "spec", data)
        project = board.with_suffix(".kicad_pro")
        named = (kicad_pro.read_project(project).drawing_sheet or "") if project.is_file() else ""
        if not named:
            return drawings.default_sheet()
        path = Path(named) if Path(named).is_absolute() else board.parent / named
        return _known_sheet(wks.read_drawing_sheet(path), "project", None)
    except (FenoliteError, OSError, UnicodeDecodeError, ValueError) as error:
        detail = getattr(error, "strerror", None) or str(error)
        message = f"the drawing sheet {Path(named).name} cannot be read or built: {detail}"
        issues.append(
            export_issue(
                "drawing.sheet-unread",
                message,
                where=Path(named).name,
                hint="correct [page] drawing_sheet in the drawing specification or the sheet of the "
                "project; without one the pages use KiCad's default sheet",
            )
        )
        return None


def _page(page: drawings.Page) -> dict[str, Any]:
    """One page of ``result.drawings``: no temporary path, no home directory and no date."""
    found: dict[str, Any] = {
        "kind": page.kind,
        "path": page.path,
        "paper": page.paper,
        "portrait": page.portrait,
        "sheet": page.sheet,
        "blocks": [
            {"name": block.name, "at": list(block.at), "size": list(block.size)} for block in page.blocks
        ],
    }
    if page.side is not None:
        found["side"] = page.side
        found["designators_added"] = page.designators_added
    return found


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    kinds = [
        kind for kind in KINDS if (args.all and kind in FAB_KINDS) or getattr(args, kind.replace("-", "_"))
    ]
    drawing_kinds = [kind for kind in drawings.DRAWING_KINDS if getattr(args, kind.replace("-", "_"))]
    if not kinds and not drawing_kinds and not args.altium_rul:
        raise CliError("FEN-2001", "no export kind selected", hint="pass --all or one of --gerbers, --drill, "
                       "--pos, --ipcd356, --ipc2581, --odb, --step, --pdf, --dxf, --sch-pdf, "
                       "--fab-drawing, --assembly-drawing, --altium-rul")  # fmt: skip
    if args.drawing_spec is not None and not drawing_kinds:
        raise CliError(
            "FEN-2001",
            "--drawing-spec is given without a drawing kind",
            hint="pass --fab-drawing or --assembly-drawing, or leave --drawing-spec out",
        )
    preset, preset_result = _preset(args.preset, ctx.cwd)
    given = Path(args.path)
    board = resolve_board(given if given.is_absolute() else ctx.cwd / given)
    spec, spec_base = _drawing_spec(args.drawing_spec, ctx.cwd)
    schematic = board.with_suffix(".kicad_sch")
    if "sch-pdf" in kinds and not schematic.is_file():
        raise CliError(
            "FEN-3001",
            f"{board.name} has no schematic {schematic.name} beside it",
            hint="--sch-pdf plots that schematic; the other kinds (--gerbers, --drill, --pos, --ipcd356, "
            "--ipc2581, --odb, --step, --pdf, --dxf) need only the board",
            where=schematic.name,
        )
    project = project_set(board)
    backend = registry.for_path(board)
    if backend is None:
        raise CliError("FEN-2001", f"no backend reads {board.name}", hint="pass a KiCad .kicad_pcb")
    artifacts: list[Artifact] = []
    issues: list[Issue] = []
    tool_writes: set[str] = set()
    model_uses: list[kicad_models.ModelUse] = []
    version: str | None = None
    pages: list[drawings.Page] = []
    if kinds or drawing_kinds:  # the rule file alone runs no tool
        cli = preflight(args.kicad_cli, args.timeout, board)
        design = backend.read(board).design
        others = {name: path for name, path in project.files.items() if name != project.board}
        major, version = cli.major(), cli.version()
        units = len(kinds) + len(drawing_kinds)  # each kind is one unit of progress, a drawing kind too
        for index, kind in enumerate(kinds):
            ctx.progress.step(kind, index=index + 1, total=units)
            found = run_kind(
                cli,
                kind,
                board,
                others,
                major=major,
                design=design,
                args=lambda k, stem, layers: presets.arguments(k, preset, stem=stem, layers=layers),
            )
            failed = any(item.severity == "error" for item in found.issues)
            ctx.progress.done(kind, detail="failed" if failed else f"{len(found.artifacts)} file(s)")
            artifacts += found.artifacts
            issues += found.issues
            note = stackup_note(kind, design)
            if note is not None:
                issues.append(note)
            tool_writes.update(found.tool_writes)
            model_uses += found.models
        sheet = _drawing_sheet(spec, spec_base, board, major, issues) if drawing_kinds else None
        for index, kind in enumerate(drawing_kinds):
            if sheet is None:  # the sheet could not be read: its issue is an error, nothing is written
                break
            ctx.progress.step(kind, index=len(kinds) + index + 1, total=units)
            drawn = drawings.RUNNERS[kind](cli, board, others, design=design, spec=spec, sheet=sheet)
            failed = any(item.severity == "error" for item in drawn.issues)
            ctx.progress.done(kind, detail="failed" if failed else f"{len(drawn.artifacts)} file(s)")
            artifacts += drawn.artifacts
            issues += drawn.issues
            tool_writes.update(drawn.tool_writes)
            pages += drawn.pages
    rule_file = _rule_file(board, issues) if args.altium_rul else None
    if rule_file is not None and rule_file.data:
        artifacts.append(Artifact(rule_file.path, altium_rul.KIND, None, rule_file.data, True))
    artifacts.sort(key=lambda a: a.path)
    data = board.read_bytes()
    board_sha = hashlib.sha256(data).hexdigest()
    version_number = board_format(board)
    result: dict[str, Any] = {
        "board": project.board,
        "out": str(args.out),
        "kinds": [*kinds, *([altium_rul.KIND] if args.altium_rul else []), *drawing_kinds],
        "artifacts": [
            {key: value for key, value in dataclasses.asdict(manifest.entry(a)).items() if key in RESULT_KEYS}
            for a in artifacts
        ],
        "tool_version": version,
        "tool_writes": sorted(tool_writes),
        "preset": preset_result,
        "repeat": {
            **{kind: KINDS[kind].repeat for kind in kinds},
            **dict.fromkeys(drawing_kinds, drawings.REPEAT),
        },
        "models": [kicad_models.use_dict(use) for use in model_uses],
    }
    if drawing_kinds:
        result["drawings"] = [_page(page) for page in pages]
    if args.altium_rul:
        result["rules"] = (
            None
            if rule_file is None
            else {"written": list(rule_file.written), "not_lowered": list(rule_file.not_lowered)}
        )
    fabrication = [kind for kind in kinds if kind in FAB_KINDS]
    documents = [kind for kind in kinds if kind in DOCUMENT_KINDS]
    tool_parts = [EVIDENCE] if fabrication else []
    tool_parts += [presets.EVIDENCE] if preset is not None and fabrication else []
    document_parts = [DOCUMENTS_EVIDENCE] if documents else []
    drawing_parts = [drawings.EVIDENCE] if drawing_kinds else []
    parts = [*tool_parts, *document_parts, *drawing_parts]
    parts += [rule_file.evidence] if rule_file is not None else []
    evidence = dataclasses.replace(
        Evidence.combine(*parts) if parts else EVIDENCE,
        oracle=f"kicad-cli {version}" if kinds or drawing_kinds else None,
    )
    writes: list[PlannedWrite] = []
    if not any(found.severity == "error" for found in issues):  # a warning never holds the files back
        writes = [PlannedWrite(joined(args.out, a.path), a.data, a.kind) for a in artifacts]
        if args.manifest:
            # an entry claims no more than the run: the level of an export with a preset is the preset's.
            # A manifest in DIR that Fenolite cannot read is never overwritten: nothing at all is planned.
            # The rule file is Fenolite's own: its entry names Fenolite and the level of the rule map.
            own = manifest.ToolRef("fenolite", fenolite.__version__)
            tool = manifest.ToolRef("kicad-cli", version) if version is not None else own
            made = {"board": board_sha}
            sources = {
                kind: {"schematic": hashlib.sha256(schematic.read_bytes()).hexdigest()}
                for kind in documents
                if KINDS[kind].source == "schematic"
            }
            tools = {altium_rul.KIND: f"{own.name} {own.version}"}
            levels = {altium_rul.KIND: rule_file.evidence.level.value} if rule_file is not None else {}
            levels.update({kind: DOCUMENTS_EVIDENCE.level.value for kind in documents})
            levels.update({kind: drawings.EVIDENCE.level.value for kind in drawing_kinds})
            tool_level = Evidence.combine(*tool_parts).level.value if tool_parts else evidence.level.value
            planned, refused = merged_write(
                args.out,
                ctx,
                [
                    manifest.entry(
                        a,
                        from_=sources.get(a.kind, made),
                        tool=tools.get(a.kind, f"{tool.name} {tool.version}"),
                        evidence=levels.get(a.kind, tool_level),
                    )
                    for a in artifacts
                ],
                board=manifest.BoardRef(project.board, board_sha, version_number),
                tool=tool,
            )
            if planned is not None:
                writes.append(planned)
            if refused is not None:
                issues.append(refused)
                writes = []
    return Result(
        result=result,
        issues=tuple(issues),
        evidence=evidence,
        input=InputRef(
            path=board.name,
            sha256=board_sha,
            kind="kicad_pcb",
            format_version=None if version_number is None else str(version_number),
        ),
        writes=tuple(writes),
        depends=depends_on(
            ctx.cwd,
            board,
            *project.files.values(),
            args.preset,
            board.with_suffix(".kicad_dru") if args.altium_rul else None,
        ),
    )


_EXAMPLE = (EXAMPLE_BOARD, "--out", "fab", "--all", "--manifest")
COMMAND = Command(
    name="export",
    help=HELP,
    mutates=True,
    register=_register,
    run=_run,
    example_args=(*_EXAMPLE, "--dry-run"),
    mutation_example_args=_EXAMPLE,
    example_tools=("kicad-cli",),
)
