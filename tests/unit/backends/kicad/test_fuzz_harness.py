# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The token fuzz harness without KiCad: case building, the runner contract and evidence levels."""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import _fuzzmod
import pytest

from fenolite.backends.kicad.versions import FileKind, load_inventory
from fenolite.core.evidence import Level

fuzz = _fuzzmod.load()
INV = load_inventory()
DATA = Path(__file__).resolve().parents[4] / "tests" / "data" / "kicad" / "tokens"


def examples(*bodies: str) -> list[Any]:
    return fuzz.load_examples("".join(bodies), INV)


def ex(ident: str, host: str, fragment: str, *, kinds: str = '["kicad_pcb"]', extra: str = "") -> str:
    return (f'[[example]]\nid = "{ident}"\nkinds = {kinds}\nhost = "{host}"\nmode = "append"\n'
            f"fragment = '''{fragment}'''\n{extra}")  # fmt: skip


BASELINE = (
    '[[example]]\nid = "positive-baseline"\nkinds = ["kicad_pcb", "kicad_mod"]\n'
    'expect = { "9" = "load", "10" = "load" }\n'
)


# --- build ----------------------------------------------------------------------------------------


def test_build_10_token_on_9() -> None:
    (case,) = fuzz.build_cases(INV, examples(ex("t", "kicad_pcb/setup", "(tenting (front yes))")), 9)
    assert (case.header_version, case.expected) == (20241229, "reject")
    assert case.rows == ("tenting", "tenting-front")


def test_build_9_token_on_10() -> None:
    (case,) = fuzz.build_cases(INV, examples(ex("t", "kicad_pcb/setup", "(tenting front back)")), 10)
    assert (case.header_version, case.expected) == (20241229, "load")


def test_build_form_example_on_9() -> None:
    body = ex("n", "kicad_pcb", '(segment (start 1 1) (end 2 1) (width 0.2) (layer "F.Cu") (net "A"))',
              extra='exercises = ["net-by-name"]\n')  # fmt: skip
    (case,) = fuzz.build_cases(INV, examples(body), 9)
    assert (case.header_version, case.expected, case.rows) == (20241229, "reject", ("net-by-name",))


def test_build_obsolete_token_under_the_newer_header() -> None:
    body = ex("o", "kicad_pcb/setup", "(pcbplotparams (plotinvisibletext no))")
    cases = fuzz.build_cases(INV, examples(body), 10)
    assert [(c.header_version, c.expected) for c in cases] == [(20240108, "load"), (20260206, "load")]
    assert [c.header_version for c in fuzz.build_cases(INV, examples(body), 9)] == [20240108]


def test_build_ignored_rows_expect_load() -> None:
    (case,) = fuzz.build_cases(
        INV, examples(ex("p", "kicad_pcb/footprint/pad", "(property pad_prop_pressfit)")), 9
    )
    assert (case.header_version, case.expected) == (20241229, "load")


def test_build_baseline_per_header() -> None:
    general = ex("g", "kicad_pcb/general", "(x 1)", extra='expect = { "9" = "load", "10" = "load" }\n')
    body = BASELINE + ex("t", "kicad_pcb/setup", "(tenting (front yes))") + general
    cases = fuzz.build_cases(INV, examples(body), 10)
    baselines = sorted((c.kind.value, c.header_version) for c in cases if c.example == "positive-baseline")
    assert baselines == [("kicad_pcb", 20240108), ("kicad_pcb", 20260206)]


def test_build_host_missing() -> None:
    with pytest.raises(fuzz.UsageError, match="example h: host 'kicad_pcb/nothing' not found"):
        fuzz.build_cases(INV, examples(ex("h", "kicad_pcb/nothing", "(a)")), 10)


def test_build_files_per_kind() -> None:
    body = ex("f", "footprint", "(embedded_fonts no)", kinds='["kicad_mod"]')
    (case,) = fuzz.build_cases(INV, examples(body), 10)
    assert list(case.files) == ["case.pretty/case.kicad_mod"]
    assert b"(version 20241229)" in case.files["case.pretty/case.kicad_mod"]
    rules = ex("r", "kicad_dru", "(rule d (constraint via_dangling))", kinds='["kicad_dru"]')
    (rule_case,) = fuzz.build_cases(INV, examples(rules), 9)
    assert set(rule_case.files) == {"canary.kicad_pcb", "canary.kicad_pro", "canary.kicad_dru"}
    assert rule_case.files["canary.kicad_dru"].decode().endswith("(rule d (constraint via_dangling))\n")
    assert rule_case.expected == "reject"


# --- runner ---------------------------------------------------------------------------------------


