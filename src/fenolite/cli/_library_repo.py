# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The tooling verbs of ``fenolite library`` for the ``fenolite-library`` repository (change c0279;
``docs/library-repo.md``; ``docs/cli-contract.md``, "library"): ``audit ROOT`` (read-only), ``replay ITEM``
(read-only for the tree), ``release ROOT --version V --out DIR`` and ``gallery ROOT --release DIR --out
DIR`` (both through plan and confirm). The library holds no tooling code: its workflows call these."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, cast

from fenolite.cli.api import Context, PlannedWrite, Result, depends_on
from fenolite.cli.errors import CliError
from fenolite.core.evidence import Evidence, Level
from fenolite.library.audit import audit
from fenolite.library.licences import for_root
from fenolite.library.proof import gate
from fenolite.library.release import build_release

VERBS = ("audit", "replay", "release", "gallery")
USAGE: dict[str, tuple[bool, str]] = {
    "audit": (False, "fenolite library audit ROOT [--item PATH] [--base REF] [--proof FILE]"),
    "replay": (False, "fenolite library replay ITEM [--upstream DIR] [--keep DIR] [--with-current]"),
    "release": (True, "fenolite library release ROOT --version V --out DIR"),
    "gallery": (True, "fenolite library gallery ROOT --release DIR --out DIR"),
}
"""Per verb: whether it writes (through plan and confirm) and its usage, as ``fenolite capabilities`` lists
it (``library <verb>``)."""


def capability_entries() -> list[dict[str, object]]:
    """The entries ``library <verb>`` of ``result.commands`` of ``fenolite capabilities``."""
    return [
        {
            "name": f"library {verb}",
            "mutates": writes,
            "schema": "fenolite.library.v0",
            "hidden": False,
            "usage": usage,
        }
        for verb, (writes, usage) in USAGE.items()
    ]


EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-LIBRARY-GET",))
REPLAY_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-LIBRARY-REPLAY",))
RELEASE_KIND = "library-release"
GALLERY_KIND = "library-gallery"


def register(parser: argparse.ArgumentParser) -> None:
    group = parser.add_argument_group("library repository verbs (audit, replay, release, gallery)")
    group.add_argument("--item", metavar="PATH", help="audit: check only this item folder, relative to ROOT")
    group.add_argument(
        "--base", metavar="REF", help="audit: a base tree (folder or git ref) for the version rules"
    )
    group.add_argument(
        "--proof",
        metavar="FILE",
        help="audit with --item: gate this verify-source --json reply of the board (the proof job)",
    )
    group.add_argument("--version", dest="release_version", metavar="V", help="release: the release version")
    group.add_argument(
        "--upstream", metavar="DIR", help="replay: use this upstream checkout instead of fetching"
    )
    group.add_argument(
        "--keep", metavar="DIR", help="replay: keep the work folder here (must be missing or empty)"
    )
    group.add_argument(
        "--with-current",
        action="store_true",
        help="replay: run the fenolite steps with this Fenolite instead of the recorded version",
    )
    group.add_argument(
        "--release", metavar="DIR", help="gallery: the folder of a release made by 'library release'"
    )


def _folder(given: str | None, ctx: Context, what: str) -> Path:
    if not given:
        raise CliError("FEN-2001", f"library {what} needs a folder", where=what)
    path = Path(given) if Path(given).is_absolute() else ctx.cwd / given
    if not path.is_dir():
        raise CliError("FEN-3001", f"{given} is not a folder", where=given)
    return path


def _audit(args: argparse.Namespace, ctx: Context) -> Result:
    if len(args.path) != 2:
        raise CliError("FEN-2001", "library audit takes one ROOT", hint="fenolite library audit . --json")
    root = _folder(args.path[1], ctx, "audit")
    try:
        report = audit(root, item=args.item, base=args.base)
    except ValueError as exc:
        raise CliError("FEN-2001", str(exc), where="--item" if args.item else "--base") from exc
    issues = list(report.issues)
    gated: dict[str, object] | None = None
    if args.proof:
        if not args.item:
            raise CliError("FEN-2001", "--proof gates one board: pass --item PATH too", where="--proof")
        found = next((f for f in report.items if f.path == args.item.strip("/")), None)
        record = found.provenance if found is not None else None
        fidelity = record.get("fidelity") if record is not None else None
        try:
            reply = json.loads(
                Path(args.proof if Path(args.proof).is_absolute() else ctx.cwd / args.proof).read_text(
                    encoding="utf-8"
                )
            )
        except (OSError, ValueError) as exc:
            raise CliError("FEN-3001", f"--proof {args.proof}: {exc}", where="--proof") from exc
        body = cast(dict[str, Any], reply) if isinstance(reply, dict) else {}
        result = cast(dict[str, Any], body.get("result", body))
        member = cast(dict[str, Any], fidelity) if isinstance(fidelity, dict) else {}
        verdict = gate(result, member, item=args.item.strip("/"))
        issues += verdict.issues
        gated = {"item": args.item.strip("/"), "result": verdict.result, "skipped": dict(verdict.skipped)}
    counts: dict[str, int] = {}
    for row in report.rows:
        counts[str(row["kind"])] = counts.get(str(row["kind"]), 0) + 1
    return Result(
        result={
            "root": args.path[1],
            "items": list(report.rows),
            "counts": dict(sorted(counts.items())),
            "proof": gated,
        },
        issues=tuple(issues),
        evidence=EVIDENCE,
    )


def _release(args: argparse.Namespace, ctx: Context) -> Result:
    if len(args.path) != 2:
        raise CliError(
            "FEN-2001",
            "library release takes one ROOT",
            hint="fenolite library release . --version 1.0.0 --out dist",
        )
    root = _folder(args.path[1], ctx, "release")
    if not args.release_version or not args.out:
        raise CliError("FEN-2001", "library release needs --version V and --out DIR", where="--out")
    report = audit(root)
    if any(found.severity == "error" for found in report.issues):
        return Result(
            result={"root": args.path[1], "version": args.release_version},
            issues=report.issues,
            evidence=EVIDENCE,
        )
    try:
        release = build_release(root, report.items, args.release_version, for_root(root))
    except ValueError as exc:
        raise CliError("FEN-2001", str(exc), where="--version") from exc
    out = Path(args.out).as_posix().rstrip("/")
    writes = tuple(PlannedWrite(f"{out}/{name}", data, RELEASE_KIND) for name, data in release.assets.items())
    return Result(
        result={
            "root": args.path[1],
            "version": args.release_version,
            "out": out,
            "items": len(release.index["items"]),
            "archives": list(release.index["archives"]),
            "index_sha256": hashlib.sha256(release.assets["index.json"]).hexdigest(),
            "index_bytes": len(release.assets["index.json"]),
        },
        issues=report.issues,
        evidence=EVIDENCE,
        writes=writes,
        depends=depends_on(
            ctx.cwd, *sorted(p for p in root.rglob("*") if p.is_file() and ".git" not in p.parts)
        ),
    )


def run_verb(verb: str, args: argparse.Namespace, ctx: Context) -> Result:
    if verb == "audit":
        return _audit(args, ctx)
    if verb == "release":
        return _release(args, ctx)
    if verb == "replay":
        from fenolite.cli._library_replay import replay_command

        return replay_command(args, ctx)
    from fenolite.cli._library_gallery import gallery_command

    return gallery_command(args, ctx)


__all__ = ["EVIDENCE", "REPLAY_EVIDENCE", "USAGE", "VERBS", "capability_entries", "register", "run_verb"]
