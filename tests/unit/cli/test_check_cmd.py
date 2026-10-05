# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite check`` without a real ``kicad-cli`` (capability verification-loop: "Check command input",
"Check exit codes", "Inputs Fenolite cannot read", "Stages added for findings and round trips" and the
hermetic stage scenarios; changes c0013, c0020 and c0029)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import _ipc
import pytest
from _checkcli import hide_kicad, run, without_elapsed
from _fakecli import calls, erc_entry, fake_kicad_cli
from _projects import STEM, authored_project, built_blink_project, tree_snapshot
from _resources import posix_tools

from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.pcb import opaque_count, read_board
from fenolite.backends.kicad.sexpr import parse as parse_tree

DATA = Path(__file__).resolve().parents[2] / "data"
TWO_LAYER = DATA / "kicad" / "board" / "two_layer.kicad_pcb"
HERMETIC = ("--stages", "model.validate,roundtrip")


@pytest.fixture(autouse=True)
def _no_kicad(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    hide_kicad(monkeypatch, tmp_path)


def _stages(envelope: dict[str, object]) -> dict[str, dict[str, object]]:
    return {s["name"]: s for s in envelope["result"]["stages"]}  # type: ignore[index]


def _copy(tmp_path: Path, name: str = "board.kicad_pcb", data: bytes | None = None) -> Path:
    folder = tmp_path / "proj"
    folder.mkdir(exist_ok=True)
    target = folder / name
    target.write_bytes(TWO_LAYER.read_bytes() if data is None else data)
    return target


def _only_the_fixture_short(code: int, env: dict[str, object]) -> bool:
    """``two_layer.kicad_pcb`` holds one authored short: its ``GND_B`` fill covers pad 2 of ``D1``. With the
    default stages, which include ``copper.clearance`` (change c0029), a check of that board therefore
    exits 5 with exactly this error and no other."""
    errors = [i for i in env["issues"] if i["severity"] == "error"]  # type: ignore[union-attr,index]
    return code == 5 and [(i["code"], "D1-2" in i["where"]) for i in errors] == [("copper.short", True)]


def _no_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a subprocess was started")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)


def test_project_folder_resolved(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = _copy(tmp_path, "a.kicad_pcb")
    _copy(tmp_path, "b.kicad_pcb")
    (board.parent / "a.kicad_pro").write_text("{}\n", encoding="utf-8")
    code, env, _, _ = run(monkeypatch, tmp_path, "check", str(board.parent), "--stages", "roundtrip")
    assert code == 0 and env["result"]["project"]["board"] == "a.kicad_pcb"
    assert env["input"]["path"] == "a.kicad_pcb"


def test_ambiguous_folder(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = _copy(tmp_path, "a.kicad_pcb")
    _copy(tmp_path, "b.kicad_pcb")
    code, _, err, _ = run(monkeypatch, tmp_path, "check", str(board.parent))
    assert code == 2 and err["code"] == "FEN-2001"
    assert "a.kicad_pcb" in err["hint"] and "b.kicad_pcb" in err["hint"]


def test_unknown_stage_or_missing_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, _, err, _ = run(monkeypatch, tmp_path, "check", str(TWO_LAYER), "--stages", "drc")
    assert code == 2 and err["code"] == "FEN-2001"
    code, _, err, _ = run(monkeypatch, tmp_path, "check", str(TWO_LAYER), "--stages", "roundtrip,")
    assert code == 2 and err["code"] == "FEN-2001"
    code, _, err, _ = run(monkeypatch, tmp_path, "check", "missing.kicad_pcb")
    assert code == 3 and err["code"] == "FEN-3001"


def test_skipped_by_design(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A board without a schematic of its stem: ``erc.kicad`` is skipped, and no ``sch erc`` runs."""
    fake = fake_kicad_cli(tmp_path / "bin")
    code, env, _, _ = run(
        monkeypatch, tmp_path, "check", str(TWO_LAYER), "--kicad-cli", str(fake),
        "--stages", "model.validate,erc.kicad,roundtrip",
    )  # fmt: skip
    stages = _stages(env)
    assert code == 0
    assert (stages["erc.kicad"]["status"], stages["erc.kicad"]["reason"]) == ("skipped", "no-schematic")
    assert stages["model.validate"]["status"] == stages["roundtrip"]["status"] == "ok"
    assert not any(".erc." in i["code"] for i in env["issues"])
    assert not any(c["args"][:2] == ["sch", "erc"] for c in calls(fake))


def test_old_erc_stage_name_is_refused(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, _, err, _ = run(monkeypatch, tmp_path, "check", str(TWO_LAYER), "--stages", "erc.lite")
    assert code == 2 and err["code"] == "FEN-2001" and "erc.kicad" in err["hint"]


def test_erc_stage_alone_needs_kicad_cli(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, err, _ = run(monkeypatch, tmp_path, "check", str(TWO_LAYER), "--stages", "erc.kicad")
    assert code == 6 and err["code"] == "FEN-6001" and "model.validate,roundtrip" in err["hint"]
    assert "erc.lite" not in err["hint"] and "stages" not in env.get("result", {})


def test_erc_stage_reports_located_findings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The stage through the command, with a fake tool: one located error, exit 5, a summary that holds no
    date and no path, and a project that stays as it was."""
    root = built_blink_project(tmp_path / "blink")
    tree = parse_tree((root / "blink.kicad_sch").read_text(encoding="utf-8"))
    r1 = next(
        s for s in tree.nodes("symbol")
        if any([a.value for a in p.atoms()[:2]] == ["Reference", "R1"] for p in s.nodes("property"))
    )  # fmt: skip
    pin = next(p for p in r1.nodes("pin") if p.atoms()[0].value == "1")
    open_pin = erc_entry("pin_not_connected", pin.find("uuid").atoms()[0].value, x=0.6858, y=0.3429)
    report = json.dumps({
        "source": "blink.kicad_sch", "date": "2026-10-05T12:00:00", "kicad_version": "10.0.6",
        "coordinate_units": "mm", "ignored_checks": [{"key": "footprint_filter", "description": "d"}],
        "sheets": [{
            "path": "/", "uuid_path": "/" + tree.find("uuid").atoms()[0].value,
            "violations": [open_pin],
        }],
    })  # fmt: skip
    fake = fake_kicad_cli(tmp_path / "bin", erc_report=report, writes=("blink.kicad_prl",))
    before = tree_snapshot(root)
    code, env, _, stdout = run(
        monkeypatch, tmp_path, "check", str(root), "--kicad-cli", str(fake), "--stages", "erc.kicad"
    )
    assert code == 5 and tree_snapshot(root) == before
    (found,) = env["issues"]
    assert (found["code"], found["severity"], found["where"]) == (
        "kicad.erc.pin-not-connected",
        "error",
        "R1-1",
    )
    stage = _stages(env)["erc.kicad"]
    assert stage["status"] == "errors" and stage["evidence"]["oracle"] == "kicad-cli 10.0.6"
    assert stage["summary"] == {
        "tool_version": "10.0.6",
        "sheets": 1,
        "violations": 1,
        "by_type": {"pin_not_connected": 1},
        "by_severity": {"error": 1},
        "excluded": 0,
        "ignored_checks": ["footprint_filter"],
        "types": {"kicad.erc.pin-not-connected": "pin_not_connected"},
        "tool_writes": ["blink.kicad_prl"],
    }
    assert "2026-10-05T12:00:00" not in stdout and str(tmp_path) not in stdout
    assert "blink.kicad_sch" in env["result"]["project"]["files"]
    assert [c["args"][:2] for c in calls(fake)].count(["sch", "erc"]) == 1
    assert not any(c["args"][:2] == ["pcb", "drc"] for c in calls(fake))


def test_erc_stage_schematic_the_tool_cannot_load(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = built_blink_project(tmp_path / "blink")
    fake = fake_kicad_cli(tmp_path / "bin", erc_report="")
    code, env, _, _ = run(
        monkeypatch, tmp_path, "check", str(root), "--kicad-cli", str(fake), "--stages", "erc.kicad"
    )
    (found,) = env["issues"]
    assert code == 5 and found["code"] == "check.oracle-failed" and found["where"] == "blink.kicad_sch"
    assert "Failed to load schematic" in found["message"]
    assert _stages(env)["erc.kicad"]["evidence"]["level"] == "UNVERIFIED"


def test_parity_findings_of_the_drc_stage(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """ "Parity findings": the DRC run of a project with a schematic asks for the parity test, and each of
    its entries is a located finding."""
    root = built_blink_project(tmp_path / "blink")
    board = read_board(root / "blink.kicad_pcb")
    assert board.board is not None
    refs = {c.id: c.ref for c in board.circuit.components}
    r1 = next(f for f in board.board.footprints if refs[f.component_id] == "R1")
    pad = next(p for p in r1.pads if p.number == "2")
    entry = {
        "type": "net_conflict", "description": "Pad net (GND) doesn't match net given by schematic (LED_A).",
        "severity": "warning",
        "items": [{"uuid": pad.native_ids["kicad"], "description": "Pad 2", "pos": {"x": 1, "y": 2}}],
    }  # fmt: skip
    fake = fake_kicad_cli(tmp_path / "bin", parity=[entry])
    code, env, _, _ = run(
        monkeypatch, tmp_path, "check", str(root), "--kicad-cli", str(fake), "--stages", "drc.kicad"
    )
    summary = _stages(env)["drc.kicad"]["summary"]
    assert code == 0 and summary["parity"] == 1 and summary["parity_judged"] is True
    assert summary["types"]["kicad.drc.net-conflict"] == "net_conflict"
    (found,) = [i for i in env["issues"] if i["code"] == "kicad.drc.net-conflict"]
    assert (found["severity"], found["where"]) == ("warning", "R1-2")
    assert all("--schematic-parity" in c["args"] for c in calls(fake) if c["args"][:2] == ["pcb", "drc"])


def test_parity_unchecked_keeps_the_copper_verdict(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = built_blink_project(tmp_path / "blink")
    line = "10:50:25 PM: Error: Expecting kicad_sch in '<tmp>/blink.kicad_sch', line 2, offset 1."
    fake = fake_kicad_cli(tmp_path / "bin", parity_fail=line)
    code, env, _, _ = run(
        monkeypatch, tmp_path, "check", str(root), "--kicad-cli", str(fake), "--stages", "drc.kicad"
    )
    stage = _stages(env)["drc.kicad"]
    (found,) = [i for i in env["issues"] if i["code"] == "kicad.drc.parity-unchecked"]
    assert code == 0 and found["severity"] == "warning" and found["where"] == "blink.kicad_sch"
    assert found["message"].endswith(
        "Error: Expecting kicad_sch in '<tmp>/blink.kicad_sch', line 2, offset 1."
    )
    assert "10:50:25" not in found["message"]
    assert stage["summary"]["parity_judged"] is False and stage["summary"]["canary"] == "fired"
    assert stage["status"] == "ok" and stage["evidence"]["level"] != "UNVERIFIED"


def test_project_without_a_schematic_asks_for_no_parity(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = fake_kicad_cli(tmp_path / "bin")
    code, env, _, _ = run(
        monkeypatch, tmp_path, "check", str(TWO_LAYER), "--kicad-cli", str(fake), "--stages", "drc.kicad"
    )
    summary = _stages(env)["drc.kicad"]["summary"]
    assert code == 0 and summary["parity_judged"] is False and summary["parity"] == 0
    assert not any("--schematic-parity" in c["args"] for c in calls(fake))
    assert not any(i["code"] == "kicad.drc.parity-unchecked" for i in env["issues"])


def test_built_input_detected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=10, built=True)
    code, env, _, _ = run(monkeypatch, tmp_path, "check", str(root), *HERMETIC)
    assert code == 0 and env["result"]["project"]["built"] is True
    assert _stages(env)["model.validate"]["status"] == "ok"


def test_clean_built_project(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=10, built=True)
    code, env, _, _ = run(monkeypatch, tmp_path, "check", str(root), "--stages", "model.validate")
    stage = _stages(env)["model.validate"]
    assert code == 0 and stage["status"] == "ok" and stage["evidence"]["level"] == "INFERRED"


def test_unreadable_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=10, built=True)
    (root / ".fenolite" / "board.json").write_text("{", encoding="utf-8")
    code, env, _, stdout = run(monkeypatch, tmp_path, "check", str(root), *HERMETIC)
    stages = _stages(env)
    assert [i["code"] for i in env["issues"]].count("check.cache-unreadable") == 1
    assert stages["model.validate"]["reason"] == "cache-unreadable"
    assert stages["roundtrip"]["status"] == "ok" and code == 0
    assert str(tmp_path) not in stdout


def test_native_board_passes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _, _ = run(monkeypatch, tmp_path, "check", str(TWO_LAYER), "--stages", "roundtrip")
    text = TWO_LAYER.read_text(encoding="utf-8")
    assert code == 0 and _stages(env)["roundtrip"]["summary"]["opaque_count"] == opaque_count(
        read_board(text)
    )


def test_hermetic_stages_are_deterministic(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    first = run(monkeypatch, tmp_path, "check", str(TWO_LAYER), *HERMETIC)[3]
    second = run(monkeypatch, tmp_path, "check", str(TWO_LAYER), *HERMETIC)[3]
    assert without_elapsed(first) == without_elapsed(second)
    assert str(DATA) not in first


def test_missing_tool(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, _, err, _ = run(monkeypatch, tmp_path, "check", str(TWO_LAYER))
    assert code == 6 and err["code"] == "FEN-6001" and "--stages" in err["hint"]


@pytest.mark.parametrize(
    ("version", "header"),
    [("8.0.7", None), ("9.0.9", b"20260206"), ("10.0.6", b"20990101")],
)
def test_unsupported_or_older_major(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, version: str,
                                    header: bytes | None) -> None:  # fmt: skip
    data = TWO_LAYER.read_bytes()
    if header is not None:
        data = data.replace(b"(version 20241229)", b"(version " + header + b")", 1)
    board = _copy(tmp_path, data=data)
    fake = fake_kicad_cli(tmp_path / "bin", version=version)
    code, _, err, _ = run(monkeypatch, tmp_path, "check", str(board), "--kicad-cli", str(fake))
    assert code == 6 and err["code"] == "FEN-6002"
    assert [c["args"] for c in calls(fake)] == [["version"]]


@posix_tools  # a timeout kills the .cmd launcher of the fake, not its Python child
def test_oracle_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=10)
    fake = fake_kicad_cli(tmp_path / "bin", sleep=30.0)
    real_version = KicadCli.version

    def patient_version(self: KicadCli) -> str:
        # The quick ``version`` call gets a generous limit, so that a loaded machine cannot make it late;
        # only the sleeping calls run under ``--timeout 2``.
        limit, self.timeout = self.timeout, 60.0
        try:
            return real_version(self)
        finally:
            self.timeout = limit

    monkeypatch.setattr(KicadCli, "version", patient_version)
    code, env, _, _ = run(
        monkeypatch, tmp_path, "check", str(root), "--kicad-cli", str(fake), "--timeout", "2"
    )
    failed = [i for i in env["issues"] if i["code"] == "check.oracle-failed"]
    assert code == 5 and failed and all(i["retryable"] is True for i in failed)
    assert {s["name"] for s in env["result"]["stages"] if s["status"] == "errors"} == {
        "zone.fill",
        "drc.kicad",
        "netlist.assignment_compare",
    }


def test_rules_without_project(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = _copy(tmp_path)
    shutil.copyfile(DATA / "kicad" / "rules" / "units.kicad_dru", board.with_suffix(".kicad_dru"))
    fake = fake_kicad_cli(
        tmp_path / "bin", ipcd356=_ipc.for_board(board), refill_board=board.read_text(encoding="utf-8") + "\n"
    )
    code, env, _, _ = run(monkeypatch, tmp_path, "check", str(board.parent), "--kicad-cli", str(fake))
    assert "kicad.drc.rules-not-loaded" in [i["code"] for i in env["issues"]]
    assert _stages(env)["drc.kicad"]["summary"]["canary"] == "not-applicable"
    assert _only_the_fixture_short(code, env)  # native input: the rules verdict is an info


def test_unreadable_board_without_drc(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = _copy(tmp_path, data=TWO_LAYER.read_bytes() + b"\n(trailing)\n")
    _no_subprocess(monkeypatch)
    code, env, err, _ = run(
        monkeypatch, tmp_path, "check", str(board), "--stages", "model.validate,roundtrip"
    )
    assert code == 3 and err["code"] == "FEN-3004"
    assert env["ok"] is False
    assert [i["code"] for i in env["issues"]] == ["check.read-refused"]
    assert env["issues"][0]["message"].startswith("FEN-3004: ")
    assert env["issues"][0]["where"].startswith("board.kicad_pcb:") and "@" in env["issues"][0]["where"]


def test_board_older_than_the_read_floor(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = _copy(
        tmp_path, data=TWO_LAYER.read_bytes().replace(b"(version 20241229)", b"(version 20221018)", 1)
    )
    code, env, err, _ = run(monkeypatch, tmp_path, "check", str(board), "--stages", "roundtrip")
    assert code == 3 and err["code"] == "FEN-3003"
    assert [i["code"] for i in env["issues"]] == ["check.read-refused"]
    assert env["issues"][0]["message"].startswith("FEN-3003: ")


def test_unreadable_board_with_a_report(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=10)
    board = root / f"{STEM}.kicad_pcb"
    board.write_bytes(board.read_bytes() + b"\n(trailing)\n")
    fake = fake_kicad_cli(tmp_path / "bin")
    code, env, _, _ = run(monkeypatch, tmp_path, "check", str(root), "--kicad-cli", str(fake))
    stages = _stages(env)
    assert code == 5 and stages["roundtrip"]["reason"] == "read-refused"
    assert stages["model.validate"]["reason"] == "read-refused"
    assert stages["drc.kicad"]["summary"]["canary_reason"] == "board-unparsed"
    assert env["issues"][0]["code"] == "check.read-refused"


# -- stages added by c0020


def _native(tmp_path: Path) -> tuple[Path, Path]:
    board = _copy(tmp_path)
    board.with_suffix(".kicad_pro").write_text("{}\n", encoding="utf-8")
    return board, fake_kicad_cli(
        tmp_path / "bin", ipcd356=_ipc.for_board(board), refill_board=board.read_text(encoding="utf-8") + "\n"
    )


def test_default_stages_leave_rt2_out(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board, fake = _native(tmp_path)
    code, env, _, _ = run(monkeypatch, tmp_path, "check", str(board.parent), "--kicad-cli", str(fake))
    assert _only_the_fixture_short(code, env), env["issues"]
    assert [s["name"] for s in env["result"]["stages"]] == [
        "model.validate",
        "erc.kicad",
        "copper.clearance",
        "zone.fill",
        "drc.kicad",
        "netlist.assignment_compare",
        "roundtrip",
    ]
    assert _stages(env)["copper.clearance"]["status"] == "errors"
    compare = _stages(env)["netlist.assignment_compare"]
    assert compare["status"] == "ok"
    assert compare["summary"]["pairs"] == [
        {"a": "board", "b": "export", "common": 4, "only_a": 0, "only_b": 0, "differences": 0}
    ]
    assert _stages(env)["drc.kicad"]["summary"]["violations_judged"] is True


def test_rt2_selected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board, fake = _native(tmp_path)
    code, env, _, _ = run(
        monkeypatch, tmp_path, "check", str(board.parent), "--kicad-cli", str(fake),
        "--stages", "roundtrip.rt2,roundtrip",
    )  # fmt: skip
    assert code == 0, env["issues"]
    assert [s["name"] for s in env["result"]["stages"]] == ["roundtrip", "roundtrip.rt2"]
    rt2 = _stages(env)["roundtrip.rt2"]
    assert rt2["status"] == "ok" and rt2["summary"]["holds"] is True and rt2["summary"]["normalised"] is True
    assert [c["args"][:2] for c in calls(fake)].count(["pcb", "upgrade"]) == 2


@pytest.mark.parametrize("stage", ["netlist.assignment_compare", "roundtrip.rt2"])
def test_new_stages_need_kicad_cli(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, stage: str) -> None:
    code, env, err, _ = run(monkeypatch, tmp_path, "check", str(TWO_LAYER), "--stages", stage)
    assert code == 6 and err["code"] == "FEN-6001"
    assert "stages" not in env.get("result", {})


def test_oracle_built_only_for_oracle_stages(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = _copy(tmp_path)
    _no_subprocess(monkeypatch)
    code, env, _, _ = run(monkeypatch, tmp_path, "check", str(board), *HERMETIC)
    assert code == 0 and [s["name"] for s in env["result"]["stages"]] == ["model.validate", "roundtrip"]


def test_render_stage_is_opt_in(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Capability verification-loop, "Render stage" (c0024): absent by default, selected by name."""
    board, fake = _native(tmp_path)
    code, env, _, _ = run(monkeypatch, tmp_path, "check", str(board), "--kicad-cli", str(fake))
    assert _only_the_fixture_short(code, env) and "render" not in _stages(env)
    assert not any(c["args"][:2] == ["pcb", "render"] for c in calls(fake))
    code, env, _, _ = run(
        monkeypatch, tmp_path, "check", str(board), "--stages", "roundtrip,render", "--kicad-cli", str(fake)
    )
    assert code == 0, env["issues"]
    render = _stages(env)["render"]
    assert render["status"] == "ok"
    assert [v["name"] for v in render["summary"]["views"]] == [  # type: ignore[index]
        "back.svg",
        "bottom.png",
        "front.svg",
        "top.png",
    ]
    assert sorted(p.name for p in board.parent.iterdir()) == ["board.kicad_pcb", "board.kicad_pro"]


def test_a_failed_view_never_fails_the_check(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = _copy(tmp_path)
    fake = fake_kicad_cli(tmp_path / "bin", export_fail=("render",))
    code, env, err, _ = run(
        monkeypatch, tmp_path, "check", str(board), "--stages", "render", "--kicad-cli", str(fake)
    )
    assert code == 0 and err == {}
    assert [(i["code"], i["severity"]) for i in env["issues"]] == [("render.failed", "warning")] * 2


def test_render_stage_needs_the_tool(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = _copy(tmp_path)
    code, _, err, _ = run(monkeypatch, tmp_path, "check", str(board), "--stages", "render")
    assert code == 6 and err["code"] == "FEN-6001"
