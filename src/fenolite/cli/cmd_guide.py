# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite guide [TOPIC]``: the pages of the packaged agent guide, for the installed version
(capability cli-contract, "Guide command"; ``docs/cli-contract.md``, "guide"). Reads only packaged data."""

from __future__ import annotations

import argparse
import difflib

from fenolite import __version__
from fenolite.agent import guide
from fenolite.cli.api import Command, Context, Result
from fenolite.cli.errors import CliError

HELP = "print the agent guide of the installed version: the list of its pages, or one page"


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/cli-contract.md, 'guide'."
    parser.add_argument(
        "topic", metavar="TOPIC", nargs="?", help="the page to print, for example start (default: list them)"
    )


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    pages = guide.pages()
    if args.topic is None:
        topics = [
            {"topic": p.topic, "title": p.title, "summary": p.summary, "lines": len(p.text.splitlines())}
            for p in pages
        ]
        text = "".join(f"{p.topic}: {p.summary}\n" for p in pages)
        return Result(result={"version": __version__, "topics": topics}, text=text)
    topic = str(args.topic)
    found = next((p for p in pages if p.topic == topic), None)
    if found is None:
        names = [p.topic for p in pages]
        close = difflib.get_close_matches(topic, names, n=3, cutoff=0.5)
        hint = f"did you mean: {', '.join(close)}" if close else f"the pages are: {', '.join(names)}"
        raise CliError("FEN-2001", f"unknown guide page {topic!r}", hint=hint, where=topic)
    return Result(
        result={
            "topic": found.topic,
            "title": found.title,
            "summary": found.summary,
            "text": found.text,
            "version": __version__,
        },
        text=found.text,
    )


COMMAND = Command(
    name="guide",
    help=HELP,
    mutates=False,
    register=_register,
    run=_run,
    example_args=("start",),
)
