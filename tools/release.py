# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The steps of the release workflow that are not a shell one-liner (change c0210).

    uv run --no-project python tools/release.py check --tag vX.Y.Z [--source DIR]
    uv run --no-project python tools/release.py notes --tag vX.Y.Z --dist DIR [--source DIR]
                                                      [--previous vA.B.C] [--run-url URL] [--pypi]
    uv run --no-project python tools/release.py latest --tag vX.Y.Z --tags FILE
    uv run --no-project python tools/release.py pypi-files --tag vX.Y.Z --dist DIR

``check`` fails unless the tag, ``fenolite.__version__``, the alias version, the alias pin and a
``## [X.Y.Z]`` section of ``CHANGELOG.md`` agree. ``notes`` writes the body of the GitHub Release from
that section, the install lines and the SHA-256 of the files in ``DIR``. ``latest`` prints ``true`` when
the tag is the highest final version of the list. ``pypi-files`` replaces ``DIR`` with the files that
PyPI holds for the version, checked against PyPI's digests, so the release attaches the published bytes.

Standard library only: the workflow runs it before anything is installed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.request
from collections.abc import Callable, Sequence
from pathlib import Path

REPOSITORY = "lgili/Fenolite"
PACKAGES = ("fenolite", "phenolite")
"""The core package and its alias, which installs the core at the same version."""
BODY_LIMIT = 125_000
"""GitHub refuses a release body above 125 000 characters."""
FINAL = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
TAG = re.compile(r"^v(\d+\.\d+\.\d+(?:(?:a|b|rc)\d+|\.dev\d+|\.post\d+)?)$")


class ReleaseError(Exception):
    """A release input that disagrees with another; the message says which."""


def version_of(tag: str) -> str:
    """``X.Y.Z`` of ``vX.Y.Z`` (a PEP 440 pre-, dev- or post-release suffix is kept)."""
    found = TAG.match(tag)
    if not found:
        raise ReleaseError(f"tag {tag!r} is not v<major>.<minor>.<patch>[pre]")
    return found.group(1)


def is_final(version: str) -> bool:
    return FINAL.match(version) is not None


def changelog_section(text: str, version: str) -> tuple[str, str]:
    """The date and the body of ``## [version] - date`` in a changelog, without its heading."""
    heading = re.compile(rf"^## \[{re.escape(version)}\](?: - (\S+))?\s*$", re.MULTILINE)
    found = heading.search(text)
    if not found:
        raise ReleaseError(f"CHANGELOG.md has no section ## [{version}]")
    following = re.compile(r"^## \[", re.MULTILINE).search(text, found.end())
    body = text[found.end() : following.start() if following else len(text)].strip("\n")
    if not body.strip():
        raise ReleaseError(f"the section ## [{version}] of CHANGELOG.md is empty")
    return found.group(1) or "", body


def check(source: Path, tag: str) -> list[str]:
    """Why ``tag`` cannot be released from ``source``; empty when everything agrees."""
    version = version_of(tag)
    problems: list[str] = []
    init = (source / "src" / "fenolite" / "__init__.py").read_text(encoding="utf-8")
    core = re.search(r'^__version__ = "([^"]+)"$', init, re.MULTILINE)
    if not core or core.group(1) != version:
        problems.append(
            f"src/fenolite/__init__.py: __version__ is {core and core.group(1)!r}, not {version!r}"
        )
    alias = (source / "packaging" / "phenolite" / "pyproject.toml").read_text(encoding="utf-8")
    alias_version = re.search(r'^version = "([^"]+)"$', alias, re.MULTILINE)
    if not alias_version or alias_version.group(1) != version:
        problems.append(f"packaging/phenolite/pyproject.toml: version is not {version!r}")
    if f'"fenolite=={version}"' not in alias:
        problems.append(f"packaging/phenolite/pyproject.toml: the alias does not pin fenolite=={version}")
    try:
        changelog_section((source / "CHANGELOG.md").read_text(encoding="utf-8"), version)
    except ReleaseError as error:
        problems.append(str(error))
    return problems


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def notes(
    *,
    tag: str,
    changelog: str,
    files: Sequence[Path],
    previous: str | None,
    run_url: str | None,
    record: bool,
    on_pypi: bool,
) -> str:
    """The body of the GitHub Release of ``tag``."""
    version = version_of(tag)
    date, body = changelog_section(changelog, version)
    base = f"https://github.com/{REPOSITORY}"
    lines = [f"# Fenolite {version}", ""]
    when = f" on {date}" if date else ""
    pypi = " and ".join(f"[{name}](https://pypi.org/project/{name}/{version}/)" for name in PACKAGES)
    lines += [
        f"Fenolite {version}, released{when}. Published on PyPI as {pypi} (the alias installs "
        f"`fenolite=={version}`)."
        if on_pypi
        else f"Fenolite {version}, released{when}.",
        "",
        "## Install",
        "",
        "```sh",
        f"pip install fenolite=={version}",
        "# or, as a tool",
        f"uv tool install fenolite=={version}",
        "```",
        "",
    ]
    links = []
    if record:
        minor = ".".join(version.split(".")[:2])
        links.append(
            f"[release record]({base}/blob/{tag}/docs/release/v{minor}.md) (shipped changes, open tasks)"
        )
    if previous:
        links.append(f"[full diff]({base}/compare/{previous}...{tag})")
    links.append(f"[changelog]({base}/blob/{tag}/CHANGELOG.md)")
    lines += ["See the " + ", the ".join(links) + ".", "", "## Changes", "", body, ""]
    if files:
        lines += ["## Files", "", "| file | SHA-256 |", "|---|---|"]
        lines += [f"| `{path.name}` | `{sha256(path)}` |" for path in sorted(files, key=lambda p: p.name)]
        lines += [""]
        source = (
            "the files PyPI serves for this version, checked against its SHA-256 digests"
            if on_pypi
            else ("built from the tagged commit")
        )
        run = f" ([release run]({run_url}))" if run_url else ""
        lines += [f"The attached files are {source}{run}; `SHA256SUMS` lists the same digests.", ""]
    text = "\n".join(lines)
    if len(text) > BODY_LIMIT:
        cut = f"\n\n… the list goes on in the [changelog]({base}/blob/{tag}/CHANGELOG.md).\n"
        text = text[: BODY_LIMIT - len(cut)].rsplit("\n", 1)[0] + cut
    return text


