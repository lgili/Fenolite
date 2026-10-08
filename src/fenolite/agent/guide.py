# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Reader of the packaged agent guide (capability agent-guide, "Packaged agent guide", "Starter
projects" and "Agent folders table").

The files are data of this package: ``skill/SKILL.md`` (the start page), ``skill/references/<topic>.md``
(one page per topic) and ``starters/<name>/`` (``starter.toml`` and the templates of a first project).
Everything is read through ``importlib.resources``; this module imports the standard library only, runs
no program and opens no connection.
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from importlib import resources
from importlib.resources.abc import Traversable
from types import MappingProxyType

SKILL_NAME = "fenolite"
"""The ``name`` of the skill's front matter and the folder that ``fenolite skill install`` writes."""

START = "start"
"""The topic of the start page, which is the body of ``SKILL.md``."""

AGENT_DIRS: Mapping[str, str] = MappingProxyType(
    {
        # One row per agent: its name and the project-relative folder it reads skills from. A row is
        # added only together with the public page that documents that folder, registered in
        # docs/evidence/sources.md and named by its id in a comment on the row's own line.
        # `fenolite skill install --dir DIR` serves every other agent.
        "claude-code": ".claude/skills",  # S-0617
    }
)
"""Agent name → the project-relative folder that agent reads skills from."""

AGENTS_BEGIN = "<!-- fenolite:begin -->"
AGENTS_END = "<!-- fenolite:end -->"
AGENTS_SECTION = (
    "## Fenolite\n"
    "\n"
    "This project uses Fenolite, a command line that builds, checks and exports circuit boards.\n"
    "\n"
    "- Before a task about a circuit board, run `fenolite guide start --text` and follow that page.\n"
    "- `fenolite capabilities --brief --json` says what is installed here: commands, tools, routers.\n"
    "- `fenolite guide --text` lists the other pages; they always belong to the installed version.\n"
)
"""The pointer section that ``fenolite skill install --agents-md`` keeps between the two marker lines."""

TOPIC = re.compile(r"[a-z0-9-]+")
SUMMARY_MAX = 160
SKILL_KEYS = ("name", "description")
PAGE_KEYS = ("topic", "title", "summary")
STARTER_HEADER = "# SPDX-License-Identifier: CC0-1.0"
TEMPLATE_SUFFIX = ".tmpl"
NAME_TOKEN = "@NAME@"
_HEADING = re.compile(r"^# +(.+?)\s*$", re.MULTILINE)
FENCE = "```"
BLOCK_TAGS = ("fenolite-loop", "fenolite-cmd", "fenolite-design", "fenolite-recipe", "json", "text")
"""The tags a fenced block of a page may carry. The first four are run by the suites; ``json`` and
``text`` hold samples of output."""
PAGES_BEGIN = "<!-- pages:begin -->"
PAGES_END = "<!-- pages:end -->"
"""The two marker lines of the start page; ``tools/gen_agent_guide.py`` writes the index between them."""
GENERATED_TOPICS = ("commands", "dsl-reference")
"""The topics that ``tools/gen_agent_guide.py`` writes; every other reference page is written by hand."""

_BUILD_CALLS = "the build calls it; a script never does"
_CONSTANT = "a constant that a script has no use for"
_RETURNED = "a record that a call of the script returns; a script never names it"
_ERROR = "the error a wrong call raises; the build reports it, a script does not catch it"
DSL_NOT_TAUGHT: Mapping[str, str] = MappingProxyType(
    {
        "to_model": _BUILD_CALLS,
        "placements": _BUILD_CALLS,
        "heights": _BUILD_CALLS,
        "copper": _BUILD_CALLS,
        "meanders": _BUILD_CALLS,
        "fields": _BUILD_CALLS,
        "moves": _BUILD_CALLS,
        "module_moves": _BUILD_CALLS,
        "net_moves": _BUILD_CALLS,
        "planes": _BUILD_CALLS,
        "pad_zones": _BUILD_CALLS,
        "drawing_sheet_source": _BUILD_CALLS,
        "stackup_locked": _BUILD_CALLS,
        "outline_locked": _BUILD_CALLS,
        "via_protection_locked": _BUILD_CALLS,
        "KEYS": _CONSTANT,
        "DSL_BACKEND": _CONSTANT,
        "BOARD_ORIGIN": _CONSTANT,
        "CopperIntent": _RETURNED,
        "StitchIntent": _RETURNED,
        "TrackIntent": _RETURNED,
        "ViaIntent": _RETURNED,
        "FieldRequest": _RETURNED,
        "PadZoneRequest": _RETURNED,
        "ArcStep": _RETURNED,
        "ViaStep": _RETURNED,
        "PadEnd": _RETURNED,
        "Anchor": _RETURNED,
        "AnchorRef": _RETURNED,
        "PadRef": _RETURNED,
        "Placement": _RETURNED,
        "Length": _RETURNED,
        "Quantity": _RETURNED,
        "RuleArea": _RETURNED,
        "MeanderIntent": _RETURNED,
        "Trace": _RETURNED,
        "DslError": _ERROR,
    }
)
"""The names of ``fenolite.dsl.__all__`` that no design block of the guide uses, each with the reason.
Every other name must appear in a ``fenolite-design`` block (capability agent-guide, "Guide covers the
public surface")."""


