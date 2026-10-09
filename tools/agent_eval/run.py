# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The runner of the agent evaluation: one task, one runner, a clean place, a verdict (change c0081).

    uv run python tools/agent_eval/run.py --task led-indicator --runner replay

It builds the wheel of this checkout, installs it with no extra in a new virtual environment under a new
temporary folder outside the repository, makes an empty work folder there, copies the task's ``files/``,
runs its ``prepare`` lines, installs the agent guide as the runner's row says, prints the budget, starts
the runner with the call log first on ``PATH``, stops it when the task's minutes have passed, judges
what the folder holds and writes ``result.json`` beside the work folder.

The runner ``replay`` plays the reference solution of the task and starts no agent. Every other row of
``runners.toml`` starts a real agent, which costs money: it is refused when the variable ``CI`` is set,
and without ``--yes`` the budget is printed and nothing starts. This tool reads no key and calls no
service itself; the agent it starts gets the environment of the person who started it.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

if not __package__:  # started as a file: make the package importable, then import through it
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    __package__ = "agent_eval"

from . import judge as judging  # noqa: E402
from . import shim, tasks  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RUNNERS = Path(__file__).resolve().parent / "runners.toml"
RECORD = ROOT / "docs" / "evidence" / "agent-eval.md"
REPLAY = "replay"
ALL = "all"
FIRST_LINE = "The `fenolite` command line is installed. Work only in this folder."
SKILLS = ("none", "agents-md")
RUNS_HEADING = "## Runs"
COLUMNS = (
    "date",
    "commit",
    "runner",
    "model",
    "task",
    "verdict",
    "calls",
    "failed calls",
    "minutes",
    "first failure",
)
NOT_ISOLATED = "not isolated"
RESULT_KEYS = (
    "task",
    "runner",
    "runner_version",
    "model",
    "isolated",
    "fenolite_version",
    "commit",
    "verdict",
    "minutes",
    "timed_out",
    "calls",
    "calls_by_exit",
    "first_failure",
    "turns",
    "tokens",
    "cost",
)
REPORT_KEYS = ("model", "turns", "tokens", "cost")
_ROW_KEYS = {"argv", "version_argv", "skill", "source", "budget_flag", "report", "isolation", "unconfigured"}
EXIT_OK, EXIT_HARNESS, EXIT_USAGE, EXIT_VERDICT = 0, 1, 2, 5
STOP_GRACE_S = 5
LINE_TIMEOUT_S = 1800


@dataclass(frozen=True)
class Runner:
    """One row of ``runners.toml``."""

    name: str
    argv: tuple[str, ...] = ()
    """The command line of the agent; ``{prompt}`` and ``{workdir}`` are replaced. Empty for ``replay``."""
    version_argv: tuple[str, ...] = ()
    skill: str = "none"
    """``agent:<name>``, ``agents-md`` or ``none``: how the guide is installed in the work folder."""
    source: str = ""
    """The id, in ``docs/evidence/sources.md``, of the page that documents the non-interactive mode."""
    budget_flag: tuple[str, ...] = ()
    """The words that give the agent its own cost or turn cap, when it has one."""
    report: dict[str, str] = field(default_factory=lambda: {})
    """Where the agent's JSON output holds ``model``, ``turns``, ``tokens`` and ``cost`` (dotted keys)."""
    isolation: tuple[str, ...] = ()
    """The flags that keep the agent from loading the user's own settings, memory and skills."""
    unconfigured: str = ""
    """Why the row cannot start yet; a row with this text is refused."""

    @property
    def real(self) -> bool:
        return self.name != REPLAY

    @property
    def isolated(self) -> bool:
        """``replay`` starts no agent, so nothing can remember anything; a real row needs its flags."""
        return not self.real or bool(self.isolation)

    def command(self, prompt: str, workdir: Path) -> list[str]:
        """The agent's command line: its program, the isolation and budget flags, then its arguments."""
        words = [word.replace("{prompt}", prompt).replace("{workdir}", str(workdir)) for word in self.argv]
        return [words[0], *self.isolation, *self.budget_flag, *words[1:]]


@dataclass(frozen=True)
class Place:
    """Where a run happens: a temporary folder outside the repository."""

    root: Path
    fenolite: Path
    """The real ``fenolite`` of the run's environment."""
    python: Path
    """An interpreter that runs the call log (the environment's own)."""

    @property
    def workdir(self) -> Path:
        return self.root / "work"

    @property
    def log(self) -> Path:
        return self.root / "calls.jsonl"

    @property
    def shim_dir(self) -> Path:
        return self.root / "shim"

    @property
    def result(self) -> Path:
        return self.root / "result.json"


