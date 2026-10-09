# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The pages of the agent guide stay true to the code (capability agent-guide: "Guide pages",
"Executable blocks", "Guide covers the public surface", "Generated guide pages" and "Page budgets and
writing rules").

Every fenced block of a page is proved here or in ``test_recipes.py``: a command line by the real
parser, a design script by a build with no tool, a recipe by a run. The lists that the checks compare
with (the command registry, ``fenolite.dsl.__all__``, the error registry, the reply of
``capabilities``) are read when the test runs, so a later change that adds to one of them fails here
until a page teaches it.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import io
import re
import shlex
import textwrap
import tokenize
from collections.abc import Iterable, Mapping
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from _sandbox import inside, run, starter_script

import fenolite.dsl
from fenolite.agent import guide
from fenolite.cli.api import Command, discover
from fenolite.cli.errors import REGISTRY, CliError
from fenolite.cli.main import build_parser

ROOT = Path(__file__).resolve().parents[3]
SKILL = ROOT / "src" / "fenolite" / "agent" / "skill"
WRITTEN = (
    "altium",
    "checks",
    "design-script",
    "fabrication",
    "files",
    "footprints",
    "parts",
    "placement",
    "recovery",
    "routing",
    "rules",
)
"""The eleven pages written by hand."""
GENERATED = guide.GENERATED_TOPICS
RUN_TAGS = ("fenolite-loop", "fenolite-cmd", "fenolite-recipe")
"""The tags whose lines are commands: a public command needs a line in one of them."""
WRITTEN_LINES, WRITTEN_BYTES, GENERATED_LINES, START_LINES, FOLDER_BYTES = 250, 12_000, 600, 200, 150_000
KICAD_TARGETS = ("9", "10")
LABELS = ("KICAD-VERIFIED", "ORACLE-VERIFIED", "CORPUS-VERIFIED", "ALTIUM-VERIFIED", "INFERRED", "UNVERIFIED")
RULE = "adds a tested line to a page of the agent guide"
"""The words by which ``AGENTS.md`` and ``CONTRIBUTING.md`` state the rule for new commands and names."""

HOME: Mapping[str, tuple[str, ...]] = {
    "design-script": ("init", "build", "sync", "template"),
    "parts": ("catalog",),
    "footprints": (),
    "placement": ("place", "pads", "neighbors", "region"),
    "routing": ("route", "fill", "net", "fetch"),
    "rules": ("analyze",),
    "checks": ("check", "ready", "explain", "netlist", "parity", "doctor", "capabilities"),
    "files": ("inspect", "diff", "equivalent", "roundtrip", "fmt", "restore"),
    "fabrication": ("export", "render", "bom", "pnp", "manifest", "models"),
    "altium": ("kit",),
    "recovery": ("guide", "skill"),
}
"""Topic → the commands whose tested line is on that page. A command that is not registered (``fetch``
before the change that adds it) is not asked for."""

TEACHES: Mapping[str, tuple[str, ...]] = {
    "design-script": (
        "`design`", "Design(", "Module(", "Net(", "Part(", "connect(", "no_connect(", "Power(", "mm()",
        "top-left corner", "Y down", "--dry-run", "--confirm", "What a rebuild keeps",
    ),
    "parts": (
        "a symbol", "a footprint", "catalog list --query", "fp-lib-table", "sym-lib-table", "pad_map",
        "`ohm`", "`farad`", "`henry`", "`volt`", "`amp`", "`watt`", "`hertz`", "`second`", "properties",
        "Interface(", "I2C(", "SPI(", "UART(", "USB2(", "Harness(", "DiffPair(",
    ),
    "footprints": ("Footprint(", "Symbol(", "`INFERRED`", "datasheet"),
    "placement": (
        "place(", "side=", "rot=", "locked=True", "place --strategy grid", "place --move", "fenolite pads",
        "field(",
    ),
    "routing": (
        "`direct`", "`freerouting`", "--nets", "--rip", "result.unrouted", "design.track", "design.via",
        "design.stitch", "via_step", "arc_to", "design.zone", "fenolite fill",
    ),
    "rules": ("netclass(", "minimum(", "select.", "is an example", "fabricator"),
    "checks": (
        "model.validate", "copper.clearance", "drc.kicad", "`code`", "`severity`", "`where`", "explain CODE",
        "One fix per iteration", "--fields", "--stages", "--format concise", "--limit", *LABELS[:3],
        "INFERRED",
    ),
    "files": ("roundtrip", "fenolite diff", "fenolite equivalent", "fenolite restore", "did not write"),
    "fabrication": ("fenolite export", "bill of materials", "position", "manifest", "fenolite render"),
    "altium": (
        "build --target altium", "What it writes",
        "The Altium verification kit is a run that a person performs in Altium Designer",
    ),
    "recovery": (
        "kicad.drc.", "kicad.erc.", "fenolite check blink/build --json", "fenolite explain copper.short",
    ),
}  # fmt: skip
"""Topic → words the page must hold, from the requirement "Guide pages"."""