class GuideError(ValueError):
    """A file of the packaged guide is malformed; the message starts with the file's name."""


@dataclass(frozen=True, slots=True)
class Page:
    """One page of the guide. ``text`` is the file without its front matter."""

    topic: str
    title: str
    summary: str
    text: str


@dataclass(frozen=True, slots=True)
class Block:
    """One fenced block of a page. ``tag`` is the first word after the opening fence and ``argument``
    the rest of that line; ``lines`` are the lines between the fences, as written; ``line_number`` is
    the line of the opening fence in ``Page.text``, from 1."""

    tag: str
    argument: str
    lines: tuple[str, ...]
    line_number: int


def blocks(page: Page) -> tuple[Block, ...]:
    """Every fenced block of ``page``, in order. A fence is a line whose first three characters, after
    its indentation, are backquotes; a block without a tag has the tag ``""``. A fence that is never
    closed raises :class:`GuideError` naming the topic and the line."""
    found: list[Block] = []
    opened: tuple[int, str, str] | None = None
    body: list[str] = []
    for number, line in enumerate(page.text.split("\n"), start=1):
        stripped = line.strip()
        if not stripped.startswith(FENCE):
            if opened is not None:
                body.append(line)
            continue
        if opened is None:
            tag, _, argument = stripped[len(FENCE) :].strip().partition(" ")
            opened = (number, tag, argument.strip())
            body = []
        else:
            found.append(Block(opened[1], opened[2], tuple(body), opened[0]))
            opened = None
    if opened is not None:
        raise GuideError(f"{page.topic}: the block opened at line {opened[0]} is never closed")
    return tuple(found)


@dataclass(frozen=True, slots=True)
class SkillFile:
    """One file of the skill folder: ``path`` is relative to it, in POSIX form."""

    path: str
    data: bytes


@dataclass(frozen=True, slots=True)
class Starter:
    """A starter project: ``files`` are the names of the files it writes."""

    name: str
    summary: str
    files: tuple[str, ...]


def _root(root: Traversable | None) -> Traversable:
    return resources.files("fenolite.agent") if root is None else root


def _text(node: Traversable, name: str) -> str:
    try:
        return node.read_bytes().decode("utf-8").replace("\r\n", "\n")
    except UnicodeDecodeError as exc:
        raise GuideError(f"{name}: not UTF-8") from exc


def front_matter(text: str, name: str, keys: tuple[str, ...]) -> tuple[dict[str, str], str]:
    """The ``key: value`` lines between the two ``---`` lines at the top of ``text``, and the rest.
    The keys must be exactly ``keys``; :class:`GuideError` names ``name`` otherwise."""
    lines = text.split("\n")
    if lines[0] != "---" or "---" not in lines[1:]:
        raise GuideError(f"{name}: no front matter between two '---' lines")
    end = lines.index("---", 1)
    found: dict[str, str] = {}
    for line in lines[1:end]:
        key, colon, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if not colon or not key or not value:
            raise GuideError(f"{name}: front matter line {line!r} is not 'key: value'")
        if key in found:
            raise GuideError(f"{name}: front matter key {key!r} is given twice")
        found[key] = value
    for key in keys:
        if key not in found:
            raise GuideError(f"{name}: front matter lacks {key!r}")
    for key in found:
        if key not in keys:
            raise GuideError(f"{name}: unknown front matter key {key!r}")
    body = "\n".join(lines[end + 1 :])
    return found, body.lstrip("\n")


def _start(root: Traversable) -> Page:
    name = "skill/SKILL.md"
    node = root.joinpath("skill", "SKILL.md")
    if not node.is_file():
        raise GuideError(f"{name}: missing")
    front, body = front_matter(_text(node, name), name, SKILL_KEYS)
    if front["name"] != SKILL_NAME:
        raise GuideError(f"{name}: name is {front['name']!r}, expected {SKILL_NAME!r}")
    heading = _HEADING.search(body)
    if heading is None:
        raise GuideError(f"{name}: no first-level heading")
    return Page(START, heading.group(1), front["description"], body)


def _reference(node: Traversable) -> Page:
    name = f"skill/references/{node.name}"
    front, body = front_matter(_text(node, name), name, PAGE_KEYS)
    topic = front["topic"]
    if TOPIC.fullmatch(topic) is None:
        raise GuideError(f"{name}: topic {topic!r} is not of [a-z0-9-]+")
    if topic == START:
        raise GuideError(f"{name}: the topic {START!r} belongs to SKILL.md")
    if topic != node.name[: -len(".md")]:
        raise GuideError(f"{name}: topic {topic!r} differs from the file name")
    if len(front["summary"]) > SUMMARY_MAX:
        raise GuideError(f"{name}: summary is longer than {SUMMARY_MAX} characters")
    return Page(topic, front["title"], front["summary"], body)


