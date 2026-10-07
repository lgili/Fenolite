# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The packaged agent guide and its reader (capability agent-guide, "Packaged agent guide", "Starter
projects" and "Agent folders table"; change c0079)."""

from __future__ import annotations

import ast
import re
import shutil
import sys
from importlib import resources
from pathlib import Path

import pytest

from fenolite.agent import guide

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / "src" / "fenolite" / "agent"
SOURCES = ROOT / "docs" / "evidence" / "sources.md"
PAGE = "---\ntopic: {topic}\ntitle: A page\nsummary: One line.\n---\n\n# A page\n\nText.\n"
ROW = re.compile(r'^\s*"(?P<agent>[^"]+)":\s*"(?P<dir>[^"]*)",?\s*(?:#\s*(?P<comment>.*))?$')
SOURCE_ID = re.compile(r"\bS-\d{4}\b")


def _copy(tmp_path: Path) -> Path:
    """A copy of the packaged data that a test may break: the start page and the starters, with an
    empty ``references`` folder for the pages a test writes."""
    target = tmp_path / "agent"
    shutil.copytree(PACKAGE, target, ignore=shutil.ignore_patterns("*.py", "__pycache__"))
    shutil.rmtree(target / "skill" / "references", ignore_errors=True)
    (target / "skill" / "references").mkdir()
    return target


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def test_loads_from_the_installed_package() -> None:
    """Scenario "Guide loads from the installed package"."""
    pages = guide.pages()
    assert pages[0].topic == "start" and pages[0].title and pages[0].summary
    assert not pages[0].text.startswith("---") and pages[0].text.startswith("# ")
    assert [p.topic for p in pages[1:]] == sorted(p.topic for p in pages[1:])
    files = guide.skill_files()
    assert "SKILL.md" in [f.path for f in files]
    assert [f.path for f in files] == sorted(f.path for f in files)
    assert all("\\" not in f.path and not f.path.startswith("/") for f in files)
    assert "blink" in [s.name for s in guide.starters()]
    assert guide.page("start") == pages[0]
    with pytest.raises(KeyError):
        guide.page("no-such-topic")


def test_loads_through_importlib_resources() -> None:
    """The files are found as data of the installed package, and the repository root holds no guide."""
    base = resources.files("fenolite.agent")
    skill = base.joinpath("skill", "SKILL.md").read_bytes()
    assert skill == next(f.data for f in guide.skill_files() if f.path == "SKILL.md")
    assert base.joinpath("starters", "blink", "starter.toml").is_file()
    assert base.joinpath("starters", "blink", "design.py.tmpl").is_file()
    old = ROOT / "agent"  # git keeps no empty folder, so a leftover one holds no file
    assert not old.exists() or not [path for path in old.rglob("*") if path.is_file()]


def test_loads_skill_front_matter() -> None:
    text = (PACKAGE / "skill" / "SKILL.md").read_text(encoding="utf-8")
    front, body = guide.front_matter(text, "SKILL.md", guide.SKILL_KEYS)
    assert front["name"] == guide.SKILL_NAME == "fenolite"
    assert guide.pages()[0].summary == front["description"] and guide.pages()[0].text == body


def test_loads_a_reference_page(tmp_path: Path) -> None:
    copy = _copy(tmp_path)
    _write(copy / "skill" / "references" / "routing.md", PAGE.format(topic="routing"))
    _write(copy / "skill" / "references" / "checks.md", PAGE.format(topic="checks"))
    assert [p.topic for p in guide.pages(copy)] == ["start", "checks", "routing"]
    page = guide.page("routing", copy)
    assert (page.title, page.summary, page.text) == ("A page", "One line.", "# A page\n\nText.\n")
    assert [f.path for f in guide.skill_files(copy)] == [
        "SKILL.md",
        "references/checks.md",
        "references/routing.md",
    ]