def _tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("gen_agent_guide", ROOT / "tools" / "gen_agent_guide.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _with(page: guide.Page, text: str) -> guide.Page:
    """A copy of ``page`` with another text."""
    return dataclasses.replace(page, text=text)


def _lines(block: guide.Block) -> list[tuple[int, str]]:
    """The non-empty lines of ``block``, stripped, each with its line number in the page."""
    return [
        (number, line.strip())
        for number, line in enumerate(block.lines, start=block.line_number + 1)
        if line.strip()
    ]


def _prose(page: guide.Page) -> list[tuple[int, str]]:
    """The lines of ``page`` that are in no fenced block, each with its number."""
    inside_block = False
    found: list[tuple[int, str]] = []
    for number, line in enumerate(page.text.split("\n"), start=1):
        if line.strip().startswith(guide.FENCE):
            inside_block = not inside_block
        elif not inside_block:
            found.append((number, line))
    return found


def tag_problems(page: guide.Page) -> list[str]:
    """The blocks of ``page`` that no suite proves: an unknown tag, no tag, or any block on a generated
    page."""
    problems: list[str] = []
    for block in guide.blocks(page):
        where = f"{page.topic}: line {block.line_number}"
        if page.topic in GENERATED:
            problems.append(f"{where}: a generated page holds no fenced block")
        elif not block.tag:
            problems.append(f"{where}: a block without a tag; the tags are {', '.join(guide.BLOCK_TAGS)}")
        elif block.tag not in guide.BLOCK_TAGS:
            problems.append(f"{where}: unknown tag {block.tag!r}; the tags are {', '.join(guide.BLOCK_TAGS)}")
        elif block.tag == "fenolite-design" and block.argument not in guide.DESIGN_TARGETS:
            known = ", ".join(repr(name) for name in guide.DESIGN_TARGETS if name)
            problems.append(f"{where}: fenolite-design takes no argument but {known}, not {block.argument!r}")
    return problems


def cmd_problems(page: guide.Page) -> list[str]:
    """Why a ``fenolite-cmd`` line of ``page`` is not a command line that the parser accepts."""
    parser = build_parser(discover())
    problems: list[str] = []
    for block in guide.blocks(page):
        if block.tag != "fenolite-cmd":
            continue
        for number, line in _lines(block):
            where = f"{page.topic}: line {number}"
            if not line.startswith("fenolite "):
                problems.append(f"{where}: not a fenolite command: {line}")
            elif "<" in line or ">" in line:
                problems.append(f"{where}: a placeholder or a redirection, not a concrete line: {line}")
            else:
                try:
                    parser.parse_args(shlex.split(line)[1:])
                except CliError as error:
                    problems.append(f"{where}: the parser refuses ({error.message}): {line}")
    return problems


def commands_of(page: guide.Page) -> set[str]:
    """The commands that the lines of the run blocks of ``page`` call."""
    found: set[str] = set()
    for block in guide.blocks(page):
        if block.tag in RUN_TAGS:
            for _, line in _lines(block):
                words = shlex.split(line, comments=True)
                if words[:1] == ["fenolite"] and len(words) > 1:
                    found.add(words[1])
    return found


def command_problems(registry: Mapping[str, Command], pages: Iterable[guide.Page]) -> list[str]:
    """The public commands of ``registry`` that no run block of the start page or of a written page
    calls."""
    taught: set[str] = set()
    for page in pages:
        if page.topic not in GENERATED:
            taught |= commands_of(page)
    return [
        f"the command {name!r} has no tested line in a guide page"
        for name in sorted(registry)
        if not registry[name].hidden and name not in taught
    ]


def design_names(pages: Iterable[guide.Page]) -> set[str]:
    """The bare names that the code of the design blocks uses: no comment, no text, no attribute after
    a dot and no keyword of a call."""
    found: set[str] = set()
    for page in pages:
        for block in guide.blocks(page):
            if block.tag != "fenolite-design":
                continue
            code = textwrap.dedent("\n".join(block.lines)) + "\n"
            tokens = [
                token
                for token in tokenize.generate_tokens(io.StringIO(code).readline)
                if token.type in (tokenize.NAME, tokenize.OP)
            ]
            for index, token in enumerate(tokens):
                if token.type != tokenize.NAME:
                    continue
                attribute = index > 0 and tokens[index - 1].string == "."
                keyword = index + 1 < len(tokens) and tokens[index + 1].string == "="
                if not attribute and not keyword:
                    found.add(token.string)
    return found


def dsl_problems(names: Iterable[str], used: set[str], not_taught: Mapping[str, str]) -> list[str]:
    """Why the design blocks and ``not_taught`` do not cover ``names`` exactly once each."""
    public = set(names)
    problems = [
        f"the DSL name {name!r} is in no fenolite-design block and not in DSL_NOT_TAUGHT"
        for name in sorted(public)
        if name not in used and name not in not_taught
    ]
    problems += [
        f"DSL_NOT_TAUGHT holds {name!r}, which is not in fenolite.dsl.__all__"
        for name in sorted(not_taught)
        if name not in public
    ]
    problems += [
        f"DSL_NOT_TAUGHT holds {name!r}, which a fenolite-design block uses"
        for name in sorted(not_taught)
        if name in used
    ]
    problems += [
        f"DSL_NOT_TAUGHT gives no one-line reason for {name!r}"
        for name, reason in sorted(not_taught.items())
        if not reason.strip() or "\n" in reason
    ]
    return problems


def writing_problems(page: guide.Page) -> list[str]:
    """The forbidden forms of ``page``, each with its line."""
    problems: list[str] = []
    for number, line in enumerate(page.text.split("\n"), start=1):
        where = f"{page.topic}: line {number}"
        if re.search(r"\bc\d{4}\b", line):
            problems.append(f"{where}: a change id")
        if re.search(r"\bH-[A-Z]", line):
            problems.append(f"{where}: a hypothesis id")
        if re.search(r"/(Users|home)/|[A-Za-z]:\\\\Users", line):
            problems.append(f"{where}: a private path")
    for number, line in _prose(page):
        where = f"{page.topic}: line {number}"
        if re.search(r"rules\.(minimum|netclass)\([^)]*\d", line) and "example" not in line:
            problems.append(f"{where}: a number in a rule call without the word 'example'")
        without_labels = line
        for label in LABELS:
            without_labels = without_labels.replace(label, "")
        if re.search(r"(?<![\w-])verified\b", without_labels, re.IGNORECASE) and without_labels == line:
            problems.append(f"{where}: says 'verified' without an evidence label")
    return problems


def budget_problems(files: Iterable[guide.SkillFile]) -> list[str]:
    """The files of the skill folder that are over their budget, and the folder itself."""
    problems: list[str] = []
    total = 0
    for file in files:
        total += len(file.data)
        lines = len(file.data.decode("utf-8").splitlines())
        topic = Path(file.path).stem
        if file.path == "SKILL.md":
            if lines >= START_LINES:
                problems.append(f"{file.path}: {lines} lines; the start page stays under {START_LINES}")
        elif topic in GENERATED:
            if lines > GENERATED_LINES:
                problems.append(f"{file.path}: {lines} lines; a generated page has at most {GENERATED_LINES}")
        else:
            if lines > WRITTEN_LINES:
                problems.append(f"{file.path}: {lines} lines; a written page has at most {WRITTEN_LINES}")
            if len(file.data) > WRITTEN_BYTES:
                problems.append(
                    f"{file.path}: {len(file.data)} bytes; a written page has at most {WRITTEN_BYTES}"
                )
    if total >= FOLDER_BYTES:
        problems.append(f"the skill folder holds {total} bytes; it stays under {FOLDER_BYTES}")
    return problems


def read_next_problems(page: guide.Page, topics: set[str]) -> list[str]:
    """Why ``page`` does not end with a ``Read next:`` line that names one to three other pages."""
    last = [line for line in page.text.split("\n") if line.strip()][-1]
    if not last.startswith("Read next:"):
        return [f"{page.topic}: the last line is not 'Read next:'"]
    named = re.findall(r"`([^`]+)`", last)
    problems = [
        f"{page.topic}: Read next names the unknown page {name!r}" for name in named if name not in topics
    ]
    if not 1 <= len(named) <= 3 or len(set(named)) != len(named) or page.topic in named:
        problems.append(f"{page.topic}: Read next names one to three other pages, each once")
    return problems


def altium_rows(reply: Mapping[str, Any]) -> dict[str, tuple[str, str]]:
    """Altium write kind → its status and its evidence level, as ``capabilities`` reports them."""
    backend = next(entry for entry in reply["backends"] if entry["name"] == "altium")
    rows: dict[str, tuple[str, str]] = {}
    for row in reply["matrix"]:
        if row["backend"] != "altium" or row["write"] is None:
            continue
        if row["kind"] in backend["write_kinds"]:
            status = "write_kinds"
        else:
            status = "experimental" if "write" in row["experimental"] else "unlisted"
        rows[row["kind"]] = (status, row["write"])
    return rows


def altium_table(page: guide.Page) -> dict[str, tuple[str, str]]:
    """Altium write kind → the status and the evidence level that the table of ``page`` gives."""
    rows: dict[str, tuple[str, str]] = {}
    for _, line in _prose(page):
        cells = [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]
        if line.startswith("| `altium_") and len(cells) >= 3:
            rows[cells[0]] = (cells[-2], cells[-1])
    return rows


def altium_problems(page: guide.Page, reply: Mapping[str, Any]) -> list[str]:
    """Where the table of the page ``altium`` differs from the reply of ``capabilities``."""
    told, real = altium_table(page), altium_rows(reply)
    problems = [f"the page has no row for the kind {kind}" for kind in sorted(real) if kind not in told]
    problems += [
        f"the page has a row for {kind}, which is no Altium write kind" for kind in sorted(told - real.keys())
    ]
    problems += [
        f"{kind}: the page says {told[kind]}, capabilities reports {real[kind]}"
        for kind in sorted(real)
        if kind in told and told[kind] != real[kind]
    ]
    return problems


def build_problems(block: guide.Block, folder: Path, target: str) -> list[str]:
    """Why the design block does not build in the empty ``folder`` for ``target`` (``9``, ``10`` or
    ``altium``): an empty list for exit 0 without an issue of severity ``error``."""
    folder.mkdir(parents=True, exist_ok=True)
    script = textwrap.dedent("\n".join(block.lines)) + "\n"
    (folder / "design.py").write_text(script, encoding="utf-8", newline="\n")
    option = "--target altium" if target == "altium" else f"--kicad-version {target}"
    with inside(folder):
        outcome = run(f"fenolite build design.py --out out {option} --confirm --json")
    errors = [issue for issue in (outcome.envelope or {}).get("issues", []) if issue["severity"] == "error"]
    problems = [f"{issue['code']}: {issue['message']}" for issue in errors]
    if outcome.code != 0:
        problems.append(f"exit code {outcome.code}: {outcome.error}")
    return problems


PAGES = guide.pages()
DESIGNS = [
    pytest.param(page.topic, block, target, id=f"{page.topic}:{block.line_number}:{target}")
    for page in PAGES
    for block in guide.blocks(page)
    if block.tag == "fenolite-design"
    for target in guide.DESIGN_TARGETS.get(block.argument, KICAD_TARGETS)
]


def test_topics_load() -> None:
    """Scenario "The eleven pages load"."""
    pages = guide.pages()
    topics = [page.topic for page in pages]
    assert topics == [guide.START, *sorted((*WRITTEN, *GENERATED))]
    assert len(WRITTEN) == 11 and len(GENERATED) == 2
    for page in pages:
        assert page.title and page.summary and "\n" not in page.summary, page.topic
        assert page.text.startswith(f"# {page.title}\n"), page.topic
    for page in pages:
        if page.topic in WRITTEN:
            assert read_next_problems(page, set(topics)) == []
    routing = guide.page("routing")
    assert read_next_problems(_with(routing, routing.text + "\nMore.\n"), set(topics))
    assert read_next_problems(_with(routing, "Read next: `nowhere`.\n"), set(topics)) == [
        "routing: Read next names the unknown page 'nowhere'"
    ]
    assert read_next_problems(
        _with(routing, "Read next: `rules`, `checks`, `files`, `parts`.\n"), set(topics)
    )


def test_topics_teach_what_the_requirement_names() -> None:
    """Each page holds the words and the tested command lines that "Guide pages" gives it."""
    registry = discover()
    assert set(TEACHES) == set(HOME) == set(WRITTEN)
    for topic in WRITTEN:
        page = guide.page(topic)
        missing = [words for words in TEACHES[topic] if words not in page.text]
        assert missing == [], f"{topic} does not hold {missing}"
        wanted = {name for name in HOME[topic] if name in registry}
        assert wanted <= commands_of(page), (
            f"{topic} lacks a tested line of {sorted(wanted - commands_of(page))}"
        )


def test_topics_index_of_the_start_page() -> None:
    """The start page lists every other page with its summary, between the two marker lines."""
    pages = guide.pages()
    rows = pages[0].text.split("\n")
    begin, end = rows.index(guide.PAGES_BEGIN), rows.index(guide.PAGES_END)
    assert rows[begin + 1 : end] == [f"- `{page.topic}`: {page.summary}" for page in pages[1:]]


def test_topics_through_the_command_line(no_tools: None) -> None:
    """Scenario "A page through the command line"."""
    outcome = run("fenolite guide routing --json")
    assert outcome.code == 0 and outcome.envelope is not None
    text = str(outcome.envelope["result"])
    for words in ("direct", "--rip", "design.track", "fenolite fill"):
        assert words in text, words
    listed = run("fenolite guide --json")
    assert listed.envelope is not None
    assert [entry["topic"] for entry in listed.envelope["result"]["topics"]] == [
        p.topic for p in guide.pages()
    ]


def test_cmd_lines_parse() -> None:
    """Scenario "Every command line parses"."""
    for page in guide.pages():
        assert tag_problems(page) == []
        assert cmd_problems(page) == []
    assert sum(block.tag == "fenolite-cmd" for page in guide.pages() for block in guide.blocks(page)) >= 20


def test_cmd_explain_lines_answer(no_tools: None) -> None:
    """Every code that a page asks ``fenolite explain`` about has an entry."""
    asked = 0
    for page in guide.pages():
        for block in guide.blocks(page):
            if block.tag != "fenolite-cmd":
                continue
            for number, line in _lines(block):
                if shlex.split(line)[1] == "explain":
                    asked += 1
                    assert run(line).code == 0, f"{page.topic}: line {number}: {line}"
    assert asked >= 3


@pytest.mark.parametrize(("topic", "block", "target"), DESIGNS)
def test_design_blocks_build(
    topic: str, block: guide.Block, target: str, tmp_path: Path, no_tools: None
) -> None:
    """Scenario "Every design builds": in an empty folder, with the catalog alone and no subprocess."""
    assert build_problems(block, tmp_path / "work", target) == [], f"{topic}: line {block.line_number}"


def test_design_blocks_exist_where_names_are_taught() -> None:
    """The pages that teach names of the DSL hold a design block, and one block is for Altium."""
    per_topic = {topic: 0 for topic in WRITTEN}
    for page in guide.pages():
        for block in guide.blocks(page):
            if block.tag == "fenolite-design":
                per_topic[page.topic] += 1
                assert "\ndesign = Design(" in "\n" + "\n".join(block.lines), f"{page.topic}: no design"
    for topic in ("design-script", "parts", "footprints", "routing", "rules", "altium"):
        assert per_topic[topic] >= 1, topic
    altium = [
        block.argument for block in guide.blocks(guide.page("altium")) if block.tag == "fenolite-design"
    ]
    assert altium == ["altium"]


def test_target_ten_block_is_built_for_ten_alone(tmp_path: Path, no_tools: None) -> None:
    """Scenario "A block for target 10 alone": the block of the page ``fabrication`` that fills and caps the
    vias of a stitch is built for target 10 only, and the build for target 9 refuses it with exit 7."""
    (block,) = [b for b in guide.blocks(guide.page("fabrication")) if b.tag == "fenolite-design"]
    assert block.argument == "kicad10" and guide.DESIGN_TARGETS["kicad10"] == ("10",)
    assert [target for _topic, b, target in (p.values for p in DESIGNS) if b == block] == ["10"]
    assert "protect(filling=True, capping=True)" in "\n".join(block.lines)
    problems = build_problems(block, tmp_path / "nine", "9")
    assert problems and "exit code 7" in problems[-1]
    assert tag_problems(_with(guide.page("fabrication"), "x")) == []
    fence = guide.FENCE
    wrong = tag_problems(
        _with(guide.page("fabrication"), f"{fence}fenolite-design kicad9\ndesign = 1\n{fence}\n")
    )
    assert len(wrong) == 1 and "'altium', 'kicad10'" in wrong[0]


def test_design_block_that_does_not_build_is_reported(tmp_path: Path, no_tools: None) -> None:
    """A block with an unknown lib id, and one that raises, are refused."""
    block = next(b for b in guide.blocks(guide.page("design-script")) if b.tag == "fenolite-design")
    lines = tuple(line.replace("Fenolite:Chip_0603", "Fenolite:Chip_0630") for line in block.lines)
    assert build_problems(dataclasses.replace(block, lines=lines), tmp_path / "a", "10")
    lines = tuple(line.replace("mil(250)", "250") for line in block.lines)
    problems = build_problems(dataclasses.replace(block, lines=lines), tmp_path / "b", "9")
    assert problems and "FEN-3004" in problems[-1]


def test_design_power_with_catalog_parts_builds(tmp_path: Path, no_tools: None) -> None:
    """The page ``design-script`` says that a KiCad build of catalog parts with a ``Power`` builds: the
    build exits 0 and reports no ``build.vendor-unsafe-name`` (it was refused with that code before the
    change c0143)."""
    text = guide.page("design-script").text
    assert "`design.add(Power(vin, gnd))`" in text and "parts of the built-in catalog as well" in text
    assert "build.vendor-unsafe-name" not in text and "leave `Power` out" not in text
    script = starter_script().replace(
        "import Design, Net, Part, connect, mm", "import Design, Net, Part, Power, connect, mm"
    )
    script += "design.add(Power(vin, gnd))\n"
    assert "Power(vin, gnd)" in script and "Part, Power" in script
    folder = tmp_path / "work"
    folder.mkdir()
    (folder / "design.py").write_text(script, encoding="utf-8", newline="\n")
    with inside(folder):
        outcome = run("fenolite build design.py --out out --confirm --json")
    assert outcome.code == 0 and "build.vendor-unsafe-name" not in outcome.codes()
    libraries = sorted(path.name for path in (folder / "out" / "lib").glob("*.kicad_sym"))
    assert libraries == ["Fenolite.kicad_sym"]  # the names as the folder lists them: no ``fenolite``
    assert '(symbol "PWR_FLAG"' in (folder / "out" / "lib" / libraries[0]).read_text(encoding="utf-8")


def test_untested_block_is_refused() -> None:
    """Scenario "An untested block is refused"."""
    page = guide.page("routing")
    fence = guide.FENCE
    python = _with(page, f"# A\n\n{fence}python\nprint(1)\n{fence}\n")
    assert tag_problems(python) == [
        "routing: line 3: unknown tag 'python'; the tags are " + ", ".join(guide.BLOCK_TAGS)
    ]
    bare = _with(page, f"# A\n\ntext\n\n{fence}\nfenolite check blink/build\n{fence}\n")
    assert tag_problems(bare) and "line 5: a block without a tag" in tag_problems(bare)[0]
    stale = _with(page, f"# A\n\n{fence}fenolite-cmd\nfenolite route blink/build --engine x\n{fence}\n")
    problems = cmd_problems(stale)
    assert len(problems) == 1 and "--engine" in problems[0] and "routing: line 4" in problems[0]
    for line in (
        "kicad-cli pcb drc blink/build",
        "fenolite check <board>",
        "fenolite frobnicate blink/build",
    ):
        assert cmd_problems(_with(page, f"{fence}fenolite-cmd\n{line}\n{fence}\n")), line
    assert tag_problems(_with(page, f"{fence}fenolite-design kicad\ndesign = 1\n{fence}\n"))
    generated = guide.page("commands")
    assert tag_problems(_with(generated, f"{fence}text\nsample\n{fence}\n")) == [
        "commands: line 1: a generated page holds no fenced block"
    ]
    with pytest.raises(guide.GuideError, match="line 2"):
        guide.blocks(_with(page, f"# A\n{fence}text\nnever closed\n"))


def test_untested_blocks_api() -> None:
    """``guide.blocks`` gives the tag, the argument, the lines and the line of every fenced block."""
    page = _with(
        guide.page("routing"), "# A\n\n```fenolite-recipe starter\n  one\ntwo\n```\n\n```json\n{}\n```\n"
    )
    assert guide.blocks(page) == (
        guide.Block("fenolite-recipe", "starter", ("  one", "two"), 3),
        guide.Block("json", "", ("{}",), 8),
    )
    assert guide.blocks(_with(page, "no block\n")) == ()
    assert {block.tag for p in guide.pages() for block in guide.blocks(p)} <= set(guide.BLOCK_TAGS)


def test_budget_holds() -> None:
    """Scenario "Budgets hold"."""
    files = guide.skill_files()
    assert budget_problems(files) == []
    assert {Path(file.path).stem for file in files if file.path != "SKILL.md"} == {*WRITTEN, *GENERATED}
    page = next(file for file in files if file.path == "references/routing.md")
    long = dataclasses.replace(page, data=page.data + b"line\n" * WRITTEN_LINES)
    assert any("at most 250" in problem for problem in budget_problems([long]))
    wide = dataclasses.replace(page, data=page.data + b"x" * WRITTEN_BYTES)
    assert any("at most 12000" in problem for problem in budget_problems([wide]))
    generated = guide.SkillFile("references/commands.md", b"line\n" * (GENERATED_LINES + 1))
    assert budget_problems([generated]) == [
        "references/commands.md: 601 lines; a generated page has at most 600"
    ]
    assert budget_problems([guide.SkillFile("SKILL.md", b"line\n" * START_LINES)])
    assert any(
        "stays under 150000" in p for p in budget_problems([guide.SkillFile("x.bin", b"x" * FOLDER_BYTES)])
    )


def test_writing_rules_hold() -> None:
    """The pages hold no change id, no hypothesis id and no private path, mark the numbers of rule calls
    as examples and name the evidence label wherever they say that something is verified."""
    for page in guide.pages():
        assert writing_problems(page) == []
    for topic in ("design-script", "placement", "routing", "rules", "altium"):
        assert "example" in guide.page(topic).text, topic


def test_writing_rules_forbidden_forms_are_reported() -> None:
    """Scenario "Forbidden forms are reported"."""
    page = guide.page("rules")
    assert writing_problems(_with(page, "# Rules\n\nSince c0042 a class has a width.\n")) == [
        "rules: line 3: a change id"
    ]
    assert writing_problems(_with(page, "KiCad accepts it (H-K-DSL-MINIMUM).\n")) == [
        "rules: line 1: a hypothesis id"
    ]
    assert writing_problems(_with(page, "see /" + "home" + "/someone/notes\n")) == [
        "rules: line 1: a private path"
    ]
    call = "Write `design.rules.minimum(clearance=mm(0.2))` first.\n"
    assert writing_problems(_with(page, call)) == [
        "rules: line 1: a number in a rule call without the word 'example'"
    ]
    assert writing_problems(_with(page, call.replace("first", "(example) first"))) == []
    assert writing_problems(_with(page, '`design.rules.netclass("PWR", track_width=mm(0.5))` is a class.\n'))
    assert writing_problems(_with(page, "The board is verified by KiCad.\n")) == [
        "rules: line 1: says 'verified' without an evidence label"
    ]
    assert writing_problems(_with(page, "The board is verified by KiCad (`KICAD-VERIFIED`).\n")) == []
    assert writing_problems(_with(page, "The state `native-verified` is the highest.\n")) == []
    assert writing_problems(_with(page, "Chip_0603 and a 2512 land.\n")) == []


def test_generated_pages_are_current() -> None:
    """Scenario "Pages are current", and the form of a generated page."""
    tool = _tool()
    assert tool.stale() == []
    assert tool.main(["--check"]) == 0
    first, second = tool.render(), tool.render()
    assert first == second and set(first) == {tool.COMMANDS, tool.DSL, tool.START}
    registry = discover()
    public = sorted(name for name in registry if not registry[name].hidden)
    for path, topic in ((tool.COMMANDS, "commands"), (tool.DSL, "dsl-reference")):
        page = guide.page(topic)
        assert page.text.split("\n")[2].startswith("This page is generated by `tools/gen_agent_guide.py`")
        assert guide.blocks(page) == () and tag_problems(page) == []
        assert (SKILL / path).read_text(encoding="utf-8") == first[path]
    commands = guide.page("commands").text
    assert re.findall(r"^## (\S+)$", commands, re.MULTILINE) == public
    assert "| `build` | yes |" in commands and "| `check` | no |" in commands
    assert "- `--router` (string, required)" in commands and "one of `footprint`, `symbol`" in commands
    names = re.findall(r"^## (\S+)$", guide.page("dsl-reference").text, re.MULTILINE)
    assert names == sorted(set(fenolite.dsl.__all__) - set(guide.DSL_NOT_TAUGHT))
    reference = guide.page("dsl-reference").text
    assert "Class: `Design(name: 'str')" in reference and "Function: `mm(" in reference
    assert " at 0x" not in reference
    assert "gen_agent_guide.py --check" in (ROOT / "Makefile").read_text(encoding="utf-8")


def test_generated_drift_is_reported(capsys: pytest.CaptureFixture[str]) -> None:
    """Scenario "Drift is reported"."""
    tool = _tool()
    registry = dict(discover())
    registry["check"] = dataclasses.replace(registry["check"], help="check a project, in other words")
    assert tool.stale(registry=registry) == [tool.COMMANDS]
    capsys.readouterr()
    assert tool.main(["--check"], registry=registry) == 1
    assert "references/commands.md" in capsys.readouterr().err
    assert (SKILL / tool.COMMANDS).read_text(encoding="utf-8") == tool.render()[tool.COMMANDS]


def test_generated_files_are_written_into_a_copy(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Without ``--check`` the tool writes the three files; a page added by hand joins the index."""
    import shutil

    tool = _tool()
    copy = tmp_path / "skill"
    shutil.copytree(SKILL, copy)
    (copy / tool.COMMANDS).unlink()
    page = (
        "---\ntopic: extra\ntitle: Extra\nsummary: One more page.\n---\n\n# Extra\n\nRead next: `checks`.\n"
    )
    (copy / "references" / "extra.md").write_text(page, encoding="utf-8", newline="\n")
    assert sorted(tool.stale(copy)) == [tool.START, tool.COMMANDS]
    assert tool.main(["--check"], skill=copy) == 1
    assert not (copy / tool.COMMANDS).exists()
    assert tool.main([], skill=copy) == 0
    assert "wrote references/commands.md" in capsys.readouterr().out
    assert tool.stale(copy) == []
    assert "- `extra`: One more page." in (copy / tool.START).read_text(encoding="utf-8").split("\n")
    assert (copy / tool.COMMANDS).read_bytes() == (SKILL / tool.COMMANDS).read_bytes()
    broken = (copy / tool.START).read_text(encoding="utf-8").replace(guide.PAGES_END, "")
    (copy / tool.START).write_text(broken, encoding="utf-8", newline="\n")
    with pytest.raises(guide.GuideError, match="pages:end"):
        tool.render(copy)


def test_altium_status_follows_capabilities(no_tools: None) -> None:
    """Scenario "Altium status follows capabilities"."""
    outcome = run("fenolite capabilities --json --no-tools")
    assert outcome.code == 0 and outcome.envelope is not None
    reply = outcome.envelope["result"]
    page = guide.page("altium")
    real = altium_rows(reply)
    assert real and altium_table(page) == real
    assert altium_problems(page, reply) == []
    kind = sorted(kind for kind, (status, _) in real.items() if status != "write_kinds")[0]
    moved = {
        **reply,
        "backends": [
            {**entry, "write_kinds": [*entry["write_kinds"], kind]} if entry["name"] == "altium" else entry
            for entry in reply["backends"]
        ],
        "matrix": [{**row, "experimental": []} if row["kind"] == kind else row for row in reply["matrix"]],
    }
    problems = altium_problems(page, moved)
    assert len(problems) == 1 and problems[0].startswith(f"{kind}: the page says ('experimental', ")
    assert "('write_kinds', " in problems[0]
    level = {
        **reply,
        "matrix": [
            {**row, "write": "KICAD-VERIFIED"} if row["kind"] == kind else row for row in reply["matrix"]
        ],
    }
    assert altium_problems(page, level) and kind in altium_problems(page, level)[0]
    assert altium_problems(_with(page, page.text.replace(f"| `{kind}` |", "| `altium_other` |")), reply) == [
        f"the page has no row for the kind {kind}",
        "the page has a row for altium_other, which is no Altium write kind",
    ]
    for number, line in _prose(page):
        if not line.startswith("|"):
            assert not re.search(r"\b(stable|graduat\w*|production)\b|[A-Z]+-VERIFIED", line), (
                f"line {number}"
            )


def test_fen_codes_are_named() -> None:
    """Scenario "Every error code is named"."""
    text = guide.page("recovery").text
    assert len(REGISTRY) >= 17
    missing = [code for code in sorted(REGISTRY) if f"`{code}`" not in text]
    assert missing == [], f"the page recovery does not name {missing}"
    for code, spec in REGISTRY.items():
        row = re.search(rf"^\| `{code}` \| (\d) \|", text, re.MULTILINE)
        assert row is not None and int(row.group(1)) == int(spec.exit_code), code


def test_coverage_holds() -> None:
    """Scenario "Coverage holds"."""
    pages = guide.pages()
    assert command_problems(discover(), pages) == []
    assert dsl_problems(fenolite.dsl.__all__, design_names(pages), guide.DSL_NOT_TAUGHT) == []
    assert set(guide.DSL_NOT_TAUGHT) <= set(fenolite.dsl.__all__)


def test_coverage_reports_a_new_command() -> None:
    """Scenario "A new command without a line is reported"."""
    registry = dict(discover())
    registry["frobnicate"] = dataclasses.replace(registry["check"], name="frobnicate")
    assert command_problems(registry, guide.pages()) == [
        "the command 'frobnicate' has no tested line in a guide page"
    ]
    registry["_hidden"] = dataclasses.replace(registry["check"], name="_hidden", help=None)
    assert len(command_problems(registry, guide.pages())) == 1
    only_generated = [page for page in guide.pages() if page.topic in GENERATED]
    assert len(command_problems(discover(), only_generated)) == sum(not c.hidden for c in discover().values())


def test_coverage_reports_dsl_names() -> None:
    """A name that nothing teaches, a key that is no name and a key that a block uses are reported."""
    used = design_names(guide.pages())
    names = [*fenolite.dsl.__all__, "Frobnicator"]
    assert dsl_problems(names, used, guide.DSL_NOT_TAUGHT) == [
        "the DSL name 'Frobnicator' is in no fenolite-design block and not in DSL_NOT_TAUGHT"
    ]
    assert dsl_problems(fenolite.dsl.__all__, used, {**guide.DSL_NOT_TAUGHT, "Gone": "left"}) == [
        "DSL_NOT_TAUGHT holds 'Gone', which is not in fenolite.dsl.__all__"
    ]
    assert dsl_problems(fenolite.dsl.__all__, used, {**guide.DSL_NOT_TAUGHT, "mm": "a unit"}) == [
        "DSL_NOT_TAUGHT holds 'mm', which a fenolite-design block uses"
    ]
    assert dsl_problems(fenolite.dsl.__all__, used, {**guide.DSL_NOT_TAUGHT, "copper": " "})
    fence = guide.FENCE
    code = "# copper, fields\nstack.copper('35um')\nd.board(a, copper=4)\nx = planes\n"
    page = _with(guide.page("rules"), f"{fence}fenolite-design\n{code}{fence}\n")
    assert design_names([page]) == {"stack", "d", "a", "planes"}


def test_coverage_rule_is_stated_for_contributors() -> None:
    """``AGENTS.md`` (Workflow) and ``CONTRIBUTING.md`` state the rule for new commands, names and codes."""
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    workflow = agents.split("## Workflow", 1)[1].split("\n## ", 1)[0]
    contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    for text in (workflow, contributing):
        flat = " ".join(text.split())
        assert RULE in flat
        for words in ("public command", "public DSL name", "`FEN-` code", "tests/unit/agent/test_pages.py"):
            assert words in flat, words
