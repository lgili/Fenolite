# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite kit build|verify|record|status``: the Altium verification kit (capability cli-contract, "Kit
command"; ``docs/cli-contract.md``, "kit"; user guide ``docs/altium-kit.md``).

``build`` writes the kit; ``verify`` reads a kit folder after a run and judges every step; ``record``
writes the archive of the results beside the kit and the run record into a repository; ``status`` lists
the committed runs and the register rows whose run is stale. Nothing here starts Altium or its script: a
person performs the run.

The action is a positional argument, as in ``template``: the dispatcher adds the global options,
``--dry-run`` and ``--confirm`` to this command's own parser. ``verify`` and ``status`` plan no write, so
they need neither flag.
"""

from __future__ import annotations

import argparse
import os
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Any

from fenolite import __version__
from fenolite.cli import _kit
from fenolite.cli.api import Command, Context, PlannedWrite, Result
from fenolite.cli.errors import CliError
from fenolite.core.errors import FormatError, Issue, Severity
from fenolite.core.evidence import Evidence, Level
from fenolite.verify.hypotheses import load_register
from fenolite.verify.kit import manifest, record
from fenolite.verify.kit.results import KitVerdict, verify_results

HELP = "build the Altium verification kit, check the files a run left, record the run, list the runs"
ACTIONS = ("build", "verify", "record", "status")
REGISTER = "docs/hypotheses.md"
ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "kit.file-changed": "error",
        "kit.form": "error",
        "kit.step-failed": "error",
        "kit.record-refused": "error",
        "kit.step-skipped": "info",
        "kit.pending": "info",
        "kit.synthetic": "warning",
        "kit.privacy": "warning",
        "kit.project-resaved": "info",
        "kit.stale": "warning",
    }
)
BUILD_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-A-KIT-STABLE",))
"""The kit's files are Fenolite's own writes; nothing was opened in Altium."""
UNVERIFIED_RUN = Evidence(Level.INFERRED)
"""A run that did not pass in full, or that no tool performed, verifies nothing."""
KIT_RUN = Evidence(Level.ALTIUM_VERIFIED_KIT)
MAX_PRIVACY_ISSUES = 20
_PRIVACY_KINDS = {
    "home-folder": "a home folder",
    "absolute-path": "an absolute path of the machine",
    "login-name": "a login name",
}


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/altium-kit.md and docs/cli-contract.md, 'kit'."
    parser.add_argument("action", choices=ACTIONS, help="what to do with the kit")
    parser.add_argument("folder", metavar="DIR", nargs="?", help="verify, record: the kit folder after a run")
    parser.add_argument(
        "-o",
        "--out",
        metavar="DIR",
        default=None,
        help="build: the folder to write the kit into; record: the repository that gets the run record",
    )
    parser.add_argument(
        "--samples",
        metavar="DIR",
        default=None,
        help="build, status: the folder of the sample scripts (default: examples/kit of the source checkout)",
    )
    parser.add_argument(
        "--repo", metavar="DIR", default=None, help="status: the repository to read (default: this folder)"
    )


def _issue(code: str, message: str, where: str = "", hint: str = "") -> Issue:
    return Issue(code=code, severity=ISSUE_CODES[code], message=message, where=where, hint=hint)


def _usage(message: str, where: str) -> CliError:
    return CliError("FEN-2001", message, where=where, hint="see docs/cli-contract.md, 'kit'")


def _path(ctx: Context, given: str) -> Path:
    path = Path(given)
    return path if path.is_absolute() else ctx.cwd / path


def _only(args: argparse.Namespace, *allowed: str) -> None:
    for name, flag in (("folder", "DIR"), ("out", "--out"), ("samples", "--samples"), ("repo", "--repo")):
        if getattr(args, name) is not None and name not in allowed:
            raise _usage(f"{flag} is not an argument of kit {args.action}", flag)


def _sources(ctx: Context, given: str | None) -> manifest.KitSources:
    folder = None if given is None else _path(ctx, given)
    try:
        return _kit.kit_sources(folder)
    except FormatError as error:
        raise CliError(
            "FEN-3001",
            f"the sample scripts cannot be built: {error}",
            where="--samples",
            hint="run from a source checkout, or name the folder of the sample scripts with --samples",
        ) from error


def _build(args: argparse.Namespace, ctx: Context) -> Result:
    _only(args, "out", "samples")
    if args.out is None:
        raise _usage("kit build needs --out DIR", "--out")
    seed = manifest.DEFAULT_SEED if ctx.seed is None else ctx.seed
    timestamp = manifest.DEFAULT_TIMESTAMP if getattr(args, "timestamp", None) is None else ctx.timestamp
    files = manifest.kit_files(_sources(ctx, args.samples), seed=seed, timestamp=timestamp)
    kit = manifest.read_kit(files[manifest.KIT_FILE])
    out = Path(args.out)
    writes = tuple(
        PlannedWrite(path=(out / rel).as_posix(), data=data, kind="altium-kit")
        for rel, data in sorted(files.items())
    )
    result: dict[str, Any] = {
        "out": out.as_posix(),
        "kit_sha256": kit.digest,
        "kit_version": kit.data["kit_version"],
        "seed": seed,
        "timestamp": manifest.stamp(timestamp),
        "samples": [{"name": name, "digest": digest} for name, digest in kit.samples.items()],
        "steps": len(kit.steps),
        "scripted": [step.id for step in kit.steps if step.scripted],
        "files": len(files),
    }
    return Result(result=result, evidence=BUILD_EVIDENCE, writes=writes)


def _kit_folder(args: argparse.Namespace, ctx: Context) -> Path:
    if args.folder is None:
        raise _usage(f"kit {args.action} needs the kit folder DIR", "DIR")
    folder = _path(ctx, args.folder)
    if not (folder / manifest.KIT_FILE).is_file():
        raise CliError(
            "FEN-3001",
            f"{folder.name} holds no {manifest.KIT_FILE}: it is not a kit folder",
            where=folder.name,
            hint="name the folder that 'fenolite kit build --out' wrote",
        )
    return folder


def _verdict_result(verdict: KitVerdict) -> dict[str, Any]:
    return {
        "kit_sha256": verdict.kit.digest,
        "synthetic": verdict.synthetic,
        "altium_version": verdict.altium_version,
        "passed": verdict.passed,
        "counts": {
            outcome: sum(1 for step in verdict.steps if step.outcome == outcome)
            for outcome in ("pass", "fail", "skipped")
        },
        "kit_problems": list(verdict.kit_problems),
        "kit_resaved": list(verdict.resaved),
        "form_problems": list(verdict.form_problems),
        "steps": [
            {
                "id": step.id,
                "sample": step.sample,
                "kind": step.kind,
                "outcome": step.outcome,
                "scripted": step.scripted,
                "reasons": list(step.reasons),
                "pending": list(step.pending),
            }
            for step in verdict.steps
        ],
        "hypotheses": [
            {"id": found.id, "outcome": found.outcome, "form": found.form, "steps": list(found.steps)}
            for found in verdict.hypotheses
        ],
        "privacy": [
            {"file": found.file, "offset": found.offset, "kind": found.kind, "text": found.text}
            for found in verdict.privacy
        ],
        "result_files": len(verdict.results),
    }


def _verdict_issues(verdict: KitVerdict) -> list[Issue]:
    issues = [_issue("kit.file-changed", text, hint="build the kit again") for text in verdict.kit_problems]
    issues += [
        _issue(
            "kit.project-resaved",
            f"{path} was saved again by the tool: its bytes are not the manifest's, and it lists exactly "
            "the sample's documents, so the sample's steps are judged",
            path,
        )
        for path in verdict.resaved
    ]
    issues += [_issue("kit.form", text, manifest.FORM_FILE) for text in verdict.form_problems]
    for step in verdict.steps:
        if step.outcome == "fail":
            issues.append(_issue("kit.step-failed", f"{step.id}: {'; '.join(step.reasons)}", step.id))
        elif step.outcome == "skipped":
            issues.append(_issue("kit.step-skipped", f"{step.id}: {'; '.join(step.reasons)}", step.id))
        issues += [_issue("kit.pending", f"{step.id}: {text}", step.id) for text in step.pending]
    if verdict.synthetic:
        issues.append(
            _issue(
                "kit.synthetic",
                "the form says the run is synthetic (or does not say that it is not): no label comes from it",
                manifest.FORM_FILE,
            )
        )
    shown = verdict.privacy[:MAX_PRIVACY_ISSUES]
    issues += [
        _issue(
            "kit.privacy",
            f"{found.file} holds what looks like {_PRIVACY_KINDS[found.kind]} at byte {found.offset}",
            found.file,
            "read result.privacy before publishing the archive",
        )
        for found in shown
    ]
    return issues


def _verify(args: argparse.Namespace, ctx: Context) -> Result:
    _only(args, "folder")
    verdict = verify_results(_kit_folder(args, ctx), judge=_kit.judge_document)
    evidence = KIT_RUN if verdict.passed and not verdict.synthetic else UNVERIFIED_RUN
    return Result(result=_verdict_result(verdict), issues=tuple(_verdict_issues(verdict)), evidence=evidence)


def _relative(target: Path, ctx: Context) -> str:
    try:
        return Path(os.path.relpath(target, ctx.cwd)).as_posix()
    except ValueError as error:  # another drive on Windows
        raise CliError(
            "FEN-2001", f"{target.name} is on another drive than the working directory", where=target.name
        ) from error


def _record(args: argparse.Namespace, ctx: Context) -> Result:
    _only(args, "folder", "out")
    folder = _kit_folder(args, ctx)
    if args.out is None:
        raise _usage("kit record needs --out REPO, the repository that gets the run record", "--out")
    repository = _path(ctx, args.out)
    if not repository.is_dir():
        raise CliError("FEN-3001", f"--out {args.out} is not a folder", where="--out")
    verdict = verify_results(folder, judge=_kit.judge_document)
    result = _verdict_result(verdict)
    result["rows"] = []
    refusal = record.refusal(verdict)
    if refusal:
        issue = _issue("kit.record-refused", f"no record is written: {refusal}", folder.name)
        return Result(result=result, issues=(issue, *_verdict_issues(verdict)), evidence=UNVERIFIED_RUN)
    archive = record.archive_bytes(folder, verdict)
    made = record.run_record(verdict, archive=archive, fenolite_version=__version__)
    data = record.record_bytes(made)
    target = repository.joinpath(*record.RECORDS_DIR.split("/"), f"{made['run_id']}.json")
    if target.is_file() and target.read_bytes() != data:
        issue = _issue(
            "kit.record-refused",
            f"{target.name} exists with other content: a committed record is never edited",
            target.name,
        )
        return Result(result=result, issues=(issue,), evidence=UNVERIFIED_RUN)
    result.update(
        {
            "run_id": made["run_id"],
            "archive": made["archive"],
            "record": _relative(target, ctx),
            "rows": record.candidate_rows(made),
        }
    )
    writes = (
        PlannedWrite(
            path=_relative(folder.parent / record.ARCHIVE_FILE, ctx), data=archive, kind="kit-archive"
        ),
        PlannedWrite(path=_relative(target, ctx), data=data, kind="kit-run-record"),
    )
    evidence = KIT_RUN if verdict.passed else UNVERIFIED_RUN
    # the record is written also for a run with failed steps: it records them; the exit code says so
    return Result(result=result, issues=tuple(_verdict_issues(verdict)), evidence=evidence, writes=writes)


def _status(args: argparse.Namespace, ctx: Context) -> Result:
    _only(args, "repo", "samples")
    repository = ctx.cwd if args.repo is None else _path(ctx, args.repo)
    records = record.load_records(repository)
    runs = [
        {
            "run_id": made["run_id"],
            "date": made["date"],
            "altium_version": made["altium_version"],
            "kit_sha256": made["kit_sha256"],
            "archive_sha256": made["archive"]["sha256"],
            "passed": sorted(h["id"] for h in made["hypotheses"] if h["outcome"] == "pass"),
            "failed": sorted(h["id"] for h in made["hypotheses"] if h["outcome"] == "fail"),
        }
        for made in records
    ]
    result: dict[str, Any] = {"runs": runs, "stale": [], "problems": []}
    issues: list[Issue] = []
    register = repository.joinpath(*REGISTER.split("/"))
    if records and register.is_file():
        rows = load_register(register)
        kit = manifest.read_kit(manifest.kit_files(_sources(ctx, args.samples))[manifest.KIT_FILE])
        result["kit_sha256"] = kit.digest
        result["stale"] = list(record.stale_rows(rows, records, kit))
        result["problems"] = record.label_problems(rows, records, None)
        issues += [
            _issue("kit.stale", f"{ident}: its kit run is stale: a sample changed since the run", ident)
            for ident in result["stale"]
        ]
    return Result(result=result, issues=tuple(issues), evidence=UNVERIFIED_RUN)


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    actions = {"build": _build, "verify": _verify, "record": _record, "status": _status}
    return actions[args.action](args, ctx)


COMMAND = Command(
    name="kit",
    help=HELP,
    mutates=True,
    register=_register,
    run=_run,
    example_args=("status",),
    mutation_example_args=("build", "--out", "fenolite-kit"),
)
