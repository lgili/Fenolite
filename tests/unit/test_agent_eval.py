# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The agent evaluation harness without any tool and without any agent (capability agent-eval; c0081).

Tasks load and refuse a malformed copy; every reference solution builds in process with the expected
nets; the judge decides from files and never says ``passed`` without ``kicad-cli``; the call log passes
a call through unchanged and records no private value; the runner refuses a real agent in CI and
without ``--yes``, stops a runner whose time is over, and the record page keeps its form.

No test here starts an agent, reads a key or uses the network. The runners that stand for an agent are
small Python programs written into ``tmp_path``.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest
from _agenteval import ROOT, copy_task, hermetic, in_process, judge, real_fenolite, run, shim, tasks, tool

from fenolite.agent import guide

NAMES = ("custom-footprint", "fix-short", "led-indicator", "regulator-zone", "two-sided")
BUILT_SUFFIXES = (".kicad_pcb", ".kicad_sch", ".kicad_pro", ".gbr", ".drl")
IN_PROCESS = ("build", "place", "route")
"""The commands of a solution that need no external tool: the hermetic tests run these and no other."""
PAGE = ROOT / "docs" / "evidence" / "agent-eval.md"
SOURCES = ROOT / "docs" / "evidence" / "sources.md"


def _tracked(folder: str) -> list[str] | None:
    """The files git tracks under ``folder``; ``None`` outside a git checkout."""
    if not (ROOT / ".git").exists() or shutil.which("git") is None:
        return None
    listed = subprocess.run(
        ["git", "ls-files", folder], cwd=ROOT, capture_output=True, text=True, check=False
    )
    return listed.stdout.splitlines() if listed.returncode == 0 else None


# --- tasks ----------------------------------------------------------------------------------------


def test_tasks_load() -> None:
    """Scenario "Tasks load"."""
    assert tasks.names() == NAMES
    titles = [page.title for page in guide.pages()]
    topics = [page.topic for page in guide.pages()]
    for name in NAMES:
        task = tasks.load(name)
        assert task.name == name and task.title
        assert len(task.prompt.split()) <= 300, name
        assert "fenolite" not in task.prompt.lower(), name
        assert "--" not in task.prompt, name
        for ref in task.expect.refs():
            assert re.search(rf"\b{re.escape(ref)}\b", task.prompt), (name, ref)
        assert task.expect.project in task.prompt, name
        for pattern in task.expect.outputs:
            assert tasks.output_folder(pattern) in task.prompt, (name, pattern)
        for title in titles:
            assert title not in task.prompt, (name, title)
        for topic in topics:
            assert f"guide {topic}" not in task.prompt, (name, topic)
        assert 1 <= task.minutes <= 60
        assert task.commands(), name
        assert all(line.split()[0] == "fenolite" for line in (*task.commands(), *task.prepare)), name


def test_tasks_budgets_and_routers() -> None:
    """Decision 9: 20 minutes, 30 for ``custom-footprint``; no solution needs an external router."""
    minutes = {name: tasks.load(name).minutes for name in NAMES}
    assert minutes == {**dict.fromkeys(NAMES, 20), "custom-footprint": 30}
    assert sum(minutes.values()) == 110
    for name in NAMES:
        task = tasks.load(name)
        for line in (*task.prepare, *task.commands()):
            words = line.split()
            assert "freerouting" not in words and "fetch" not in words, (name, line)
            if words[1] == "route":
                assert words[words.index("--router") + 1] == "direct", (name, line)


def test_tasks_parts_are_catalog_or_authored() -> None:
    """Every part of every script is an id of the built-in catalog or of a library the script authors."""
    scripts = sorted(tasks.TASKS_DIR.rglob("*.py"))
    assert len(scripts) == 5
    for script in scripts:
        text = script.read_text(encoding="utf-8")
        authored = set(re.findall(r'(?:Footprint|Symbol)\("([A-Za-z0-9_]+)"', text))
        for library in re.findall(r'"([A-Za-z0-9_]+):[A-Za-z0-9_.]+"', text):
            assert library == "Fenolite" or library in authored, (script.name, library)


def test_tasks_folder_holds_no_built_project() -> None:
    """No task folder holds a built project, on disk or in git; the README names the licence."""
    built = [path for path in tasks.TASKS_DIR.rglob("*") if path.suffix in BUILT_SUFFIXES]
    assert built == []
    tracked = _tracked("tools/agent_eval/tasks")
    if tracked is not None:
        assert [name for name in tracked if name.endswith(BUILT_SUFFIXES)] == []
    readme = (tasks.TASKS_DIR / "README.md").read_text(encoding="utf-8")
    assert "CC0-1.0" in readme
    assert "private project" in readme and "organisation" in readme


@pytest.mark.parametrize(
    ("change", "key"),
    [
        ({'max_size = ["40mm", "30mm"]': "max_size = [40, 30]"}, "max_size"),
        ({'LED_A = ["R1-2", "D1-1"]': 'LED_A = ["R1-2", "D1-1", "R1-1"]'}, "R1-1"),
        ({'project = "board/build"\n': ""}, "expect.project"),
        ({"copper_layers = 2": "copper_layers = 2\nrouter = 1"}, "expect.router"),
        ({"minutes = 20": "minutes = 90"}, "budget.minutes"),
        ({"minutes = 20": "minutes = true"}, "budget.minutes"),
        ({"copper_layers = 2": "copper_layers = 3"}, "copper_layers"),
        ({'project = "board/build"': 'project = "../board/build"'}, "expect.project"),
        ({"Make a small": "Run fenolite to make a small"}, "fenolite"),
        ({"Make a small": "Pass --confirm to make a small"}, "command line"),
        ({"R1, a chip resistor": "A chip resistor", "R1 pin": "its pin"}, "R1"),
        ({"- board/fab: the fabrication": "- there: the fabrication"}, "board/fab"),
        ({'GND = ["D1-2", "J1-2"]': 'GND = ["D1-2", "J1 2"]'}, "REF-PIN"),
    ],
)
def test_tasks_malformed(tmp_path: Path, change: dict[str, str], key: str) -> None:
    """Scenario "Malformed task is refused": the error names the task and the key."""
    root = copy_task("led-indicator", tmp_path, change)
    with pytest.raises(ValueError, match="led-indicator") as caught:
        tasks.load("led-indicator", root)
    assert key in str(caught.value)


