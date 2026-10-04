# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite check`` without a real ``kicad-cli`` (capability verification-loop: "Check command input",
"Check exit codes", "Inputs Fenolite cannot read", "Stages added for findings and round trips" and the
hermetic stage scenarios; changes c0013, c0020 and c0029)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import _ipc
import pytest
from _checkcli import hide_kicad, run, without_elapsed
from _fakecli import calls, fake_kicad_cli
from _projects import STEM, authored_project

from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.pcb import opaque_count, read_board

DATA = Path(__file__).resolve().parents[2] / "data"
TWO_LAYER = DATA / "kicad" / "board" / "two_layer.kicad_pcb"
HERMETIC = ("--stages", "model.validate,erc.lite,roundtrip")


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
    code, env, _, _ = run(monkeypatch, tmp_path, "check", str(TWO_LAYER), *HERMETIC)
    stages = _stages(env)
    assert code == 0
    assert (stages["erc.lite"]["status"], stages["erc.lite"]["reason"]) == ("skipped", "native-input")
    assert stages["model.validate"]["status"] == stages["roundtrip"]["status"] == "ok"
    assert not any(i["code"].startswith("erc.") for i in env["issues"])


def test_built_input_detected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=10, built=True)
    code, env, _, _ = run(monkeypatch, tmp_path, "check", str(root), *HERMETIC)
    assert code == 0 and env["result"]["project"]["built"] is True
    assert _stages(env)["erc.lite"]["status"] == "ok"


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
    assert stages["model.validate"]["reason"] == stages["erc.lite"]["reason"] == "cache-unreadable"
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
        "drc.kicad",
        "netlist.assignment_compare",
    }


def test_rules_without_project(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = _copy(tmp_path)
    shutil.copyfile(DATA / "kicad" / "rules" / "units.kicad_dru", board.with_suffix(".kicad_dru"))
    fake = fake_kicad_cli(tmp_path / "bin", ipcd356=_ipc.for_board(board))
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
    return board, fake_kicad_cli(tmp_path / "bin", ipcd356=_ipc.for_board(board))


def test_default_stages_leave_rt2_out(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board, fake = _native(tmp_path)
    code, env, _, _ = run(monkeypatch, tmp_path, "check", str(board.parent), "--kicad-cli", str(fake))
    assert _only_the_fixture_short(code, env), env["issues"]
    assert [s["name"] for s in env["result"]["stages"]] == [
        "model.validate",
        "erc.lite",
        "copper.clearance",
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
    assert code == 0 and [s["name"] for s in env["result"]["stages"]] == [
        "model.validate",
        "erc.lite",
        "roundtrip",
    ]


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
