# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Generate the prepared CLI/Python contract snapshot or its pre-freeze review."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from fenolite.cli.api import discover
from fenolite.cli.surface import Surface, cli_surface, review, surface_changes

ROOT = Path(__file__).resolve().parents[1]


def render(surface: Surface) -> str:
    return json.dumps(surface.to_json(), ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def release_tag(version: str, *, root: Path | None = None) -> str | None:
    """Read the last reachable stable 1.x+ release; neither fetch nor create tags."""
    folder = ROOT if root is None else root
    match = re.match(r"(\d+)\.(\d+)\.(\d+)", version)
    if match is None:
        raise ValueError(f"invalid package version {version!r}")
    current = tuple(int(part) for part in match.groups())
    if current[0] < 1:
        return None
    tags = subprocess.run(
        ["git", "tag", "--merged", "HEAD"], cwd=folder, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    released = []
    for tag in tags:
        match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", tag)
        if match is not None:
            number = tuple(map(int, match.groups()))
            if (1, 0, 0) <= number <= current:
                released.append((number, tag))
    if not released:
        if current == (1, 0, 0):  # the first freeze is the committed snapshot, until its release tag
            return None
        raise ValueError("no reachable 1.0+ release surface; restore the local release tags before checking")
    return max(released)[1]


def release_baseline(surface: Surface) -> Surface | None:
    tag = release_tag(str(surface.data["version"]))
    if tag is None:
        return None
    raw = subprocess.run(
        ["git", "show", f"{tag}:docs/cli-surface.json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return Surface.from_json(raw)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail when the committed snapshot differs")
    parser.add_argument(
        "--review", action="store_true", help="write static review references with pending decisions"
    )
    parser.add_argument(
        "--keep-all", action="store_true", help="record an authorized keep-all review decision"
    )
    parser.add_argument("--out", type=Path, help="snapshot or review destination")
    args = parser.parse_args(argv)
    if args.review and args.check:
        parser.error("--review and --check cannot be combined")
    if args.keep_all and not args.review:
        parser.error("--keep-all requires --review")
    commands = discover()
    surface = cli_surface(commands)
    path = args.out or (ROOT / "docs/cli-surface.json" if not args.review else None)
    text = review(surface, ROOT, commands, keep_all=args.keep_all) if args.review else render(surface)
    if path is None:
        sys.stdout.write(text)
    elif args.check:
        if not path.is_file() or path.read_text(encoding="utf-8") != text:
            print(f"contract surface differs: run tools/gen_cli_surface.py ({path.name})", file=sys.stderr)
            if path.is_file():
                before = Surface.from_json(path.read_text(encoding="utf-8"))
                for change in surface_changes(before, surface):
                    print(f"  {change.kind}: {change.path}", file=sys.stderr)
            return 1
        try:
            baseline = release_baseline(surface)
        except (ValueError, subprocess.CalledProcessError) as exc:
            print(f"cannot check release compatibility: {exc}", file=sys.stderr)
            return 1
        breaking = (
            () if baseline is None else tuple(c for c in surface_changes(baseline, surface) if c.breaking)
        )
        if breaking:
            for change in breaking:
                print(f"breaking {change.kind}: {change.path}", file=sys.stderr)
            return 1
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
