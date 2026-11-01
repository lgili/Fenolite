# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Local PDF binding, deterministic proposal generation and staged device writes (c0265)."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any

from fenolite import __file__ as package_file
from fenolite.catalog.records import DeviceRecord, ProposalOrigin, parse_record
from fenolite.cli._library_import import target_folder
from fenolite.cli.api import Context, PlannedWrite, Result, depends_on
from fenolite.cli.errors import CliError
from fenolite.core.errors import FormatError
from fenolite.core.evidence import Evidence, Level
from fenolite.library.proposals.agreement import agreement
from fenolite.library.proposals.checks import bind, self_check
from fenolite.library.proposals.convert import GenerationRefused, convert, seal
from fenolite.library.proposals.schema import datasheet_bytes, parse_proposal, skeleton

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-PROPOSAL",))
DATA = Path(package_file).resolve().parents[2] / "tests/data/proposals"
EXAMPLE = (
    "propose",
    "--datasheet",
    str(DATA / "exb6202.pdf"),
    "--proposal",
    str(DATA / "exb6202.proposal.toml"),
    "--out",
    "devices/proposed",
)


def register(parser: argparse.ArgumentParser) -> None:
    group = parser.add_argument_group("datasheet parameter proposals")
    group.add_argument(
        "--proposal",
        action="append",
        default=[],
        metavar="FILE",
        help="propose: one or two cited parameter proposal files",
    )
    group.add_argument(
        "--licence", metavar="SPDX", help="propose: record licence (default: see source terms)"
    )


def only_propose(args: argparse.Namespace, form: str) -> None:
    if args.proposal or args.licence is not None:
        raise CliError("FEN-2001", f"--proposal and --licence belong to library propose, not {form}")


def _existing(folder: Path) -> None:
    if not folder.exists():
        return
    try:
        record = parse_record((folder / "device.toml").read_text(), allow_stale_reviews=True)
        if not isinstance(record, DeviceRecord) or not isinstance(record.header.origin, ProposalOrigin):
            raise ValueError("not a proposed folder")
        origin = record.header.origin
        expected = {"device.toml", "pins.toml", "package.toml", *(entry.file for entry in origin.output)}
        if {p.name for p in folder.iterdir() if p.is_file()} != expected:
            raise ValueError("folder has extra or missing files")
        for name in ("device.toml", "pins.toml", "package.toml"):
            current = parse_record((folder / name).read_text(), allow_stale_reviews=True)
            if (
                not isinstance(current.header.origin, ProposalOrigin)
                or current.header.reviewed_by
                or seal(current).header.origin != current.header.origin
            ):
                raise ValueError("record is reviewed or edited")
        for output in origin.output:
            path = folder / output.file
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != output.sha256:
                raise ValueError("generated output or proposal was edited")
    except (OSError, ValueError, FormatError):
        raise CliError(
            "FEN-7001",
            "corrected proposals cannot replace a reviewed or hand-edited folder",
            where=folder.name,
        ) from None


def run(args: argparse.Namespace, ctx: Context) -> Result:
    if len(args.path) != 1 or not args.datasheet:
        raise CliError("FEN-2001", "library propose takes --datasheet FILE and no positional sources")
    for flag in (
        "diff",
        "library",
        "positions",
        "no_step",
        "no_pcblib",
        "into",
        "device_id",
        "symbol",
        "footprint",
        "pin",
        "manufacturer",
        "mpn",
        "ref_prefix",
        "no_crosscheck",
        "prefer",
        "sheets",
        "compare",
        "rules",
        "skip",
        "accept",
        "revoke",
        "reviewer",
        "sheet",
        "item",
        "base",
        "proof",
        "release_version",
        "upstream",
        "keep",
        "with_current",
        "release",
    ):
        if getattr(args, flag, None):
            raise CliError("FEN-2001", f"--{flag.replace('_', '-')} is not a propose option")
    path = Path(args.datasheet) if Path(args.datasheet).is_absolute() else ctx.cwd / args.datasheet
    if not path.is_file():
        raise CliError("FEN-3001", "datasheet does not exist", where=args.datasheet)
    pdf = datasheet_bytes(path)
    if not args.proposal:
        if args.out or args.licence:
            raise CliError("FEN-2001", "--out and --licence require a proposal")
        return Result(
            result={
                "schema": "fenolite.library-propose.v0",
                "skeleton": skeleton(path.name, pdf),
                "guide": "datasheets",
            },
            evidence=EVIDENCE,
        )
    if len(args.proposal) > 2:
        raise CliError("FEN-2001", "give one or two --proposal files")
    files = [Path(p) if Path(p).is_absolute() else ctx.cwd / p for p in args.proposal]
    for file in files:
        if not file.is_file():
            raise CliError("FEN-3001", f"proposal {file.name} does not exist")
    proposals = [parse_proposal(p.read_text(), file=p.name) for p in files]
    findings = [f for p in proposals for f in (*bind(p, pdf), *self_check(p))] + agreement(proposals)
    ident = proposals[0].data["device"]["id"]
    if not args.out:
        raise CliError("FEN-2001", "library propose requires --out DIR")
    root = target_folder(args.out, ctx.cwd)
    folder = root / ident.split(":", 1)[1]
    target_folder(folder.relative_to(ctx.cwd).as_posix(), ctx.cwd)
    result: dict[str, Any] = {
        "schema": "fenolite.library-propose.v0",
        "device": ident,
        "folder": folder.relative_to(ctx.cwd).as_posix(),
        "datasheet": {"file": path.name, "sha256": hashlib.sha256(pdf).hexdigest()},
        "proposals": [
            {
                "file": file.name,
                "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
                "proposer": p.data["proposer"],
            }
            for file, p in zip(files, proposals, strict=True)
        ],
        "package": {"family": proposals[0].family, "pins": len(proposals[0].pins)},
        "doubts": [r for p in proposals for r in p.data.get("doubt", [])],
        "uncited": [name for p in proposals for name in p.uncited],
        "evidence": "UNVERIFIED",
    }
    if any(f.severity == "error" for f in findings):
        return Result(result=result, issues=tuple(findings), evidence=EVIDENCE)
    _existing(folder)
    try:
        generated = convert(
            proposals,
            pdf,
            date=ctx.timestamp.date().isoformat(),
            licence=args.licence or "see source terms",
            source_digests=[(p.name, hashlib.sha256(p.read_bytes()).hexdigest()) for p in files],
            target=ctx.kicad_target,
        )
    except GenerationRefused as error:
        return Result(result=result, issues=error.issues, evidence=EVIDENCE)
    if folder.exists() and any(file.name not in generated.files for file in folder.iterdir()):
        raise CliError(
            "FEN-7001",
            "corrected proposal would leave obsolete files; use a new output folder",
            where=result["folder"],
        )
    result["package"]["pins"] = len(generated.symbol.pins)
    result["record_digests"] = {
        record.header.schema: getattr(record.header.origin, "content_sha256", "")
        for record in generated.records
    }
    return Result(
        result=result,
        issues=generated.issues,
        evidence=EVIDENCE,
        writes=tuple(
            PlannedWrite(f"{result['folder']}/{name}", data, "library-proposal")
            for name, data in sorted(generated.files.items())
        ),
        depends=depends_on(ctx.cwd, path, *files, *(sorted(folder.iterdir()) if folder.is_dir() else ())),
    )
