# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Fetch the public test corpus declared in tests/corpus/manifest.toml and verify SHA-256.

    uv run python tools/corpus_fetch.py [--manifest PATH] [--cache DIR] [--only ID ...]
                                        [--uses TAG ...] [--exclude-uses TAG ...]

Files land in <cache>/<id>/<name>, where <name> is the URL-decoded last segment of the URL path; the
default cache is ~/.cache/fenolite/corpus (override with FENOLITE_CORPUS_CACHE). ``--uses`` keeps the
items that have any of the given tags, ``--exclude-uses`` drops the items that have any of them. A
file whose hash does not match is deleted and the run exits with code 1.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ("id", "url", "ref", "sha256", "license", "license_variant", "embeddable", "uses", "notes")
USER_AGENT = "fenolite-corpus-fetch (+https://github.com/lgili/Fenolite)"
# A host that answers 429 (too many requests) or a 5xx is asked again after a pause: the CI fetches
# hundreds of rows from one host when its cache key changes, and a rate limit is not a missing file.
RETRY_STATUS = frozenset({429, 500, 502, 503, 504})
RETRY_ATTEMPTS = 6
RETRY_FIRST_PAUSE_S = 5.0
RETRY_MAX_PAUSE_S = 120.0


def default_cache() -> Path:
    override = os.environ.get("FENOLITE_CORPUS_CACHE")
    return Path(override) if override else Path.home() / ".cache" / "fenolite" / "corpus"


def load_manifest(path: Path) -> list[dict[str, Any]]:
    return list(tomllib.loads(path.read_text(encoding="utf-8")).get("file", []))


def file_name(entry: dict[str, Any]) -> str:
    """The cached file name: the URL-decoded last segment of the URL path (the id if empty)."""
    return urllib.parse.unquote(Path(urllib.parse.urlparse(entry["url"]).path).name) or entry["id"]


def select(entries: list[dict[str, Any]], uses: list[str], exclude: list[str]) -> list[dict[str, Any]]:
    """Items with any tag of ``uses`` (all items when empty) and none of ``exclude``."""
    kept = [e for e in entries if not uses or set(uses) & set(e.get("uses", []))]
    return [e for e in kept if not set(exclude) & set(e.get("uses", []))]


def _download(url: str) -> bytes:
    scheme = urllib.parse.urlparse(url).scheme
    if scheme not in ("https", "file"):
        raise ValueError(f"unsupported URL scheme {scheme!r} (use https or file)")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=300) as response:  # noqa: S310 (scheme checked above)
        return response.read()


def _retry_pause(error: urllib.error.HTTPError, attempt: int) -> float:
    """Seconds to wait before asking again: the server's Retry-After when it gives one in seconds,
    else a doubling pause from RETRY_FIRST_PAUSE_S; never more than RETRY_MAX_PAUSE_S."""
    header = error.headers.get("Retry-After")
    if header is not None and header.strip().isdigit():
        return min(float(header.strip()), RETRY_MAX_PAUSE_S)
    return min(RETRY_FIRST_PAUSE_S * 2**attempt, RETRY_MAX_PAUSE_S)


def download_with_retry(
    url: str,
    *,
    download: Callable[[str], bytes] = _download,
    sleep: Callable[[float], None] = time.sleep,
    attempts: int = RETRY_ATTEMPTS,
) -> bytes:
    """Download ``url``, asking again after a pause when the host answers a status of RETRY_STATUS.
    Any other error, or the last attempt's error, is raised."""
    for attempt in range(attempts):
        try:
            return download(url)
        except urllib.error.HTTPError as exc:
            if exc.code not in RETRY_STATUS or attempt == attempts - 1:
                raise
            sleep(_retry_pause(exc, attempt))
    raise AssertionError("unreachable: the loop returns or raises")


def fetch(entries: list[dict[str, Any]], cache: Path) -> tuple[list[str], list[str], list[str]]:
    fetched: list[str] = []
    cached: list[str] = []
    failed: list[str] = []
    for entry in entries:
        missing = [k for k in REQUIRED if k not in entry]
        if missing:
            failed.append(f"{entry.get('id', '?')}: missing keys {missing}")
            continue
        target = cache / entry["id"] / file_name(entry)
        if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == entry["sha256"]:
            cached.append(entry["id"])
            continue
        try:
            data = download_with_retry(entry["url"])
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
    parser.add_argument("--uses", action="append", default=[], metavar="TAG", help="keep items with this tag")
    parser.add_argument(
        "--exclude-uses", action="append", default=[], metavar="TAG", help="drop items with this tag"
    )
    args = parser.parse_args(argv)
    entries = select(load_manifest(args.manifest), args.uses, args.exclude_uses)
    if args.only:
        entries = [e for e in entries if e.get("id") in set(args.only)]
    fetched, cached, failed = fetch(entries, args.cache or default_cache())
    print(
        f"corpus: {len(entries)} item(s): {len(fetched)} fetched, {len(cached)} already cached, "
        f"{len(failed)} failed"
    )
    for line in failed:
        print(f"  failed: {line}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
