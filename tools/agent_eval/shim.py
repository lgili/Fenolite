# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The call log of the agent evaluation: a stand-in named ``fenolite`` (change c0081).

Installed first on the ``PATH`` of an agent, it starts the real command named by ``FENOLITE_EVAL_REAL``
with the same arguments, standard input, standard output and standard error, exits with its exit code,
and appends one line of JSON to the file named by ``FENOLITE_EVAL_LOG``::

    {"n": 3, "argv": ["build", "design.py", "--json"], "exit": 3, "elapsed_ms": 412, "error_code": "FEN-3004"}

- ``n`` counts the calls of the log from 1.
- ``error_code`` is the ``code`` of the JSON object on the last line of standard error when the exit code
  is not 0 and that line is such an object, else ``null``.
- ``argv`` holds the arguments as given, with one change that only the log sees: an argument that is an
  absolute path is written relative to the current folder when it lies in it, and as ``<outside>/NAME``
  otherwise. The log holds no environment value, no user name and no path outside the work folder.

The caller receives the bytes of the real command: standard input and output are inherited, standard
error is copied through as it arrives. This file is copied into the place of a run and started by the
launcher that ``install`` writes; it uses the standard library only and imports nothing of Fenolite.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import IO, cast

ENV_REAL = "FENOLITE_EVAL_REAL"
ENV_LOG = "FENOLITE_EVAL_LOG"
LOG_KEYS = ("n", "argv", "exit", "elapsed_ms", "error_code")
OUTSIDE = "<outside>"
TAIL_BYTES = 65536
CHUNK = 8192
EXIT_USAGE = 2
EXIT_NOT_STARTED = 127


def scrub(word: str, cwd: Path) -> str:
    """``word`` as the log holds it: an absolute path is made relative to ``cwd`` or loses its folder."""
    head, sep, value = word.partition("=") if word.startswith("--") else ("", "", word)
    if not value or not os.path.isabs(value):
        return word
    try:
        shown = Path(os.path.abspath(value)).relative_to(cwd).as_posix()
    except ValueError:
        shown = f"{OUTSIDE}/{Path(value).name}"
    return f"{head}{sep}{shown}"


def error_code(tail: bytes) -> str | None:
    """The ``code`` of the JSON object on the last line of what standard error held, or ``None``."""
    lines = tail.decode("utf-8", errors="replace").strip().splitlines()
    if not lines:
        return None
    try:
        found: object = json.loads(lines[-1])
    except json.JSONDecodeError:
        return None
    code = cast("dict[str, object]", found).get("code") if isinstance(found, dict) else None
    return code if isinstance(code, str) else None


def append(log: Path, argv: list[str], code: int, elapsed_ms: int, error: str | None) -> None:
    """Append the line of one call; its number is one more than the lines the log holds."""
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "a+", encoding="utf-8", newline="\n") as stream:
        stream.seek(0)
        number = sum(1 for line in stream if line.strip()) + 1
        record = {"n": number, "argv": argv, "exit": code, "elapsed_ms": elapsed_ms, "error_code": error}
        stream.seek(0, os.SEEK_END)
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")


def _copy(source: IO[bytes], tail: bytearray) -> None:
    """Copy standard error through as it arrives and keep its last bytes."""
    target = sys.stderr.buffer
    read: Callable[[int], bytes] = getattr(source, "read1", source.read)
    while True:
        chunk = read(CHUNK)
        if not chunk:
            return
        target.write(chunk)
        target.flush()
        tail += chunk
        if len(tail) > TAIL_BYTES:
            del tail[: len(tail) - TAIL_BYTES]


def main(argv: list[str] | None = None) -> int:
    """Run the real command with ``argv`` and log the call."""
    args = list(sys.argv[1:] if argv is None else argv)
    real, log = os.environ.get(ENV_REAL), os.environ.get(ENV_LOG)
    for name, value in ((ENV_REAL, real), (ENV_LOG, log)):
        if not value:
            sys.stderr.write(f"fenolite call log: the environment variable {name} is not set\n")
            return EXIT_USAGE
    assert real and log
    cwd = Path.cwd()
    started = time.monotonic()
    tail = bytearray()
    try:
        process = subprocess.Popen([real, *args], stderr=subprocess.PIPE)
    except OSError as error:
        sys.stderr.write(f"fenolite call log: {ENV_REAL} cannot be started: {error.strerror}\n")
        return EXIT_NOT_STARTED
    assert process.stderr is not None
    reader = threading.Thread(target=_copy, args=(process.stderr, tail), daemon=True)
    reader.start()
    try:
        code = process.wait()
    except KeyboardInterrupt:
        code = process.wait()
    reader.join()
    elapsed_ms = int((time.monotonic() - started) * 1000)
    found = error_code(bytes(tail)) if code != 0 else None
    append(Path(log), [scrub(word, cwd) for word in args], code, elapsed_ms, found)
    return code


def install(folder: Path, python: Path, shim: Path | None = None) -> Path:
    """Write into ``folder`` the launcher named ``fenolite`` that runs this file with ``python``.

    On Windows the launcher is ``fenolite.cmd``; elsewhere a ``/bin/sh`` script. Both quote the two paths.
    Returns the launcher.
    """
    folder.mkdir(parents=True, exist_ok=True)
    program = Path(__file__).resolve() if shim is None else shim
    if os.name == "nt":
        launcher = folder / "fenolite.cmd"
        launcher.write_text(f'@"{python}" "{program}" %*\r\n', encoding="utf-8", newline="")
        return launcher
    launcher = folder / "fenolite"

    def quoted(path: Path) -> str:
        return "'" + str(path).replace("'", "'\\''") + "'"

    launcher.write_text(
        f'#!/bin/sh\nexec {quoted(python)} {quoted(program)} "$@"\n', encoding="utf-8", newline="\n"
    )
    launcher.chmod(0o755)
    return launcher


if __name__ == "__main__":
    raise SystemExit(main())
