# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Benchmark a few boards of the newest fenolite-library release with this Fenolite (change c0279, task 4.4).

Usage: ``python tools/library_bench.py --out DIR [--library CHECKOUT | --release latest|vX.Y.Z]
[--boards N] [--only ID]...``. The optional scheduled job ``library-bench`` of ``nightly.yml`` runs it on
the head of ``dev``.

Each selected board is replayed with the running Fenolite (``fenolite library replay ITEM --upstream SRC
--with-current``) and its fidelity proof is run again (``fenolite verify-source``); the rows go through
``fenolite.library.proof.bench_table``, the same table the library's ``bench.yml`` publishes. Without
``--only`` the ``--boards`` boards with the fewest files are chosen, so the job stays short.

Outputs under ``--out``: ``bench.json`` (the table), ``run.json`` (release, library commit, Fenolite version,
boards) and the replies of every command; or ``not-run.json`` with the reason when there is no release to
benchmark yet. Exit codes: 0 when every selected board passes or nothing could run, 1 when a board fails,
2 on bad arguments. The job is optional and never gates a merge.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

REPOSITORY = "lgili/fenolite-library"
API = f"https://api.github.com/repos/{REPOSITORY}/releases"
CLONE = f"https://github.com/{REPOSITORY}.git"


def newest_release(fetch: Callable[[str], bytes] | None = None) -> str | None:
    """The tag of the newest published release, or ``None`` when the library has none yet (HTTP 404)."""
    opener = fetch or _get
    try:
        data = json.loads(opener(API + "/latest"))
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise
    tag = data.get("tag_name")
    return tag if isinstance(tag, str) and tag else None


def _get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(request, timeout=60) as reply:
        return reply.read()


def boards(library: Path) -> list[tuple[str, Path, int]]:
    """Every board item of a library checkout: (id, folder, file count), sorted by id."""
    found: list[tuple[str, Path, int]] = []
    for marker in sorted((library / "boards").rglob("item.json")):
        item = json.loads(marker.read_text(encoding="utf-8"))
        size = sum(1 for path in marker.parent.rglob("*") if path.is_file())
        found.append((str(item["id"]), marker.parent, size))
    return sorted(found)


def select(
    found: Sequence[tuple[str, Path, int]], *, count: int, only: Sequence[str] = ()
) -> list[tuple[str, Path]]:
    """The boards to run: those named by ``only`` (in that order), else the ``count`` smallest by files."""
    if only:
        by_id = {ident: root for ident, root, _ in found}
        missing = [ident for ident in only if ident not in by_id]
        if missing:
            raise SystemExit("no such board in the release: " + ", ".join(missing))
        return [(ident, by_id[ident]) for ident in only]
    ranked = sorted(found, key=lambda row: (row[2], row[0]))[:count]
    return sorted((ident, root) for ident, root, _ in ranked)


def _run(args: list[str], out: Path) -> int:
    with out.open("w", encoding="utf-8") as stream:
        return subprocess.run(args, stdout=stream, check=False).returncode


