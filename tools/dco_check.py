# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Check that every commit carries the sign-off that ``CONTRIBUTING.md`` requires.

Usage: ``python3 tools/dco_check.py [<revision range>]``. Without an argument every commit reachable
from ``HEAD`` is read; with one, the commits of that range (``origin/main..HEAD``). A commit with more
than one parent is skipped: the checkout of a pull request is a merge commit made by the runner. A
commit passes when its message holds a line ``Signed-off-by: <name> <<address>>``; the line is not
compared with the author, because the certificate is the signer's own statement.

A commit whose full hash is listed in ``tools/dco_exceptions.txt`` (a hash, then the reason) is skipped: a
commit already on the main branch cannot gain a trailer, and each entry is the maintainer's decision.

Output: one line ``<short hash> <subject>`` per failing commit. Exit codes: 0 when none fails, 1 when
one does, 2 when ``git`` fails. Standard library only.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

SIGN_OFF = re.compile(r"^Signed-off-by: \S.* <[^<>\s]+@[^<>\s]+>\s*$", re.MULTILINE)
RECORD, FIELD = "\x1e", "\x1f"
EXCEPTIONS = Path(__file__).resolve().with_name("dco_exceptions.txt")


def exceptions(path: Path = EXCEPTIONS) -> frozenset[str]:
    """The full hashes listed in the exceptions file; a line needs a 40-digit hash and a reason."""
    if not path.is_file():
        return frozenset()
    found: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        commit, _, reason = line.partition(" ")
        if not re.fullmatch(r"[0-9a-f]{40}", commit) or not reason.strip():
            raise ValueError(f"{path.name}: a line needs a full hash and a reason: {line!r}")
        found.add(commit)
    return frozenset(found)


def unsigned(revisions: str) -> list[str]:
    """``<short hash> <subject>`` of every single-parent commit of ``revisions`` without a sign-off."""
    log = subprocess.run(
        ["git", "log", "--no-merges", f"--format=%H{FIELD}%h{FIELD}%s{FIELD}%B{RECORD}", revisions],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    skipped = exceptions()
    failing: list[str] = []
    for record in log.stdout.split(RECORD):
        if not record.strip():
            continue
        full, short, subject, body = record.strip("\n").split(FIELD, 3)
        if full not in skipped and not SIGN_OFF.search(body):
            failing.append(f"{short} {subject}")
    return failing


def main(argv: list[str]) -> int:
    if len(argv) > 1:
        print("usage: dco_check.py [<revision range>]", file=sys.stderr)
        return 2
    try:
        failing = unsigned(argv[0] if argv else "HEAD")
    except (subprocess.CalledProcessError, OSError, ValueError) as error:
        detail = getattr(error, "stderr", "") or str(error)
        what = "the exceptions file is malformed" if isinstance(error, ValueError) else "git failed"
        print(f"dco_check: {what}: {detail.strip()}", file=sys.stderr)
        return 2
    for line in failing:
        print(line)
    return 1 if failing else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
