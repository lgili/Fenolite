# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite library replay ITEM``: replay the conversion of a library item from its pinned upstream
(change c0279, ``docs/library-repo.md``, "Replay"; change c0281, "Replayable conversion steps").

The upstream is fetched at ``upstream.commit`` (a shallow git fetch) or copied from ``--upstream DIR`` into
a temporary work folder holding ``upstream/`` and ``out/``. The recorded steps run there as recorded:
``fenolite`` with the recorded version (in this process when it is the running one or with
``--with-current``, else through ``uvx --from fenolite==<version>``), ``kicad-cli`` with the recorded
version; any other tool, or a step holding ``--plan``, is refused before a step runs (``FEN-3004``). Then the
tree of ``out/`` (without its ``PROVENANCE.json``) is compared with ``conversion.outputs_tree`` and the
payload. Nothing is written into the library; ``--keep DIR`` plans the work folder as writes.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import fenolite
from fenolite.cli.api import Context, PlannedWrite, Result, depends_on
from fenolite.cli.errors import CliError
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.library.codes import issue
from fenolite.library.items import (
    ITEM_FILE,
    PROVENANCE_FILE,
    ItemError,
    folder_files,
    load_json,
    read_item,
    tree_digest,
)
from fenolite.library.provenance import step_problems, steps_of

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-LIBRARY-REPLAY",))
KEEP_KIND = "replay-work"
STEP_TIMEOUT_S = 3600


def _tool_versions(record: Mapping[str, Any]) -> dict[str, str]:
    conversion = cast(Mapping[str, Any], record.get("conversion") or {})
    return {
        str(t.get("name")): str(t.get("version"))
        for t in cast(list[Mapping[str, Any]], conversion.get("tools") or [])
    }


def _fetch_upstream(record: Mapping[str, Any], target: Path) -> None:
    upstream = cast(Mapping[str, Any], record.get("upstream") or {})
    if upstream.get("archive_sha256"):
        raise CliError(
            "FEN-2001",
            "this item was converted from an archive; replay it with --upstream DIR",
            where="--upstream",
            hint="download the archive, check its SHA-256 and unpack it",
        )
    url, commit = str(upstream.get("url")), str(upstream.get("commit"))
    target.mkdir(parents=True)
    commands = (
        ["git", "init", "-q", str(target)],
        ["git", "-C", str(target), "fetch", "-q", "--depth", "1", url, commit],
        ["git", "-C", str(target), "checkout", "-q", "FETCH_HEAD"],
    )
    for command in commands:
        try:
            subprocess.run(command, check=True, capture_output=True, timeout=STEP_TIMEOUT_S)
        except (OSError, subprocess.SubprocessError) as exc:
            raise CliError(
                "FEN-6003",
                f"the upstream {url} at {commit} could not be fetched: {exc}",
                where=url,
                hint="replay with --upstream DIR, a checkout of that commit",
            ) from exc


def _run_fenolite(argv: Sequence[str], work: Path, version: str, current: bool) -> tuple[int, str]:
    if current or version == fenolite.__version__:
        from fenolite.cli.main import invoke

        code, _, error = invoke(list(argv), cwd=work)
        return code, "" if error is None else str(error.get("message", ""))
    uvx = shutil.which("uvx")
    if uvx is None:
        raise CliError(
            "FEN-6001",
            f"replaying with fenolite {version} needs uvx",
            where="uvx",
            hint="install uv, or replay with --with-current (this Fenolite)",
        )
    done = subprocess.run(
        [uvx, "--from", f"fenolite=={version}", "fenolite", *argv],
        cwd=work,
        capture_output=True,
        text=True,
        timeout=STEP_TIMEOUT_S,
    )
    return done.returncode, done.stderr.strip()[-500:]


def _run_kicad(argv: Sequence[str], work: Path, version: str) -> tuple[int, str]:
    from fenolite.cli._kicadtool import DEFAULT_TIMEOUT, supported_tool

    cli = supported_tool(None, DEFAULT_TIMEOUT)
    found = cli.version()
    if version and not found.startswith(version):
        raise CliError(
            "FEN-6002",
            f"the step was recorded with kicad-cli {version}; {found} is installed",
            where="kicad-cli",
            hint="set FENOLITE_KICAD_CLI to the recorded version",
        )
    done = subprocess.run(
        [str(cli.path), *argv], cwd=work, capture_output=True, text=True, timeout=STEP_TIMEOUT_S
    )
    return done.returncode, done.stderr.strip()[-500:]


def _outputs(out: Path) -> dict[str, bytes]:
    if not out.is_dir():
        return {}
    return {path: data for path, data in folder_files(out).items() if path != PROVENANCE_FILE}