class Fake:
    """A fake kicad-cli: answers ``version`` and loads unless the case file contains 'REJECT'."""

    def __init__(self, version: str = "10.0.6", *, svg: bool = True, load_all: bool = False) -> None:
        self.version = version
        self.svg = svg
        self.load_all = load_all
        self.envs: list[dict[str, str]] = []

    def __call__(self, args: Sequence[str], cwd: Path, env: dict[str, str], timeout: float) -> Any:
        self.envs.append(env)
        if args[0] == "version":
            return fuzz.RunResult(0, f"{self.version}\n")
        text = "".join(p.read_text() for p in cwd.rglob("*") if p.is_file() and p.suffix.startswith(".kicad"))
        if "REJECT" in text and not self.load_all:
            return fuzz.RunResult(3, f"Failed to load board: unknown token in '{cwd}/case.kicad_pcb'\n")
        if self.svg and "-o" in args:
            out = cwd / args[args.index("-o") + 1]
            target = out / "x.svg" if out.is_dir() else out
            target.write_text("<svg/>")
        return fuzz.RunResult(0, "Plotted\n")


def run_main(tmp_path: Path, examples_text: str, runner: Any, *extra: str) -> int:
    path = tmp_path / "examples.toml"
    path.write_text(examples_text)
    for name in (
        "skeleton.kicad_pcb",
        "skeleton.kicad_mod",
        "skeleton.kicad_wks",
        "skeleton.kicad_sch",
        "skeleton.kicad_sym",
    ):
        (tmp_path / name).write_bytes((DATA / name).read_bytes())
    (tmp_path / "canary").mkdir(exist_ok=True)
    for name in ("canary.kicad_pcb", "canary.kicad_pro", "canary.kicad_dru"):
        (tmp_path / "canary" / name).write_bytes((DATA / "canary" / name).read_bytes())
    return fuzz.main(["--examples", str(path), *extra], runner=runner)