def test_tasks_malformed_folder(tmp_path: Path) -> None:
    root = copy_task("led-indicator", tmp_path)
    assert tasks.load("led-indicator", root).name == "led-indicator"
    long = " ".join(["word"] * 301)
    with pytest.raises(ValueError, match="more than 300"):
        tasks.check_prompt(long, tasks.load("led-indicator").expect, "t")
    (root / "led-indicator" / "solution" / "commands.txt").write_text("kicad-cli version\n", encoding="utf-8")
    with pytest.raises(ValueError, match=r"led-indicator.*commands\.txt"):
        tasks.load("led-indicator", root)
    (root / "led-indicator" / "solution" / "commands.txt").unlink()
    with pytest.raises(ValueError, match=r"led-indicator.*commands\.txt"):
        tasks.load("led-indicator", root)
    with pytest.raises(ValueError, match="task.toml is missing"):
        tasks.load("no-such-task", root)
    with pytest.raises(ValueError, match="task name"):
        tasks.load("../led-indicator", root)


def test_tasks_lengths() -> None:
    assert tasks.length_nm("40mm") == 40_000_000
    assert tasks.length_nm("0.5 mm") == 500_000
    assert tasks.length_nm("100mil") == 2_540_000
    for bad in (40, "40", "mm", "-1mm", "0mm", "0.0000001mm", True):
        with pytest.raises(ValueError):
            tasks.length_nm(bad)
    assert tasks.output_folder("board/fab/**/*.gbr") == "board/fab"
    assert tasks.split_ref_pin("U1-3") == ("U1", "3")


# --- the starting project and the solutions --------------------------------------------------------


def _play(task: Any, work: Path) -> list[dict[str, Any]]:
    """Prepare the task and play the tool-free lines of its solution in this process."""
    assert run.prepare(task, work, "fenolite") is None
    run.copy_tree(task.solution_files, work)
    envelopes: list[dict[str, Any]] = []
    for line in task.commands():
        words = line.split()
        if words[1] not in IN_PROCESS:
            continue
        code, envelope, said = in_process(words[1:], work)
        assert code == 0, (line, said)
        envelopes.append(envelope)
    return envelopes


