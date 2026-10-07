# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite guide`` (capability cli-contract, "Guide command"; change c0079)."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest
from _checkcli import run

import fenolite
from fenolite.agent import guide
from fenolite.cli.cmd_guide import COMMAND
from fenolite.cli.main import main

SKILL = Path(fenolite.__file__).resolve().parent / "agent" / "skill" / "SKILL.md"


@pytest.fixture(autouse=True)
def no_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("guide started a subprocess")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)


def test_list_of_pages(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "List of pages"."""
    code, envelope, _, _ = run(monkeypatch, tmp_path, "guide")
    assert code == 0 and list(envelope["result"]) == ["version", "topics"]
    assert envelope["result"]["version"] == fenolite.__version__
    topics = envelope["result"]["topics"]
    assert topics[0]["topic"] == "start"
    assert [t["topic"] for t in topics] == [p.topic for p in guide.pages()]
    for entry in topics:
        assert list(entry) == ["topic", "title", "summary", "lines"]
        assert entry["summary"] and "\n" not in entry["summary"] and entry["lines"] > 0
    assert envelope["evidence"]["level"] == "UNVERIFIED" and envelope["receipt"] is None


def test_list_of_pages_as_text(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["guide", "--text"]) == 0
    lines = capsys.readouterr().out.split("\n")
    assert lines[:2] == ["fenolite guide: ok", ""]
    assert lines[2:-1] == [f"{p.topic}: {p.summary}" for p in guide.pages()] and lines[-1] == ""


def test_one_page_as_text(capsys: pytest.CaptureFixture[str]) -> None:
    """Scenario "One page as text"."""
    assert main(["guide", "start", "--text"]) == 0
    out = capsys.readouterr().out
    file = SKILL.read_text(encoding="utf-8")
    body = file.split("\n---\n", 1)[1].lstrip("\n")
    assert not body.startswith("---") and body.startswith("# ")
    assert out == "fenolite guide: ok\n\n" + body
    assert "description:" not in out


def test_one_page_as_json(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, envelope, _, raw = run(monkeypatch, tmp_path, "guide", "start")
    assert code == 0 and list(envelope["result"]) == ["topic", "title", "summary", "text", "version"]
    page = guide.page("start")
    assert envelope["result"] == {
        "topic": "start",
        "title": page.title,
        "summary": page.summary,
        "text": page.text,
        "version": fenolite.__version__,
    }
    assert not re.search(r"/(Users|home)/|[A-Za-z]:\\\\", raw) and str(tmp_path) not in raw
    again = run(monkeypatch, tmp_path, "guide", "start")[1]
    assert again["result"] == envelope["result"]


def test_unknown_topic(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Unknown topic"."""
    code, envelope, error, _ = run(monkeypatch, tmp_path, "guide", "strat")
    assert code == 2 and envelope["ok"] is False
    assert error["code"] == "FEN-2001" and "start" in error["hint"]
    code, _, error, _ = run(monkeypatch, tmp_path, "guide", "zzzzzz")
    assert code == 2 and error["hint"].startswith("the pages are: start")


def test_fields_and_declaration(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["guide", "start", "--json", "--fields", "title,version"]) == 0
    assert list(json.loads(capsys.readouterr().out)["result"]) == ["title", "version"]
    assert COMMAND.example_args == ("start",) and COMMAND.mutates is False and COMMAND.paged is None
