# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite skill show|install``: copy the packaged skill folder to where an agent reads it (capability
cli-contract, "Skill command"; ``docs/cli-contract.md``, "skill").

``show`` lists what the package holds. ``install`` plans one file per file of the skill under
``<folder>/fenolite/`` and, with ``--agents-md``, a pointer section in the ``AGENTS.md`` of the working
directory. It writes only through the mutation protocol, runs no tool and opens no connection.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from fenolite import __version__
from fenolite.agent import guide
from fenolite.cli.api import Command, Context, PlannedWrite, Result
from fenolite.cli.errors import CliError
from fenolite.core.io import sha256_bytes

HELP = "show the packaged agent skill, or install it into an agent's skill folder or point AGENTS.md at it"
ACTIONS = ("show", "install")
AGENTS_FILE = "AGENTS.md"
NOTHING_ASKED = "say where: --agent NAME, --dir DIR, or --agents-md for a pointer section in AGENTS.md"


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/cli-contract.md, 'skill'."
    parser.add_argument("skill_action", metavar="ACTION", choices=ACTIONS, help="show or install")
    parser.add_argument(
        "--agent", metavar="NAME", help="install: the agent whose project skill folder is used"
    )
    parser.add_argument("--dir", metavar="DIR", help="install: any folder; the skill goes to DIR/fenolite")
    parser.add_argument(
        "--agents-md",
        action="store_true",
        help="install: also keep a pointer section in the AGENTS.md of this folder",
    )


def version_line(version: str) -> str:
    """The last line of an installed ``SKILL.md``: it names the version the copy came from."""
    return f"<!-- installed from fenolite {version} -->"


def installed_skill(data: bytes, version: str) -> bytes:
    """The packaged ``SKILL.md`` followed by :func:`version_line`."""
    text = data.decode("utf-8")
    return (text + ("" if text.endswith("\n") else "\n") + version_line(version) + "\n").encode("utf-8")


def marked_section() -> str:
    return f"{guide.AGENTS_BEGIN}\n{guide.AGENTS_SECTION}{guide.AGENTS_END}\n"


def with_pointer(existing: str | None) -> str:
    """The content of ``AGENTS.md`` with the pointer section: a new file, the text between the two marker
    lines replaced, or the section appended after one empty line. :class:`ValueError` when the file holds
    one marker without the other, a marker twice, or the end before the beginning."""
    if existing is None:
        return marked_section()
    lines = existing.split("\n")
    begins = [n for n, line in enumerate(lines) if line.rstrip() == guide.AGENTS_BEGIN]
    ends = [n for n, line in enumerate(lines) if line.rstrip() == guide.AGENTS_END]
    if not begins and not ends:
        body = existing if existing.endswith("\n") or not existing else existing + "\n"
        return body + ("\n" if body else "") + marked_section()
    if len(begins) != 1 or len(ends) != 1 or begins[0] > ends[0]:
        raise ValueError(
            f"expected one line {guide.AGENTS_BEGIN!r} followed by one line {guide.AGENTS_END!r}; "
            f"found {len(begins)} and {len(ends)}"
        )
    section = marked_section().split("\n")[:-1]
    return "\n".join([*lines[: begins[0]], *section, *lines[ends[0] + 1 :]])


def _show() -> Result:
    start = guide.page(guide.START)
    return Result(
        result={
            "name": guide.SKILL_NAME,
            "description": start.summary,
            "version": __version__,
            "files": [
                {"path": file.path, "bytes": len(file.data), "sha256": sha256_bytes(file.data)}
                for file in guide.skill_files()
            ],
            "agents": [{"agent": agent, "dir": folder} for agent, folder in sorted(guide.AGENT_DIRS.items())],
        }
    )


def _target(args: argparse.Namespace) -> str | None:
    """The folder the skill folder goes into, or ``None`` with ``--agents-md`` alone."""
    if args.agent is not None and args.dir is not None:
        raise CliError("FEN-2001", "--agent and --dir are mutually exclusive", hint="use one of them")
    if args.agent is not None:
        if args.agent not in guide.AGENT_DIRS:
            known = ", ".join(sorted(guide.AGENT_DIRS)) or "none yet"
            raise CliError(
                "FEN-2001",
                f"unknown agent {args.agent!r}",
                hint=f"the agents with a known skill folder are: {known}; --dir DIR names any folder",
                where="--agent",
            )
        return guide.AGENT_DIRS[args.agent]
    if args.dir is not None:
        if not str(args.dir).strip():
            raise CliError("FEN-2001", "--dir is empty", hint="name a folder", where="--dir")
        return Path(args.dir).as_posix()
    if not args.agents_md:
        raise CliError("FEN-2001", "install: nothing to install", hint=NOTHING_ASKED)
    return None


def _pointer(ctx: Context) -> PlannedWrite:
    path = ctx.cwd / AGENTS_FILE
    existing: str | None = None
    if path.exists():
        try:
            existing = path.read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise CliError(
                "FEN-3004", f"{AGENTS_FILE} cannot be read as UTF-8 text", where=AGENTS_FILE
            ) from exc
    try:
        text = with_pointer(existing)
    except ValueError as exc:
        raise CliError(
            "FEN-3004",
            f"{AGENTS_FILE}: {exc}",
            hint="keep both marker lines or remove both, then run the command again",
            where=AGENTS_FILE,
        ) from exc
    return PlannedWrite(path=AGENTS_FILE, data=text.encode("utf-8"), kind="agents-md")


def _install(args: argparse.Namespace, ctx: Context) -> Result:
    target = _target(args)
    writes: list[PlannedWrite] = []
    if target is not None:
        for file in guide.skill_files():
            data = installed_skill(file.data, __version__) if file.path == "SKILL.md" else file.data
            path = Path(target, guide.SKILL_NAME, *file.path.split("/")).as_posix()
            writes.append(PlannedWrite(path=path, data=data, kind="skill"))
    if args.agents_md:
        writes.append(_pointer(ctx))
    result: dict[str, Any] = {
        "action": "install",
        "target": None if target is None else Path(target, guide.SKILL_NAME).as_posix(),
        "files": [write.path for write in writes],
        "version": __version__,
    }
    return Result(result=result, writes=tuple(writes))


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    if args.skill_action == "show":
        if args.agent is not None or args.dir is not None or args.agents_md:
            raise CliError(
                "FEN-2001", "show takes no option", hint="--agent, --dir and --agents-md belong to install"
            )
        return _show()
    return _install(args, ctx)


COMMAND = Command(
    name="skill",
    help=HELP,
    mutates=True,
    register=_register,
    run=_run,
    example_args=("show",),
    mutation_example_args=("install", "--dir", "skills"),
)
