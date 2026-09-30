# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Residue scan: find material that must not be in the public repository.

See tools/residue/README.md. Exit codes: 0 clean, 5 hits, 2 usage error.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import io
import os
import re
import subprocess
import sys
import tomllib
import zipfile
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CFB_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
MAX_BYTES = 64 * 1024 * 1024
ZIP_SUFFIXES = (".zip", ".whl")


@dataclass(frozen=True)
class Pattern:
    id: str
    regex: re.Pattern[str]
    paths: tuple[str, ...] = ("**",)
    private: bool = False


@dataclass(frozen=True)
class Hit:
    path: str
    offset: int
    pattern: str

    def line(self) -> str:
        return f"{self.path}:{self.offset}:{self.pattern}"


@dataclass
class Config:
    patterns: list[Pattern]
    blobs: dict[str, str]  # sha256 -> label
    exclude: list[str]
    waivers: list[tuple[str, str]]  # (path glob, pattern id)
    private_tokens: int = 0
    private_blobs: int = 0
    notes: list[str] = field(default_factory=lambda: [])


def _glob(path: str, pattern: str) -> bool:
    if pattern == "**":
        return True
    if pattern.endswith("/**"):
        return path.startswith(pattern[:-2]) or path == pattern[:-3]
    return fnmatch.fnmatchcase(path, pattern)


def _read_lines(path: Path) -> list[str]:
    if not path.is_file():
        return []
    return [
        ln.strip()
        for ln in path.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]


def _token_regex(token: str) -> re.Pattern[str]:
    if token.startswith("re:"):
        return re.compile(token[3:], re.IGNORECASE)
    return re.compile(r"(?<![A-Za-z0-9])" + re.escape(token) + r"(?![A-Za-z0-9])", re.IGNORECASE)


def private_tokens(environ: Mapping[str, str] | None = None) -> list[str]:
    env = os.environ if environ is None else environ
    inline = env.get("FENOLITE_RESIDUE_TOKENS")
    if inline:
        return [t.strip() for t in re.split(r"[,\n]", inline) if t.strip() and not t.strip().startswith("#")]
    source = env.get("FENOLITE_RESIDUE_TOKENS_FILE") or str(Path.home() / ".fenolite-residue-tokens")
    return _read_lines(Path(source))


def _blob_lines(path: Path) -> dict[str, str]:
    blobs: dict[str, str] = {}
    for line in _read_lines(path):
        digest, _, label = line.partition(" ")
        if re.fullmatch(r"[0-9a-f]{64}", digest):
            blobs[digest] = label.strip() or "blob"
    return blobs


def load_config(repo: Path = REPO, environ: Mapping[str, str] | None = None) -> Config:
    env = os.environ if environ is None else environ
    residue = repo / "tools" / "residue"
    scope = (
        tomllib.loads((residue / "scope.toml").read_text(encoding="utf-8"))
        if (residue / "scope.toml").exists()
        else {}
    )
    restricted: dict[str, tuple[str, ...]] = {
        pid: tuple(spec.get("paths", ["**"])) for pid, spec in scope.get("patterns", {}).items()
    }
    patterns: list[Pattern] = []
    for line in _read_lines(residue / "patterns.regex"):
        pid, _, regex = line.partition(" ")
        patterns.append(Pattern(pid, re.compile(regex.strip()), restricted.get(pid, ("**",))))
    tokens = private_tokens(env)
    for index, token in enumerate(tokens):
        patterns.append(Pattern(f"private-token-{index + 1}", _token_regex(token), private=True))
    blobs = _blob_lines(residue / "blobs.sha256")
    private_blob_file = Path(
        env.get("FENOLITE_RESIDUE_BLOBS_FILE") or Path.home() / ".fenolite-residue-blobs"
    )
    private_blobs = _blob_lines(private_blob_file)
    blobs.update(private_blobs)
    waivers = [(w["path"], w["pattern"]) for w in scope.get("waiver", [])]
    return Config(patterns, blobs, list(scope.get("exclude", [])), waivers, len(tokens), len(private_blobs))


def _decodings(data: bytes) -> Iterator[tuple[str, str]]:
    yield "utf-8", data.decode("utf-8", "surrogateescape")
    yield "utf-16le", data[: len(data) // 2 * 2].decode("utf-16le", "replace")
    yield "cp1252", data.decode("cp1252", "replace")


def _byte_offset(text: str, index: int, encoding: str) -> int:
    if encoding == "utf-8":
        return len(text[:index].encode("utf-8", "surrogateescape"))
    if encoding == "utf-16le":
        return index * 2
    return index


def scan_bytes(path: str, data: bytes, config: Config) -> list[Hit]:
    """All hits in one file's bytes (and, for zip archives, in each member)."""
    hits: set[Hit] = set()
    digest = hashlib.sha256(data).hexdigest()
    if digest in config.blobs:
        hits.add(Hit(path, 0, "known-blob"))
    active = [p for p in config.patterns if any(_glob(path.split("!", 1)[0], g) for g in p.paths)]
    active = [p for p in active if not any(_glob(path, wp) and wid == p.id for wp, wid in config.waivers)]
    for encoding, text in _decodings(data):
        for pattern in active:
            for match in pattern.regex.finditer(text):
                hits.add(Hit(path, _byte_offset(text, match.start(), encoding), pattern.id))
    if path.lower().endswith(ZIP_SUFFIXES) and zipfile.is_zipfile(io.BytesIO(data)):
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for info in archive.infolist():
                if not info.is_dir() and info.file_size <= MAX_BYTES:
                    hits.update(scan_bytes(f"{path}!{info.filename}", archive.read(info), config))
    return sorted(hits, key=lambda h: (h.path, h.offset, h.pattern))


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, check=False)


