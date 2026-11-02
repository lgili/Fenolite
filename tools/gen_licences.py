# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Generate the dependency licence inventory from the lock and exact installed metadata."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import re
import sys
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "docs/licences.md"
COPYLEFT = re.compile(r"\b(?:A?GPL|LGPL)(?:\b|[- ])|GNU.*?General Public", re.IGNORECASE)
MPL = re.compile(r"\bMPL(?:\b|-)|Mozilla Public License", re.IGNORECASE)
ALIASES = {
    "Apache 2.0": "Apache-2.0",
    "Apache Software License": "Apache-2.0",
    "BSD 3-Clause": "BSD-3-Clause",
    "3-Clause BSD License": "BSD-3-Clause",
    "MIT License": "MIT",
}


def normalized(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


@dataclass(frozen=True)
class Metadata:
    licence: str
    field: str
    copyleft: bool = False
    mpl: bool = False


@dataclass(frozen=True)
class Package:
    name: str
    version: str
    metadata: Metadata | None


Inventory = dict[str, tuple[Package, ...]]


def environment() -> dict[tuple[str, str], Metadata]:
    """Read self-declared metadata without importing any dependency's code."""
    found: dict[tuple[str, str], Metadata] = {}
    for distribution in importlib.metadata.distributions():
        data = distribution.metadata
        names = data.get_all("Name", [])
        name = names[0] if names else ""
        if not name:
            continue
        expressions = data.get_all("License-Expression", [])
        licences = data.get_all("License", [])
        expression = expressions[0].strip() if expressions else ""
        legacy = licences[0].strip() if licences else ""
        classifiers = [
            value.removeprefix("License :: ")
            for value in data.get_all("Classifier", [])
            if value.startswith("License :: ")
        ]
        raw = expression or legacy
        field = "License-Expression" if expression else "License"
        declarations = expression or legacy or "\n".join(classifiers)
        if not raw:
            raw = "; ".join(classifiers) or "not stated"
            field = "Classifier" if classifiers else "no licence field"
        if len(raw) > 160 or "\n" in raw:
            digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
            field += f" text sha256:{digest}"
            raw = "; ".join(classifiers) or "licence text (see metadata digest)"
        raw = ALIASES.get(raw, raw)
        found[(normalized(name), distribution.version)] = Metadata(
            raw, field, bool(COPYLEFT.search(declarations)), bool(MPL.search(declarations))
        )
    return found


def inventory(lock: Mapping[str, Any], installed: Mapping[tuple[str, str], Metadata]) -> Inventory:
    """Resolve all universal-lock branches, including dependency-requested extras."""
    packages = lock.get("package", [])
    project = next(package for package in packages if package.get("name") == "fenolite")
    by_name: dict[str, list[Mapping[str, Any]]] = {}
    for package in packages:
        if package is not project:
            by_name.setdefault(normalized(package["name"]), []).append(package)

    def closure(roots: Sequence[Mapping[str, Any]]) -> tuple[Package, ...]:
        pending = list(roots)
        visited: set[tuple[str, str, tuple[str, ...]]] = set()
        selected: dict[tuple[str, str], Package] = {}
        while pending:
            edge = pending.pop()
            name = normalized(edge["name"])
            matches = [
                package
                for package in by_name.get(name, ())
                if "version" not in edge or package.get("version") == edge["version"]
            ]
            if not matches:
                raise ValueError(f"dependency {name!r} has no matching locked package")
            extras = tuple(sorted(edge.get("extra", ())))
            for package in matches:
                version = str(package["version"])
                key = (name, version, extras)
                if key in visited:
                    continue
                visited.add(key)
                selected[(name, version)] = Package(name, version, installed.get((name, version)))
                pending.extend(package.get("dependencies", ()))
                optional = package.get("optional-dependencies", {})
                for extra in extras:
                    pending.extend(optional.get(extra, ()))
        return tuple(selected[key] for key in sorted(selected))

    runtime = list(project.get("dependencies", ()))
    found = {"runtime": closure(runtime)}
    for extra, roots in sorted(project.get("optional-dependencies", {}).items()):
        found[extra] = closure([*runtime, *roots])
    return found


def copyleft_problems(found: Inventory) -> list[str]:
    problems: list[str] = []
    for extra, packages in found.items():
        if extra == "dev":
            continue
        for package in packages:
            metadata = package.metadata
            if metadata is not None and (metadata.copyleft or metadata.mpl):
                problems.append(
                    f"{extra}: {package.name} {package.version}: {metadata.licence}; "
                    "copyleft tools require a process boundary"
                )
    return problems


def _cell(value: str) -> str:
    return " ".join(value.split()).replace("|", "\\|").replace("`", "'")


def page_copyleft_problems(text: str) -> list[str]:
    """Check the committed inventory even in an environment without the optional dependencies."""
    extra = ""
    problems: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            extra = line.removeprefix("## ").strip()
        elif line.startswith("| ") and not line.startswith("| Package |"):
            cells = line.removeprefix("| ").removesuffix(" |").split(" | ")
            if len(cells) != 4 or not extra:
                raise ValueError("invalid licence inventory table row")
            name, version, licence, source = cells
            if extra != "dev" and (COPYLEFT.search(licence) or MPL.search(licence)):
                problems.append(f"{extra}: {name} {version}: {licence} ({source})")
    return problems


def render(found: Inventory) -> str:
    lines = [
        "# Dependency licence inventory",
        "",
        "Generated by `tools/gen_licences.py` from `uv.lock` and exact installed distribution metadata.",
        "Regenerate with `uv run --all-extras python tools/gen_licences.py`; use `--check` to detect drift.",
        "",
        "This records self-declared metadata, not a legal opinion. S-1180 defines the metadata fields;",
        "S-1181 describes the universal lock. All locked platform/interpreter branches are listed;",
        "an absent or different installed version is marked **not inspected**. Long legacy licence",
        "texts are represented by a digest and classifier rather than copied here. Short unambiguous",
        "legacy spellings are normalized. No dependency module is imported by this inventory.",
        "",
        "GPL, AGPL and LGPL software stays behind a process boundary. Imported extras reject it;",
        "MPL-2.0 is permitted only in development tools. An uninspected row is no licence approval.",
    ]
    for extra, packages in found.items():
        lines.extend(("", f"## {extra}", ""))
        if not packages:
            lines.append("No dependencies.")
            continue
        lines.extend(("| Package | Locked version | Declared licence | Metadata |", "|---|---|---|---|"))
        for package in packages:
            metadata = package.metadata
            licence = metadata.licence if metadata is not None else "not inspected"
            source = metadata.field if metadata is not None else "not installed at this locked version"
            values = (package.name, package.version, licence, source)
            lines.append("| " + " | ".join(_cell(value) for value in values) + " |")
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    with (ROOT / "uv.lock").open("rb") as source:
        found = inventory(tomllib.load(source), environment())
    problems = copyleft_problems(found)
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    content = render(found)
    if args.check:
        if not PAGE.is_file() or PAGE.read_bytes() != content.encode("utf-8"):
            print(
                "docs/licences.md is stale; run uv run --all-extras python tools/gen_licences.py",
                file=sys.stderr,
            )
            return 1
    else:
        PAGE.write_bytes(content.encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
