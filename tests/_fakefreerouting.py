# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Fake ``java``, ``docker`` and Freerouting jars for the hermetic tests of the Freerouting plugin (change
c0023). Nothing here is Freerouting's: the fakes record how they were called and write a session authored
for Fenolite.

Environment read by the fakes: ``FAKE_JAVA_RECORD`` (a JSON file that receives ``argv``, ``cwd`` and
``home`` of each router run; a ``-version`` call is not a run), ``FAKE_JAVA_OUTPUT`` (what the router
prints), ``FAKE_JAVA_SESSION`` (the session text to write to the ``-do`` file) and ``FAKE_JAVA_MODE``:
``write`` (default), ``none`` (exit 0, no session),
``fail`` (exit 3 with a message), ``garbage`` (a file that is no session), ``sleep`` or ``sleep-optimizer``
(sleep only when the argument that switches the optimizer off is absent).

For jobs of several runs (change c0109): ``FAKE_JAVA_RUNS`` names a file that receives one JSON line per
router run, with its ``argv`` and the text of the design file it was given (``dsn``);
``FAKE_JAVA_SESSION_<n>`` is the session of run ``n`` (counted from 1 in that file) instead of
``FAKE_JAVA_SESSION``; ``FAKE_JAVA_SLEEP_RUN`` is the number of the run that sleeps.
"""

from __future__ import annotations

import shlex
import stat
import sys
import textwrap
import zipfile
from pathlib import Path

from _resources import fake_tool

PINNED_REVISION = "ae3d377740b6ffa744bed1bab26625fe0278fa90"

_BODY = """\
import json
import os
import sys
import time
from pathlib import Path

VERSION = {version!r}
DOCKER = {docker!r}
argv = sys.argv[1:]
if not DOCKER and "-version" in argv:
    print(f'openjdk version "{{VERSION}}" 2026-01-01', file=sys.stderr)
    raise SystemExit(0)
folder = Path.cwd()
if DOCKER:
    mount = argv[argv.index("-v") + 1]
    folder = Path(mount.rsplit(":", 1)[0])
record = os.environ.get("FAKE_JAVA_RECORD")
if record:
    Path(record).write_text(
        json.dumps({{"argv": argv, "cwd": os.getcwd(), "home": os.environ.get("HOME", "")}}), encoding="utf-8"
    )
design_file = folder / argv[argv.index("-de") + 1] if "-de" in argv else None
number = 1
runs = os.environ.get("FAKE_JAVA_RUNS")
if runs:
    listed = Path(runs)
    if listed.exists():
        number = len(listed.read_text(encoding="utf-8").splitlines()) + 1
    dsn = design_file.read_text(encoding="utf-8") if design_file and design_file.is_file() else ""
    with open(listed, "a", encoding="utf-8") as stream:
        stream.write(json.dumps({{"argv": argv, "dsn": dsn}}) + "\\n")
kept = os.environ.get("FAKE_JAVA_KEEP_DSN")
if kept and design_file is not None:
    # change c0107: keep the design file the router was given
    given = design_file.read_text(encoding="utf-8")
    Path(kept).write_text(given, encoding="utf-8")
mode = os.environ.get("FAKE_JAVA_MODE", "write")
optimizer = "--router.optimizer.enabled=false" not in argv
if (
    mode == "sleep"
    or (mode == "sleep-optimizer" and optimizer)
    or os.environ.get("FAKE_JAVA_SLEEP_RUN") == str(number)
):
    time.sleep(5)
if mode == "fail":
    print("boom from the fake router in " + os.getcwd(), file=sys.stderr)
    raise SystemExit(3)
if mode == "none":
    raise SystemExit(0)
output = folder / argv[argv.index("-do") + 1]
assert (folder / argv[argv.index("-de") + 1]).is_file()
if mode == "garbage":
    output.write_text("(pcb not-a-session)", encoding="utf-8")
else:
    session = os.environ.get(f"FAKE_JAVA_SESSION_{{number}}") or os.environ["FAKE_JAVA_SESSION"]
    output.write_text(Path(session).read_text(encoding="utf-8"), encoding="utf-8")
print(os.environ.get("FAKE_JAVA_OUTPUT", "fake router done"))
"""


def _script(path: Path, *, version: str, docker: bool) -> Path:
    body = textwrap.dedent(_BODY).format(version=version, docker=docker)
    source = path.with_name(path.name + "_fake.py")
    source.write_text(body, encoding="utf-8")
    if sys.platform == "win32":
        # a ``.cmd`` launcher that a process starts by its path, as it starts the shell wrapper elsewhere
        return fake_tool(path, source)
    # a shell wrapper, not a shebang: the interpreter's path may hold blanks
    path.write_text(f'#!/bin/sh\nexec {shlex.quote(sys.executable)} {shlex.quote(str(source))} "$@"\n')
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def create_fake_java(folder: Path, *, version: str = "25.0.1") -> Path:
    """An executable ``java`` in ``folder/bin`` whose ``-version`` prints ``version``."""
    bin_dir = folder / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    return _script(bin_dir / "java", version=version, docker=False)


def create_fake_docker(folder: Path) -> Path:
    """An executable ``docker`` in ``folder/docker-bin``: it writes the session into the mounted folder.
    Returns the folder, to put on ``PATH``."""
    bin_dir = folder / "docker-bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    _script(bin_dir / "docker", version="", docker=True)
    return bin_dir


def create_fake_jar(
    folder: Path, name: str = "router.jar", *, revision: str | None = PINNED_REVISION
) -> Path:
    """A jar holding only a manifest; ``revision`` is its ``Build-Revision`` (``None``: no such line)."""
    jar = folder / name
    lines = ["Manifest-Version: 1.0", "Implementation-Title: fake"]
    if revision is not None:
        lines.append(f"Build-Revision: {revision}")
    with zipfile.ZipFile(jar, "w") as archive:
        archive.writestr("META-INF/MANIFEST.MF", "\r\n".join(lines) + "\r\n")
    return jar


__all__ = ["PINNED_REVISION", "create_fake_docker", "create_fake_jar", "create_fake_java"]
