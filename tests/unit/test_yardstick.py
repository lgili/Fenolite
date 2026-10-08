# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The yardstick runner, hermetic (capability release-gate, "Yardstick stages", "Yardstick runner",
"Yardstick budgets" and "Yardstick record"; change c0119).

``tools/yardstick.py`` runs every step as a child process. Here the child is a fake ``fenolite``: a
script that answers each command with a small reply and writes the files the rules read. No KiCad, no
library and no corpus file is needed; the two heavy boards are empty files in a folder of the test.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tomllib
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from _needles import absent

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "yardstick.py"
EXAMPLE = ROOT / "examples" / "yardstick"
BUDGETS = ROOT / "tools" / "yardstick_budgets.toml"
PAGE = ROOT / "docs" / "evidence" / "yardstick.md"


def _load_tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("yardstick_tool", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


yard = _load_tool()

FAKE = r"""
import hashlib, json, os, sys
from pathlib import Path

args = sys.argv[1:]
command = args[0]
mode = json.loads(os.environ.get("YARD_FAKE", "{}"))
BOARD = Path("yardstick.kicad_pcb")


def reply(result, issues=(), code=0):
    print(json.dumps({"ok": code == 0, "command": command, "result": result, "issues": list(issues)}))
    if code:
        sys.stderr.write(json.dumps({"code": "FEN-5001", "message": "findings"}))
    sys.exit(code)


def fail(code):
    sys.stderr.write(json.dumps({"code": "FEN-3004", "message": f"{command} failed in {os.getcwd()}"}))
    sys.exit(code)


def option(name):
    return args[args.index(name) + 1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def listed(paths):
    # add files under fab to fab/fenolite-artifacts.json, as --manifest does
    manifest = Path("fab") / "fenolite-artifacts.json"
    data = json.loads(manifest.read_text()) if manifest.is_file() else {"artifacts": []}
    lacks = mode.get("package_lacks", "")
    data["artifacts"] += [{"path": path} for path in paths if not (lacks and path.endswith(lacks))]
    manifest.write_text(json.dumps(data))
    return [{"path": "fab/" + path} for path in paths] + [{"path": str(manifest)}]


if command == "capabilities":
    tools = {} if mode.get("no_kicad") else {"kicad-cli": {"path": "/opt/kicad-cli", "version": "10.0.6"}}
    reply({"fenolite_version": "0.0.0", "tools": tools, "routers": [{"name": "direct"}]})
if command == "build":
    out = Path(option("--out"))
    first = b"(kicad_pcb first)\n"
    if "--dry-run" in args:
        data = (out / BOARD).read_bytes() if (out / BOARD).is_file() else first
        reply({"plan": [
            {"path": str(BOARD), "sha256": sha(data)},
            {"path": ".fenolite/board.json", "sha256": "0" * 64},
        ]})
    if mode.get("build_exit"):
        fail(mode["build_exit"])
    again = (out / BOARD).is_file()
    (out / ".fenolite").mkdir(exist_ok=True)
    (out / ".fenolite" / "board.json").write_text("{}", encoding="utf-8")
    if not again:
        (out / BOARD).write_bytes(first)
    elif mode.get("rebuild_changes"):
        (out / BOARD).write_bytes(b"(kicad_pcb second)\n")
    reply({"components": 3})
if command == "fill":
    reply({"zones": []})
if command == "check":
    routed = Path("routed.flag").is_file()
    erc = dict(mode.get("erc", {}))
    if routed:
        drc = {"unconnected_items": mode.get("routed_open", 3), **mode.get("routed_drc", {})}
        drc = {kind: n for kind, n in drc.items() if n}
    else:
        drc = {"unconnected_items": 12, **mode.get("drc", {})}
    summary = [
        {"code": "kicad.drc." + kind.replace("_", "-"), "count": n, "by_severity": {"error": n}}
        for kind, n in drc.items()
    ] + [
        {"code": "kicad.erc." + kind.replace("_", "-"), "count": n, "by_severity": {"error": n}}
        for kind, n in erc.items()
    ]
    stages = [
        {"name": "model.validate", "status": "ok", "summary": {"components": 3, "nets": 4}},
        {"name": "erc.kicad", "status": "errors" if erc else "ok", "summary": {
            "by_type": erc, "types": {"kicad.erc." + k.replace("_", "-"): k for k in erc}}},
        {"name": "copper.clearance", "status": "ok", "summary": {
            "clearance": 0, "shorts": 0, "layers": ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"]}},
        {"name": "zone.fill", "status": "ok", "summary": {"zones": 4, "current": 4, "unfilled": 0}},
        {"name": "drc.kicad", "status": "errors" if drc else "ok", "summary": {
            "by_type": {k: n for k, n in drc.items() if k != "unconnected_items"},
            "unconnected": drc.get("unconnected_items", 0),
            "types": {"kicad.drc." + k.replace("_", "-"): k for k in drc},
            "limits": []}},
        {"name": "parity", "status": "ok", "summary": {"differences": 0}},
        {"name": "netlist.assignment_compare", "status": "ok", "summary": {
            "pairs": [{"a": "model", "b": "board", "common": 9, "differences": 0}]}},
        {"name": "roundtrip", "status": "ok", "summary": {"level": "RT1"}},
    ]
    reply({"stages": stages, "issues_summary": summary}, code=5 if drc or erc else 0)
if command == "route":
    freerouting = "freerouting" in args
    if freerouting:
        Path("routed.flag").write_text("1")
    nets = ["CH1_SW", "GND"] if freerouting else []
    reply({
        "selected": nets, "routed": nets, "unrouted": [], "connections": {"before": len(nets), "after": 0},
        "tracks": 4 * len(nets), "vias": len(nets),
        "budget": {"seconds": 60, "spent": 1.0, "exhausted": False},
        "runs": [{"tier": 0, "nets": len(nets), "seconds": 1.0, "outcome": "done"}] if nets else [],
        "plane_fanout": {"nets": ["GND"] if nets else [], "pads": 2, "joined": 0, "tracks": 2, "vias": 2,
                         "failed": []},
        "pairs": [], "escape": [],
    }, issues=[] if freerouting else [{"code": "route.pair-skipped", "severity": "warning"}])
if command == "net":
    open_ = 1 if Path("routed.flag").is_file() else 9
    reply({"nets": [{"name": "GND", "open": 0}, {"name": "USB_DP", "open": open_}]})
if command in ("impedance", "analyze"):
    reply({"rows": []} if command == "impedance" else {"distances": [], "summary": {}})
if command == "export" and "--ipc2581" in args:
    paths = ["ipc2581/yardstick.xml", "drawings/yardstick-fab.pdf"]
    for path in paths:
        (Path("fab") / path).parent.mkdir(parents=True, exist_ok=True)
        (Path("fab") / path).write_text(command, encoding="utf-8")
    written = listed(paths)
    print(json.dumps({"ok": True, "command": command, "result": {"artifacts": [{"path": p} for p in paths]},
                      "issues": [], "receipt": {"written": written}}))
    sys.exit(0)
if command == "testpoints":
    Path(option("--out")).write_text("ref\n", encoding="utf-8")
    written = listed(["testpoints.csv"])
    print(json.dumps({"ok": True, "command": command, "result": {"counts": {}}, "issues": [],
                      "receipt": {"written": written}}))
    sys.exit(0)
if command in ("export", "render"):
    folder = Path(option("-o"))
    name = "gerbers/board-F_Cu.gbr" if command == "export" else "front.svg"
    (folder / name).parent.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(command, encoding="utf-8")
    reply({"artifacts" if command == "export" else "views": [{"path": name}]})
if command in ("bom", "pnp"):
    Path(option("--out")).write_text("ref\n", encoding="utf-8")
    reply({"counts": {}})
if command == "manifest":
    folder = Path(option("--artifacts"))
    listed = sorted(p.as_posix() for p in folder.rglob("*") if p.is_file())
    if mode.get("manifest_lacks"):
        listed = [path for path in listed if not path.endswith(mode["manifest_lacks"])]
    reply({"states": {"generated": len(listed)}, "artifacts": [{"path": path} for path in listed]})
if command in ("inspect", "roundtrip"):
    if not Path(args[1]).is_file():
        fail(3)
    reply({"kind": "kicad_pcb"})
fail(2)
"""


@pytest.fixture
def stage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A folder for one run: the fake ``fenolite``, a library cache, the two heavy boards as empty
    files, a script at stage 1 (``example1``) and a budgets file that holds an empty table for stage 1."""
    fake = tmp_path / "fake_fenolite.py"
    fake.write_text(FAKE, encoding="utf-8")
    monkeypatch.setattr(yard, "FENOLITE", (sys.executable, str(fake)))
    (tmp_path / "libs").mkdir()
    monkeypatch.setenv("FENOLITE_LIBS_CACHE", str(tmp_path / "libs"))
    monkeypatch.setenv("FENOLITE_CORPUS_CACHE", str(tmp_path / "corpus"))
    monkeypatch.delenv("YARD_FAKE", raising=False)
    for row, name in yard.heavy_rows():
        (tmp_path / "corpus" / row).mkdir(parents=True)
        (tmp_path / "corpus" / row / name).write_bytes(b"")
    (tmp_path / "budgets.toml").write_text('[stage1]\nsource = "provisional"\n', encoding="utf-8")
    (tmp_path / "example1").mkdir()
    (tmp_path / "example1" / "design.py").write_text("STAGE = 1\n", encoding="utf-8")
    return tmp_path


def _run(folder: Path, *extra: str, name: str = "out") -> tuple[int, dict[str, Any], str]:
    """``run`` through ``main``: the exit code, the record (empty when none was written), the summary. The
    script is the one at stage 1 of the fixture unless ``extra`` names another."""
    record, summary = folder / f"{name}-record.json", folder / f"{name}-summary.md"
    example = () if "--example" in extra else ("--example", str(folder / "example1"))
    argv = [
        "run", "--out", str(folder / name), "--budgets", str(folder / "budgets.toml"),
        "--record", str(record), "--summary", str(summary), *example, *extra,
    ]  # fmt: skip
    code = yard.main(argv)
    found = json.loads(record.read_text(encoding="utf-8")) if record.is_file() else {}
    return code, found, summary.read_text(encoding="utf-8") if summary.is_file() else ""


def _step(record: dict[str, Any], name: str) -> dict[str, Any]:
    return next(step for step in record["steps"] if step["name"] == name)


# ---- stages, steps, peak memory


def test_stage_read_without_running_the_script(tmp_path: Path) -> None:
    script = tmp_path / "design.py"
    script.write_text("raise RuntimeError('never raised')\nSTAGE = 2\n", encoding="utf-8")
    assert yard.read_stage(script) == 2
    assert yard.read_stage(EXAMPLE / "design.py") in yard.STAGES


@pytest.mark.parametrize(
    "text", ["design = 1\n", "STAGE = 6\n", "STAGE = 0\n", "STAGE = '2'\n", "STAGE = True\n"]
)
def test_stage_missing_or_out_of_range_exits_2(
    text: str, stage: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (stage / "example").mkdir()
    (stage / "example" / "design.py").write_text(text, encoding="utf-8")
    code, record, _ = _run(stage, "--example", str(stage / "example"))
    assert code == 2 and not record
    assert "STAGE" in capsys.readouterr().err


def test_stage_needs_of_the_example() -> None:
    """The example is at a stage only when every change the stage needs is archived or named as cut."""
    number = yard.read_stage(EXAMPLE / "design.py")
    archived = [entry.name for entry in yard.ARCHIVE.iterdir()]
    assert yard.stage_problems(number, archived, PAGE.read_text(encoding="utf-8")) == []


def test_stage_needs_names_a_change_that_is_not_archived() -> None:
    """Scenario "Stage without its changes"."""
    page = "## Stages\n\n| stage | state |\n|---|---|\n| 2 | waiting |\n\n## Runs\n"
    problems = yard.stage_problems(2, ["2026-10-07-c0101-board-stackup"], page)
    assert len(problems) == 1 and "c0100" in problems[0] and "STAGE = 2" in problems[0]
    assert yard.stage_problems(2, ["2026-10-07-c0101-x", "2026-10-07-c0100-board-layer-count"], page) == []
    cut = page.replace("waiting", "not reached (cut: c0100)")
    assert yard.stage_problems(2, ["2026-10-07-c0101-board-stackup"], cut) == []
    complete = page.replace("waiting", "waiting (complete for 0.4: c0100, c0101)")
    assert yard.stage_problems(2, [], complete) == []
    assert yard.stage_problems(3, [], complete)  # c0102 and the others of stage 3 are named nowhere
    assert yard.stage_problems(1, [], page) == []


def test_steps_of_stage_1() -> None:
    rows = yard.heavy_rows()
    assert [row for row, _ in rows] == ["kicad-demo-10-0-6-pcb-06", "kicad-demo-10-0-6-pcb-18"]
    steps = yard.steps_for(1)
    names = [step.name for step in steps]
    assert names == [
        "capabilities", "build-dry", "build", "fill", "check", "export", "render", "bom", "pnp", "manifest",
        "rebuild-dry", "rebuild", "inspect", "build-install",
        "heavy-read:kicad-demo-10-0-6-pcb-06", "heavy-read:kicad-demo-10-0-6-pcb-18",
        "heavy-rt1:kicad-demo-10-0-6-pcb-06", "heavy-rt1:kicad-demo-10-0-6-pcb-18",
    ]  # fmt: skip
    assert not [name for name in names if name.startswith("route")]
    by_name = {step.name: step for step in steps}
    writing = ["--seed", "250025", "--timestamp", "2026-10-04T00:00:00Z", "--no-backup", "--confirm"]
    assert list(by_name["bom"].args) == [
        "bom",
        ".",
        "--source",
        "model",
        "--out",
        "fab/bom.csv",
        "--manifest",
        *writing,
    ]
    assert list(by_name["pnp"].args) == ["pnp", ".", "--out", "fab/pnp.csv", "--manifest", *writing]
    assert list(by_name["manifest"].args) == ["manifest", ".", "--artifacts", "fab", "--no-check", *writing]
    assert (
        list(by_name["check"].args) == ["check", ".", "--format", "concise"] and by_name["check"].expect == 5
    )
    assert (
        by_name["build-install"].drop_env == ("FENOLITE_LIBS_CACHE",)
        and "--dry-run" in by_name["build-install"].args
    )
    assert by_name["inspect"].args == ("inspect", "{board}")
    assert by_name["heavy-rt1:kicad-demo-10-0-6-pcb-18"].args[1].endswith(".kicad_pcb")
    assert all(step.expect == 0 for step in steps if step.name != "check")


def test_steps_of_later_stages_are_cumulative() -> None:
    assert [step.name for step in yard.steps_for(2)] == [step.name for step in yard.steps_for(1)]
    names = [step.name for step in yard.steps_for(5, rows=())]
    assert {"impedance", "route-pairs", "route", "net", "analyze", "export-package", "testpoints"} <= set(
        names
    )
    assert yard.stage_needs(3)[:3] == ("c0100", "c0101", "c0102")
    with pytest.raises(yard.Usage):
        yard.steps_for(6)


def test_peak_memory_units() -> None:
    assert yard.peak_mib(1048576, "darwin") == 1.0
    assert yard.peak_mib(1024, "linux") == 1.0


# ---- runs with a fake fenolite


def test_passing_run(stage: Path) -> None:
    code, record, summary = _run(stage)
    assert code == 0, summary
    assert [step["name"] for step in record["steps"]] == [step.name for step in yard.steps_for(1)]
    for step in record["steps"]:
        assert step["status"] == "ok" and step["exit"] == step["expected_exit"]
        assert {"seconds", "peak_mib", "reply_bytes", "exit", "issues", "budget"} <= set(step)
        assert step["seconds"] >= 0 and step["reply_bytes"] > 0 and step["budget"] is None
        assert (stage / "out" / step["reply"]).is_file()
    assert _step(record, "check")["exit"] == 5
    assert _step(record, "check")["issues"] == {"kicad.drc.unconnected-items": 12}
    assert all(rule["passed"] for rule in record["rules"])
    assert {"rebuild-dry.no-write", "rebuild.board-unchanged", "manifest.lists-artefacts"} <= {
        rule["rule"] for rule in record["rules"]
    }
    board = record["board"]
    assert (board["parts"], board["nets"], board["pads"], board["copper_layers"]) == (3, 4, 9, 4)
    assert board["drc"]["errors"] == {"unconnected_items": 12} and board["drc"]["unconnected"] == 12
    assert board["artefacts"] == {"generated": 4} and board["library_read"]["same_board"] is True
    assert "## Yardstick, stage 1: passed" in summary and "`build-install`" in summary


def test_drc_error_other_than_unconnected_items(stage: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YARD_FAKE", json.dumps({"drc": {"clearance": 1}}))
    code, record, summary = _run(stage, "--skip-heavy")
    assert code == 1 and record["verdict"] == "failed"
    failed = [rule for rule in record["rules"] if not rule["passed"]]
    assert [rule["rule"] for rule in failed] == ["check.drc.kicad"]
    assert "check" in failed[0]["detail"] and "clearance" in failed[0]["detail"]
    assert "check" in summary and "clearance" in summary
    assert not [step for step in record["steps"] if step["status"] != "ok"]  # every other step still ran


def test_accepted_finding_is_counted_and_another_fails(stage: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (stage / "budgets.toml").write_text(
        '[stage1]\nsource = "provisional"\n\n[stage1.accepted.power]\nstage = "erc.kicad"\n'
        'type = "power_pin_not_driven"\nreason = "the built schematic has no flag"\nowner = "c0000"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("YARD_FAKE", json.dumps({"erc": {"power_pin_not_driven": 2}}))
    code, record, summary = _run(stage, "--skip-heavy", name="first")
    assert code == 0, summary
    assert record["accepted"] == [
        {
            "stage": "erc.kicad",
            "type": "power_pin_not_driven",
            "count": 2,
            "owner": "c0000",
            "reason": "the built schematic has no flag",
        }
    ]
    assert "power_pin_not_driven" in summary and "c0000" in summary
    monkeypatch.setenv("YARD_FAKE", json.dumps({"erc": {"power_pin_not_driven": 2, "pin_not_connected": 1}}))
    code, record, summary = _run(stage, "--skip-heavy", name="second")
    assert code == 1
    failed = [rule for rule in record["rules"] if not rule["passed"]]
    assert [rule["rule"] for rule in failed] == ["check.erc.kicad"]
    assert "erc.kicad" in failed[0]["detail"] and "pin_not_connected" in failed[0]["detail"]
    assert "power_pin_not_driven" not in failed[0]["detail"]
    assert record["accepted"][0]["count"] == 2


def test_accepted_entry_without_an_owner_exits_2(stage: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (stage / "budgets.toml").write_text(
        '[stage1]\nsource = "provisional"\n\n[stage1.accepted.power]\nstage = "erc.kicad"\n'
        'type = "power_pin_not_driven"\nreason = "none"\n',
        encoding="utf-8",
    )
    code, record, _ = _run(stage, "--skip-heavy")
    assert code == 2 and not record
    assert "owner" in capsys.readouterr().err


def test_rebuild_that_changes_the_board(stage: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YARD_FAKE", json.dumps({"rebuild_changes": True}))
    code, record, summary = _run(stage, "--skip-heavy")
    assert code == 1
    failed = [rule for rule in record["rules"] if not rule["passed"]]
    assert [rule["rule"] for rule in failed] == ["rebuild.board-unchanged"]
    assert "yardstick.kicad_pcb" in failed[0]["detail"] and "yardstick.kicad_pcb" in summary


def test_manifest_that_lacks_a_written_file(stage: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YARD_FAKE", json.dumps({"manifest_lacks": "pnp.csv"}))
    code, record, _ = _run(stage, "--skip-heavy")
    failed = [rule for rule in record["rules"] if not rule["passed"]]
    assert code == 1 and [rule["rule"] for rule in failed] == ["manifest.lists-artefacts"]
    assert "fab/pnp.csv" in failed[0]["detail"]


def test_failed_build(stage: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YARD_FAKE", json.dumps({"build_exit": 3}))
    code, record, summary = _run(stage)
    assert code == 1 and record["verdict"] == "failed"
    build = _step(record, "build")
    assert build["exit"] == 3 and build["status"] == "failed" and "FEN-3004" in build["error"]
    assert absent(str(stage), json.dumps(record))  # the error text held the folder of the run
    after = record["steps"][[step["name"] for step in record["steps"]].index("build") + 1 :]
    ran = [step["name"] for step in after if step["status"] != "skipped"]
    assert ran == ["build-install", *(step.name for step in yard.steps_for(1) if step.row)]
    assert _step(record, "fill")["status"] == "skipped" and _step(record, "inspect")["status"] == "skipped"
    assert "skipped" in summary and "exit.build" in summary


def test_no_kicad_cli(
    stage: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("YARD_FAKE", json.dumps({"no_kicad": True}))
    code, record, _ = _run(stage, "--skip-heavy")
    assert code == 2 and not record
    assert "kicad-cli" in capsys.readouterr().err


def test_missing_library_cache_and_corpus_row_exit_2(
    stage: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    row, name = yard.heavy_rows()[0]
    (stage / "corpus" / row / name).unlink()
    assert _run(stage)[0] == 2
    assert row in capsys.readouterr().err
    monkeypatch.delenv("FENOLITE_LIBS_CACHE")
    assert _run(stage, "--skip-heavy")[0] == 2
    assert "FENOLITE_LIBS_CACHE" in capsys.readouterr().err
    assert not (stage / "out").exists()


def test_output_folder_must_be_empty(stage: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (stage / "out").mkdir()
    (stage / "out" / "old.txt").write_text("x", encoding="utf-8")
    assert _run(stage, "--skip-heavy")[0] == 2
    assert "not empty" in capsys.readouterr().err


# ---- the record and the row


def test_record_shape(stage: Path) -> None:
    code, record, _ = _run(stage)
    assert code == 0
    assert set(record) == {
        "schema", "date", "commit", "stage", "run", "runner", "tools", "board", "steps", "rules", "accepted",
        "budgets", "verdict",
    }  # fmt: skip
    assert record["schema"] == "fenolite.yardstick-record.v0"
    assert record["stage"] == 1 and record["verdict"] == "passed" and record["accepted"] == []
    assert set(record["runner"]) == {"system", "machine", "cpus", "memory_mib"}
    assert record["tools"] == {"fenolite": "0.0.0", "kicad-cli": "10.0.6", "routers": ["direct"]}
    assert record["budgets"] == {"file": "budgets.toml", "source": "provisional", "findings": []}
    text = json.dumps(record)
    for folder in (stage, ROOT, Path.home()):
        assert str(folder) not in text and str(folder).replace("\\", "\\\\") not in text
    assert "/opt/kicad-cli" not in text
    heavy = _step(record, "heavy-read:kicad-demo-10-0-6-pcb-06")
    assert heavy["args"][1].startswith("{corpus}/kicad-demo-10-0-6-pcb-06/")
    assert _step(record, "build")["args"][1] == "{script}"


def test_row_from_a_record(stage: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, record, _ = _run(stage, "--skip-heavy")
    assert code == 0
    capsys.readouterr()
    url = "https://example.invalid/run/1"
    assert yard.main(["row", str(stage / "out-record.json"), "--url", url]) == 0
    line = capsys.readouterr().out.strip()
    cells = [cell.strip() for cell in line.strip("|").split("|")]
    total = sum(step["seconds"] for step in record["steps"])
    assert "\n" not in line and len(cells) == 10
    assert cells[:4] == [record["date"][:10], record["commit"][:8], "1", url]
    assert cells[4] == f"{total:.0f}" and cells[6] == "12" and cells[7] == "0" and cells[8] == "passed"
    page = f"## Runs\n\n| a |\n|---|\n{line}\n"
    assert not [problem for problem in yard.page_problems(page) if problem.startswith("Runs")]
    (stage / "other.json").write_text("{}", encoding="utf-8")
    assert yard.main(["row", str(stage / "other.json")]) == 2


# ---- budgets


def test_step_over_its_budget(stage: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "A step over its budget": the fake build is measured at 31 s against 30 s."""
    (stage / "budgets.toml").write_text(
        '[stage1]\nsource = "provisional"\n\n[stage1.steps.build]\nseconds = 30\nmib = 100000\n'
        "\n[stage1.steps.fill]\nseconds = 600\nmib = 100000\n",
        encoding="utf-8",
    )
    real = yard.run_child

    def slow(command: Any, cwd: Path, env: Any, out: Path, err: Path) -> Any:
        measured = real(command, cwd, env, out, err)
        return yard.Measured(measured.exit, 31.0, measured.peak_mib) if out.name == "build.json" else measured

    monkeypatch.setattr(yard, "run_child", slow)
    code, record, summary = _run(stage, "--skip-heavy")
    assert code == 1 and record["verdict"] == "failed"
    assert all(rule["passed"] for rule in record["rules"])
    assert record["budgets"]["findings"] == [
        {"step": "build", "measure": "seconds", "value": 31.0, "budget": 30.0}
    ]
    assert _step(record, "build")["budget"] == {"seconds": 30, "mib": 100000}
    assert _step(record, "fill")["budget"] == {"seconds": 600, "mib": 100000}
    assert _step(record, "check")["budget"] is None  # no budget: recorded as null, fails nothing
    line = next(line for line in summary.splitlines() if line.startswith("- budget"))
    assert "build" in line and "31" in line and "30" in line


def test_judge_reads_seconds_and_mib_of_the_base_step() -> None:
    budgets = yard.StageBudgets("provisional", {"heavy-read": {"seconds": 10, "mib": 100}})
    record = {
        "steps": [
            {"name": "heavy-read:a", "status": "ok", "seconds": 5.0, "peak_mib": 150.0},
            {"name": "heavy-read:b", "status": "ok", "seconds": 5.0, "peak_mib": None},
            {"name": "build", "status": "ok", "seconds": 999.0, "peak_mib": 999.0},
            {"name": "fill", "status": "skipped", "reason": "build failed"},
        ]
    }
    assert yard.judge(record, budgets) == [yard.Finding("heavy-read:a", "mib", 150.0, 100.0)]


def _record(seconds: float, peak: float, run: str) -> dict[str, Any]:
    return {
        "schema": yard.SCHEMA,
        "stage": 1,
        "run": run,
        "steps": [
            {"name": "build", "status": "ok", "seconds": seconds, "peak_mib": peak},
            {"name": "heavy-read:x", "status": "ok", "seconds": 1.0, "peak_mib": 40.0},
            {"name": "fill", "status": "skipped", "reason": "build failed"},
        ],
    }


def test_rebase_from_three_runs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Scenario "Budgets from three runs": 20, 30 and 25 s give 40 s; 200, 220 and 210 MiB give 300."""
    files = []
    for index, (seconds, peak) in enumerate(((20, 200), (30, 220), (25, 210)), start=1):
        files.append(tmp_path / f"r{index}.json")
        files[-1].write_text(json.dumps(_record(seconds, peak, f"90{index}")), encoding="utf-8")
    assert yard.main(["rebase", *(str(path) for path in files)]) == 0
    text = capsys.readouterr().out
    table = tomllib.loads(text)["stage1"]
    assert table["source"] == "runs 901, 902, 903"
    assert table["steps"]["build"] == {"seconds": 40, "mib": 300}
    assert "seconds = 40" in text and "mib = 300" in text
    assert table["steps"]["heavy-read:x"] == {"seconds": 10, "mib": 50} and "fill" not in table["steps"]
    assert yard.main(["rebase", str(files[0])]) == 2
    assert yard.main(["rebase", str(files[0]), "--provisional"]) == 0
    provisional = tomllib.loads(capsys.readouterr().out)["stage1"]
    assert provisional["source"] == "provisional" and provisional["steps"]["build"] == {
        "seconds": 80,
        "mib": 400,
    }


def test_rebase_rounds_up_only_past_a_whole_step() -> None:
    assert yard.round_up(30.0, 10) == 30 and yard.round_up(30.01, 10) == 40
    assert yard.round_up(250.0, 50) == 250 and yard.round_up(0.4, 10) == 10


def test_no_budget_table_for_the_stage(stage: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (stage / "example").mkdir()
    (stage / "example" / "design.py").write_text("STAGE = 2\n", encoding="utf-8")
    code, record, _ = _run(stage, "--example", str(stage / "example"))
    assert code == 2 and not record
    assert "stage2" in capsys.readouterr().err


# ---- the stages that route and package (stages 3 to 5)

STAGE5_BUDGETS = (
    '[stage5]\nsource = "provisional"\n\n[stage5.ratchets]\nopen_connections = 5\ndrc_errors = 0\n'
)


@pytest.fixture
def stage5(stage: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The folder of ``stage`` with a script at stage 5, its budgets with ratchets and the two routers."""
    (stage / "example5").mkdir()
    (stage / "example5" / "design.py").write_text("STAGE = 5\n", encoding="utf-8")
    (stage / "budgets.toml").write_text(STAGE5_BUDGETS, encoding="utf-8")
    (stage / "krt").mkdir()
    (stage / "freerouting-2.4.1.jar").write_bytes(b"")
    monkeypatch.setenv("FENOLITE_KRT", str(stage / "krt"))
    monkeypatch.setenv("FENOLITE_FREEROUTING_JAR", str(stage / "freerouting-2.4.1.jar"))
    return stage


def _run5(folder: Path, *extra: str, name: str = "out") -> tuple[int, dict[str, Any], str]:
    return _run(folder, "--example", str(folder / "example5"), "--skip-heavy", *extra, name=name)


def test_steps_of_stages_3_to_5() -> None:
    steps = {step.name: step for step in yard.steps_for(5, rows=())}
    names = list(steps)
    assert names[-9:] == [
        "impedance", "route-pairs", "route", "fill-routed", "check-routed", "net", "analyze",
        "export-package", "testpoints",
    ]  # fmt: skip
    route = list(steps["route"].args or ())
    assert route[:4] == ["route", ".", "--router", "freerouting"]
    assert route[route.index("--timeout") + 1] == "3600" and route.count("--order") == 2
    pairs = list(steps["route-pairs"].args or ())
    assert "kicadroutingtools" in pairs and "USB_D*" in pairs and "U3" in pairs
    assert steps["check-routed"].accepts(0) and steps["check-routed"].accepts(5)
    assert not steps["check-routed"].accepts(1) and not steps["check"].accepts(0)
    package = list(steps["export-package"].args or ())
    for kind in ("--ipc2581", "--odb", "--step", "--pdf", "--dxf", "--sch-pdf", "--fab-drawing"):
        assert kind in package, kind
    assert "--manifest" in package and "--manifest" in (steps["testpoints"].args or ())
    assert steps["analyze"].args and "--groove-width" in steps["analyze"].args
    assert all(step.args is not None for step in steps.values())


def test_passing_run_at_stage_5(stage5: Path) -> None:
    code, record, summary = _run5(stage5)
    assert code == 0, summary
    assert [step["name"] for step in record["steps"]] == [step.name for step in yard.steps_for(5, rows=())]
    assert _step(record, "check-routed")["exit"] == 5 and _step(record, "check-routed")["status"] == "ok"
    rules = {rule["rule"]: rule for rule in record["rules"]}
    assert (
        rules["ratchet.open_connections"]["passed"]
        and "3 of the ratchet 5" in (rules["ratchet.open_connections"]["detail"])
    )
    assert rules["ratchet.drc_errors"]["passed"] and rules["package.in-manifest"]["passed"]
    assert rules["check-routed.drc.kicad"]["passed"]
    routed = record["board"]["routed"]
    assert routed["drc"]["unconnected"] == 3 and routed["net_open"] == 1 and routed["nets_open"] == 1
    assert routed["route"]["routed"] == 2 and routed["route"]["budget"]["exhausted"] is False
    assert routed["route-pairs"]["selected"] == 0
    cells = [cell.strip() for cell in yard.row(record).strip("|").split("|")]
    assert cells[2] == "5" and cells[6] == "3" and cells[7] == "0"
    assert "Routed: KiCad counts 3 open connections" in summary


def test_routed_board_over_its_ratchets(stage5: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YARD_FAKE", json.dumps({"routed_open": 7, "routed_drc": {"clearance": 2}}))
    code, record, summary = _run5(stage5)
    assert code == 1
    failed = {rule["rule"]: rule["detail"] for rule in record["rules"] if not rule["passed"]}
    assert set(failed) == {"ratchet.open_connections", "ratchet.drc_errors"}
    assert "7 over the ratchet 5" in failed["ratchet.open_connections"]
    assert "2 over the ratchet 0" in failed["ratchet.drc_errors"] and "ratchet" in summary
    monkeypatch.setenv("YARD_FAKE", json.dumps({"routed_open": 0}))
    code, record, _ = _run5(stage5, name="closed")
    assert code == 0 and _step(record, "check-routed")["exit"] == 0


def test_package_missing_from_the_manifest(stage5: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YARD_FAKE", json.dumps({"package_lacks": "testpoints.csv"}))
    code, record, _ = _run5(stage5)
    failed = [rule for rule in record["rules"] if not rule["passed"]]
    assert code == 1 and [rule["rule"] for rule in failed] == ["package.in-manifest"]
    assert "fab/testpoints.csv" in failed[0]["detail"]


def test_missing_router_or_ratchets_exit_2(
    stage5: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("FENOLITE_FREEROUTING_JAR")
    assert _run5(stage5)[0] == 2
    assert "Freerouting" in capsys.readouterr().err
    monkeypatch.setenv("FENOLITE_FREEROUTING_JAR", str(stage5 / "freerouting-2.4.1.jar"))
    monkeypatch.setenv("FENOLITE_KRT", str(stage5 / "nowhere"))
    assert _run5(stage5)[0] == 2
    assert "KiCadRoutingTools" in capsys.readouterr().err
    monkeypatch.setenv("FENOLITE_KRT", str(stage5 / "krt"))
    (stage5 / "budgets.toml").write_text('[stage5]\nsource = "provisional"\n', encoding="utf-8")
    assert _run5(stage5)[0] == 2
    assert "stage5.ratchets" in capsys.readouterr().err
    assert not (stage5 / "out").exists()


def test_rebase_prints_the_ratchets(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    files = []
    for index, (open_, errors) in enumerate(((4, 1), (9, 0), (6, 2)), start=1):
        record = {**_record(20, 200, f"80{index}"), "stage": 4}
        record["board"] = {
            "routed": {
                "drc": {"unconnected": open_, "errors": {"unconnected_items": open_, "clearance": errors}}
            }
        }
        files.append(tmp_path / f"r{index}.json")
        files[-1].write_text(json.dumps(record), encoding="utf-8")
    assert yard.main(["rebase", *(str(path) for path in files)]) == 0
    table = tomllib.loads(capsys.readouterr().out)["stage4"]
    assert table["ratchets"] == {"open_connections": 9, "drc_errors": 2}


def test_budgets_file() -> None:
    """Scenario "Provisional budgets of stage 1": the committed file."""
    data = tomllib.loads(BUDGETS.read_text(encoding="utf-8"))
    budgets = yard.stage_budgets(data, 1)
    page = PAGE.read_text(encoding="utf-8")
    if budgets.source != "provisional":
        runs = re_runs(budgets.source)
        assert len(runs) == 3 and all(run in yard._section(page, "Runs") for run in runs), budgets.source
    for step in yard.steps_for(1):
        if step.row:
            continue
        budget = budgets.of(step.name)
        assert budget is not None, step.name
        assert budget["seconds"] > 0 and budget["seconds"] % 10 == 0, step.name
        assert budget["mib"] > 0 and budget["mib"] % 50 == 0, step.name
    for entry in budgets.accepted:
        assert entry.type in yard._section(page, "Budgets"), entry.type
    stage = yard.read_stage(EXAMPLE / "design.py")
    assert yard.stage_budgets(data, stage).source  # the table of the example's stage exists


def re_runs(source: str) -> list[str]:
    return [name.strip() for name in source.removeprefix("runs ").split(",") if name.strip()]


# ---- the page


def test_page_guard() -> None:
    page = PAGE.read_text(encoding="utf-8")
    assert yard.page_problems(page) == []
    assert "mirrors no board" in yard._section(page, "How to read")
    assert "2026-10-07" in yard._section(page, "How to read")


def test_page_problems_are_found() -> None:
    good = (
        "## How to read\n\ntext\n\n## Stages\n\n| stage | state | since |\n|---|---|---|\n"
        + "".join(f"| {n} | waiting | c0100 |\n" for n in range(1, 6))
        + "\n## Runs\n\n| date | commit | stage | run | s | MiB | open | DRC | verdict | note |\n"
        + "|---|---|---|---|---|---|---|---|---|---|\n"
        + "| 2026-10-08 | abc | 1 | local | 9 | 9 | 1 | 0 | passed | |\n"
        + "\n## Budgets\n\ntext\n\n## Not measured\n\ntext\n"
    )
    assert yard.page_problems(good) == []
    assert any("Budgets" in p for p in yard.page_problems(good.replace("## Budgets", "## Costs")))
    assert any("stage 3" in p for p in yard.page_problems(good.replace("| 3 | waiting | c0100 |\n", "")))
    assert any("stage 2" in p for p in yard.page_problems(good.replace("| 2 | waiting", "| 2 | soon")))
    assert any("verdict" in p for p in yard.page_problems(good.replace("| passed |", "| fine |")))
    assert any("stage" in p for p in yard.page_problems(good.replace("| abc | 1 |", "| abc | 7 |")))