def tree_files(root: Path) -> list[str]:
    """Tracked and untracked-but-not-ignored files; falls back to a filtered walk without git."""
    proc = _git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    if proc.returncode == 0:
        files = [p for p in proc.stdout.decode("utf-8", "surrogateescape").split("\0") if p]
    else:
        skip = {".git", ".venv", "private", "__pycache__", ".pytest_cache", ".ruff_cache", "dist", "build"}
        files: list[str] = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in skip]
            for name in filenames:
                files.append((Path(dirpath) / name).relative_to(root).as_posix())
    files += [p.relative_to(root).as_posix() for p in sorted((root / "dist").glob("*.whl"))]
    return sorted(set(files))


def staged_files(root: Path) -> Iterator[tuple[str, bytes]]:
    proc = _git(root, "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z")
    if proc.returncode != 0:
        raise SystemExit(f"git failed: {proc.stderr.decode(errors='replace').strip()}")
    for name in (p for p in proc.stdout.decode("utf-8", "surrogateescape").split("\0") if p):
        blob = _git(root, "show", f":{name}")
        if blob.returncode == 0:
            yield name, blob.stdout


def history_files(root: Path) -> Iterator[tuple[str, bytes]]:
    """Every distinct blob reachable from any ref, labelled ``<commit>:<path>`` where first seen."""
    revs = _git(root, "rev-list", "--all")
    if revs.returncode != 0:  # not a repository, or no commits yet
        return
    seen: set[str] = set()
    for commit in revs.stdout.decode().split():
        tree = _git(root, "ls-tree", "-r", "-z", commit)
        for entry in (e for e in tree.stdout.decode("utf-8", "surrogateescape").split("\0") if e):
            meta, _, name = entry.partition("\t")
            kind, blob = meta.split()[1:3]
            if kind != "blob" or blob in seen:
                continue
            seen.add(blob)
            yield f"{commit[:12]}:{name}", _git(root, "cat-file", "blob", blob).stdout


def _repo_path(label: str) -> str:
    """Strip the ``<commit>:`` prefix that history mode adds, for scope matching."""
    head, sep, rest = label.partition(":")
    return rest if sep and re.fullmatch(r"[0-9a-f]{12}", head) else label


def scan(
    root: Path, config: Config, targets: Iterable[tuple[str, bytes]] | None = None
) -> tuple[list[Hit], int]:
    hits: list[Hit] = []
    count = 0
    if targets is None:
        targets = ((p, (root / p).read_bytes()) for p in tree_files(root)
                   if (root / p).is_file() and (root / p).stat().st_size <= MAX_BYTES)  # fmt: skip
    for path, data in targets:
        if any(_glob(_repo_path(path), pattern) for pattern in config.exclude):
            continue
        count += 1
        hits.extend(scan_bytes(path, data, config))
    return hits, count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Residue scan for the Fenolite repository.")
    parser.add_argument("--root", type=Path, default=REPO, help="tree to scan (default: this repository)")
    parser.add_argument("--staged", action="store_true", help="scan the files staged for commit")
    parser.add_argument("--history", action="store_true", help="scan every blob reachable from any ref")
    parser.add_argument("--list-patterns", action="store_true", help="list public patterns and exit")
    args = parser.parse_args(argv)
    config = load_config(REPO)
    if args.list_patterns:
        for p in config.patterns:
            if not p.private:
                print(f"{p.id}\t{', '.join(p.paths)}\t{p.regex.pattern}")
        print(f"known-blob\t**\t{len(config.blobs) - config.private_blobs} public hash(es)")
        print(
            f"private tokens loaded: {config.private_tokens}; private hashes loaded: {config.private_blobs}"
        )
        return 0
    root = args.root.resolve()
    targets = staged_files(root) if args.staged else history_files(root) if args.history else None
    hits, count = scan(root, config, targets)
    for hit in hits:
        print(hit.line())
    gate = "on" if (config.private_tokens or config.private_blobs) else "skipped (no private list configured)"
    files = {h.path for h in hits}
    print(f"residue: {len(hits)} hit(s) in {len(files)} file(s); {count} file(s) scanned; "
          f"waivers: {len(config.waivers)}; private gate: {gate}")  # fmt: skip
    return 5 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