@pytest.mark.parametrize(
    ("name", "text", "said"),
    [
        ("routing.md", "---\ntopic: routing\ntitle: A page\n---\n\n# A\n", "lacks 'summary'"),
        ("routing.md", PAGE.format(topic="placement"), "differs from the file name"),
        ("routing.md", PAGE.format(topic="routing").replace("title:", "owner: x\ntitle:"), "unknown"),
        ("Routing_1.md", PAGE.format(topic="Routing_1"), "[a-z0-9-]+"),
        ("start.md", PAGE.format(topic="start"), "belongs to SKILL.md"),
        ("routing.md", PAGE.format(topic="routing").replace("One line.", "x" * 161), "longer than 160"),
        ("routing.md", "# No front matter\n", "no front matter"),
        ("routing.md", PAGE.format(topic="routing").replace("title: A page", "title A page"), "key: value"),
    ],
)
def test_malformed_page_is_refused(tmp_path: Path, name: str, text: str, said: str) -> None:
    """Scenario "Malformed page is refused"."""
    copy = _copy(tmp_path)
    _write(copy / "skill" / "references" / name, text)
    with pytest.raises(guide.GuideError) as caught:
        guide.pages(copy)
    assert f"skill/references/{name}" in str(caught.value) and said in str(caught.value)


def test_malformed_skill_is_refused(tmp_path: Path) -> None:
    copy = _copy(tmp_path)
    skill = copy / "skill" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")
    _write(skill, text.replace("name: fenolite", "name: other", 1))
    with pytest.raises(guide.GuideError, match=r"skill/SKILL\.md: name is 'other'"):
        guide.pages(copy)
    _write(skill, text.replace("description: ", "summary: ", 1))
    with pytest.raises(guide.GuideError, match=r"skill/SKILL\.md: front matter lacks 'description'"):
        guide.pages(copy)
    skill.unlink()
    with pytest.raises(guide.GuideError, match=r"skill/SKILL\.md: missing"):
        guide.pages(copy)


def test_duplicate_front_matter_key_is_refused() -> None:
    with pytest.raises(guide.GuideError, match="x.md: front matter key 'topic' is given twice"):
        guide.front_matter("---\ntopic: a\ntopic: b\n---\n", "x.md", ("topic",))


def test_starters_render(tmp_path: Path) -> None:
    (starter,) = [s for s in guide.starters() if s.name == "blink"]
    assert starter.files == ("design.py",) and starter.summary and "\n" not in starter.summary
    assert [s.name for s in guide.starters()] == sorted(s.name for s in guide.starters())
    files = guide.render_starter("blink", "my_board")
    assert list(files) == ["design.py"]
    text = files["design.py"].decode("utf-8")
    assert text.startswith("# SPDX-License-Identifier: CC0-1.0\n")
    assert 'Design("my_board")' in text and "@NAME@" not in text and "\r" not in text
    with pytest.raises(KeyError):
        guide.render_starter("no-such-starter", "x")


def test_malformed_starter_is_refused(tmp_path: Path) -> None:
    copy = _copy(tmp_path)
    blink = copy / "starters" / "blink"
    template = (blink / "design.py.tmpl").read_text(encoding="utf-8")
    _write(blink / "design.py.tmpl", template.replace("CC0-1.0", "MIT", 1))
    with pytest.raises(guide.GuideError, match=r"starters/blink/design\.py\.tmpl: the first line"):
        guide.starters(copy)
    _write(blink / "design.py.tmpl", template)
    _write(blink / "starter.toml", 'summary = "ok"\nowner = "x"\n')
    with pytest.raises(guide.GuideError, match=r"starters/blink/starter\.toml"):
        guide.starters(copy)
    (blink / "starter.toml").unlink()
    with pytest.raises(guide.GuideError, match=r"starters/blink/starter\.toml: missing"):
        guide.starters(copy)


