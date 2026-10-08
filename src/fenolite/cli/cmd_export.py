# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite export PATH --out DIR``: fabrication files through ``kicad-cli``, on a copy of the project
(capability manufacturing-exports; ``docs/cli-contract.md``, "export"; user guide ``docs/exports.md``).

``--altium-rul`` (change c0084) writes the project's rules as an Altium rule file. It runs no tool, so it
alone needs no ``kicad-cli``; it is not one of the kinds of ``--all``.

``kicad-cli`` only sees the copy set of ``projectset.project_set``, so the project folder never changes.
Every file the tool wrote becomes a planned write under ``DIR``; when a kind fails, nothing is planned,
so a folder never holds a partial set.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
from pathlib import Path
from typing import Any

import fenolite
from fenolite.backends import registry
from fenolite.backends.kicad.projectset import project_set, resolve_board
from fenolite.cli._examples import EXAMPLE_BOARD
from fenolite.cli._kicadtool import DEFAULT_TIMEOUT, board_format, preflight
from fenolite.cli._manifest import joined, merged_write
from fenolite.cli.api import Command, Context, PlannedWrite, Result
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.errors import FormatError, Issue
from fenolite.core.evidence import Evidence
from fenolite.exports import EVIDENCE, altium_rul, manifest
from fenolite.exports import preset as presets
from fenolite.exports.codes import issue as export_issue
from fenolite.exports.plan import KINDS, Artifact, run_kind

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
    parser.add_argument("--all", action="store_true", help="the four kinds")
    parser.add_argument(
        "--altium-rul",
        dest="altium_rul",
        action="store_true",
        help="the project's rules as an Altium rule file (no tool runs; not part of --all)",
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


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    kinds = [kind for kind in KINDS if args.all or getattr(args, kind)]
    if not kinds and not args.altium_rul:
        raise CliError("FEN-2001", "no export kind selected", hint="pass --all or one of --gerbers, --drill, "
                       "--pos, --ipcd356, --altium-rul")  # fmt: skip
    preset, preset_result = _preset(args.preset, ctx.cwd)
    given = Path(args.path)
    board = resolve_board(given if given.is_absolute() else ctx.cwd / given)
    project = project_set(board)
    backend = registry.for_path(board)
    if backend is None:
        raise CliError("FEN-2001", f"no backend reads {board.name}", hint="pass a KiCad .kicad_pcb")
    artifacts: list[Artifact] = []
    issues: list[Issue] = []
    tool_writes: set[str] = set()
    version: str | None = None
    if kinds:  # the rule file alone runs no tool
        cli = preflight(args.kicad_cli, args.timeout, board)
        design = backend.read(board).design
        others = {name: path for name, path in project.files.items() if name != project.board}
        major, version = cli.major(), cli.version()
        for kind in kinds:
            found = run_kind(
                cli,
                kind,
                board,
                others,
                major=major,
                design=design,
                args=lambda k, stem, layers: presets.arguments(k, preset, stem=stem, layers=layers),
            )
            artifacts += found.artifacts
            issues += found.issues
            tool_writes.update(found.tool_writes)
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
        "kinds": [*kinds, *([altium_rul.KIND] if args.altium_rul else [])],
        "artifacts": [
            {key: value for key, value in dataclasses.asdict(manifest.entry(a)).items() if key in RESULT_KEYS}
            for a in artifacts
        ],
        "tool_version": version,
        "tool_writes": sorted(tool_writes),
        "preset": preset_result,
    }
    if args.altium_rul:
        result["rules"] = (
            None
            if rule_file is None
            else {"written": list(rule_file.written), "not_lowered": list(rule_file.not_lowered)}
        )
    tool_parts = [EVIDENCE] if kinds else []
    tool_parts += [presets.EVIDENCE] if preset is not None and kinds else []
    parts = [*tool_parts, *([rule_file.evidence] if rule_file is not None else [])]
    evidence = dataclasses.replace(
        Evidence.combine(*parts) if parts else EVIDENCE,
        oracle=f"kicad-cli {version}" if kinds else None,
    )
    writes: list[PlannedWrite] = []
    if not issues:
        writes = [PlannedWrite(joined(args.out, a.path), a.data, a.kind) for a in artifacts]
        if args.manifest:
            # an entry claims no more than the run: the level of an export with a preset is the preset's.
            # A manifest in DIR that Fenolite cannot read is never overwritten: nothing at all is planned.
            # The rule file is Fenolite's own: its entry names Fenolite and the level of the rule map.
            own = manifest.ToolRef("fenolite", fenolite.__version__)
            tool = manifest.ToolRef("kicad-cli", version) if version is not None else own
            made = {"board": board_sha}
            tools = {altium_rul.KIND: f"{own.name} {own.version}"}
            levels = {altium_rul.KIND: rule_file.evidence.level.value} if rule_file is not None else {}
            tool_level = Evidence.combine(*tool_parts).level.value if tool_parts else evidence.level.value
            planned, refused = merged_write(
                args.out,
                ctx,
                [
                    manifest.entry(
                        a,
                        from_=made,
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
