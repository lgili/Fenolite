# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Write the contract surface ``docs/cli-surface.json`` (capability cli-contract, "Contract surface";
change c0216).

    uv run python tools/gen_cli_surface.py                       # (re)write docs/cli-surface.json
    uv run python tools/gen_cli_surface.py --check               # exit 1 when the file would change
    uv run python tools/gen_cli_surface.py --review --out FILE   # the list for the pre-freeze review

The review names, for each option of each visible command, whether a test, the command's examples, the
agent guide and ``docs/cli-contract.md`` name it; each hidden command; and each issue code that no test
names. It is written for the maintainer, outside the repository: nothing is renamed or dropped without his
answer.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "cli-surface.json"
GUIDE = ROOT / "src" / "fenolite" / "agent" / "skill"
CONTRACT = ROOT / "docs" / "cli-contract.md"
TESTS = ROOT / "tests"


def generate() -> str:
    """The text of ``docs/cli-surface.json`` for the code as it is."""
    from fenolite.cli.api import discover
    from fenolite.cli.surface import cli_surface

    return cli_surface(discover()).dumps()


def check(text: str) -> list[str]:
    """What differs between the committed file and ``text``, one line per change; empty when equal."""
    import json

    from fenolite.cli.surface import Surface, surface_changes

    if not OUT.exists():
        return [f"{OUT.relative_to(ROOT).as_posix()} is missing"]
    committed = OUT.read_text(encoding="utf-8")
    if committed == text:
        return []
    before = Surface.from_json(json.loads(committed))
    after = Surface.from_json(json.loads(text))
    lines = [str(change) for change in surface_changes(before, after)]
    return lines or ["the file differs only in its layout"]


# ------------------------------------------------------------------------------------------------ review


@dataclass(frozen=True)
class _Texts:
    tests: Mapping[str, str]
    guide: str
    contract: str


def _read(paths: Iterable[Path]) -> dict[str, str]:
    return {
        path.relative_to(ROOT).as_posix(): path.read_text(encoding="utf-8", errors="replace")
        for path in paths
    }


def _texts() -> _Texts:
    tests = _read(sorted(p for p in TESTS.rglob("*.py") if p.is_file()))
    guide = "\n".join(_read(sorted(GUIDE.rglob("*.md"))).values())
    return _Texts(tests, guide, CONTRACT.read_text(encoding="utf-8"))


def _flag(flag: str) -> re.Pattern[str]:
    return re.compile(re.escape(flag) + r"(?![A-Za-z0-9-])")


def _command_named(name: str) -> re.Pattern[str]:
    return re.compile(r"[\"'`]" + re.escape(name) + r"[\"'`\s]")


def _option_rows(
    commands: Mapping[str, Any], examples: Mapping[str, Sequence[str]], texts: _Texts
) -> list[tuple[str, str, bool, bool, bool, bool]]:
    rows: list[tuple[str, str, bool, bool, bool, bool]] = []
    for name, entry in sorted(commands.items()):
        if name == "*":
            continue
        files = [text for text in texts.tests.values() if _command_named(name).search(text)]
        for flag in sorted(entry["options"]):
            if flag.startswith("<"):
                continue
            pattern = _flag(flag)
            rows.append(
                (
                    name,
                    flag,
                    any(pattern.search(text) for text in files),
                    flag in examples.get(name, ()),
                    bool(pattern.search(texts.guide)),
                    bool(pattern.search(texts.contract)),
                )
            )
    return rows


def _untested_codes(codes: Iterable[str], texts: _Texts) -> list[str]:
    corpus = "\n".join(texts.tests.values())
    missing: list[str] = []
    for code in sorted(codes):
        needle = code[:-2] + "." if code.endswith(".*") else code
        if needle not in corpus:
            missing.append(code)
    return missing


def _shape(option: Mapping[str, Any]) -> str:
    choices = option.get("choices")
    return str(option["type"]) + (f" {{{','.join(sorted(choices))}}}" if choices else "")


def _differing(commands: Mapping[str, Any]) -> list[tuple[str, str]]:
    shapes: dict[str, dict[str, list[str]]] = {}
    for name, entry in sorted(commands.items()):
        for flag, option in entry["options"].items():
            if not flag.startswith("<"):
                shapes.setdefault(flag, {}).setdefault(_shape(option), []).append(name)
    return [
        (flag, "; ".join(f"{shape} ({', '.join(names)})" for shape, names in sorted(found.items())))
        for flag, found in sorted(shapes.items())
        if len(found) > 1
    ]


def _outside_feature(commands: Mapping[str, Any]) -> list[tuple[str, str]]:
    prefixes = {
        f"--{choice}-"
        for entry in commands.values()
        for option in entry["options"].values()
        for choice in option.get("experimental_choices", ())
    }
    return [
        (name, flag)
        for name, entry in sorted(commands.items())
        for flag, option in sorted(entry["options"].items())
        if any(flag.startswith(prefix) for prefix in prefixes) and not option["experimental"]
    ]