def latest(tag: str, tags: Sequence[str]) -> bool:
    """Whether ``tag`` is the highest final version among ``tags`` (itself included)."""
    version = version_of(tag)
    if not is_final(version):
        return False

    def key(name: str) -> tuple[int, ...] | None:
        try:
            found = FINAL.match(version_of(name))
        except ReleaseError:
            return None
        return tuple(int(part) for part in found.groups()) if found else None

    finals = [k for k in (key(name) for name in (*tags, tag)) if k is not None]
    return key(tag) == max(finals)


Fetch = Callable[[str], bytes]


def _fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as reply:  # noqa: S310 - https URLs of pypi.org only
        return reply.read()


def pypi_files(tag: str, dist: Path, fetch: Fetch = _fetch) -> list[Path]:
    """Replace the files of ``dist`` with what PyPI holds for the version of ``tag``, each checked against
    PyPI's SHA-256; empty (and ``dist`` untouched) when PyPI holds no file of the version yet."""
    version = version_of(tag)
    found: list[tuple[str, str, str]] = []
    for name in PACKAGES:
        try:
            meta = json.loads(fetch(f"https://pypi.org/pypi/{name}/{version}/json"))
        except Exception:  # noqa: BLE001 - a version not on PyPI answers 404
            return []
        found += [(row["filename"], row["url"], row["digests"]["sha256"]) for row in meta["urls"]]
    if not found:
        return []
    for old in dist.iterdir():
        old.unlink()
    written = []
    for filename, url, digest in found:
        data = fetch(url)
        if hashlib.sha256(data).hexdigest() != digest:
            raise ReleaseError(f"{filename}: the downloaded bytes do not have PyPI's SHA-256")
        path = dist / filename
        path.write_bytes(data)
        written.append(path)
    return written


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("check", "notes", "latest", "pypi-files"):
        sub = commands.add_parser(name)
        sub.add_argument("--tag", required=True)
        if name in ("check", "notes"):
            sub.add_argument("--source", type=Path, default=Path("."))
        if name in ("notes", "pypi-files"):
            sub.add_argument("--dist", type=Path, required=True)
        if name == "notes":
            sub.add_argument("--previous")
            sub.add_argument("--run-url")
            sub.add_argument("--pypi", action="store_true", help="the version is on PyPI")
        if name == "latest":
            sub.add_argument("--tags", type=Path, required=True, help="a file with one tag per line")
    args = parser.parse_args(argv)
    try:
        if args.command == "check":
            problems = check(args.source, args.tag)
            for problem in problems:
                print(f"release: {problem}", file=sys.stderr)
            if not problems:
                print(f"release: {args.tag} agrees with the versions and the changelog")
            return 1 if problems else 0
        if args.command == "notes":
            files = sorted(p for p in args.dist.iterdir() if p.is_file())
            minor = ".".join(version_of(args.tag).split(".")[:2])
            print(
                notes(
                    tag=args.tag,
                    changelog=(args.source / "CHANGELOG.md").read_text(encoding="utf-8"),
                    files=files,
                    previous=args.previous or None,
                    run_url=args.run_url,
                    record=(args.source / "docs" / "release" / f"v{minor}.md").is_file(),
                    on_pypi=args.pypi,
                )
            )
            return 0
        if args.command == "latest":
            tags = [
                line.strip() for line in args.tags.read_text(encoding="utf-8").splitlines() if line.strip()
            ]
            print("true" if latest(args.tag, tags) else "false")
            return 0
        written = pypi_files(args.tag, args.dist)
        print("\n".join(path.name for path in written) or "release: the version is not on PyPI yet")
        return 0
    except ReleaseError as error:
        print(f"release: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
