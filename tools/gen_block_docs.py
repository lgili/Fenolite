# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The pages of the shipped blocks (change c0268, ``docs/blocks.md``, "Generated pages").

    uv run python tools/gen_block_docs.py           # write docs/blocks/<name>.md and docs/blocks/index.md
    uv run python tools/gen_block_docs.py --check   # fail on any difference from the committed pages

Each page is ``fenolite.dsl.record.page`` of a shipped block's record, with each source's link from
``docs/evidence/sources.md`` (the core never reads that file). The index lists every shipped block.
"""

from __future__ import annotations

import argparse
import ast
import inspect
import re
import sys
import textwrap
from collections.abc import Mapping, Sequence
from pathlib import Path

from fenolite.cli.blocksrc import find_blocks
from fenolite.dsl.record import BlockRecord, page

ROOT = Path(__file__).resolve().parents[1]
FOLDER = Path("docs") / "blocks"
SOURCES = Path("docs") / "evidence" / "sources.md"
_ROW = re.compile(r"^\| (S-\d{4,}) \| ([^|]+) \|", re.MULTILINE)


def source_titles(root: Path = ROOT) -> dict[str, str]:
    """Source id → the link of its row in ``docs/evidence/sources.md``."""
    text = (root / SOURCES).read_text(encoding="utf-8")
    return {match.group(1): match.group(2).strip() for match in _ROW.finditer(text)}


def shipped_records() -> list[BlockRecord]:
    return [entry.record for entry in find_blocks() if entry.source == "builtin"]


def details() -> dict[str, str]:
    """Authored source and checked layout metadata beside each shipped definition."""
    from fenolite.reuse.blocklayout import read_block_layout
    from fenolite.testing.blocks import convention

    found: dict[str, str] = {}
    for entry in find_blocks():
        if entry.source != "builtin":
            continue
        definition = entry.definition
        text = textwrap.dedent(inspect.getsource(definition.function))
        reasons: list[str] = []
        for node in ast.walk(ast.parse(text)):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "expect"
                and len(node.args) >= 2
            ):
                continue
            reason = node.args[1]
            if isinstance(reason, ast.Constant) and isinstance(reason.value, str):
                reasons.append(reason.value)
            elif isinstance(reason, ast.JoinedStr):
                reasons.append(
                    "".join(v.value if isinstance(v, ast.Constant) else "<part>" for v in reason.values)
                )
        rows = ["", "## Expectations", "", *[f"- {reason}" for reason in reasons], ""]
        paths = convention(definition)
        usage = paths.path("usage")
        if usage is not None and usage.is_file():
            rows += [
                "## Usage",
                "",
                f"`usage/{usage.name}`:",
                "",
                "```python",
                usage.read_text(encoding="utf-8").rstrip(),
                "```",
                "",
            ]
        layout = entry.record.layout
        if layout is not None and paths.root is not None:
            asset = read_block_layout(paths.root / layout)
            rows += [
                "## Layout",
                "",
                f"`{layout}`; evidence `{asset.evidence}`.",
                "",
                "| local part | footprint |",
                "|---|---|",
            ]
            rows += [f"| `{name}` | `{part.footprint}` |" for name, part in sorted(asset.parts.items())]
            rows += [
                "",
                "Coordinates and copper are authored by `tools/blocks/starter_layouts.py` and",
                "captured through the CLI. No GUI placement or human layout review is claimed.",
                "The containing board routes the connectors and fills any return zone.",
                "",
            ]
        if entry.id.endswith(":protected_input"):
            rows += [
                "The `Example:IllustrativeTVS` usage record is `UNVERIFIED`; every electrical",
                "number is illustrative. Its operating voltage is the stand-off limit; the surge",
                "clamp is a separate required input. Pair `inject_max` with `hold`; the held",
                "voltage is also judged against `abs_max`. Overlapping ranges are `unsure`,",
                "so a 1 kΩ example does not pass the 5 mA requirement.",
                "",
            ]
        if entry.id.endswith(":led_indicator"):
            rows += [
                "No LED electrical default is shipped. An LED device's `operating` voltage",
                "states its forward-voltage range, with an `abs_max` current rating, or pass",
                "`vf` and `led_current_max` explicitly. Colour affects value text only.",
                "",
            ]
        found[entry.id] = "\n".join(rows)
    return found


def pages(
    records: Sequence[BlockRecord], titles: Mapping[str, str], sections: Mapping[str, str] | None = None
) -> dict[str, str]:
    """POSIX path below the repository → page text: one page per block and the index."""
    out: dict[str, str] = {}
    rows = ["# Shipped blocks", "", "Generated by `tools/gen_block_docs.py` from the block records.", ""]
    listed = sorted(records, key=lambda record: record.id)
    if listed:
        rows += ["| block | version | category | summary |", "|---|---|---|---|"]
    else:
        rows.append("No block is shipped yet.")
    for record in listed:
        name = record.id.split(":", 1)[-1]
        out[(FOLDER / f"{name}.md").as_posix()] = page(record, titles=titles) + (sections or {}).get(
            record.id, ""
        )
        header = record.header
        version, category, summary = (
            (header.version, header.category, header.summary) if header is not None else ("", "", "")
        )
        rows.append(f"| [{record.id}]({name}.md) | {version} | {category} | {summary} |")
    rows += [
        "",
        "## Later",
        "",
        "Decoupling set, reverse-polarity protection, crystal with load capacitors,",
        "reset network, and connector with ESD protection. Each needs sourced relations",
        "and its own implementation and proofs.",
        "",
    ]
    out[(FOLDER / "index.md").as_posix()] = "\n".join(rows).rstrip() + "\n"
    return out


def differences(wanted: Mapping[str, str], root: Path = ROOT) -> list[str]:
    """The pages that differ from ``wanted``, are missing, or are left over in ``docs/blocks/``."""
    found: list[str] = []
    for path, text in sorted(wanted.items()):
        target = root / path
        if not target.is_file():
            found.append(f"{path}: missing; run `uv run python tools/gen_block_docs.py`")
        elif target.read_text(encoding="utf-8") != text:
            found.append(f"{path}: stale; run `uv run python tools/gen_block_docs.py`")
    folder = root / FOLDER
    for extra in sorted(folder.glob("*.md")) if folder.is_dir() else ():
        path = (FOLDER / extra.name).as_posix()
        if path not in wanted:
            found.append(f"{path}: no shipped block has this page; remove it")
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail on any difference; write nothing")
    args = parser.parse_args(argv)
    wanted = pages(shipped_records(), source_titles(), details())
    if args.check:
        problems = differences(wanted)
        for problem in problems:
            print(problem, file=sys.stderr)
        return 1 if problems else 0
    (ROOT / FOLDER).mkdir(parents=True, exist_ok=True)
    for path, text in wanted.items():
        (ROOT / path).write_text(text, encoding="utf-8", newline="\n")
    for problem in differences(wanted):
        print(problem, file=sys.stderr)
    print(f"wrote {len(wanted)} pages under {FOLDER.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