def review() -> str:
    """The Markdown list of the pre-freeze review (task 1.3 of c0216)."""
    import json

    from fenolite.cli.api import discover
    from fenolite.cli.main import MUTATION_FLAGS

    every = discover()
    surface = json.loads(generate())
    texts = _texts()
    examples = {
        name: (*command.example_args, *(command.mutation_example_args or ()))
        for name, command in every.items()
    }
    rows = [row for row in _option_rows(surface["commands"], examples, texts) if row[1] not in MUTATION_FLAGS]
    unused = [row for row in rows if not any(row[2:])]
    thin = [row for row in rows if any(row[2:]) and not row[2]]
    hidden = sorted(name for name, command in every.items() if command.hidden)
    issue_codes: Mapping[str, Mapping[str, Any]] = surface["issue_codes"]
    untested = _untested_codes(issue_codes, texts)
    differing = _differing(surface["commands"])
    outside = _outside_feature(surface["commands"])
    lines = [
        "# Pre-freeze review of the contract surface (c0216, task 1.3)",
        "",
        f"Generated from {len(surface['commands']) - 1} visible commands, {len(rows)} options (the global "
        f"options and {', '.join(MUTATION_FLAGS)} left out), {len(surface['fen_codes'])} FEN codes and "
        f"{len(issue_codes)} issue codes.",
        "",
        "A name counts as used by a test when a file under `tests/` names both the command (quoted)",
        "and the flag; the guide is `src/fenolite/agent/skill/`; the contract is `docs/cli-contract.md`.",
        "For each item answer keep, rename (the old name stays as deprecated until 2.0) or drop.",
        "",
        f"## 1. Options named nowhere ({len(unused)})",
        "",
        "Neither a test, an example, the guide nor the contract names them.",
        "",
        *[f"- `{name} {flag}`" for name, flag, *_ in unused],
        "",
        f"## 2. Options without a test ({len(thin)})",
        "",
        "Documented or in an example, but no test names them with their command.",
        "",
        "| option | example | guide | contract |",
        "|---|---|---|---|",
        *[
            f"| `{name} {flag}` | {'yes' if ex else '-'} | {'yes' if gd else '-'} | {'yes' if ct else '-'} |"
            for name, flag, _, ex, gd, ct in thin
        ],
        "",
        f"## 3. One flag, several shapes ({len(differing)})",
        "",
        "The same flag takes another type or other choices on another command.",
        "",
        *[f"- `{flag}`: {shapes}" for flag, shapes in differing],
        "",
        f"## 4. Experimental-format options outside the experimental feature ({len(outside)})",
        "",
        "Flags named after an experimental choice (`--altium-*`) on a command whose options are not marked",
        "experimental: they freeze with 1.0 unless marked.",
        "",
        *[f"- `{name} {flag}`" for name, flag in outside],
        "",
        f"## 5. Hidden commands ({len(hidden)})",
        "",
        "Out of the contract (the maintainer's answer of 2026-10-27); listed to confirm.",
        "",
        *[f"- `{name}`" for name in hidden],
        "",
        f"## 6. Issue codes no test names ({len(untested)})",
        "",
        "| code | severities | experimental |",
        "|---|---|---|",
        *[
            f"| `{code}` | {', '.join(issue_codes[code]['severities'])} | "
            f"{'yes' if issue_codes[code]['experimental'] else '-'} |"
            for code in untested
        ],
        "",
        "## 7. Every option",
        "",
        "| option | test | example | guide | contract |",
        "|---|---|---|---|---|",
        *[
            f"| `{name} {flag}` | {'yes' if t else '-'} | {'yes' if ex else '-'} | {'yes' if gd else '-'} | "
            f"{'yes' if ct else '-'} |"
            for name, flag, t, ex, gd, ct in rows
        ],
        "",
    ]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--check", action="store_true", help="exit 1 when docs/cli-surface.json would change")
    parser.add_argument("--review", action="store_true", help="write the list for the pre-freeze review")
    parser.add_argument("--out", type=Path, help="with --review: the file to write (outside the repository)")
    args = parser.parse_args(argv)
    if args.review:
        if args.out is None:
            parser.error("--review needs --out FILE")
        args.out.write_text(review(), encoding="utf-8", newline="\n")
        print(f"wrote {args.out}")
        return 0
    text = generate()
    if args.check:
        changes = check(text)
        if changes:
            print("docs/cli-surface.json is stale: run tools/gen_cli_surface.py", file=sys.stderr)
            for line in changes:
                print(f"  {line}", file=sys.stderr)
            return 1
        return 0
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