def test_guide_imports_the_standard_library_only() -> None:
    """Scenario "Guide stays stdlib-only": no other ``fenolite`` package and no third-party one."""
    for path in sorted(PACKAGE.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                assert node.level == 0, f"{path.name}: relative import"
                names = [node.module or ""]
            for name in names:
                assert name.split(".")[0] in sys.stdlib_module_names, f"{path.name} imports {name}"


def test_guide_names_hold_no_reserved_word() -> None:
    """No module, class or public name of the guide holds the word that belongs to the Altium
    verification package (``fenolite kit``)."""
    names = [path.stem for path in PACKAGE.rglob("*") if path.name != "__pycache__"] + list(guide.__all__)
    assert [name for name in names if "kit" in name.lower()] == []


def agent_dir_problems(source: str, registered: set[str]) -> list[str]:
    """Why the rows of ``AGENT_DIRS`` in the module text ``source`` are not all sourced and safe."""
    match = re.search(r"^AGENT_DIRS\b.*?^\)", source, re.MULTILINE | re.DOTALL)
    if match is None:
        return ["AGENT_DIRS not found"]
    problems: list[str] = []
    for line in match.group(0).splitlines():
        if line.lstrip().startswith("#") or '"' not in line.split("#", 1)[0]:
            continue
        row = ROW.match(line)
        if row is None:
            problems.append(f"not one row per line: {line.strip()}")
            continue
        agent, folder = row.group("agent"), row.group("dir")
        ids = SOURCE_ID.findall(row.group("comment") or "")
        if not ids:
            problems.append(f"{agent}: no source id in a comment on the row")
        problems += [
            f"{agent}: {ident} is not in docs/evidence/sources.md" for ident in ids if ident not in registered
        ]
        parts = folder.replace("\\", "/").split("/")
        if not folder or folder.startswith(("/", "\\", "~")) or ":" in folder or ".." in parts:
            problems.append(f"{agent}: {folder!r} is not a relative folder without '..'")
    return problems


def _registered() -> set[str]:
    return set(re.findall(r"^\| (S-\d{4}) \|", SOURCES.read_text(encoding="utf-8"), re.MULTILINE))


def test_agent_dirs_rows_are_sourced() -> None:
    """Scenario "Rows are sourced"."""
    source = (PACKAGE / "guide.py").read_text(encoding="utf-8")
    registered = _registered()
    assert registered
    assert agent_dir_problems(source, registered) == []
    rows = [m.group("agent") for m in map(ROW.match, source.splitlines()) if m is not None]
    assert sorted(rows) == sorted(guide.AGENT_DIRS), "a row of the table is not written one per line"
    for folder in guide.AGENT_DIRS.values():
        assert folder and not Path(folder).is_absolute() and ".." not in Path(folder).parts

    known = sorted(registered)[0]
    table = "AGENT_DIRS: Mapping[str, str] = MappingProxyType(\n    {\n%s    }\n)\n"
    assert (
        agent_dir_problems(table % f'        "some-agent": ".agent/skills",  # {known}\n', registered) == []
    )
    unsourced = agent_dir_problems(table % '        "some-agent": ".agent/skills",\n', registered)
    assert unsourced == ["some-agent: no source id in a comment on the row"]
    unknown = agent_dir_problems(table % '        "some-agent": ".agent/skills",  # S-9999\n', registered)
    assert unknown == ["some-agent: S-9999 is not in docs/evidence/sources.md"]
    for folder in ("../skills", "/etc/skills", "a/../../b", "C:/skills"):
        row = f'        "some-agent": "{folder}",  # {known}\n'
        assert len(agent_dir_problems(table % row, registered)) == 1, folder


def test_agent_dirs_holds_the_first_row() -> None:
    assert guide.AGENT_DIRS["claude-code"] == ".claude/skills"
    source = (PACKAGE / "guide.py").read_text(encoding="utf-8")
    assert '"claude-code": ".claude/skills",  # S-0617' in source and "S-0617" in _registered()


def test_agents_section() -> None:
    section = guide.AGENTS_SECTION
    assert "fenolite guide start --text" in section and "fenolite capabilities --brief" in section
    assert "circuit board" in section
    assert section.endswith("\n") and len(section.splitlines()) <= 12
    assert guide.AGENTS_BEGIN not in section and guide.AGENTS_END not in section
