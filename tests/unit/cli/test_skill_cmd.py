# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite skill show|install`` (capability cli-contract, "Skill command"; change c0079)."""

from __future__ import annotations

import hashlib
import socket
import subprocess
from pathlib import Path

import pytest
from _checkcli import run
from _cliexamples import folder_snapshot

import fenolite
from fenolite.agent import guide
from fenolite.cli import cmd_skill
from fenolite.cli.cmd_skill import COMMAND, installed_skill, marked_section, version_line, with_pointer

USER_TEXT = "# My project\nRead the wiki first.\n"
VERSION_LINE = f"<!-- installed from fenolite {fenolite.__version__} -->"


@pytest.fixture(autouse=True)
def no_tool_no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("skill started a subprocess or opened a connection")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_show(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, envelope, _, _ = run(monkeypatch, tmp_path, "skill", "show")
    result = envelope["result"]
    assert code == 0 and list(result) == ["name", "description", "version", "files", "agents"]
    assert result["name"] == "fenolite" and result["version"] == fenolite.__version__
    assert result["description"] == guide.page("start").summary
    assert result["files"] == [
        {"path": file.path, "bytes": len(file.data), "sha256": _sha(file.data)}
        for file in guide.skill_files()
    ]
    assert result["agents"] == [{"agent": a, "dir": d} for a, d in sorted(guide.AGENT_DIRS.items())]
    assert "plan" not in result and envelope["receipt"] is None and folder_snapshot(tmp_path) == {}
    code, _, error, _ = run(monkeypatch, tmp_path, "skill", "show", "--dir", "skills")
    assert code == 2 and error["code"] == "FEN-2001" and "install" in error["hint"]


def test_install_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Install into a named folder"."""
    code, envelope, error, _ = run(monkeypatch, tmp_path, "skill", "install", "--dir", "skills", "--confirm")
    assert code == 0, error
    packaged = {file.path: file.data for file in guide.skill_files()}
    installed = tmp_path / "skills" / "fenolite" / "SKILL.md"
    data = installed.read_bytes()
    lines = data.decode("utf-8").split("\n")
    assert lines[-2:] == [VERSION_LINE, ""]
    assert data[: len(packaged["SKILL.md"])] == packaged["SKILL.md"]
    assert data == packaged["SKILL.md"] + (VERSION_LINE + "\n").encode("utf-8")
    assert VERSION_LINE.encode("utf-8") not in packaged["SKILL.md"]
    for path, content in packaged.items():
        if path != "SKILL.md":
            assert (tmp_path / "skills" / "fenolite" / path).read_bytes() == content
    written = envelope["receipt"]["written"]
    assert [w["path"] for w in written] == [f"skills/fenolite/{path}" for path in packaged]
    assert all(w["sha256"] == _sha((tmp_path / w["path"]).read_bytes()) for w in written)
    assert sorted(folder_snapshot(tmp_path)) == sorted(w["path"] for w in written)
    assert envelope["result"] == {
        "action": "install",
        "target": "skills/fenolite",
        "files": [f"skills/fenolite/{path}" for path in packaged],
        "version": fenolite.__version__,
    }


def test_install_copies_reference_pages_byte_for_byte(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    files = (
        guide.SkillFile("SKILL.md", b"---\nname: fenolite\ndescription: d\n---\n\n# T\n"),
        guide.SkillFile("references/routing.md", b"---\ntopic: routing\n---\r\nbytes \xc3\xa9\n"),
    )
    monkeypatch.setattr(guide, "skill_files", lambda: files)
    code, envelope, error, _ = run(monkeypatch, tmp_path, "skill", "install", "--dir", "a/b", "--dry-run")
    assert code == 0, error
    assert [(p["path"], p["kind"], p["sha256"]) for p in envelope["result"]["plan"]] == [
        ("a/b/fenolite/SKILL.md", "skill", _sha(installed_skill(files[0].data, fenolite.__version__))),
        ("a/b/fenolite/references/routing.md", "skill", _sha(files[1].data)),
    ]
    assert folder_snapshot(tmp_path) == {}


def test_install_for_claude_code(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Install for an agent"."""
    code, envelope, error, _ = run(
        monkeypatch, tmp_path, "skill", "install", "--agent", "claude-code", "--dry-run"
    )
    assert code == 0, error
    assert envelope["result"]["plan"][0]["path"] == ".claude/skills/fenolite/SKILL.md"
    assert envelope["result"]["target"] == ".claude/skills/fenolite" and folder_snapshot(tmp_path) == {}
    code, envelope, _, _ = run(monkeypatch, tmp_path, "skill", "show")
    assert {"agent": "claude-code", "dir": ".claude/skills"} in envelope["result"]["agents"]


def test_install_for_an_agent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The same on a table that a test row stands in for: any row of the table is served."""
    monkeypatch.setattr(guide, "AGENT_DIRS", {"some-agent": ".some-agent/skills"})
    code, envelope, error, _ = run(
        monkeypatch, tmp_path, "skill", "install", "--agent", "some-agent", "--dry-run"
    )
    assert code == 0, error
    assert envelope["result"]["plan"][0]["path"] == ".some-agent/skills/fenolite/SKILL.md"
    assert envelope["result"]["target"] == ".some-agent/skills/fenolite"
    assert folder_snapshot(tmp_path) == {}
    code, envelope, _, _ = run(monkeypatch, tmp_path, "skill", "show")
    assert envelope["result"]["agents"] == [{"agent": "some-agent", "dir": ".some-agent/skills"}]


def test_install_unknown_agent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(guide, "AGENT_DIRS", {"some-agent": ".some-agent/skills"})
    code, _, error, _ = run(monkeypatch, tmp_path, "skill", "install", "--agent", "other", "--dry-run")
    assert code == 2 and error["code"] == "FEN-2001"
    assert "some-agent" in error["hint"] and "--dir" in error["hint"]
    code, _, error, _ = run(
        monkeypatch, tmp_path, "skill", "install", "--agent", "some-agent", "--dir", "x", "--dry-run"
    )
    assert code == 2 and error["code"] == "FEN-2001" and "mutually exclusive" in error["message"]
    assert folder_snapshot(tmp_path) == {}


def test_nothing_asked(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Nothing asked"."""
    code, _, error, _ = run(monkeypatch, tmp_path, "skill", "install", "--dry-run")
    assert code == 2 and error["code"] == "FEN-2001"
    assert all(flag in error["hint"] for flag in ("--agent", "--dir", "--agents-md"))


def test_pointer_section_is_idempotent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Pointer section is idempotent", with the walk of the folder before and after."""
    (tmp_path / "AGENTS.md").write_bytes(USER_TEXT.encode("utf-8"))
    (tmp_path / "notes.txt").write_bytes(b"mine\n")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_bytes(b"print('x')\n")
    before = folder_snapshot(tmp_path)

    code, envelope, error, _ = run(monkeypatch, tmp_path, "skill", "install", "--agents-md", "--confirm")
    assert code == 0, error
    expected = USER_TEXT + "\n" + marked_section()
    assert (tmp_path / "AGENTS.md").read_bytes() == expected.encode("utf-8")
    assert (tmp_path / "AGENTS.md.bak").read_bytes() == USER_TEXT.encode("utf-8")
    assert envelope["result"]["target"] is None and envelope["result"]["files"] == ["AGENTS.md"]
    assert envelope["receipt"]["backup"] == ["AGENTS.md.bak"]
    after = folder_snapshot(tmp_path)
    assert sorted(set(after) - set(before)) == ["AGENTS.md.bak"]
    assert [name for name in before if after[name] != before[name]] == ["AGENTS.md"]

    code, envelope, _, _ = run(monkeypatch, tmp_path, "skill", "install", "--agents-md", "--dry-run")
    assert code == 0 and envelope["result"]["plan"] == [
        {
            "path": "AGENTS.md",
            "kind": "agents-md",
            "bytes": len(expected.encode("utf-8")),
            "sha256": _sha(expected.encode("utf-8")),
            "overwrite": True,
        }
    ]
    code, _, _, _ = run(monkeypatch, tmp_path, "skill", "install", "--agents-md", "--confirm")
    assert code == 0 and (tmp_path / "AGENTS.md").read_bytes() == expected.encode("utf-8")
    assert sorted(folder_snapshot(tmp_path)) == sorted(after)


def test_pointer_creates_a_missing_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, envelope, error, _ = run(
        monkeypatch, tmp_path, "skill", "install", "--dir", "skills", "--agents-md", "--confirm"
    )
    assert code == 0, error
    text = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert text == f"{guide.AGENTS_BEGIN}\n{guide.AGENTS_SECTION}{guide.AGENTS_END}\n"
    assert envelope["result"]["files"][-1] == "AGENTS.md" and envelope["receipt"]["backup"] == []
    assert (tmp_path / "skills" / "fenolite" / "SKILL.md").is_file()


def test_pointer_text_forms() -> None:
    section = marked_section()
    assert with_pointer(None) == section
    assert with_pointer("") == section
    assert with_pointer("a\nb") == "a\nb\n\n" + section
    old = f"top\n{guide.AGENTS_BEGIN}\nold text\nmore\n{guide.AGENTS_END}\nbottom\n"
    assert with_pointer(old) == "top\n" + section + "bottom\n"
    assert with_pointer(with_pointer(old)) == with_pointer(old)
    assert with_pointer(with_pointer("a\n")) == with_pointer("a\n")
    crlf = f"top\r\n{guide.AGENTS_BEGIN}\r\nold\r\n{guide.AGENTS_END}\r\nbottom\r\n"
    assert with_pointer(crlf) == "top\r\n" + section + "bottom\r\n"
    for broken in (
        f"a\n{guide.AGENTS_BEGIN}\nb\n",
        f"a\n{guide.AGENTS_END}\nb\n",
        f"{guide.AGENTS_END}\n{guide.AGENTS_BEGIN}\n",
        f"{guide.AGENTS_BEGIN}\n{guide.AGENTS_BEGIN}\n{guide.AGENTS_END}\n",
    ):
        with pytest.raises(ValueError, match="expected one line"):
            with_pointer(broken)


def test_one_marker_is_malformed_input(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_bytes(f"mine\n{guide.AGENTS_BEGIN}\nhalf\n".encode())
    before = folder_snapshot(tmp_path)
    code, _, error, _ = run(monkeypatch, tmp_path, "skill", "install", "--agents-md", "--confirm")
    assert code == 3 and error["code"] == "FEN-3004" and folder_snapshot(tmp_path) == before
    (tmp_path / "AGENTS.md").write_bytes(b"\xff\xfe not utf-8")
    code, _, error, _ = run(monkeypatch, tmp_path, "skill", "install", "--agents-md", "--dry-run")
    assert code == 3 and error["code"] == "FEN-3004"


def test_version_line_and_declaration() -> None:
    assert version_line("1.2.3") == "<!-- installed from fenolite 1.2.3 -->"
    assert installed_skill(b"x", "1.2.3") == b"x\n<!-- installed from fenolite 1.2.3 -->\n"
    assert COMMAND.mutates is True and COMMAND.example_args == ("show",)
    assert COMMAND.mutation_example_args == ("install", "--dir", "skills")
    assert cmd_skill.AGENTS_FILE == "AGENTS.md"