def test_runner_mismatch_exits_5(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    body = ex("t", "kicad_pcb/setup", "(tenting (front yes))")
    code = run_main(tmp_path, body, Fake("9.0.9", load_all=True), "--write", str(tmp_path / "out"))
    assert code == 5 and "t [kicad_pcb 20241229]: expected reject, got load" in capsys.readouterr().err
    written = json.loads((tmp_path / "out" / "9.0.9.json").read_text())
    assert written["cases"][0]["outcome"] == "load"


def test_runner_exit_codes_and_missing_svg(tmp_path: Path) -> None:
    body = ex("r", "kicad_pcb", "(fenolite_REJECT 1)", extra='expect = { "9" = "reject", "10" = "reject" }\n')
    assert run_main(tmp_path, body, Fake(), "--write", str(tmp_path / "out")) == 0
    case = json.loads((tmp_path / "out" / "10.0.6.json").read_text())["cases"][0]
    assert (case["outcome"], case["exit_code"]) == ("reject", 3)
    body2 = ex("s", "kicad_pcb", "(gr_text_box)", extra='expect = { "9" = "load", "10" = "load" }\n')
    assert run_main(tmp_path, body2, Fake(svg=False), "--write", str(tmp_path / "out2")) == 5


def test_runner_sanitises_details(tmp_path: Path) -> None:
    body = ex("r", "kicad_pcb", "(fenolite_REJECT 1)", extra='expect = { "9" = "reject", "10" = "reject" }\n')
    run_main(tmp_path, body, Fake(), "--write", str(tmp_path / "out"))
    detail = json.loads((tmp_path / "out" / "10.0.6.json").read_text())["cases"][0]["detail"]
    assert "<tmp>/case.kicad_pcb" in detail and "fenolite-fuzz-" not in detail
    assert fuzz.sanitise(f"x {Path.home()}/y", Path("/nowhere")) == "x ~/y"


def test_runner_env_is_isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANG", "de_DE.UTF-8")
    fake = Fake()
    body = ex("g", "kicad_pcb/general", "(x 1)", extra='expect = { "9" = "load", "10" = "load" }\n')
    run_main(tmp_path, body, fake, "--write", str(tmp_path / "out"))
    env = fake.envs[-1]
    assert env["LANG"] == "C" and env["LC_ALL"] == "C" and "fenolite-fuzz-" in env["KICAD_CONFIG_HOME"]
    header = json.loads((tmp_path / "out" / "10.0.6.json").read_text())["kicad_cli"]["env"]
    assert set(header) == {"KICAD_CONFIG_HOME", "LANG", "LC_ALL"}


def test_runner_timeout(tmp_path: Path) -> None:
    def slow(args: Sequence[str], cwd: Path, env: dict[str, str], timeout: float) -> Any:
        if args[0] == "version":
            return fuzz.RunResult(0, "10.0.6\n")
        raise subprocess.TimeoutExpired(args, timeout)

    body = ex("g", "kicad_pcb/general", "(x 1)", extra='expect = { "9" = "load", "10" = "load" }\n')
    assert run_main(tmp_path, body, slow, "--write", str(tmp_path / "out"), "--timeout", "1") == 5
    case = json.loads((tmp_path / "out" / "10.0.6.json").read_text())["cases"][0]
    assert case["outcome"] == "timeout"


def test_runner_check_drift_and_missing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    body = ex("g", "kicad_pcb/general", "(x 1)", extra='expect = { "9" = "load", "10" = "load" }\n')
    assert run_main(tmp_path, body, Fake(), "--check", str(tmp_path / "none")) == 5
    assert "results for kicad-cli 10.0.6" in capsys.readouterr().err
    out = tmp_path / "out"
    assert run_main(tmp_path, body, Fake(), "--write", str(out)) == 0
    assert run_main(tmp_path, body, Fake(), "--check", str(out)) == 0
    stored = json.loads((out / "10.0.6.json").read_text())
    stored["cases"][0]["outcome"], stored["cases"][0]["exit_code"] = "reject", 3
    (out / "10.0.6.json").write_text(json.dumps(stored))
    assert run_main(tmp_path, body, Fake(), "--check", str(out)) == 5
    assert "committed reject (exit 3), now load (exit 0)" in capsys.readouterr().err


def test_no_kicad_cli_exits_6(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = fuzz.main(["--kicad-cli", str(tmp_path / "missing"), "--write", str(tmp_path)])
    assert code == 6 and "--docker" in capsys.readouterr().err


def test_usage_error_exits_2(tmp_path: Path) -> None:
    assert fuzz.main(["--write"]) == 2
    bad = tmp_path / "examples.toml"
    bad.write_text('[[example]]\nid = "x"\nkinds = ["kicad_pcb"]\n')
    assert fuzz.main(["--examples", str(bad), "--write", str(tmp_path)], runner=Fake()) == 2


def test_docker_command(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[list[str]] = []
    monkeypatch.setattr(
        fuzz.subprocess, "run", lambda cmd, check: seen.append(cmd) or subprocess.CompletedProcess(cmd, 0)
    )
    assert fuzz.main(["--docker", "kicad/kicad:9.0.9@sha256:" + "0" * 64, "--write", "docs/x"]) == 0
    cmd = seen[0]
    assert cmd[:2] == ["docker", "run"] and "PYTHONPATH=/w/src" in cmd and "HOME=/tmp" in cmd
    assert cmd[-6:] == [
        "--kicad-cli",
        "kicad-cli",
        "--image",
        "kicad/kicad:9.0.9@sha256:" + "0" * 64,
        "--write",
        "docs/x",
    ]


# --- levels ---------------------------------------------------------------------------------------


def result(version: str, cases: list[dict[str, Any]]) -> dict[str, Any]:
    return {"kicad_cli": {"version": version}, "cases": cases}


def case(
    example: str,
    rows: list[str],
    expected: str,
    outcome: str,
    header: int = 20241229,
    kind: str = "kicad_pcb",
) -> dict[str, Any]:
    return {
        "example": example,
        "kind": kind,
        "header_version": header,
        "rows": rows,
        "expected": expected,
        "outcome": outcome,
    }


def test_levels_rejection_credited_to_the_newest_row_only() -> None:
    nine = result("9.0.9", [case("t", ["tenting", "tenting-front"], "reject", "reject")])
    levels = fuzz.row_levels(INV, [nine])
    assert levels["tenting-front"][9] == Level.KICAD_VERIFIED
    assert levels["tenting"][9] == Level.INFERRED


def test_levels_load_and_mismatch() -> None:
    ten = result("10.0.6", [case("t", ["tenting", "tenting-front"], "load", "load", 20260206)])
    levels = fuzz.row_levels(INV, [ten])
    assert levels["tenting"][10] == levels["tenting-front"][10] == Level.KICAD_VERIFIED
    bad = result("10.0.6", [case("t", ["tenting"], "load", "load"), case("u", ["tenting"], "load", "reject")])
    assert fuzz.row_levels(INV, [bad])["tenting"][10] == Level.INFERRED


def test_levels_obsolete_needs_the_newer_header() -> None:
    old = result("10.0.6", [case("o", ["plot-plotinvisibletext"], "load", "load", 20240108)])
    assert fuzz.row_levels(INV, [old])["plot-plotinvisibletext"][10] == Level.INFERRED
    new = result("10.0.6", [case("o", ["plot-plotinvisibletext"], "load", "load", 20260206)])
    assert fuzz.row_levels(INV, [new])["plot-plotinvisibletext"][10] == Level.KICAD_VERIFIED


def test_levels_inconclusive_never_counts() -> None:
    res = result("9.0.9", [case("n", ["net-by-name"], "reject", "inconclusive")])
    assert fuzz.row_levels(INV, [res])["net-by-name"][9] == Level.INFERRED


def test_kind_values() -> None:
    kinds = {"kicad_pcb", "kicad_mod", "kicad_wks", "kicad_dru", "kicad_sch", "kicad_sym"}
    assert {k.value for k in fuzz.SKELETONS} == kinds
    assert fuzz.FLOOR_MAJOR[FileKind.RULES] == 9 and sys.version_info >= (3, 11)


# --- schematics and symbol libraries (change c0060, "Load checks for schematics and symbol libraries")

BOTH = 'expect = { "9" = "reject", "10" = "reject" }\n'
LOADS = 'expect = { "9" = "load", "10" = "load" }\n'


def test_build_schematic_and_symbol_files() -> None:
    sheet = ex("s", "kicad_sch/symbol", "(fenolite_x 1)", kinds='["kicad_sch"]', extra=BOTH)
    (case,) = fuzz.build_cases(INV, examples(sheet), 10)
    assert list(case.files) == ["case.kicad_sch"] and case.kind == FileKind.SCHEMATIC
    data = case.files["case.kicad_sch"]
    assert b"(version 20231120)" in data and b"(fenolite_x 1)" in data
    lib = ex("l", "kicad_symbol_lib/symbol", "(fenolite_x 1)", kinds='["kicad_sym"]', extra=BOTH)
    (lib_case,) = fuzz.build_cases(INV, examples(lib), 9)
    assert list(lib_case.files) == ["case.kicad_sym"] and lib_case.header_version == 20231120


def test_schematic_load_and_reject(tmp_path: Path) -> None:
    body = ex("r", "kicad_sch", "(fenolite_REJECT 1)", kinds='["kicad_sch"]', extra=BOTH)
    assert run_main(tmp_path, body, Fake(), "--write", str(tmp_path / "out")) == 0
    case = json.loads((tmp_path / "out" / "10.0.6.json").read_text())["cases"][0]
    assert (case["kind"], case["outcome"], case["exit_code"]) == ("kicad_sch", "reject", 3)
    good = ex("g", "kicad_sch", "(fenolite_fine 1)", kinds='["kicad_sch"]', extra=LOADS)
    assert run_main(tmp_path, good, Fake(), "--write", str(tmp_path / "out1")) == 0


def test_schematic_without_a_netlist_is_not_a_load(tmp_path: Path) -> None:
    body = ex("s", "kicad_sch", "(fenolite_fine 1)", kinds='["kicad_sch"]', extra=LOADS)
    assert run_main(tmp_path, body, Fake(svg=False), "--write", str(tmp_path / "out")) == 5
    case = json.loads((tmp_path / "out" / "10.0.6.json").read_text())["cases"][0]
    assert (case["outcome"], case["exit_code"]) == ("reject", 0)


def test_symbol_library_load_check(tmp_path: Path) -> None:
    body = ex("l", "kicad_symbol_lib", "(fenolite_fine 1)", kinds='["kicad_sym"]', extra=LOADS)
    assert run_main(tmp_path, body, Fake(), "--write", str(tmp_path / "out")) == 0
    assert run_main(tmp_path, body, Fake(svg=False), "--write", str(tmp_path / "out2")) == 5


def test_schematic_case_is_inconclusive_without_its_skeleton(tmp_path: Path) -> None:
    class NoSkeleton(Fake):
        def __call__(self, args: Sequence[str], cwd: Path, env: dict[str, str], timeout: float) -> Any:
            if args[0] == "sch":
                return fuzz.RunResult(3, "Failed to load schematic\n")
            return super().__call__(args, cwd, env, timeout)

    baseline = (
        '[[example]]\nid = "positive-baseline"\nkinds = ["kicad_sch"]\n'
        'expect = { "9" = "load", "10" = "load" }\n'
    )
    body = baseline + ex("s", "kicad_sch", "(fenolite_x 1)", kinds='["kicad_sch"]', extra=BOTH)
    run_main(tmp_path, body, NoSkeleton(), "--write", str(tmp_path / "out"))
    cases = {c["example"]: c for c in json.loads((tmp_path / "out" / "10.0.6.json").read_text())["cases"]}
    assert cases["s"]["outcome"] == "inconclusive" and cases["positive-baseline"]["outcome"] == "reject"