class Refused(Exception):
    """A run that must not start; ``code`` is the exit code of the runner."""

    def __init__(self, message: str, code: int = EXIT_USAGE) -> None:
        super().__init__(message)
        self.code = code


def _say(text: str) -> None:
    sys.stdout.write(text + "\n")
    sys.stdout.flush()


def _words(value: object, name: str, key: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in cast("list[object]", value)):
        raise ValueError(f"runner {name}: {key} must be a list of texts")
    return tuple(cast("list[str]", value))


def load_runners(path: Path | None = None) -> dict[str, Runner]:
    """The rows of ``runners.toml``; ``ValueError`` names the row and the key of a malformed one."""
    source = RUNNERS if path is None else path
    data = tomllib.loads(source.read_text(encoding="utf-8"))
    runners: dict[str, Runner] = {}
    for name, raw in data.items():
        if not isinstance(raw, dict):
            raise ValueError(f"runner {name}: a row must be a table")
        row = cast("dict[str, Any]", raw)
        for key in sorted(row):
            if key not in _ROW_KEYS:
                raise ValueError(f"runner {name}: unknown key {key}")
        skill = row.get("skill", "none")
        if not isinstance(skill, str) or not (skill in SKILLS or skill.startswith("agent:") and skill[6:]):
            raise ValueError(f"runner {name}: skill must be agent:<name>, agents-md or none")
        if name == REPLAY:
            if set(row) - {"skill"}:
                raise ValueError(f"runner {name}: the replay row takes no key but skill")
            runners[name] = Runner(name, skill=skill)
            continue
        unconfigured = row.get("unconfigured", "")
        if not isinstance(unconfigured, str):
            raise ValueError(f"runner {name}: unconfigured must be a text")
        required = (
            ("argv", "skill", "source") if unconfigured else ("argv", "version_argv", "skill", "source")
        )
        for key in required:
            if key not in row:
                raise ValueError(f"runner {name}: the key {key} is missing")
        argv = _words(row["argv"], name, "argv")
        if not argv or not any("{prompt}" in word for word in argv):
            raise ValueError(f"runner {name}: argv must hold the program and {{prompt}}")
        source_id = row["source"]
        if not isinstance(source_id, str) or not source_id.startswith("S-"):
            raise ValueError(f"runner {name}: source must be an id of docs/evidence/sources.md")
        report = row.get("report", {})
        if not isinstance(report, dict) or set(cast("dict[str, object]", report)) - set(REPORT_KEYS):
            raise ValueError(f"runner {name}: report takes the keys {', '.join(REPORT_KEYS)}")
        runners[name] = Runner(
            name,
            argv,
            _words(row.get("version_argv", []), name, "version_argv"),
            skill,
            source_id,
            _words(row.get("budget_flag", []), name, "budget_flag"),
            {key: str(value) for key, value in cast("dict[str, object]", report).items()},
            _words(row.get("isolation", []), name, "isolation"),
            unconfigured,
        )
    if REPLAY not in runners:
        raise ValueError("runners.toml holds no row replay")
    return runners


# --- the call log ---------------------------------------------------------------------------------


def read_log(path: Path) -> list[dict[str, Any]]:
    """The calls of a log file, in order; a missing file is no call."""
    if not path.is_file():
        return []
    calls: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            calls.append(json.loads(line))
    return calls