def replay_command(args: argparse.Namespace, ctx: Context) -> Result:
    if len(args.path) != 2:
        raise CliError(
            "FEN-2001",
            "library replay takes one ITEM folder",
            hint="fenolite library replay boards/<family>/<id>",
        )
    given = args.path[1]
    folder = Path(given) if Path(given).is_absolute() else ctx.cwd / given
    try:
        item = read_item((folder / ITEM_FILE).read_bytes(), f"{given}/{ITEM_FILE}")
        record = load_json((folder / PROVENANCE_FILE).read_bytes(), f"{given}/{PROVENANCE_FILE}")
    except OSError as exc:
        raise CliError("FEN-3001", f"{given} is no item folder: {exc}", where=given) from exc
    except ItemError as exc:
        raise CliError("FEN-3004", str(exc), where=given) from exc
    if record.get("origin") != "converted":
        raise CliError(
            "FEN-2001", f"{given} is {record.get('origin')}; only converted items replay", where=given
        )
    problems = step_problems(cast(Mapping[str, Any], record.get("conversion") or {}).get("steps"))
    if problems:
        raise CliError(
            "FEN-3004",
            f"{given}: {problems[0]}; no step was run",
            where=problems[0].split(":", 1)[0],
            hint="record only fenolite and kicad-cli steps, a writing step with --confirm alone",
        )
    versions = _tool_versions(record)
    keep = Path(args.keep) if args.keep else None
    if keep is not None:
        target = keep if keep.is_absolute() else ctx.cwd / keep
        if target.exists() and (not target.is_dir() or any(target.iterdir())):
            raise CliError("FEN-2001", f"--keep {args.keep} must be missing or empty", where="--keep")
    upstream_given = None
    if args.upstream:
        upstream_given = Path(args.upstream) if Path(args.upstream).is_absolute() else ctx.cwd / args.upstream
        if not upstream_given.is_dir():
            raise CliError("FEN-3001", f"--upstream {args.upstream} is not a folder", where="--upstream")
    issues: list[Issue] = []
    rows: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="fenolite-replay-") as temp:
        work = Path(temp)
        upstream = work / "upstream"
        if upstream_given is not None:
            shutil.copytree(upstream_given, upstream, ignore=shutil.ignore_patterns(".git"))
        else:
            _fetch_upstream(record, upstream)
        base = upstream / str(cast(Mapping[str, Any], record.get("upstream") or {}).get("path") or "")
        imported = cast(Mapping[str, Any], record.get("import") or {})
        for row in cast(list[Mapping[str, Any]], imported.get("inputs") or []):
            path = base / str(row.get("file"))
            found = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "missing"
            if found != row.get("sha256"):
                issues.append(
                    issue(
                        "library.replay-differs",
                        f"the input {row.get('file')} has SHA-256 {found}, "
                        f"the record says {row.get('sha256')}",
                        where=str(row.get("file")),
                    )
                )
        for index, step in enumerate(steps_of(record), start=1):
            tool, argv = str(step["tool"]), [str(a) for a in step["argv"]]
            if tool == "fenolite":
                code, said = _run_fenolite(argv, work, versions.get("fenolite", ""), bool(args.with_current))
            else:
                code, said = _run_kicad(argv, work, versions.get("kicad-cli", ""))
            rows.append({"step": index, "tool": tool, "exit": code})
            if code != 0:
                issues.append(
                    issue(
                        "library.replay-differs",
                        f"step {index} ({tool} {' '.join(argv[:2])}) exited {code}: {said}",
                        where=f"conversion.steps[{index}]",
                    )
                )
                break
        outputs = _outputs(work / "out")
        produced = work / "out" / PROVENANCE_FILE
        if produced.is_file() and imported:
            try:
                written = load_json(produced.read_bytes(), PROVENANCE_FILE)
            except ItemError:
                written = {}
            if written != imported:
                keys = sorted(k for k in set(written) | set(imported) if written.get(k) != imported.get(k))
                issues.append(
                    issue(
                        "library.replay-differs",
                        f"out/PROVENANCE.json differs from the import member in {', '.join(keys)}",
                        where="import",
                    )
                )
        kept = folder_files(work) if keep is not None else {}
    payload = {name: (folder / name).read_bytes() for name in item.files if (folder / name).is_file()}
    tree = tree_digest(outputs)
    expected = str(cast(Mapping[str, Any], record.get("conversion") or {}).get("outputs_tree"))
    payload_tree = tree_digest(payload)
    differs = sorted(name for name in set(outputs) | set(payload) if outputs.get(name) != payload.get(name))
    if tree != expected or tree != payload_tree:
        issues.append(
            issue(
                "library.replay-differs",
                f"the replay gives {tree}; the record says {expected} and the payload "
                f"is {payload_tree} ({len(differs)} file(s) differ)",
                where=given,
                hint="regenerate the item with the pinned tools, or find what changed upstream",
            )
        )
    writes: tuple[PlannedWrite, ...] = ()
    if keep is not None:
        shown = Path(args.keep).as_posix().rstrip("/")
        writes = tuple(
            PlannedWrite(f"{shown}/{name}", data, KEEP_KIND) for name, data in sorted(kept.items())
        )
    return Result(
        result={
            "item": given,
            "id": item.id,
            "outputs_tree": tree,
            "expected": expected,
            "payload_tree": payload_tree,
            "equal": tree == expected == payload_tree,
            "steps": rows,
            "differs": differs,
            "fenolite": fenolite.__version__ if args.with_current else versions.get("fenolite"),
        },
        issues=tuple(issues),
        evidence=EVIDENCE,
        writes=writes,
        depends=depends_on(ctx.cwd, *(folder / name for name in sorted(folder_files(folder)))),
    )


__all__ = ["EVIDENCE", "replay_command"]