def bench(selected: Sequence[tuple[str, Path]], out: Path) -> list[dict[str, Any]]:
    """Replay and prove each board; one run row per board for ``bench_table``."""
    runs: list[dict[str, Any]] = []
    for index, (ident, root) in enumerate(selected):
        provenance = json.loads((root / "PROVENANCE.json").read_text(encoding="utf-8"))
        row: dict[str, Any] = {
            "id": ident,
            "levels": [],
            "differences": [],
            "fidelity": provenance.get("fidelity"),
        }
        started = time.monotonic_ns()
        with tempfile.TemporaryDirectory(prefix="library-bench-") as temporary:
            source = Path(temporary) / "upstream"
            try:
                upstream = provenance["upstream"]
                git = ["git", "-c", "core.autocrlf=false", "-c", "core.eol=lf"]
                subprocess.run([*git, "init", "-q", str(source)], check=True)
                subprocess.run(
                    [
                        *git,
                        "-C",
                        str(source),
                        "fetch",
                        "-q",
                        "--depth",
                        "1",
                        upstream["url"],
                        upstream["commit"],
                    ],
                    check=True,
                )
                subprocess.run([*git, "-C", str(source), "checkout", "-q", "FETCH_HEAD"], check=True)
                row["replay_exit"] = _run(
                    [
                        "fenolite",
                        "library",
                        "replay",
                        str(root),
                        "--upstream",
                        str(source),
                        "--with-current",
                        "--json",
                    ],
                    out / f"{index}-replay.json",
                )
                verify = out / f"{index}-verify.json"
                row["proof_exit"] = _run(
                    [
                        "fenolite",
                        "verify-source",
                        str(root / "design.py"),
                        "--against",
                        str(source / upstream["path"]),
                        "--provenance",
                        str(root / "PROVENANCE.json"),
                        "--json",
                    ],
                    verify,
                )
                result = json.loads(verify.read_text(encoding="utf-8")).get("result", {})
                row["levels"] = result.get("levels", [])
                row["differences"] = result.get("differences", [])
            except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
                row["failure"] = f"{type(error).__name__}: {error}"
        row["seconds"] = (time.monotonic_ns() - started) // 1_000_000_000
        runs.append(row)
    return runs


def table(runs: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """``bench_table`` of the runs; a board whose replay or proof command failed is a failure too."""
    from fenolite.library.proof import bench_table

    rows = bench_table(runs)
    by_id = {str(run["id"]): run for run in runs}
    for row in rows:
        run = by_id[row["id"]]
        if run.get("failure") or run.get("replay_exit", 1) or run.get("proof_exit", 1):
            row["result"] = "fail"
        row["failure"] = run.get("failure")
        row["replay_exit"] = run.get("replay_exit")
        row["proof_exit"] = run.get("proof_exit")
    return rows


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark a few boards of the newest fenolite-library release."
    )
    parser.add_argument("--out", type=Path, required=True)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--library", type=Path, help="an existing checkout of a release")
    source.add_argument("--release", default="latest", help="latest (default) or a tag vX.Y.Z")
    parser.add_argument("--boards", type=int, default=3)
    parser.add_argument("--only", action="append", default=[])
    options = parser.parse_args(argv)
    if options.boards < 1:
        parser.error("--boards must be at least 1")
    out: Path = options.out
    out.mkdir(parents=True, exist_ok=True)
    tag = None
    with tempfile.TemporaryDirectory(prefix="library-release-") as temporary:
        library = options.library
        if library is None:
            tag = newest_release() if options.release == "latest" else options.release
            if tag is None:
                _write(
                    out / "not-run.json", {"status": "not-run", "reason": f"{REPOSITORY} has no release yet"}
                )
                print(f"{REPOSITORY} has no release yet: nothing to benchmark")
                return 0
            library = Path(temporary) / "library"
            subprocess.run(
                ["git", "clone", "-q", "--depth", "1", "--branch", tag, CLONE, str(library)], check=True
            )
        found = boards(library)
        if not found:
            _write(out / "not-run.json", {"status": "not-run", "reason": "the release holds no board"})
            print("the release holds no board: nothing to benchmark")
            return 0
        selected = select(found, count=options.boards, only=options.only)
        runs = bench(selected, out)
        commit = subprocess.run(
            ["git", "-C", str(library), "rev-parse", "HEAD"], capture_output=True, text=True, check=False
        ).stdout.strip()
    rows = table(runs)
    _write(out / "bench.json", rows)
    from fenolite import __version__

    _write(
        out / "run.json",
        {"release": tag, "library_commit": commit, "fenolite": __version__, "boards": len(rows)},
    )
    for row in rows:
        print(f"{row['id']}: {row['result']} ({row['seconds']} s, {row['differences']} differences)")
    return 1 if any(row["result"] == "fail" for row in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
