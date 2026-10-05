# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``--limit``, ``--cursor`` and ``--format concise`` (capability cli-contract, "Paged results" and
"Concise output"; change c0066). Hermetic."""

from __future__ import annotations

import dataclasses
import hashlib
import json
from pathlib import Path

import pytest
from _checkcli import run, without_elapsed

from fenolite.cli.api import discover
from fenolite.cli.output import CursorError, page

DATA = Path(__file__).resolve().parents[2] / "data"
TWO_LAYER = DATA / "kicad" / "board" / "two_layer.kicad_pcb"
FOOTPRINT = DATA / "libs" / "Mini.pretty" / "Mini_R_0603.kicad_mod"


def _messages(env: dict) -> list[str]:  # type: ignore[type-arg]
    return [issue["message"] for issue in env["issues"]]


def test_two_pages_of_issues(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, first, _, _ = run(monkeypatch, tmp_path, "_echo", "--issues", "5", "--limit", "2")
    assert code == 0 and _messages(first) == ["requested issue 1 of 5", "requested issue 2 of 5"]
    page_one = first["result"]["page"]
    assert page_one == {"path": "issues", "limit": 2, "offset": 0, "total": 5, "next": page_one["next"]}
    assert page_one["next"].startswith("2.") and len(page_one["next"]) == 2 + 8

    code, second, _, _ = run(
        monkeypatch, tmp_path, "_echo", "--issues", "5", "--limit", "2", "--cursor", page_one["next"]
    )
    assert code == 0 and _messages(second) == ["requested issue 3 of 5", "requested issue 4 of 5"]
    assert second["result"]["page"]["offset"] == 2 and second["result"]["page"]["next"].startswith("4.")

    code, last, _, _ = run(
        monkeypatch,
        tmp_path,
        "_echo",
        "--issues",
        "5",
        "--limit",
        "2",
        "--cursor",
        second["result"]["page"]["next"],
    )
    assert code == 0 and _messages(last) == ["requested issue 5 of 5"]
    assert last["result"]["page"] == {"path": "issues", "limit": 2, "offset": 4, "total": 5, "next": None}


def test_without_a_limit_the_list_is_whole(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _, _ = run(monkeypatch, tmp_path, "_echo", "--issues", "5")
    assert code == 0 and len(env["issues"]) == 5 and "page" not in env["result"]
    code, env, _, _ = run(monkeypatch, tmp_path, "_echo", "--issues", "5", "--limit", "9")
    assert len(env["issues"]) == 5 and env["result"]["page"]["next"] is None


def test_exit_code_comes_from_the_whole_result(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, err, _ = run(
        monkeypatch, tmp_path, "_echo", "--issues", "3", "--issue", "error", "--limit", "2"
    )
    assert code == 5 and env["ok"] is False and err["code"] == "FEN-5001"
    assert [i["severity"] for i in env["issues"]] == ["warning", "warning"]
    assert env["result"]["page"]["total"] == 4 and "1 finding(s)" in err["message"]


def test_stale_malformed_and_misplaced_cursors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _, first, _, _ = run(monkeypatch, tmp_path, "_echo", "--issues", "5", "--limit", "2")
    cursor = first["result"]["page"]["next"]
    code, env, err, _ = run(
        monkeypatch, tmp_path, "_echo", "--issues", "6", "--limit", "2", "--cursor", cursor
    )
    assert code == 2 and err["code"] == "FEN-2001" and "result changed since the cursor" in err["message"]
    assert env == {}
    digest = cursor.split(".")[1]
    for bad in ("x", "2", f"2.{digest}0", f"+1.{digest}", f"02.{digest}", f"9.{digest}", f"5.{digest}"):
        code, _, err, _ = run(
            monkeypatch, tmp_path, "_echo", "--issues", "5", "--limit", "2", "--cursor", bad
        )
        assert code == 2 and err["code"] == "FEN-2001" and err["where"] == "--cursor", bad
    code, _, err, _ = run(monkeypatch, tmp_path, "_echo", "--issues", "5", "--cursor", cursor)
    assert code == 2 and err["code"] == "FEN-2001" and "--limit" in err["message"]


def test_command_without_a_list_and_bad_limits(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, err, _ = run(monkeypatch, tmp_path, "capabilities", "--no-tools", "--limit", "5")
    assert code == 2 and err["code"] == "FEN-2001" and env == {}
    for value in ("0", "-3"):
        code, _, err, _ = run(monkeypatch, tmp_path, "_echo", "--limit", value)
        assert code == 2 and err["code"] == "FEN-2001" and err["where"] == "--limit"
    assert run(monkeypatch, tmp_path, "_echo", "--limit", "many")[0] == 2


def test_paging_is_deterministic(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    first = run(monkeypatch, tmp_path, "_echo", "--issues", "5", "--limit", "2")[3]
    second = run(monkeypatch, tmp_path, "_echo", "--issues", "5", "--limit", "2")[3]
    assert without_elapsed(first) == without_elapsed(second)
    whole = [json.loads(run(monkeypatch, tmp_path, "_echo", "--issues", "5")[3])["issues"]][0]
    text = json.dumps(whole, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    assert json.loads(first)["result"]["page"]["next"] == "2." + hashlib.sha256(text.encode()).hexdigest()[:8]


def test_fields_apply_after_paging(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _, _ = run(
        monkeypatch, tmp_path, "_echo", "--issues", "5", "--limit", "2", "--fields", "page.total"
    )
    assert code == 0 and env["result"] == {"page": {"total": 5}} and len(env["issues"]) == 2
    code, env, _, _ = run(monkeypatch, tmp_path, "_echo", "--issues", "5", "--limit", "2", "--fields", "echo")
    assert code == 0 and "page" not in env["result"] and len(env["issues"]) == 2


def test_capabilities_list_the_paged_commands(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _, env, _, _ = run(monkeypatch, tmp_path, "capabilities", "--no-tools")
    paged = {c["name"]: (c["paged"], c["default_limit"]) for c in env["result"]["commands"] if "paged" in c}
    assert paged == {
        "_echo": ("issues", None),
        "analyze": ("issues", None),
        "check": ("issues", None),
        "diff": ("differences", 200),
        "manifest": ("differences|artifacts", None),
        "neighbors": ("neighbors", None),
        "net": ("nets|net.pads", None),
        "region": ("items", None),
    }
    assert {name for name, command in discover().items() if command.paged} == set(paged)


def test_check_pages_its_issues(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = tmp_path / "dup.kicad_pcb"
    board.write_text(TWO_LAYER.read_text(encoding="utf-8").replace('"Reference" "D1"', '"Reference" "R1"'))
    stages = ("--stages", "model.validate,erc.lite")
    code, whole, _, _ = run(monkeypatch, tmp_path, "check", str(board), *stages)
    assert len(whole["issues"]) >= 2
    paged_code, env, _, _ = run(monkeypatch, tmp_path, "check", str(board), *stages, "--limit", "1")
    assert paged_code == code and env["ok"] is whole["ok"]
    assert env["issues"] == whole["issues"][:1] and env["result"]["page"]["total"] == len(whole["issues"])
    assert env["result"]["stages"] == whole["result"]["stages"]


def _five_differences(tmp_path: Path) -> Path:
    """A copy of the authored board with five differences: one footprint moved, and one track and one
    via changed, each of which is one removed and one added."""
    text = TWO_LAYER.read_text(encoding="utf-8")
    for old, new in (
        ("(at 20 15 90)", "(at 21 15 90)"),
        ("(width 0.4)", "(width 0.5)"),
        ("(drill 0.3)", "(drill 0.2)"),
    ):
        assert text.count(old) == 1, old
        text = text.replace(old, new)
    folder = tmp_path / "copy"
    folder.mkdir()
    other = folder / TWO_LAYER.name
    other.write_text(text, encoding="utf-8", newline="\n")
    return other


def test_page_of_differences(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    other = _five_differences(tmp_path)
    code, whole, _, _ = run(monkeypatch, tmp_path, "diff", str(TWO_LAYER), str(other))
    total = whole["result"]["total"]
    assert code == 0 and total == 5 and whole["result"]["truncated"] is False
    assert whole["result"]["page"] == {
        "path": "differences",
        "limit": 200,
        "offset": 0,
        "total": total,
        "next": None,
    }

    code, env, _, _ = run(monkeypatch, tmp_path, "diff", str(TWO_LAYER), str(other), "--limit", "2")
    result = env["result"]
    assert code == 0 and result["differences"] == whole["result"]["differences"][:2]
    assert result["total"] == total and result["truncated"] is True and result["page"]["next"] is not None
    assert result["summary"] == whole["result"]["summary"] and result["equal"] is False
    code, env, _, _ = run(
        monkeypatch,
        tmp_path,
        "diff",
        str(TWO_LAYER),
        str(other),
        "--limit",
        "2",
        "--cursor",
        result["page"]["next"],
    )
    assert env["result"]["differences"] == whole["result"]["differences"][2:4]
    assert env["result"]["page"]["offset"] == 2 and env["result"]["truncated"] is True


def test_views_page_their_lists(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _, _ = run(monkeypatch, tmp_path, "net", str(TWO_LAYER), "--limit", "2")
    assert code == 0 and [n["name"] for n in env["result"]["nets"]] == ["GND", "LED_A"]
    assert env["result"]["page"]["path"] == "nets" and env["result"]["page"]["total"] == 3
    code, env, _, _ = run(monkeypatch, tmp_path, "net", str(TWO_LAYER), "LED_A", "--limit", "1")
    assert code == 0 and len(env["result"]["net"]["pads"]) == 1
    assert env["result"]["page"]["path"] == "net.pads" and env["result"]["page"]["total"] == 2
    code, env, _, _ = run(
        monkeypatch, tmp_path, "region", str(TWO_LAYER), "--box", "0mm,0mm,300mm,200mm", "--limit", "3"
    )
    assert len(env["result"]["items"]) == 3 and env["result"]["page"]["total"] == 13
    assert env["result"]["counts"]["pad"] == 4  # counts come from the whole result
    code, env, _, _ = run(
        monkeypatch, tmp_path, "neighbors", str(TWO_LAYER), "R1", "--radius", "50mm", "--limit", "1"
    )
    assert env["result"]["page"] == {"path": "neighbors", "limit": 1, "offset": 0, "total": 1, "next": None}


def test_page_function() -> None:
    items = list(range(5))
    first = page(items, 2)
    assert (first.items, first.offset, first.total) == ((0, 1), 0, 5) and first.next is not None
    assert page(items, 2, first.next).items == (2, 3)
    assert page([], 3) == dataclasses.replace(page([], 3), items=(), total=0, next=None)
    with pytest.raises(CursorError):
        page(items[:4], 2, first.next)
    with pytest.raises(ValueError):
        page(items, 0)


# --- concise output ---------------------------------------------------------------------------------


def test_concise_keeps_one_issue_per_code(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    args = ("_echo", "--issues", "2", "--issue", "info", "--issue", "warning")
    code, env, _, _ = run(monkeypatch, tmp_path, *args, "--format", "concise")
    assert code == 0 and _messages(env) == ["requested issue 1 of 2", "requested info issue"]
    assert env["result"]["issues_summary"] == [
        {"code": "echo.info", "count": 1, "by_severity": {"info": 1}},
        {"code": "echo.warning", "count": 3, "by_severity": {"warning": 3}},
    ]


def test_detailed_is_the_default(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    args = ("_echo", "--issues", "2", "--issue", "info", "--issue", "warning")
    code, plain, _, raw = run(monkeypatch, tmp_path, *args)
    assert code == 0 and len(plain["issues"]) == 4 and "issues_summary" not in plain["result"]
    detailed = run(monkeypatch, tmp_path, *args, "--format", "detailed")[3]
    assert without_elapsed(raw) == without_elapsed(detailed)
    assert run(monkeypatch, tmp_path, *args, "--format", "short")[0] == 2


def test_concise_exit_code_and_paging_after_it(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    args = ("_echo", "--issues", "3", "--issue", "info", "--issue", "error", "--issue", "error")
    code, env, err, _ = run(monkeypatch, tmp_path, *args, "--format", "concise", "--limit", "2")
    assert code == 5 and env["ok"] is False and "2 finding(s)" in err["message"]
    assert [i["code"] for i in env["issues"]] == ["echo.warning", "echo.info"]
    assert env["result"]["page"]["total"] == 3  # the list that concise leaves
    assert [s["count"] for s in env["result"]["issues_summary"]] == [2, 1, 3]
    code, env, _, _ = run(
        monkeypatch,
        tmp_path,
        *args,
        "--format",
        "concise",
        "--limit",
        "2",
        "--cursor",
        env["result"]["page"]["next"],
    )
    assert code == 5 and [i["code"] for i in env["issues"]] == ["echo.error"]
