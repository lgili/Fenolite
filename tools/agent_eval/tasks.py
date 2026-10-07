# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The tasks of the agent evaluation: a folder per task, read and checked here (change c0081).

A task is ``tasks/<name>/`` with ``task.toml``, an optional ``files/`` (copied into the work folder
before the agent starts) and ``solution/`` (``commands.txt`` and an optional ``files/``). ``load`` reads
one and refuses a malformed one with a ``ValueError`` that names the task and the key; ``names`` lists
them. Standard library only: the loader needs no Fenolite.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

TASKS_DIR = Path(__file__).resolve().parent / "tasks"
MAX_WORDS = 300
MAX_MINUTES = 60
COPPER_COUNTS = (2, 4, 6, 8)
UNITS_NM = {"nm": Fraction(1), "um": Fraction(1000), "mm": Fraction(1_000_000), "mil": Fraction(25_400)}
"""Nanometres per unit of a length of ``max_size``."""

_LENGTH = re.compile(r"^([0-9]+(?:\.[0-9]+)?)\s*(nm|um|mm|mil)$")
_REF_PIN = re.compile(r"^([A-Za-z][A-Za-z0-9_.+]*)-([A-Za-z0-9_.+~]+)$")
_NAME = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_OPTION = re.compile(r"(?:^|\s)--[A-Za-z]")
_GLOB = re.compile(r"[*?\[]")
_TOP = {"title", "prompt", "prepare", "budget", "expect"}
_REQUIRED_TOP = ("title", "prompt", "budget", "expect")
_EXPECT = ("project", "copper_layers", "max_size", "outputs", "nets")


@dataclass(frozen=True)
class Expect:
    """What a correct result holds."""

    project: str
    """The folder of the built project, relative to the work folder."""
    copper_layers: int
    max_size: tuple[int, int]
    """The largest board, two lengths in nanometres; the board may lie either way."""
    outputs: tuple[str, ...]
    """File patterns relative to the work folder; each must match at least one file."""
    nets: dict[str, tuple[str, ...]] = field(default_factory=lambda: {})
    """A label (never compared) to the ``REF-PIN`` of one net."""

    def refs(self) -> tuple[str, ...]:
        """The references the expected nets name, sorted."""
        return tuple(sorted({split_ref_pin(entry)[0] for group in self.nets.values() for entry in group}))


@dataclass(frozen=True)
class Task:
    """One task, as its folder states it."""

    name: str
    title: str
    prompt: str
    minutes: int
    expect: Expect
    folder: Path
    prepare: tuple[str, ...] = ()
    """``fenolite`` command lines that build the starting state, run before the agent starts."""

    @property
    def files(self) -> Path:
        """The folder copied into the work folder before the agent starts (it may not exist)."""
        return self.folder / "files"

    @property
    def solution_files(self) -> Path:
        """The files the reference solution writes (the folder may not exist)."""
        return self.folder / "solution" / "files"

    def commands(self) -> tuple[str, ...]:
        """The command lines of the reference solution, in order."""
        return read_lines(self.folder / "solution" / "commands.txt", self.name, "solution/commands.txt")


def split_ref_pin(entry: str) -> tuple[str, str]:
    """``("R1", "2")`` for ``"R1-2"``; ``ValueError`` for anything else."""
    match = _REF_PIN.match(entry)
    if match is None:
        raise ValueError(f"{entry!r} is not REF-PIN")
    return match.group(1), match.group(2)


def length_nm(text: object) -> int:
    """A length with a unit (``"40mm"``) as whole nanometres; ``ValueError`` without a unit."""
    match = _LENGTH.match(text) if isinstance(text, str) else None
    if match is None:
        raise ValueError(f"{text!r} is not a length with a unit (nm, um, mm or mil)")
    value = Fraction(match.group(1)) * UNITS_NM[match.group(2)]
    if value.denominator != 1 or value <= 0:
        raise ValueError(f"{text!r} is not a positive whole number of nanometres")
    return int(value)