def summarise(calls: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """``calls``, ``calls_by_exit`` and ``first_failure`` of a call log."""
    by_exit: dict[str, int] = {}
    first: dict[str, Any] | None = None
    for call in calls:
        code = int(call["exit"])
        by_exit[str(code)] = by_exit.get(str(code), 0) + 1
        if code != 0 and first is None:
            argv = [str(word) for word in call.get("argv", [])]
            name = next((word for word in argv if not word.startswith("-")), "")
            first = {"n": int(call["n"]), "command": name, "error_code": call.get("error_code")}
    ordered = {key: by_exit[key] for key in sorted(by_exit, key=int)}
    return {"calls": len(calls), "calls_by_exit": ordered, "first_failure": first}


# --- commands of a run ----------------------------------------------------------------------------


def run_line(argv: Sequence[str], cwd: Path, env: Mapping[str, str] | None = None) -> int:
    """Run one command line in ``cwd`` and return its exit code; its output is not shown. The tests
    replace this function to stay in one process."""
    done = subprocess.run(
        list(argv),
        cwd=cwd,
        env=None if env is None else dict(env),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=LINE_TIMEOUT_S,
        check=False,
    )
    return done.returncode


def _arguments(line: str) -> list[str]:
    words = shlex.split(line)
    if not words or words[0] != "fenolite":
        raise ValueError(f"{line!r} is not a fenolite command line")
    return words[1:]


def copy_tree(source: Path, target: Path) -> None:
    """Copy the files under ``source`` into ``target``; a missing ``source`` copies nothing."""
    if source.is_dir():
        shutil.copytree(source, target, dirs_exist_ok=True)


def prepare(task: tasks.Task, workdir: Path, fenolite: judging.Fenolite) -> str | None:
    """Copy the task's files and run its ``prepare`` lines with the real command, outside the call log.
    Returns the line that failed, or ``None``."""
    workdir.mkdir(parents=True, exist_ok=True)
    copy_tree(task.files, workdir)
    for line in task.prepare:
        if run_line([*judging.command(fenolite), *_arguments(line)], workdir) != 0:
            return line
    return None


def replay(
    task: tasks.Task, workdir: Path, fenolite: judging.Fenolite, env: Mapping[str, str] | None = None
) -> list[int]:
    """Play the reference solution: copy its files, then run each line of ``commands.txt`` with
    ``fenolite`` (the call log, in a run), stopping at the first exit code that is not 0. Returns the
    exit codes of the lines that ran."""
    copy_tree(task.solution_files, workdir)
    codes: list[int] = []
    for line in task.commands():
        codes.append(run_line([*judging.command(fenolite), *_arguments(line)], workdir, env))
        if codes[-1] != 0:
            break
    return codes


def install_skill(runner: Runner, workdir: Path, fenolite: judging.Fenolite) -> bool:
    """Install the guide the way the row says, as an outside user would."""
    if runner.skill == "none":
        return True
    where = ["--agents-md"] if runner.skill == "agents-md" else ["--agent", runner.skill[6:]]
    return run_line([*judging.command(fenolite), "skill", "install", *where, "--confirm"], workdir) == 0


def agent_env(place: Place, launcher: Path, base: Mapping[str, str] | None = None) -> dict[str, str]:
    """The environment of the agent: the caller's, with the call log first on ``PATH``, the run's
    environment second, and the two variables of the call log."""
    env = dict(os.environ if base is None else base)
    parts = [str(launcher.parent), str(place.fenolite.parent), env.get("PATH", "")]
    env["PATH"] = os.pathsep.join(part for part in parts if part)
    env[shim.ENV_REAL] = str(place.fenolite)
    env[shim.ENV_LOG] = str(place.log)
    env.pop("VIRTUAL_ENV", None)
    return env


def _stop(process: subprocess.Popen[bytes]) -> None:
    """Stop the agent and what it started: its process group where the system has one."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(process.pid)], capture_output=True, check=False)
        process.kill()
    else:
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.killpg(process.pid, sig)
            except (ProcessLookupError, PermissionError):
                break
            try:
                process.wait(timeout=STOP_GRACE_S)
                break
            except subprocess.TimeoutExpired:
                continue
    process.wait()


def start_agent(
    argv: Sequence[str], place: Place, env: Mapping[str, str], seconds: float
) -> tuple[int | None, bool]:
    """Start the agent in the work folder and wait at most ``seconds``. Its output goes to files beside
    the work folder, never into it. Returns its exit code (``None`` when it was stopped or could not
    start) and whether the time ran out."""
    with open(place.root / "agent.stdout", "wb") as out, open(place.root / "agent.stderr", "wb") as err:
        try:
            process = subprocess.Popen(
                list(argv),
                cwd=place.workdir,
                env=dict(env),
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=err,
                start_new_session=os.name != "nt",
            )
        except OSError as error:
            err.write(f"the runner could not be started: {error.strerror}\n".encode())
            return None, False
        try:
            return process.wait(timeout=seconds), False
        except subprocess.TimeoutExpired:
            _stop(process)
            return None, True


def _dig(data: object, dotted: str) -> object:
    for key in dotted.split("."):
        if not isinstance(data, dict) or key not in data:
            return None
        data = cast("dict[str, object]", data)[key]
    return data


def read_report(runner: Runner, place: Place) -> dict[str, Any]:
    """``model``, ``turns``, ``tokens`` and ``cost`` as the row says the agent's JSON output holds them;
    ``None`` for what it does not report."""
    found: dict[str, Any] = dict.fromkeys(REPORT_KEYS)
    output = place.root / "agent.stdout"
    if not runner.report or not output.is_file():
        return found
    try:
        data = json.loads(output.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return found
    for key, dotted in runner.report.items():
        value = _dig(data, dotted)
        found[key] = value if isinstance(value, (str, int, float)) and not isinstance(value, bool) else None
    return found


def _first_line(argv: Sequence[str], cwd: Path) -> str | None:
    try:
        done = subprocess.run(
            list(argv), cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace",
            stdin=subprocess.DEVNULL, timeout=120, check=False,
        )  # fmt: skip
    except (OSError, subprocess.TimeoutExpired):
        return None
    lines = (done.stdout or done.stderr).strip().splitlines()
    return lines[0].strip() if done.returncode == 0 and lines else None


def fenolite_version(fenolite: judging.Fenolite, cwd: Path) -> str | None:
    said = _first_line([*judging.command(fenolite), "--version"], cwd)
    return said.split()[-1] if said else None


def commit(root: Path | None = None) -> str | None:
    """The short commit of the checkout, or ``None`` outside a git checkout."""
    return _first_line(["git", "rev-parse", "--short", "HEAD"], ROOT if root is None else root)


def budget_lines(task: tasks.Task, runner: Runner, seconds: float | None = None) -> list[str]:
    """What is printed before anything starts: the task, the runner, the time and the cost cap."""
    limit = f"{task.minutes} minutes" if seconds is None else f"{seconds:g} seconds"
    lines = [f"task: {task.name} ({task.title})", f"runner: {runner.name}", f"time budget: {limit}"]
    if runner.budget_flag:
        lines.append(f"cost cap: {' '.join(runner.budget_flag)}")
    elif runner.real:
        lines.append("cost cap: none (the row has no budget_flag); the time budget is the only limit")
    if runner.real and not runner.isolated:
        lines.append("isolation: none; the record will say 'not isolated'")
    return lines


def execute(
    task: tasks.Task,
    runner: Runner,
    place: Place,
    *,
    seconds: float | None = None,
    checkout: Path | None = None,
) -> dict[str, Any] | None:
    """One run in a place that exists: prepare, guide, budget, runner, judge, ``result.json``.
    Returns the result, or ``None`` when the place could not be prepared (nothing was started)."""
    failed = prepare(task, place.workdir, place.fenolite)
    if failed is not None:
        _say(f"prepare failed, nothing was started: {failed}")
        return None
    if not install_skill(runner, place.workdir, place.fenolite):
        _say(f"the guide could not be installed ({runner.skill}), nothing was started")
        return None
    launcher = shim.install(place.shim_dir, place.python, place.root / "shim.py")
    shutil.copyfile(Path(shim.__file__), place.root / "shim.py")
    env = agent_env(place, launcher)
    for line in budget_lines(task, runner, seconds):
        _say(line)
    limit = task.minutes * 60 if seconds is None else seconds
    started = time.monotonic()
    timed_out = False
    version: str | None = "builtin"
    if runner.real:
        version = _first_line(runner.version_argv, place.root) if runner.version_argv else None
        prompt = f"{FIRST_LINE}\n\n{task.prompt}"
        _, timed_out = start_agent(runner.command(prompt, place.workdir), place, env, limit)
    else:
        replay(task, place.workdir, launcher, env)
    minutes = round((time.monotonic() - started) / 60, 1)
    verdict = judging.judge(place.workdir, task, place.fenolite)
    report = read_report(runner, place)
    summary = summarise(read_log(place.log))
    result: dict[str, Any] = {
        "task": task.name,
        "runner": runner.name,
        "runner_version": version,
        "model": report["model"],
        "isolated": runner.isolated,
        "fenolite_version": fenolite_version(place.fenolite, place.root),
        "commit": commit(checkout),
        "verdict": verdict.as_dict(),
        "minutes": minutes,
        "timed_out": timed_out,
        **summary,
        "turns": report["turns"],
        "tokens": report["tokens"],
        "cost": report["cost"],
    }
    place.result.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    failed_calls = result["calls"] - result["calls_by_exit"].get("0", 0)
    _say(
        f"verdict: {verdict.status}  task={task.name} runner={runner.name} calls={result['calls']} "
        f"failed={failed_calls} minutes={minutes}" + ("  (timed out)" if timed_out else "")
    )
    for check in verdict.checks:
        if not check.passed:
            _say(f"  {check.name}: {check.detail}")
    return result


# --- the place ------------------------------------------------------------------------------------


def _inside(path: Path, folder: Path) -> bool:
    try:
        path.resolve().relative_to(folder.resolve())
    except ValueError:
        return False
    return True


def _tool(argv: Sequence[str], what: str) -> None:
    done = subprocess.run(list(argv), capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL)
    if done.returncode != 0:
        raise Refused(f"{what} failed (exit {done.returncode}):\n{done.stderr.strip()[-2000:]}", EXIT_HARNESS)


def _uv() -> str:
    found = shutil.which("uv")
    if found is None:
        raise Refused("uv was not found: it builds the wheel and the environment of a run", EXIT_HARNESS)
    return found


def _outside(source: Path, prefix: str) -> Path:
    """A new temporary folder, which must lie outside the repository."""
    root = Path(tempfile.mkdtemp(prefix=prefix))
    if _inside(root, source):
        shutil.rmtree(root, ignore_errors=True)
        raise Refused(f"the temporary folder lies inside the repository ({root.name})", EXIT_HARNESS)
    return root


def build_wheel(checkout: Path | None = None) -> Path:
    """Build the wheel of the checkout into a new temporary folder and return the wheel."""
    source = ROOT if checkout is None else checkout
    folder = _outside(source, "fenolite-eval-wheel-")
    try:
        _tool([_uv(), "build", "--wheel", "--out-dir", str(folder), str(source)], "building the wheel")
        (wheel,) = sorted(folder.glob("fenolite-*.whl"))
    except BaseException:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    return wheel


def make_place(wheel: Path, checkout: Path | None = None) -> Place:
    """A new place: a temporary folder outside the repository, with an empty work folder and a new
    environment that holds the wheel, installed with no extra and no index, and nothing else."""
    uv = _uv()
    root = _outside(ROOT if checkout is None else checkout, "fenolite-eval-")
    try:
        env = root / "env"
        _tool([uv, "venv", "--python", sys.executable, str(env)], "creating the environment")
        scripts = env / ("Scripts" if os.name == "nt" else "bin")
        python = scripts / ("python.exe" if os.name == "nt" else "python")
        _tool(
            [uv, "pip", "install", "--python", str(python), "--no-index", "--no-deps", str(wheel)],
            "installing the wheel",
        )
        fenolite = scripts / ("fenolite.exe" if os.name == "nt" else "fenolite")
        if not fenolite.is_file():
            raise Refused("the environment holds no fenolite command after the install", EXIT_HARNESS)
        place = Place(root, fenolite, python)
        place.workdir.mkdir()
    except BaseException:
        shutil.rmtree(root, ignore_errors=True)
        raise
    return place


# --- the record -----------------------------------------------------------------------------------


def record_row(result: Mapping[str, Any], date: str) -> str:
    """The row of ``Runs`` for one result: ten cells, no path, no prompt."""

    def cell(value: object) -> str:
        return "-" if value is None or value == "" else str(value).replace("|", "/").replace("\n", " ")

    runner = cell(result["runner"])
    if result.get("runner_version") not in (None, "", "builtin"):
        runner += f" {cell(result['runner_version'])}"
    if not result.get("isolated", False):
        runner += f" ({NOT_ISOLATED})"
    by_exit = cast("Mapping[str, int]", result["calls_by_exit"])
    failed = int(result["calls"]) - int(by_exit.get("0", 0))
    first = cast("Mapping[str, Any] | None", result["first_failure"])
    failure = (
        "-" if first is None else f"call {first['n']}: {cell(first['command'])} {cell(first['error_code'])}"
    )
    verdict = cast("Mapping[str, Any]", result["verdict"])["status"]
    if result.get("timed_out"):
        verdict = f"{verdict} (timed out)"
    cells = [
        date, cell(result["commit"]), runner, cell(result["model"]), cell(result["task"]), verdict,
        str(result["calls"]), str(failed), cell(result["minutes"]), failure,
    ]  # fmt: skip
    return "| " + " | ".join(cells) + " |"


def record(result: Mapping[str, Any], page: Path | None = None, date: str | None = None) -> str:
    """Append one row to the table of ``Runs`` of the page and change nothing else. Returns the row."""
    target = RECORD if page is None else page
    day = datetime.datetime.now(datetime.UTC).date().isoformat() if date is None else date
    row = record_row(result, day)
    lines = target.read_text(encoding="utf-8").split("\n")
    try:
        start = next(n for n, line in enumerate(lines) if line.strip() == RUNS_HEADING)
    except StopIteration:
        raise ValueError(f"{target.name} has no section {RUNS_HEADING}") from None
    end = next((n for n in range(start + 1, len(lines)) if lines[n].startswith("## ")), len(lines))
    table = [n for n in range(start + 1, end) if lines[n].startswith("|")]
    if len(table) < 2:
        raise ValueError(f"{target.name}: the section {RUNS_HEADING} holds no table")
    lines.insert(table[-1] + 1, row)
    target.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return row


# --- the command line -----------------------------------------------------------------------------


def parser() -> argparse.ArgumentParser:
    made = argparse.ArgumentParser(
        prog="tools/agent_eval/run.py",
        description="Run one evaluation task with one runner in a clean place and write the verdict.",
    )
    made.add_argument("--task", required=True, help="a task name, or 'all' (needs --yes)")
    made.add_argument("--runner", required=True, help="a row of runners.toml; 'replay' starts no agent")
    made.add_argument("--repeat", type=int, default=1, metavar="N", help="run the task N times")
    made.add_argument("--keep", action="store_true", help="keep the temporary folder and print its path")
    made.add_argument("--record", action="store_true", help="append the run to docs/evidence/agent-eval.md")
    made.add_argument(
        "--yes", action="store_true", help="start a real agent (it costs money), or every task with 'all'"
    )
    return made


def guard(
    runner: Runner, task_names: Sequence[str], args: argparse.Namespace, env: Mapping[str, str]
) -> None:
    """Refuse, before anything is built, a run that must not start."""
    if runner.real and env.get("CI"):
        raise Refused(
            f"the runner {runner.name} starts a real agent and the variable CI is set: "
            "only 'replay' runs in CI"
        )
    if args.task == ALL and not args.yes:
        raise Refused("--task all runs every task: pass --yes to confirm")
    if args.repeat < 1:
        raise Refused("--repeat takes a whole number of at least 1")
    if runner.real and runner.unconfigured:
        raise Refused(f"the runner {runner.name} is not configured: {runner.unconfigured}")
    if runner.real and not args.yes:
        for name in task_names:
            for line in budget_lines(tasks.load(name), runner):
                _say(line)
        raise Refused(
            f"the runner {runner.name} starts a real agent, which costs money: nothing was started. "
            f"Pass --yes to start {len(task_names) * args.repeat} run(s) with the budget above"
        )


def main(argv: Sequence[str] | None = None, *, runners: Path | None = None) -> int:
    args = parser().parse_args(None if argv is None else list(argv))
    try:
        rows = load_runners(runners)
        if args.runner not in rows:
            raise Refused(f"unknown runner {args.runner!r}: runners.toml holds {', '.join(sorted(rows))}")
        runner = rows[args.runner]
        known = tasks.names()
        if args.task != ALL and args.task not in known:
            raise Refused(f"unknown task {args.task!r}: the tasks are {', '.join(known)}")
        chosen = list(known) if args.task == ALL else [args.task]
        guard(runner, chosen, args, os.environ)
        statuses: list[str] = []
        wheel = build_wheel()
        try:
            for name in chosen:
                task = tasks.load(name)
                for _ in range(args.repeat):
                    place = make_place(wheel)
                    try:
                        result = execute(task, runner, place)
                        if result is None:
                            return EXIT_HARNESS
                        statuses.append(result["verdict"]["status"])
                        if args.record:
                            _say(f"recorded: {record(result)}")
                    finally:
                        if args.keep:
                            _say(f"kept: {place.root}")
                        else:
                            shutil.rmtree(place.root, ignore_errors=True)
        finally:
            shutil.rmtree(wheel.parent, ignore_errors=True)
    except Refused as refusal:
        sys.stderr.write(f"agent-eval: {refusal}\n")
        return refusal.code
    except ValueError as error:
        sys.stderr.write(f"agent-eval: {error}\n")
        return EXIT_USAGE
    return EXIT_OK if all(status == "passed" for status in statuses) else EXIT_VERDICT


if __name__ == "__main__":
    raise SystemExit(main())