def test_prepare_fix_short(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Starting project is built on the code under test"."""
    hermetic(monkeypatch, tmp_path)
    task = tasks.load("fix-short")
    assert len(task.prepare) == 2
    work = tmp_path / "work"
    assert run.prepare(task, work, "fenolite") is None
    assert (work / "board" / "design.py").is_file()
    assert judge.find_board(work / "board" / "build") is not None
    code, envelope, _ = in_process(
        ["check", "board/build", "--stages", "model.validate,copper.clearance", "--json"], work
    )
    assert code == 5
    errors = [issue["code"] for issue in envelope["issues"] if issue["severity"] == "error"]
    assert errors == ["copper.short"]
    tracked = _tracked("tools/agent_eval/tasks")
    if tracked is not None:
        assert [name for name in tracked if name.endswith(".kicad_pcb")] == []


def test_prepare_failure_is_reported(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A ``prepare`` line that fails is returned, and the lines after it do not run."""
    ran: list[list[str]] = []

    def line(argv: list[str], cwd: Path, env: object = None) -> int:
        ran.append(list(argv))
        return 3

    monkeypatch.setattr(run, "run_line", line)
    task = tasks.load("fix-short")
    assert run.prepare(task, tmp_path / "work", "fenolite") == task.prepare[0]
    assert len(ran) == 1 and ran[0][:2] == ["fenolite", "build"]


@pytest.mark.parametrize("name", NAMES)
def test_solutions_build_with_the_expected_nets(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, name: str
) -> None:
    """Scenario "Solutions build with the expected nets"."""
    hermetic(monkeypatch, tmp_path)
    task = tasks.load(name)
    work = tmp_path / "work"
    envelopes = _play(task, work)
    assert envelopes, name
    for envelope in envelopes:
        assert [issue for issue in envelope["issues"] if issue["severity"] == "error"] == []
    for check in (
        judge.check_project(work, task.expect),
        judge.check_nets(work, task.expect),
        judge.check_board(work, task.expect),
    ):
        assert check.passed, (name, check)
    assert not (work / "solution").exists()


# --- the judge ------------------------------------------------------------------------------------

LED = tasks.TASKS_DIR / "led-indicator" / "solution" / "files" / "board" / "design.py"


def _built(tmp_path: Path, change: dict[str, str] | None = None, script: str | None = None) -> Path:
    """A work folder with the solution of ``led-indicator`` built and routed in process; ``change``
    replaces text of its script, ``script`` replaces the script."""
    work = tmp_path / "work"
    (work / "board").mkdir(parents=True)
    text = LED.read_text(encoding="utf-8") if script is None else script
    for old, new in (change or {}).items():
        assert old in text, old
        text = text.replace(old, new)
    (work / "board" / "design.py").write_text(text, encoding="utf-8", newline="\n")
    code, _, said = in_process(
        ["build", "board/design.py", "--out", "board/build", "--confirm", "--json"], work
    )
    assert code == 0, said
    return work


def _outputs(work: Path) -> None:
    for name in ("gerbers/board-F_Cu.gbr", "drill/board-PTH.drl"):
        path = work / "board" / "fab" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("made by the test\n", encoding="utf-8")


def _snapshot(folder: Path) -> dict[str, bytes]:
    return {
        path.relative_to(folder).as_posix(): path.read_bytes() for path in folder.rglob("*") if path.is_file()
    }


def test_judge_nets_wrong(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Wrong nets fail": ``R1-2`` on the net of ``J1-2``."""
    hermetic(monkeypatch, tmp_path)
    change = {
        "connect(led_a, r1[2], d1[1])": "connect(led_a, d1[1])",
        "d1[2], j1[2])": "d1[2], j1[2], r1[2])",
    }
    work = _built(tmp_path, change)
    check = judge.check_nets(work, tasks.load("led-indicator").expect)
    assert not check.passed
    assert "R1-2" in check.detail


def test_judge_nets_names_do_not_matter(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Names do not matter"."""
    hermetic(monkeypatch, tmp_path)
    work = _built(tmp_path, {'Net("VIN"), Net("LED_A"), Net("GND")': 'Net("A"), Net("B"), Net("C")'})
    check = judge.check_nets(work, tasks.load("led-indicator").expect)
    assert check.passed, check


def test_judge_nets_pin_names_are_resolved(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A script that names a pin by its name gives the same groups as one that uses the number."""
    hermetic(monkeypatch, tmp_path)
    work = _built(
        tmp_path, {"r1[2], d1[1])": 'r1[2], d1["A"])', "connect(gnd, d1[2]": 'connect(gnd, d1["K"]'}
    )
    check = judge.check_nets(work, tasks.load("led-indicator").expect)
    assert check.passed, check


TWO_PADS = """\
from fenolite.dsl import Design, Net, Part, connect, mm

design = Design("board")
design.board(mm(30), mm(20))
u1 = Part("U1", "Fenolite:Potentiometer", footprint="Fenolite:SOT23_5", value="P", pad_map={"3": ("3", "5")})
r1 = Part("R1", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="1k")
design.add(u1, r1)
connect(Net("N"), u1[3], r1[1])
u1.place(mm(10), mm(10))
r1.place(mm(20), mm(10))
"""


def test_judge_nets_pin_with_two_pads(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "A pin with two pads is one entry"."""
    hermetic(monkeypatch, tmp_path)
    work = _built(tmp_path, script=TWO_PADS)
    size, outputs = (30_000_000, 20_000_000), ("board/fab/*.gbr",)
    as_pin = tasks.Expect("board/build", 2, size, outputs, {"N": ("U1-3", "R1-1")})
    check = judge.check_nets(work, as_pin)
    assert check.passed, check
    as_pad = tasks.Expect("board/build", 2, size, outputs, {"N": ("U1-5", "R1-1")})
    check = judge.check_nets(work, as_pad)
    assert not check.passed
    assert "U1-5" in check.detail


def test_judge_without_kicad(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Without KiCad a run is not judged": ``unjudged``, never ``passed``; nothing is written."""
    hermetic(monkeypatch, tmp_path)
    task = tasks.load("led-indicator")
    work = _built(tmp_path)
    assert in_process(["route", "board/build", "--router", "direct", "--confirm", "--json"], work)[0] == 0
    _outputs(work)
    before = _snapshot(work)
    verdict = judge.judge(work, task, "fenolite")
    assert verdict.status == "unjudged"
    assert [check.name for check in verdict.checks] == list(judge.CHECKS)
    passed = {check.name: check.passed for check in verdict.checks}
    assert passed == {"project": True, "check": False, "nets": True, "board": True, "outputs": True}
    assert "kicad-cli" in verdict.checks[1].detail
    assert _snapshot(work) == before
    assert json.loads(json.dumps(verdict.as_dict()))["status"] == "unjudged"


def test_judge_without_kicad_and_another_failure_is_failed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``unjudged`` needs every other check to pass: without the outputs the verdict is ``failed``."""
    hermetic(monkeypatch, tmp_path)
    work = _built(tmp_path)
    verdict = judge.judge(work, tasks.load("led-indicator"), "fenolite")
    assert verdict.status == "failed"
    assert [check.name for check in verdict.checks if not check.passed] == ["check", "outputs"]
    assert "board/fab/**/*.gbr" in verdict.checks[4].detail


@pytest.mark.parametrize(
    ("code", "envelope", "status"),
    [
        (0, {"evidence": {"level": "INFERRED"}, "result": {"stages": []}, "issues": []}, "passed"),
        (
            5,
            {"evidence": {"level": "INFERRED"}, "issues": [{"code": "copper.short", "severity": "error"}]},
            "failed",
        ),
        (6, {"evidence": {"level": "UNVERIFIED"}}, "unjudged"),
        (1, {}, "failed"),
        (
            0,
            {
                "evidence": {"level": "INFERRED"},
                "result": {
                    "stages": [{"name": "drc.kicad", "status": "skipped", "reason": "kicad-cli not found"}]
                },
            },
            "unjudged",
        ),
    ],
)
def test_judge_status_follows_check(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, code: int, envelope: dict[str, Any], status: str
) -> None:
    """``passed`` only when ``fenolite check`` exits 0 with KiCad's stage run; exit 6 is ``unjudged``."""
    hermetic(monkeypatch, tmp_path)
    work = _built(tmp_path)
    _outputs(work)
    asked: list[list[str]] = []

    def command(argv: list[str], cwd: Path) -> judge.Completed:
        asked.append(list(argv))
        return judge.Completed(code, json.dumps(envelope), "")

    monkeypatch.setattr(judge, "run_command", command)
    verdict = judge.judge(work, tasks.load("led-indicator"), ["python", "-m", "fenolite"])
    assert verdict.status == status
    assert asked == [["python", "-m", "fenolite", "check", "board/build", "--json"]]
    assert verdict.evidence_level == envelope.get("evidence", {}).get("level")
    if status == "failed" and code == 5:
        assert "copper.short" in verdict.checks[1].detail


def test_judge_board_too_large(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Board too large": 50 mm by 30 mm for a limit of 40 mm by 30 mm."""
    hermetic(monkeypatch, tmp_path)
    work = _built(tmp_path, {"design.board(mm(30), mm(20))": "design.board(mm(50), mm(30))"})
    task = tasks.load("led-indicator")
    check = judge.check_board(work, task.expect)
    assert not check.passed
    assert "50 mm by 30 mm" in check.detail and "40 mm by 30 mm" in check.detail
    assert judge.judge(work, task, "fenolite").status == "failed"


def test_judge_board_orientation_and_layers(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The board may lie either way; another copper layer count does not pass."""
    hermetic(monkeypatch, tmp_path)
    work = _built(tmp_path, {"design.board(mm(30), mm(20))": "design.board(mm(28), mm(38))"})
    expect = tasks.load("led-indicator").expect
    assert judge.check_board(work, expect).passed
    four = tasks.Expect(expect.project, 4, expect.max_size, expect.outputs, expect.nets)
    check = judge.check_board(work, four)
    assert not check.passed and "2 copper layers, not 4" in check.detail


def test_judge_empty_folder(tmp_path: Path) -> None:
    """A check that cannot run because an earlier one failed says so; nothing is started."""
    work = tmp_path / "work"
    work.mkdir()
    verdict = judge.judge(work, tasks.load("led-indicator"), "no-such-program")
    assert verdict.status == "failed" and verdict.evidence_level is None
    details = {check.name: check.detail for check in verdict.checks}
    assert "does not exist" in details["project"]
    for name in ("check", "nets", "board"):
        assert details[name] == "not run: the check 'project' did not pass"
    (work / "board" / "build").mkdir(parents=True)
    assert "exactly one board file" in judge.check_project(work, tasks.load("led-indicator").expect).detail
    (work / "board" / "build" / "a.kicad_pcb").write_text("", encoding="utf-8")
    assert ".fenolite" in judge.check_project(work, tasks.load("led-indicator").expect).detail


# --- the call log ---------------------------------------------------------------------------------

ECHO = """\
import sys

data = sys.stdin.buffer.read()
sys.stdout.buffer.write(b"out:" + data)
sys.stdout.buffer.write(("|".join(sys.argv[1:]) + "\\n").encode())
sys.stderr.buffer.write(b"first line\\n\\xff\\xfe not text\\n")
sys.stderr.buffer.write(b'{"code": "FEN-9999", "message": "made by the test"}\\n')
raise SystemExit(7)
"""
ELAPSED = re.compile(r'"elapsed_ms": \d+')


def _call(
    program: Path, args: list[str], cwd: Path, env: dict[str, str] | None = None, data: bytes = b""
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [str(program), *args], cwd=cwd, env=env, input=data, capture_output=True, timeout=300, check=False
    )


def _log_env(real: Path, log: Path, **more: str) -> dict[str, str]:
    return {**os.environ, shim.ENV_REAL: str(real), shim.ENV_LOG: str(log), **more}


def _lines(log: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]


def test_shim_logs_and_passes_through(tmp_path: Path) -> None:
    """Scenario "Call is logged and passed through", with the ``fenolite`` of the test environment."""
    real = real_fenolite(tmp_path / "real")
    logged = shim.install(tmp_path / "shim dir", Path(sys.executable))
    log = tmp_path / "log" / "calls.jsonl"
    work = tmp_path / "work"
    work.mkdir()
    env = _log_env(real, log)

    first = ["capabilities", "--json", "--no-tools"]
    direct, through = _call(real, first, work), _call(logged, first, work, env)
    assert direct.returncode == through.returncode == 0
    assert ELAPSED.sub("", through.stdout.decode()) == ELAPSED.sub("", direct.stdout.decode())
    assert through.stderr == direct.stderr == b""

    second = ["build", "nothing.py", "--out", "x", "--confirm", "--json"]
    direct, through = _call(real, second, work), _call(logged, second, work, env)
    assert direct.returncode == through.returncode == 3
    assert through.stderr == direct.stderr
    assert ELAPSED.sub("", through.stdout.decode()) == ELAPSED.sub("", direct.stdout.decode())

    calls = _lines(log)
    assert [tuple(call) for call in calls] == [shim.LOG_KEYS, shim.LOG_KEYS]
    assert [(call["n"], call["argv"], call["exit"], call["error_code"]) for call in calls] == [
        (1, first, 0, None),
        (2, second, 3, "FEN-3004"),
    ]
    assert all(isinstance(call["elapsed_ms"], int) and call["elapsed_ms"] >= 0 for call in calls)
    assert list(work.iterdir()) == []


def test_shim_passes_bytes_arguments_and_exit_code(tmp_path: Path) -> None:
    """Standard input, standard output, standard error and the exit code are those of the real program,
    byte for byte, and arguments with blanks and quotes arrive as they were given."""
    real = tool(tmp_path / "real", ECHO)
    logged = shim.install(tmp_path / "it's a shim", Path(sys.executable))
    log = tmp_path / "calls.jsonl"
    data = b"\x00binary \xff input\r\nsecond line"
    args = ["one two", "--name=a b", "", "quo'te", "100mm,100mm"]
    if os.name == "nt":  # a .cmd launcher re-reads its command line: keep to what cmd.exe passes on
        args, data = ["one", "--name=a", "100mm,100mm"], b"plain input\n"
    direct = _call(real, args, tmp_path, data=data)
    through = _call(logged, args, tmp_path, _log_env(real, log), data)
    assert direct.returncode == through.returncode == 7
    assert through.stdout == direct.stdout
    assert through.stderr == direct.stderr
    assert through.stdout == b"out:" + data + "|".join(args).encode() + b"\n"
    (call,) = _lines(log)
    assert (call["n"], call["argv"], call["exit"], call["error_code"]) == (1, args, 7, "FEN-9999")
    again = _call(logged, ["second"], tmp_path, _log_env(real, log))
    assert again.returncode == 7
    assert [call["n"] for call in _lines(log)] == [1, 2]


def test_shim_log_holds_no_private_value(tmp_path: Path) -> None:
    """The privacy of the call log: no environment value, no user name, no path outside the work
    folder. A path inside the work folder is written relative to it; one outside keeps its name only."""
    real = tool(tmp_path / "real", ECHO)
    logged = shim.install(tmp_path / "shim", Path(sys.executable))
    log = tmp_path / "calls.jsonl"
    work = tmp_path / "work"
    (work / "board").mkdir(parents=True)
    home = tmp_path / "home" / "private-user-name"
    home.mkdir(parents=True)
    outside = home / "Documents" / "customer.kicad_pcb"
    secret = "sk-test-value-that-must-not-be-logged"
    env = _log_env(
        real, log, HOME=str(home), USERPROFILE=str(home), EVAL_TEST_SECRET=secret, USER="private-user-name"
    )
    args = [
        "check",
        str(work / "board" / "build"),
        str(outside),
        f"--out={outside.parent}",
        "--origin",
        "100mm,100mm",
        "relative/path.py",
    ]
    done = _call(logged, args, work, env)
    assert done.returncode == 7
    assert done.stdout.decode().rstrip().endswith("|".join(args)), "the real program gets the paths as given"
    text = log.read_text(encoding="utf-8")
    (call,) = _lines(log)
    assert tuple(call) == shim.LOG_KEYS
    assert call["argv"] == [
        "check",
        "board/build",
        "<outside>/customer.kicad_pcb",
        "--out=<outside>/Documents",
        "--origin",
        "100mm,100mm",
        "relative/path.py",
    ]
    for private in (secret, "private-user-name", str(home), str(tmp_path), str(work), str(Path.home())):
        assert private not in text, private
    assert json.dumps(str(tmp_path))[1:-1] not in text
    for name, value in os.environ.items():
        if len(value) >= 12 and name not in (shim.ENV_REAL, shim.ENV_LOG):
            assert value not in text, name


def test_shim_needs_its_two_variables(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Without either variable the call log exits 2 with a message that names the variable."""
    monkeypatch.delenv(shim.ENV_REAL, raising=False)
    monkeypatch.setenv(shim.ENV_LOG, str(tmp_path / "calls.jsonl"))
    assert shim.main(["check"]) == 2
    assert shim.ENV_REAL in capsys.readouterr().err
    monkeypatch.setenv(shim.ENV_REAL, str(tmp_path / "no-such-program"))
    monkeypatch.delenv(shim.ENV_LOG)
    assert shim.main(["check"]) == 2
    assert shim.ENV_LOG in capsys.readouterr().err
    monkeypatch.setenv(shim.ENV_LOG, str(tmp_path / "calls.jsonl"))
    assert shim.main(["check"]) == 127
    assert shim.ENV_REAL in capsys.readouterr().err
    assert not (tmp_path / "calls.jsonl").exists()


def test_shim_error_code_and_scrub(tmp_path: Path) -> None:
    assert shim.error_code(b'progress\n{"code": "FEN-3004", "message": "m"}\n') == "FEN-3004"
    assert shim.error_code(b'{"code": "FEN-3004"}\nnot the last line\n') is None
    assert shim.error_code(b"") is None and shim.error_code(b"[1]\n") is None
    assert shim.error_code(b'{"code": 5}\n') is None
    assert shim.scrub("--json", tmp_path) == "--json"
    assert shim.scrub("R1=15mm,14mm", tmp_path) == "R1=15mm,14mm"
    assert shim.scrub(str(tmp_path / "a" / "b.py"), tmp_path) == "a/b.py"
    assert shim.scrub(f"--out={tmp_path.parent / 'x'}", tmp_path) == "--out=<outside>/x"
    assert shim.__doc__ is not None and "import fenolite" not in Path(shim.__file__).read_text(
        encoding="utf-8"
    )


# --- the runner -----------------------------------------------------------------------------------

FAKE_ROW = """
[fake-agent]
argv = ["{program}", "{{prompt}}"]
version_argv = ["{program}", "--version"]
skill = "none"
source = "S-0618"
budget_flag = ["--max-cost", "1"]
"""
SLEEPER = """\
import json, os, sys, time
from pathlib import Path

if sys.argv[1:] == ["--version"]:
    print("sleeper 1.2.3")
    raise SystemExit(0)
seen = {"argv": sys.argv[1:], "path": os.environ["PATH"].split(os.pathsep)[:2],
        "real": os.environ.get("FENOLITE_EVAL_REAL"), "log": os.environ.get("FENOLITE_EVAL_LOG"),
        "cwd": os.getcwd()}
Path("seen.json").write_text(json.dumps(seen), encoding="utf-8")
time.sleep(120)
"""


def _runners(tmp_path: Path, program: str = "no-such-agent-program") -> Path:
    path = tmp_path / "runners.toml"
    text = run.RUNNERS.read_text(encoding="utf-8") + FAKE_ROW.format(program=program)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def _no_start(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Fail the test when the runner builds, installs or starts anything; returns what was tried."""
    tried: list[str] = []

    def refuse(name: str) -> Any:
        def call(*args: object, **kwargs: object) -> None:
            tried.append(name)
            raise AssertionError(f"{name} was called")

        return call

    for name in ("build_wheel", "make_place", "execute", "start_agent", "run_line"):
        monkeypatch.setattr(run, name, refuse(name))
    monkeypatch.setattr(subprocess, "Popen", refuse("Popen"))
    monkeypatch.setattr(subprocess, "run", refuse("subprocess.run"))
    return tried


def test_summary_of_calls() -> None:
    """Scenario "Summary of calls"."""
    calls = [
        {
            "n": n,
            "argv": ["build", "board/design.py", "--json"],
            "exit": 0,
            "elapsed_ms": 5,
            "error_code": None,
        }
        for n in range(1, 6)
    ]
    calls[2] = {
        "n": 3,
        "argv": ["--json", "build", "x.py"],
        "exit": 3,
        "elapsed_ms": 5,
        "error_code": "FEN-3004",
    }
    summary = run.summarise(calls)
    assert summary == {
        "calls": 5,
        "calls_by_exit": {"0": 4, "3": 1},
        "first_failure": {"n": 3, "command": "build", "error_code": "FEN-3004"},
    }
    assert run.summarise([]) == {"calls": 0, "calls_by_exit": {}, "first_failure": None}


def test_summary_reads_a_log_file(tmp_path: Path) -> None:
    log = tmp_path / "calls.jsonl"
    assert run.read_log(log) == []
    shim.append(log, ["check", "board/build"], 5, 12, "FEN-5001")
    shim.append(log, ["check", "board/build"], 0, 12, None)
    summary = run.summarise(run.read_log(log))
    assert summary["calls"] == 2 and summary["calls_by_exit"] == {"0": 1, "5": 1}
    assert summary["first_failure"] == {"n": 1, "command": "check", "error_code": "FEN-5001"}


@pytest.mark.parametrize("value", ["true", "1"])
def test_ci_guard(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str], value: str
) -> None:
    """Scenario "Real agents never run in CI": exit 2 before anything is built, with or without --yes."""
    tried = _no_start(monkeypatch)
    monkeypatch.setenv("CI", value)
    runners = _runners(tmp_path)
    for more in ([], ["--yes"], ["--yes", "--record"]):
        code = run.main(["--task", "led-indicator", "--runner", "fake-agent", *more], runners=runners)
        said = capsys.readouterr()
        assert code == 2
        assert "CI" in said.err and "fake-agent" in said.err
        assert said.out == ""
    assert tried == []


def test_ci_guard_covers_every_real_row(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Every row of the committed ``runners.toml`` but ``replay`` is refused while ``CI`` is set."""
    tried = _no_start(monkeypatch)
    monkeypatch.setenv("CI", "true")
    rows = run.load_runners()
    assert "replay" in rows and not rows["replay"].real
    real = [name for name, row in rows.items() if row.real]
    assert real == ["claude-code"]
    for name in real:
        assert run.main(["--task", "led-indicator", "--runner", name, "--yes"]) == 2
        assert "CI" in capsys.readouterr().err
    assert tried == []


def test_consent_is_needed_for_a_real_agent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Outside CI a real agent does not start without ``--yes``: the budget is printed, then exit 2."""
    tried = _no_start(monkeypatch)
    monkeypatch.delenv("CI", raising=False)
    code = run.main(["--task", "led-indicator", "--runner", "fake-agent"], runners=_runners(tmp_path))
    said = capsys.readouterr()
    assert code == 2
    assert said.out.splitlines() == [
        "task: led-indicator (LED indicator)",
        "runner: fake-agent",
        "time budget: 20 minutes",
        "cost cap: --max-cost 1",
        "isolation: none; the record will say 'not isolated'",
    ]
    assert "--yes" in said.err and "costs money" in said.err and "nothing was started" in said.err
    assert tried == []


def test_consent_with_yes_reaches_the_start(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The same command with ``--yes`` is the one that goes on: the guard is what held it back. The
    test stops it at the first step, so nothing is built or started here either."""
    tried = _no_start(monkeypatch)
    monkeypatch.delenv("CI", raising=False)
    with pytest.raises(AssertionError, match="build_wheel was called"):
        run.main(["--task", "led-indicator", "--runner", "fake-agent", "--yes"], runners=_runners(tmp_path))
    assert tried == ["build_wheel"]


def test_unconfigured_row_is_refused(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The committed row of the first real agent cannot start, even with ``--yes``, until it is completed."""
    tried = _no_start(monkeypatch)
    monkeypatch.delenv("CI", raising=False)
    row = run.load_runners()["claude-code"]
    assert row.unconfigured and row.version_argv == () and row.source == "S-0618"
    assert run.main(["--task", "led-indicator", "--runner", "claude-code", "--yes"]) == 2
    said = capsys.readouterr()
    assert "not configured" in said.err and said.out == ""
    assert tried == []


def test_usage_guards(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``--task all`` needs ``--yes``; an unknown task, runner or repeat count is refused."""
    tried = _no_start(monkeypatch)
    monkeypatch.delenv("CI", raising=False)
    for argv, word in (
        (["--task", "all", "--runner", "replay"], "--yes"),
        (["--task", "no-such-task", "--runner", "replay"], "no-such-task"),
        (["--task", "led-indicator", "--runner", "no-such-runner"], "no-such-runner"),
        (["--task", "led-indicator", "--runner", "replay", "--repeat", "0"], "--repeat"),
    ):
        assert run.main(argv, runners=_runners(tmp_path)) == 2, argv
        assert word in capsys.readouterr().err
    assert tried == []


def test_runner_rows_are_well_formed(tmp_path: Path) -> None:
    """``runners.toml`` holds ``replay``; a real row names a registered source; a malformed row is refused."""
    rows = run.load_runners()
    sources = SOURCES.read_text(encoding="utf-8")
    for row in rows.values():
        if row.real:
            assert f"\n| {row.source} | " in sources, row.name
            assert any("{prompt}" in word for word in row.argv)
    assert rows["replay"].isolated and rows["claude-code"].isolated
    fake = run.load_runners(_runners(tmp_path))["fake-agent"]
    assert not fake.isolated
    assert fake.command("P", tmp_path) == ["no-such-agent-program", "--max-cost", "1", "P"]
    for text, word in (
        ('[x]\nargv = ["a", "{prompt}"]\nskill = "none"\nsource = "S-0618"\n', "version_argv"),
        ('[x]\nargv = ["a"]\nversion_argv = ["a"]\nskill = "none"\nsource = "S-0618"\n', "prompt"),
        ('[x]\nargv = ["a", "{prompt}"]\nversion_argv = ["a"]\nskill = "all"\nsource = "S-0618"\n', "skill"),
        (
            '[x]\nargv = ["a", "{prompt}"]\nversion_argv = ["a"]\nskill = "none"\nsource = "S-0618"\nk = 1\n',
            "unknown key k",
        ),
        (
            '[x]\nargv = ["a", "{prompt}"]\nversion_argv = ["a"]\nskill = "none"\nsource = "a page"\n',
            "source",
        ),
        (
            '[x]\nargv = ["a", "{prompt}"]\nversion_argv = ["a"]\nskill = "none"\nsource = "S-0618"\n',
            "replay",
        ),
    ):
        path = tmp_path / "bad.toml"
        head = "" if word == "replay" else '[replay]\nskill = "none"\n'
        path.write_text(head + text, encoding="utf-8")
        with pytest.raises(ValueError, match=word):
            run.load_runners(path)


def test_replay_stops_at_the_first_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """``replay`` copies the solution's files and runs the lines in order, through the program it is
    given, until one does not exit 0."""
    ran: list[list[str]] = []

    def line(argv: list[str], cwd: Path, env: object = None) -> int:
        ran.append(list(argv))
        return 0 if len(ran) < 2 else 3

    monkeypatch.setattr(run, "run_line", line)
    task = tasks.load("led-indicator")
    work = tmp_path / "work"
    work.mkdir()
    assert run.replay(task, work, tmp_path / "shim" / "fenolite") == [0, 3]
    assert (work / "board" / "design.py").is_file()
    assert [argv[0] for argv in ran] == [str(tmp_path / "shim" / "fenolite")] * 2
    assert [argv[1] for argv in ran] == ["build", "route"]
    assert ran[0][1:] == task.commands()[0].split()[1:]


def test_skill_install_follows_the_row(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    ran: list[list[str]] = []

    def line(argv: list[str], cwd: Path, env: object = None) -> int:
        ran.append(list(argv))
        return 0

    monkeypatch.setattr(run, "run_line", line)
    for skill in ("none", "agent:claude-code", "agents-md"):
        assert run.install_skill(run.Runner("r", skill=skill), tmp_path, "fenolite")
    assert ran == [
        ["fenolite", "skill", "install", "--agent", "claude-code", "--confirm"],
        ["fenolite", "skill", "install", "--agents-md", "--confirm"],
    ]


def test_skill_install_in_an_empty_folder(tmp_path: Path) -> None:
    """The two ways of a row install the guide as an outside user would, with the real command."""
    for skill, expected in (
        ("agent:claude-code", ".claude/skills/fenolite/SKILL.md"),
        ("agents-md", "AGENTS.md"),
    ):
        work = tmp_path / skill.replace(":", "-")
        work.mkdir()
        code, _, said = in_process(
            [
                "skill",
                "install",
                *(["--agents-md"] if skill == "agents-md" else ["--agent", skill[6:]]),
                "--confirm",
            ],
            work,
        )
        assert code == 0, said
        assert (work / expected).is_file()


def test_budget_stops_a_runner_that_sleeps(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Scenario "Time budget": the program is stopped, ``timed_out`` is true and the verdict is
    ``failed`` with the check ``project`` not passed. The program stands for an agent; it is a Python
    file of this test that sleeps."""
    program = tool(tmp_path / "agent", SLEEPER)
    real = real_fenolite(tmp_path / "real")
    place = run.Place(tmp_path / "place", real, Path(sys.executable))
    place.workdir.mkdir(parents=True)
    task = tasks.load("led-indicator")
    assert task.minutes == 20
    runner = run.Runner(
        "sleeper", (str(program), "{prompt}"), (str(program), "--version"), "none", "S-0618", ("--cap", "1")
    )
    started = time.monotonic()
    result = run.execute(task, runner, place, seconds=2, checkout=ROOT)
    assert time.monotonic() - started < 90
    assert result is not None
    assert tuple(result) == run.RESULT_KEYS
    assert result["timed_out"] is True
    assert result["verdict"]["status"] == "failed"
    assert result["verdict"]["checks"][0] == {
        "name": "project",
        "passed": False,
        "detail": "the folder board/build does not exist",
    }
    assert (result["task"], result["runner"], result["runner_version"]) == (
        "led-indicator",
        "sleeper",
        "sleeper 1.2.3",
    )
    assert result["isolated"] is False and result["calls"] == 0 and result["first_failure"] is None
    assert (result["model"], result["turns"], result["tokens"], result["cost"]) == (None, None, None, None)
    assert json.loads(place.result.read_text(encoding="utf-8")) == result
    assert place.result.parent == place.workdir.parent

    said = capsys.readouterr().out.splitlines()
    assert said[:4] == [
        "task: led-indicator (LED indicator)",
        "runner: sleeper",
        "time budget: 2 seconds",
        "cost cap: --cap 1",
    ]
    assert said[5].startswith("verdict: failed  task=led-indicator runner=sleeper calls=0 failed=0")
    assert said[5].endswith("(timed out)")

    seen = json.loads((place.workdir / "seen.json").read_text(encoding="utf-8"))
    assert seen["argv"][:2] == ["--cap", "1"]
    assert seen["argv"][2] == f"{run.FIRST_LINE}\n\n{task.prompt}"
    assert seen["path"] == [str(place.shim_dir), str(real.parent)]
    assert (seen["real"], seen["log"]) == (str(real), str(place.log))
    assert Path(seen["cwd"]).resolve() == place.workdir.resolve()
    assert sorted(path.name for path in place.workdir.iterdir()) == ["seen.json"], "no solution is copied"


def test_repeat_keep_and_exit_codes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``--repeat N`` runs the task N times, each in its own place; a place is removed unless ``--keep``
    is given; the exit code is 0 for passes, 5 for another verdict and 1 when a place cannot be
    prepared. The three steps that build, install and run are stand-ins here."""
    monkeypatch.delenv("CI", raising=False)
    places: list[Path] = []
    statuses: list[str | None] = []

    def build_wheel(checkout: Path | None = None) -> Path:
        folder = tmp_path / f"wheel-{len(list(tmp_path.glob('wheel-*')))}"
        folder.mkdir()
        (folder / "fenolite-0-py3-none-any.whl").write_bytes(b"")
        return folder / "fenolite-0-py3-none-any.whl"

    def make_place(wheel: Path, checkout: Path | None = None) -> Any:
        assert wheel.is_file()
        root = tmp_path / f"place-{len(places)}"
        (root / "work").mkdir(parents=True)
        places.append(root)
        return run.Place(root, root / "env" / "fenolite", Path(sys.executable))

    def execute(task: Any, runner: Any, place: Any, **more: object) -> dict[str, Any] | None:
        status = statuses.pop(0)
        return None if status is None else {**RESULT, "verdict": {"status": status, "checks": []}}

    monkeypatch.setattr(run, "build_wheel", build_wheel)
    monkeypatch.setattr(run, "make_place", make_place)
    monkeypatch.setattr(run, "execute", execute)
    page = tmp_path / "agent-eval.md"
    shutil.copyfile(PAGE, page)
    monkeypatch.setattr(run, "RECORD", page)

    statuses[:] = ["passed", "passed", "passed"]
    assert run.main(["--task", "led-indicator", "--runner", "replay", "--repeat", "3", "--record"]) == 0
    assert len(places) == 3 and len(set(places)) == 3
    assert not any(place.exists() for place in places)
    assert list(tmp_path.glob("wheel-*/*.whl")) == []
    assert capsys.readouterr().out.count("recorded: |") == 3
    assert len(_runs(page.read_text(encoding="utf-8"))) == 5

    statuses[:] = ["passed", "unjudged"]
    assert run.main(["--task", "led-indicator", "--runner", "replay", "--repeat", "2", "--keep"]) == 5
    said = capsys.readouterr().out
    assert [f"kept: {place}" for place in places[3:]] == said.splitlines()
    assert all(place.exists() for place in places[3:])

    statuses[:] = [None]
    assert run.main(["--task", "led-indicator", "--runner", "replay"]) == 1
    assert not places[-1].exists()

    statuses[:] = ["passed"] * 5
    assert run.main(["--task", "all", "--runner", "replay", "--yes"]) == 0
    assert len(places) == 11 and statuses == []


def test_agent_output_is_read_as_the_row_says(tmp_path: Path) -> None:
    place = run.Place(tmp_path, tmp_path / "bin" / "fenolite", Path(sys.executable))
    runner = run.Runner("r", ("a", "{prompt}"), report={"cost": "total_cost_usd", "model": "usage.model"})
    assert run.read_report(runner, place) == {"model": None, "turns": None, "tokens": None, "cost": None}
    (tmp_path / "agent.stdout").write_text(
        '{"total_cost_usd": 0.42, "usage": {"model": "m-1"}}', encoding="utf-8"
    )
    assert run.read_report(runner, place) == {"model": "m-1", "turns": None, "tokens": None, "cost": 0.42}
    (tmp_path / "agent.stdout").write_text("not json", encoding="utf-8")
    assert run.read_report(runner, place)["cost"] is None


def test_agent_environment(tmp_path: Path) -> None:
    place = run.Place(tmp_path, tmp_path / "env" / "bin" / "fenolite", Path(sys.executable))
    launcher = tmp_path / "shim" / "fenolite"
    env = run.agent_env(place, launcher, {"PATH": "sys", "VIRTUAL_ENV": "v", "KEEP": "k"})
    assert env["PATH"].split(os.pathsep) == [str(launcher.parent), str(place.fenolite.parent), "sys"]
    assert env[shim.ENV_REAL] == str(place.fenolite) and env[shim.ENV_LOG] == str(place.log)
    assert "VIRTUAL_ENV" not in env and env["KEEP"] == "k"


def test_the_tool_reads_no_key_and_calls_no_service() -> None:
    """The harness itself names no credential variable and imports no network module."""
    for name in ("run.py", "judge.py", "shim.py", "tasks.py"):
        text = (ROOT / "tools" / "agent_eval" / name).read_text(encoding="utf-8")
        for word in (
            "urllib",
            "http.client",
            "socket",
            "requests",
            "API_KEY",
            "TOKEN",
            "anthropic",
            "openai",
        ):
            assert word not in text, (name, word)


# --- the record -----------------------------------------------------------------------------------

SECTIONS = ["How to read this page", "Runs", "Findings", "Not measured"]
PATH_LIKE = re.compile(r"^(/|[A-Za-z]:[\\/]|~)")


def _runs(text: str) -> list[list[str]]:
    """The cells of each line of the table of ``Runs``."""
    section = text.split("\n## Runs\n", 1)[1].split("\n## ", 1)[0]
    return [
        [cell.strip() for cell in line.strip().strip("|").split("|")]
        for line in section.splitlines()
        if line.startswith("|")
    ]


RESULT = {
    "task": "led-indicator",
    "runner": "replay",
    "runner_version": "builtin",
    "model": None,
    "isolated": True,
    "fenolite_version": "0.2.1",
    "commit": "abc1234",
    "verdict": {"status": "passed", "evidence_level": "INFERRED", "checks": []},
    "minutes": 0.3,
    "timed_out": False,
    "calls": 4,
    "calls_by_exit": {"0": 4},
    "first_failure": None,
    "turns": None,
    "tokens": None,
    "cost": None,
}


def test_record_page_is_well_formed() -> None:
    """Scenario "Page is well formed"."""
    text = PAGE.read_text(encoding="utf-8")
    assert re.findall(r"^## (.+)$", text, flags=re.MULTILINE) == SECTIONS
    rows = _runs(text)
    assert tuple(rows[0]) == run.COLUMNS and len(run.COLUMNS) == 10
    assert set("".join(rows[1])) == {"-"}
    for row in rows[2:]:
        assert len(row) == 10, row
        for cell in row:
            assert PATH_LIKE.match(cell) is None, cell
    for line in text.splitlines():
        if line.startswith("|"):
            for cell in line.strip().strip("|").split("|"):
                assert PATH_LIKE.match(cell.strip()) is None, line
    for phrase in (
        "A row is one sample",
        "`fenolite check`",
        "expected groups of `REF-PIN`",
        "The tasks prescribe the netlist",
        "No row supports a release claim",
        "No path, no prompt and no transcript",
    ):
        assert phrase in text, phrase
    assert str(ROOT) not in text and "/Users/" not in text and "/home/" not in text
    for name in NAMES:
        assert tasks.load(name).prompt.splitlines()[0] not in text


def test_record_page_claims_nothing_beyond_its_rows() -> None:
    """Task 5.1: with no run recorded the page says so, and every finding belongs to a recorded run."""
    text = PAGE.read_text(encoding="utf-8")
    runs = _runs(text)[2:]
    findings = text.split("\n## Findings\n", 1)[1].split("\n## ", 1)[0]
    found = [line for line in findings.splitlines() if line.startswith("|")][2:]
    if not runs:
        assert found == []
        assert "No run with a real agent is recorded yet" in text
    for row in runs:
        assert row[5].split()[0] in ("passed", "failed", "unjudged"), row


def test_recording_a_run(tmp_path: Path) -> None:
    """Scenario "Recording a run": one more row of ten cells, every other line unchanged."""
    page = tmp_path / "agent-eval.md"
    shutil.copyfile(PAGE, page)
    before = page.read_text(encoding="utf-8").split("\n")
    row = run.record(RESULT, page, date="2026-10-08")
    after = page.read_text(encoding="utf-8").split("\n")
    assert len(after) == len(before) + 1
    assert [line for line in after if line != row] == before
    cells = _runs("\n".join(after))[-1]
    assert cells == ["2026-10-08", "abc1234", "replay", "-", "led-indicator", "passed", "4", "0", "0.3", "-"]
    assert after.index(row) == before.index("|---|---|---|---|---|---|---|---|---|---|") + 1

    failed = {
        **RESULT,
        "runner": "some-agent",
        "runner_version": "9.9 (test)",
        "isolated": False,
        "model": "model|x",
        "verdict": {"status": "failed", "checks": []},
        "timed_out": True,
        "calls": 7,
        "calls_by_exit": {"0": 5, "3": 1, "5": 1},
        "first_failure": {"n": 2, "command": "build", "error_code": "FEN-3004"},
    }
    second = run.record(failed, page, date="2026-10-09")
    rows = _runs(page.read_text(encoding="utf-8"))
    assert len(rows) == 4 and all(len(cells) == 10 for cells in rows)
    assert rows[-1] == [
        "2026-10-09", "abc1234", "some-agent 9.9 (test) (not isolated)", "model/x", "led-indicator",
        "failed (timed out)", "7", "2", "0.3", "call 2: build FEN-3004",
    ]  # fmt: skip
    assert page.read_text(encoding="utf-8").split("\n").index(second) == after.index(row) + 1
    assert run.NOT_ISOLATED in second and str(tmp_path) not in page.read_text(encoding="utf-8")


def test_recording_needs_the_table(tmp_path: Path) -> None:
    page = tmp_path / "page.md"
    page.write_text("# Page\n\n## Findings\n", encoding="utf-8")
    with pytest.raises(ValueError, match="## Runs"):
        run.record(RESULT, page, date="2026-10-08")
    assert page.read_text(encoding="utf-8") == "# Page\n\n## Findings\n"


def test_harness_is_documented_and_stays_out_of_the_wheel() -> None:
    """``tools/README.md``, ``CONTRIBUTING.md`` and the Makefile name the harness; the wheel is built
    from ``src/fenolite`` only, so nothing of ``tools/`` is in it."""
    import tomllib

    for name in ("tools/README.md", "CONTRIBUTING.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "tools/agent_eval" in text and "docs/evidence/agent-eval.md" in text, name
        assert "--yes" in text and "costs money" in text, name
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "agent-eval:" in makefile
    assert "tools/agent_eval/run.py --task $(TASK) --runner $(RUNNER)" in makefile
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == ["src/fenolite"]
    assert project["project"]["dependencies"] == []