def pages(root: Traversable | None = None) -> tuple[Page, ...]:
    """The page ``start`` first, then every page of ``skill/references/`` sorted by topic. ``root``
    replaces the packaged folder (the tests read copies with it)."""
    base = _root(root)
    found = [_start(base)]
    folder = base.joinpath("skill", "references")
    others: dict[str, Page] = {}
    if folder.is_dir():
        for node in sorted(folder.iterdir(), key=lambda n: n.name):
            if not node.is_file() or not node.name.endswith(".md"):
                continue
            page_ = _reference(node)
            if page_.topic.lower() in {topic.lower() for topic in others}:
                raise GuideError(f"skill/references/{node.name}: duplicate topic {page_.topic!r}")
            others[page_.topic] = page_
    return (*found, *(others[topic] for topic in sorted(others)))


def page(topic: str, root: Traversable | None = None) -> Page:
    """The page of ``topic``; :class:`KeyError` for an unknown one."""
    for found in pages(root):
        if found.topic == topic:
            return found
    raise KeyError(topic)


def _walk(node: Traversable, prefix: str) -> list[SkillFile]:
    files: list[SkillFile] = []
    for child in node.iterdir():
        path = f"{prefix}{child.name}"
        if child.is_dir():
            if child.name != "__pycache__":
                files += _walk(child, path + "/")
        elif child.is_file():
            files.append(SkillFile(path, child.read_bytes()))
    return files


def skill_files(root: Traversable | None = None) -> tuple[SkillFile, ...]:
    """Every file of ``skill/`` with its bytes, sorted by path."""
    return tuple(sorted(_walk(_root(root).joinpath("skill"), ""), key=lambda f: f.path))


def _templates(folder: Traversable, name: str) -> dict[str, str]:
    """Output file name → template text of the starter ``name``."""
    found: dict[str, str] = {}
    for node in sorted(folder.iterdir(), key=lambda n: n.name):
        if not node.is_file() or not node.name.endswith(TEMPLATE_SUFFIX):
            continue
        where = f"starters/{name}/{node.name}"
        text = _text(node, where)
        if text.split("\n", 1)[0] != STARTER_HEADER:
            raise GuideError(f"{where}: the first line is not {STARTER_HEADER!r}")
        found[node.name[: -len(TEMPLATE_SUFFIX)]] = text
    return found


def _starter(folder: Traversable) -> tuple[Starter, dict[str, str]]:
    name = folder.name
    where = f"starters/{name}/starter.toml"
    node = folder.joinpath("starter.toml")
    if not node.is_file():
        raise GuideError(f"{where}: missing")
    try:
        table = tomllib.loads(_text(node, where))
    except tomllib.TOMLDecodeError as exc:
        raise GuideError(f"{where}: {exc}") from exc
    summary = table.get("summary")
    if set(table) != {"summary"} or not isinstance(summary, str) or not summary or "\n" in summary:
        raise GuideError(f"{where}: expected exactly one key, 'summary', a one-line string")
    templates = _templates(folder, name)
    if "design.py" not in templates:
        raise GuideError(f"starters/{name}/design.py{TEMPLATE_SUFFIX}: missing")
    return Starter(name, summary, tuple(sorted(templates))), templates


def _starters(root: Traversable | None) -> dict[str, tuple[Starter, dict[str, str]]]:
    folder = _root(root).joinpath("starters")
    found: dict[str, tuple[Starter, dict[str, str]]] = {}
    if folder.is_dir():
        for node in sorted(folder.iterdir(), key=lambda n: n.name):
            if node.is_dir() and node.name != "__pycache__":
                found[node.name] = _starter(node)
    return found


def starters(root: Traversable | None = None) -> tuple[Starter, ...]:
    """The starter projects, sorted by name."""
    return tuple(starter for starter, _ in _starters(root).values())


def render_starter(name: str, design_name: str, root: Traversable | None = None) -> Mapping[str, bytes]:
    """The files of the starter ``name`` (file name → bytes) with every ``@NAME@`` replaced by
    ``design_name``; :class:`KeyError` for an unknown starter."""
    _, templates = _starters(root)[name]
    return MappingProxyType(
        {file: text.replace(NAME_TOKEN, design_name).encode("utf-8") for file, text in templates.items()}
    )


__all__ = [
    "AGENTS_BEGIN",
    "AGENTS_END",
    "AGENTS_SECTION",
    "AGENT_DIRS",
    "BLOCK_TAGS",
    "DSL_NOT_TAUGHT",
    "GENERATED_TOPICS",
    "PAGES_BEGIN",
    "PAGES_END",
    "SKILL_NAME",
    "START",
    "Block",
    "GuideError",
    "Page",
    "SkillFile",
    "Starter",
    "blocks",
    "front_matter",
    "page",
    "pages",
    "render_starter",
    "skill_files",
    "starters",
]
