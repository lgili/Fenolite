# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Fetch the public test corpus declared in tests/corpus/manifest.toml and verify SHA-256.

    uv run python tools/corpus_fetch.py [--manifest PATH] [--cache DIR] [--only ID ...]

Files land in <cache>/<id>/<file name>; the default cache is ~/.cache/fenolite/corpus
(override with FENOLITE_CORPUS_CACHE). A file whose hash does not match is deleted and the run
exits with code 1.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import tomllib
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ("id", "url", "ref", "sha256", "license", "license_variant", "embeddable", "uses", "notes")


def default_cache() -> Path:
    override = os.environ.get("FENOLITE_CORPUS_CACHE")
    return Path(override) if override else Path.home() / ".cache" / "fenolite" / "corpus"


def load_manifest(path: Path) -> list[dict[str, Any]]:
    return list(tomllib.loads(path.read_text(encoding="utf-8")).get("file", []))


def _download(url: str) -> bytes:
    scheme = urllib.parse.urlparse(url).scheme
    if scheme not in ("https", "file"):
        raise ValueError(f"unsupported URL scheme {scheme!r} (use https or file)")
    with urllib.request.urlopen(url, timeout=120) as response:  # noqa: S310 (scheme checked above)
        return response.read()


def fetch(entries: list[dict[str, Any]], cache: Path) -> tuple[list[str], list[str], list[str]]:
    fetched: list[str] = []
    cached: list[str] = []
    failed: list[str] = []
    for entry in entries:
        missing = [k for k in REQUIRED if k not in entry]
        if missing:
            failed.append(f"{entry.get('id', '?')}: missing keys {missing}")
            continue
        name = Path(urllib.parse.urlparse(entry["url"]).path).name or entry["id"]
        target = cache / entry["id"] / name
        if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == entry["sha256"]:
            cached.append(entry["id"])
            continue
        try:
            data = _download(entry["url"])
        except Exception as exc:  # network errors are reported, not raised
            failed.append(f"{entry['id']}: download failed: {exc}")
            continue
        digest = hashlib.sha256(data).hexdigest()
        if digest != entry["sha256"]:
            target.unlink(missing_ok=True)
            failed.append(f"{entry['id']}: sha256 mismatch (got {digest})")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        fetched.append(entry["id"])
    return fetched, cached, failed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch and verify the public test corpus.")
    parser.add_argument("--manifest", type=Path, default=ROOT / "tests" / "corpus" / "manifest.toml")
    parser.add_argument("--cache", type=Path, default=None)
    parser.add_argument("--only", nargs="*", default=None, help="fetch only these ids")
    args = parser.parse_args(argv)
    entries = load_manifest(args.manifest)
    if args.only:
        entries = [e for e in entries if e.get("id") in set(args.only)]
    fetched, cached, failed = fetch(entries, args.cache or default_cache())
    print(f"corpus: {len(fetched)} fetched, {len(cached)} already cached, {len(failed)} failed")
    for line in failed:
        print(f"  failed: {line}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