def read_lines(path: Path, task: str, key: str) -> tuple[str, ...]:
    """The ``fenolite`` command lines of a file: blank lines and ``#`` lines are skipped."""
    if not path.is_file():
        raise ValueError(f"task {task}: {key} is missing")
    lines = tuple(
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    return _command_lines(lines, task, key)


def _command_lines(lines: tuple[str, ...], task: str, key: str) -> tuple[str, ...]:
    if not lines:
        raise ValueError(f"task {task}: {key} holds no command line")
    for line in lines:
        if line.split()[0] != "fenolite":
            raise ValueError(f"task {task}: {key}: {line!r} is not a fenolite command line")
    return lines


def _table(value: object, task: str, key: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"task {task}: {key} must be a table")
    return cast("dict[str, Any]", value)


def _keys(table: dict[str, Any], required: tuple[str, ...], allowed: set[str], task: str, where: str) -> None:
    prefix = f"{where}." if where else ""
    for key in required:
        if key not in table:
            raise ValueError(f"task {task}: the key {prefix}{key} is missing")
    for key in sorted(table):
        if key not in allowed:
            raise ValueError(f"task {task}: unknown key {prefix}{key}")


def _text(value: object, task: str, key: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"task {task}: {key} must be a non-empty text")
    return value


def _strings(value: object, task: str, key: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"task {task}: {key} must be a non-empty list of texts")
    items = cast("list[object]", value)
    return tuple(_text(item, task, key) for item in items)


def _relative(text: str, task: str, key: str) -> str:
    path = Path(text)
    if path.is_absolute() or text.startswith(("/", "\\")) or ".." in path.parts or ":" in text:
        raise ValueError(f"task {task}: {key} must be relative to the work folder, got {text!r}")
    return text


def output_folder(pattern: str) -> str:
    """The folder a pattern of ``expect.outputs`` names: its parts before the first wildcard."""
    parts: list[str] = []
    for part in pattern.split("/")[:-1]:
        if _GLOB.search(part):
            break
        parts.append(part)
    return "/".join(parts)


def _expect(table: dict[str, Any], task: str) -> Expect:
    _keys(table, _EXPECT, set(_EXPECT), task, "expect")
    project = _relative(_text(table["project"], task, "expect.project"), task, "expect.project")
    layers = table["copper_layers"]
    if isinstance(layers, bool) or layers not in COPPER_COUNTS:
        raise ValueError(f"task {task}: expect.copper_layers must be one of {COPPER_COUNTS}")
    size = table["max_size"]
    if not isinstance(size, list) or len(cast("list[object]", size)) != 2:
        raise ValueError(f"task {task}: expect.max_size must be two lengths with units")
    try:
        width, height = (length_nm(item) for item in cast("list[object]", size))
    except ValueError as error:
        raise ValueError(f"task {task}: expect.max_size: {error}") from None
    outputs = tuple(
        _relative(item, task, "expect.outputs") for item in _strings(table["outputs"], task, "expect.outputs")
    )
    raw = _table(table["nets"], task, "expect.nets")
    if not raw:
        raise ValueError(f"task {task}: expect.nets is empty")
    nets: dict[str, tuple[str, ...]] = {}
    seen: dict[str, str] = {}
    for label in raw:
        group = _strings(raw[label], task, f"expect.nets.{label}")
        for entry in group:
            try:
                split_ref_pin(entry)
            except ValueError as error:
                raise ValueError(f"task {task}: expect.nets.{label}: {error}") from None
            if entry in seen:
                raise ValueError(
                    f"task {task}: expect.nets lists {entry} in two nets ({seen[entry]} and {label})"
                    if seen[entry] != label
                    else f"task {task}: expect.nets.{label} lists {entry} twice"
                )
            seen[entry] = label
        nets[label] = group
    return Expect(project, int(layers), (width, height), outputs, nets)


def check_prompt(prompt: str, expect: Expect, task: str) -> None:
    """The rules of a prompt: its length, what it must name and what it must not hold."""
    words = len(prompt.split())
    if words > MAX_WORDS:
        raise ValueError(f"task {task}: prompt has {words} words, more than {MAX_WORDS}")
    if "fenolite" in prompt.lower():
        raise ValueError(f"task {task}: prompt holds the word 'fenolite'")
    if _OPTION.search(prompt):
        raise ValueError(f"task {task}: prompt holds a command line (an option that starts with --)")
    for ref in expect.refs():
        if re.search(rf"(?<![A-Za-z0-9_]){re.escape(ref)}(?![A-Za-z0-9_])", prompt) is None:
            raise ValueError(f"task {task}: prompt does not name the reference {ref} of expect.nets")
    for folder in (expect.project, *(output_folder(pattern) for pattern in expect.outputs)):
        if folder and folder not in prompt:
            raise ValueError(f"task {task}: prompt does not name the folder {folder}")


def load(name: str, root: Path | None = None) -> Task:
    """Read the task ``name`` under ``root`` (the tasks of the repository by default)."""
    if _NAME.match(name) is None:
        raise ValueError(f"task {name!r}: a task name is lower-case words joined by '-'")
    folder = (TASKS_DIR if root is None else root) / name
    path = folder / "task.toml"
    if not path.is_file():
        raise ValueError(f"task {name}: task.toml is missing")
    try:
        data: dict[str, Any] = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        raise ValueError(f"task {name}: task.toml is not valid TOML: {error}") from None
    _keys(data, _REQUIRED_TOP, _TOP, name, "")
    title = _text(data["title"], name, "title")
    prompt = _text(data["prompt"], name, "prompt").strip()
    budget = _table(data["budget"], name, "budget")
    _keys(budget, ("minutes",), {"minutes"}, name, "budget")
    minutes = budget["minutes"]
    if isinstance(minutes, bool) or not isinstance(minutes, int) or not 1 <= minutes <= MAX_MINUTES:
        raise ValueError(f"task {name}: budget.minutes must be a whole number from 1 to {MAX_MINUTES}")
    expect = _expect(_table(data["expect"], name, "expect"), name)
    check_prompt(prompt, expect, name)
    prepare: tuple[str, ...] = ()
    if "prepare" in data:
        prepare = _command_lines(_strings(data["prepare"], name, "prepare"), name, "prepare")
    task = Task(name, title, prompt, minutes, expect, folder, prepare)
    task.commands()
    return task


def names(root: Path | None = None) -> tuple[str, ...]:
    """The names of the tasks under ``root``, sorted."""
    folder = TASKS_DIR if root is None else root
    return tuple(sorted(path.parent.name for path in folder.glob("*/task.toml")))
