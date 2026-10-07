# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite export`` against the fake ``kicad-cli`` (capability cli-contract, "Export command";
manufacturing-exports, "Export evidence" and "Manifest merging"; changes c0024 and c0065). Hermetic."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import _schema
import pytest
from _checkcli import hide_kicad, run
from _fakecli import PDF, calls, fake_kicad_cli
from _models import BOX, BOX_REL, official, with_models
from _projects import SCHEMATICS, authored_project, tree_snapshot

from fenolite.backends.kicad.models import board_models
from fenolite.exports import DOCUMENTS_EVIDENCE, EVIDENCE
from fenolite.exports.manifest import content_sha256

ALL = ("--all", "--manifest")
FILES = [
    "fab/drill/board-NPTH.drl",
    "fab/drill/board-PTH.drl",
    "fab/gerbers/board-Edge_Cuts.gbr",
    "fab/gerbers/board-F_Cu.gbr",
    "fab/gerbers/board-job.gbrjob",
    "fab/netlist/board.d356",
    "fab/pos/board-pos.csv",
    "fab/fenolite-artifacts.json",
]


@pytest.fixture
def root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    hide_kicad(monkeypatch, tmp_path)
    return authored_project(tmp_path, major=10)


def _fake(tmp_path: Path, **options: object) -> str:
    return str(fake_kicad_cli(tmp_path / "bin", **options))  # type: ignore[arg-type]


def test_plan_then_write(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    args = ("export", str(root), "--out", "fab", *ALL, "--kicad-cli", _fake(tmp_path))
    code, env, _, _ = run(monkeypatch, work, *args, "--dry-run")
    assert code == 0, env
    assert [p["path"] for p in env["result"]["plan"]] == FILES
    assert list(work.iterdir()) == []

    code, env, _, _ = run(monkeypatch, work, *args, "--confirm")
    assert code == 0, env
    written = {w["path"]: w["sha256"] for w in env["receipt"]["written"]}
    assert list(written) == FILES
    for path, sha in written.items():
        assert hashlib.sha256((work / path).read_bytes()).hexdigest() == sha
    assert env["result"]["kinds"] == ["gerbers", "drill", "pos", "ipcd356"]
    assert env["result"]["board"] == "board.kicad_pcb" and env["result"]["out"] == "fab"
    assert env["result"]["tool_version"] == "10.0.6"


def test_manifest_matches_the_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    stamp = "2026-01-02T03:04:05+00:00"
    args = ("export", str(root), "--out", "fab", *ALL, "--kicad-cli", _fake(tmp_path), "--timestamp", stamp)
    code, env, _, _ = run(monkeypatch, work, *args, "--confirm")
    assert code == 0, env
    text = (work / "fab" / "fenolite-artifacts.json").read_text(encoding="utf-8")
    manifest = json.loads(text)
    assert _schema.validate(manifest, _schema.load("fenolite.artifacts.v0.json")) == []
    assert manifest["generated"] == stamp
    board = (root / "board.kicad_pcb").read_bytes()
    assert manifest["board"]["path"] == "board.kicad_pcb"
    assert manifest["board"]["sha256"] == hashlib.sha256(board).hexdigest() == env["input"]["sha256"]
    assert manifest["board"]["format_version"] == int(env["input"]["format_version"])
    assert manifest["tool"] == {"name": "kicad-cli", "version": "10.0.6"}
    assert [e["path"] for e in manifest["artifacts"]] == sorted(p[4:] for p in FILES[:-1])
    for entry in manifest["artifacts"]:
        data = (work / "fab" / entry["path"]).read_bytes()
        assert entry["bytes"] == len(data) and entry["sha256"] == hashlib.sha256(data).hexdigest()
        assert entry["content_sha256"] == content_sha256(data, entry["kind"])
    layers = {e["path"]: e["layer"] for e in manifest["artifacts"]}
    assert layers["gerbers/board-F_Cu.gbr"] == "F.Cu" and layers["gerbers/board-job.gbrjob"] is None
    result = {a["path"]: a for a in env["result"]["artifacts"]}
    assert all("evidence" not in a for a in result.values())
    assert result["pos/board-pos.csv"]["sha256"] == result["pos/board-pos.csv"]["content_sha256"]
    for needle in (str(tmp_path), str(Path.home()), "fenolite-kicad-"):
        assert needle not in text and needle not in json.dumps(env["result"])

    code, _, _, _ = run(monkeypatch, work, *args, "--confirm", "--no-backup")
    assert code == 0 and (work / "fab" / "fenolite-artifacts.json").read_text(encoding="utf-8") == text


def test_selected_kinds_only_and_no_manifest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path
) -> None:
    fake = _fake(tmp_path)
    args = ("export", str(root), "--out", "fab", "--drill", "--pos", "--kicad-cli", fake, "--dry-run")
    code, env, _, _ = run(monkeypatch, tmp_path, *args)
    assert code == 0 and env["result"]["kinds"] == ["drill", "pos"]
    assert [p["path"] for p in env["result"]["plan"]] == [
        "fab/drill/board-NPTH.drl",
        "fab/drill/board-PTH.drl",
        "fab/pos/board-pos.csv",
    ]
    exports = [c["args"][2] for c in calls(Path(fake)) if c["args"][:2] == ["pcb", "export"]]
    assert exports == ["drill", "pos"]


def test_confirmation_is_required(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    args = ("export", str(root), "--out", "fab", *ALL, "--kicad-cli", _fake(tmp_path))
    code, env, err, _ = run(monkeypatch, work, *args)
    assert code == 4 and err["code"] == "FEN-4001" and len(env["result"]["plan"]) == len(FILES)
    assert list(work.iterdir()) == []


def test_one_failing_kind_writes_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    fake = _fake(tmp_path, export_fail=("drill",))
    code, env, err, _ = run(
        monkeypatch, work, "export", str(root), "--out", "fab", "--all", "--kicad-cli", fake, "--confirm"
    )
    assert code == 5 and err["code"] == "FEN-5001"
    (failure,) = env["issues"]
    assert failure["code"] == "export.failed" and failure["where"] == "drill"
    assert "plan" not in env["result"] and env["receipt"] is None
    assert not (work / "fab").exists()
    assert [a["kind"] for a in env["result"]["artifacts"]].count("gerbers") == 3  # the other kinds still ran


def test_no_kind_selected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path) -> None:
    code, _, err, _ = run(monkeypatch, tmp_path, "export", str(root), "--out", "fab", "--confirm")
    assert code == 2 and err["code"] == "FEN-2001"


def test_no_tool(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path) -> None:
    code, _, err, _ = run(monkeypatch, tmp_path, "export", str(root), "--out", "fab", "--all", "--dry-run")
    assert code == 6 and err["code"] == "FEN-6001"


def test_unsupported_major(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path) -> None:
    fake = _fake(tmp_path, version="8.0.9")
    code, _, err, _ = run(
        monkeypatch, tmp_path, "export", str(root), "--out", "fab", "--all", "--kicad-cli", fake, "--dry-run"
    )
    assert code == 6 and err["code"] == "FEN-6002"


def test_missing_path_and_unreadable_board(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path
) -> None:
    fake = _fake(tmp_path)
    tail = ("--out", "fab", "--all", "--kicad-cli", fake, "--dry-run")
    code, _, err, _ = run(monkeypatch, tmp_path, "export", str(tmp_path / "nowhere"), *tail)
    assert code == 3 and err["code"] == "FEN-3001"
    bad = tmp_path / "bad.kicad_pcb"
    bad.write_text("(kicad_pcb (version 20260206) (unclosed", encoding="utf-8")
    code, _, err, _ = run(monkeypatch, tmp_path, "export", str(bad), *tail)
    assert code == 3 and err["code"].startswith("FEN-3")


def test_a_kind_that_writes_nothing_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path
) -> None:
    fake = _fake(tmp_path, export_files={"pos": {}})
    code, env, _, _ = run(
        monkeypatch, tmp_path, "export", str(root), "--out", "fab", "--pos", "--kicad-cli", fake, "--dry-run"
    )
    assert code == 5 and env["issues"][0]["code"] == "export.failed"
    assert "wrote no file" in env["issues"][0]["message"]


def test_source_is_untouched(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path) -> None:
    fake = _fake(tmp_path, writes=("x.kicad_prl",), rewrite_input=True)
    before = tree_snapshot(root)
    work = tmp_path / "elsewhere"
    work.mkdir()
    code, env, _, _ = run(
        monkeypatch, work, "export", str(root), "--out", "fab", *ALL, "--kicad-cli", fake, "--confirm"
    )
    assert code == 0, env
    assert tree_snapshot(root) == before and not (root / "x.kicad_prl").exists()
    assert env["result"]["tool_writes"] == ["x.kicad_prl"]
    assert (work / "fab" / "gerbers" / "board-F_Cu.gbr").is_file()


def test_evidence_in_the_envelope(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path) -> None:
    code, env, _, _ = run(
        monkeypatch, tmp_path, "export", str(root), "--out", "fab", "--pos", "--kicad-cli", _fake(tmp_path),
        "--dry-run",
    )  # fmt: skip
    assert code == 0
    assert env["evidence"]["level"] == EVIDENCE.level.value
    assert env["evidence"]["oracle"] == "kicad-cli 10.0.6"
    assert env["evidence"]["hypotheses"] == ["H-K-EXPORT-FILES", "H-K-EXPORT-REPEAT"]


# -- presets (c0074)

PRESET = 'schema = "fenolite.export-preset.v0"\n[drill]\nunits = "in"\n'


def _export_calls(fake: str) -> dict[str, list[str]]:
    return {c["args"][2]: c["args"] for c in calls(Path(fake)) if c["args"][:2] == ["pcb", "export"]}


def test_preset_changes_the_drill_units(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    (work / "fab.toml").write_text(PRESET, encoding="utf-8")
    fake = _fake(tmp_path)
    args = ("export", str(root), "--out", "fab", "--drill", "--preset", "fab.toml", "--kicad-cli", fake)
    code, env, _, _ = run(monkeypatch, work, *args, "--dry-run")
    assert code == 0, env
    drill = _export_calls(fake)["drill"]
    assert drill[drill.index("--excellon-units") + 1] == "in"
    preset = env["result"]["preset"]
    assert preset["file"] == "fab.toml"
    assert preset["sha256"] == hashlib.sha256(PRESET.encode("utf-8")).hexdigest()
    assert "H-K-EXPORT-OPTIONS" in env["evidence"]["hypotheses"]


def test_no_preset_runs_the_fixed_arguments(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path
) -> None:
    fake = _fake(tmp_path)
    args = ("export", str(root), "--out", "fab", "--drill", "--kicad-cli", fake, "--dry-run")
    code, env, _, _ = run(monkeypatch, tmp_path, *args)
    assert code == 0 and env["result"]["preset"] is None
    drill = _export_calls(fake)["drill"]
    assert drill[drill.index("--excellon-units") + 1] == "mm"
    assert "H-K-EXPORT-OPTIONS" not in env["evidence"]["hypotheses"]


def test_invalid_preset(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    (work / "fab.toml").write_text('schema = "other.v1"\n', encoding="utf-8")
    fake = _fake(tmp_path)
    args = ("export", str(root), "--out", "fab", "--drill", "--preset", "fab.toml", "--kicad-cli", fake)
    code, _, err, _ = run(monkeypatch, work, *args, "--dry-run")
    assert code == 3 and err["code"] == "FEN-3004" and "fab.toml" in err["message"] + err.get("where", "")
    assert calls(Path(fake)) == []


def test_missing_preset(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path) -> None:
    fake = _fake(tmp_path)
    args = ("export", str(root), "--out", "fab", "--drill", "--preset", "none.toml", "--kicad-cli", fake)
    code, _, err, _ = run(monkeypatch, tmp_path, *args, "--dry-run")
    assert code == 3 and err["code"] == "FEN-3001" and calls(Path(fake)) == []


def test_position_file_follows_its_format(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path
) -> None:
    work = tmp_path / "work"
    work.mkdir()
    (work / "fab.toml").write_text(
        'schema = "fenolite.export-preset.v0"\n[pos]\nformat = "ascii"\n', encoding="utf-8"
    )
    fake = _fake(tmp_path)
    args = ("export", str(root), "--out", "fab", "--pos", "--preset", "fab.toml", "--kicad-cli", fake)
    code, env, _, _ = run(monkeypatch, work, *args, "--dry-run")
    assert code == 0, env
    assert [p["path"] for p in env["result"]["plan"]] == ["fab/pos/board-pos.pos"]
    assert "pos/board-pos.pos" in _export_calls(fake)["pos"]


def _listed(work: Path) -> dict[str, dict[str, object]]:
    text = (work / "fab" / "fenolite-artifacts.json").read_text(encoding="utf-8")
    manifest = json.loads(text)
    assert _schema.validate(manifest, _schema.load("fenolite.artifacts.v0.json")) == []
    assert [e["path"] for e in manifest["artifacts"]] == sorted(e["path"] for e in manifest["artifacts"])
    assert manifest["check"] is None and sum(manifest["states"].values()) == len(manifest["artifacts"])
    return {e["path"]: e for e in manifest["artifacts"]}


def test_merge_two_runs_into_one_manifest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path
) -> None:
    work = tmp_path / "work"
    work.mkdir()
    base = ("export", str(root), "--out", "fab", "--manifest", "--kicad-cli", _fake(tmp_path), "--confirm")
    code, env, _, _ = run(monkeypatch, work, *base, "--gerbers")
    assert code == 0, env
    gerbers = ["gerbers/board-Edge_Cuts.gbr", "gerbers/board-F_Cu.gbr", "gerbers/board-job.gbrjob"]
    assert list(_listed(work)) == gerbers
    code, env, _, _ = run(monkeypatch, work, *base, "--drill")
    assert code == 0, env
    assert [a["path"] for a in env["result"]["artifacts"]] == ["drill/board-NPTH.drl", "drill/board-PTH.drl"]
    assert set(env["result"]["artifacts"][0]) == {
        "path",
        "kind",
        "layer",
        "bytes",
        "sha256",
        "content_sha256",
    }
    listed = _listed(work)
    assert list(listed) == ["drill/board-NPTH.drl", "drill/board-PTH.drl", *gerbers]
    first = hashlib.sha256((root / "board.kicad_pcb").read_bytes()).hexdigest()
    for item in listed.values():
        assert item["state"] == "generated" and item["stale"] is False
        assert item["from"] == {"board": first} and item["tool"] == "kicad-cli 10.0.6"

    # the board changes and the Gerbers are exported again: they are replaced by path, the rest is kept
    board = root / "board.kicad_pcb"
    board.write_bytes(board.read_bytes() + b"\n")
    second = hashlib.sha256(board.read_bytes()).hexdigest()
    code, env, _, _ = run(monkeypatch, work, *base, "--gerbers")
    assert code == 0 and first != second, env
    listed = _listed(work)
    assert {listed[path]["from"]["board"] for path in gerbers} == {second}  # type: ignore[index]
    assert listed["drill/board-PTH.drl"]["from"] == {"board": first}
    manifest = json.loads((work / "fab" / "fenolite-artifacts.json").read_text(encoding="utf-8"))
    assert manifest["board"]["sha256"] == second == manifest["project"]["board"]["sha256"]
    assert manifest["states"]["generated"] == 5


def test_merge_into_a_manifest_of_v01(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path) -> None:
    work = tmp_path / "work"
    (work / "fab").mkdir(parents=True)
    old = Path(__file__).resolve().parents[2] / "data" / "exports" / "manifest_v01.json"
    (work / "fab" / "fenolite-artifacts.json").write_bytes(old.read_bytes())
    args = ("export", str(root), "--out", "fab", "--pos", "--manifest", "--kicad-cli", _fake(tmp_path))
    code, env, _, _ = run(monkeypatch, work, *args, "--confirm")
    assert code == 0, env
    listed = _listed(work)
    assert list(listed) == ["drill/board-PTH.drl", "gerbers/board-F_Cu.gbr", "pos/board-pos.csv"]
    kept = listed["gerbers/board-F_Cu.gbr"]
    assert (kept["state"], kept["stale"], kept["from"], kept["tool"]) == ("generated", False, {}, None)
    assert kept["sha256"] == "4" * 64 and listed["pos/board-pos.csv"]["tool"] == "kicad-cli 10.0.6"


@pytest.mark.parametrize("text", ["{", '{"schema": "fenolite.artifacts.v9", "artifacts": []}'])
def test_unreadable_manifest_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path, text: str
) -> None:
    work = tmp_path / "work"
    (work / "fab").mkdir(parents=True)
    (work / "fab" / "fenolite-artifacts.json").write_text(text, encoding="utf-8")
    before = tree_snapshot(work)
    args = ("export", str(root), "--out", "fab", "--gerbers", "--manifest", "--kicad-cli", _fake(tmp_path))
    code, env, err, _ = run(monkeypatch, work, *args, "--confirm")
    assert code == 5 and err["code"] == "FEN-5001"
    (refusal,) = env["issues"]
    assert refusal["code"] == "manifest.unreadable" and refusal["severity"] == "error"
    assert refusal["where"] == "fab/fenolite-artifacts.json"
    assert "plan" not in env["result"] and env["receipt"] is None and tree_snapshot(work) == before
    # without --manifest the command does not look at the file
    code, env, _, _ = run(monkeypatch, work, *args[:5], *args[6:], "--confirm")
    assert code == 0 and (work / "fab" / "fenolite-artifacts.json").read_text(encoding="utf-8") == text


def test_manifest_entry_of_a_preset_export_has_the_level_of_the_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path
) -> None:
    """An export with a preset is ``INFERRED`` (c0074); its entries claim no more than the envelope."""
    work = tmp_path / "work"
    work.mkdir()
    (work / "fab.toml").write_text(PRESET, encoding="utf-8")
    base = ("export", str(root), "--out", "fab", "--manifest", "--kicad-cli", _fake(tmp_path), "--confirm")
    code, env, _, _ = run(monkeypatch, work, *base, "--pos")
    assert code == 0 and env["evidence"]["level"] == "KICAD-VERIFIED", env
    code, env, _, _ = run(monkeypatch, work, *base, "--drill", "--preset", "fab.toml")
    assert code == 0 and env["evidence"]["level"] == "INFERRED", env
    listed = _listed(work)
    assert listed["pos/board-pos.csv"]["evidence"] == "KICAD-VERIFIED"
    assert {listed[p]["evidence"] for p in listed if p.startswith("drill/")} == {"INFERRED"}


# --- the Altium rule file (capability manufacturing-exports, "Altium rule file export"; change c0084) ---


def test_altium_rule_file_needs_no_tool(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path) -> None:
    """Scenario "Rule file from a built project": dry run, confirm and receipt, with ``kicad-cli`` hidden."""
    from fenolite.backends.altium import rulemap
    from fenolite.backends.altium.read.rul import read_rule_file
    from fenolite.backends.altium.read.rules import map_rules
    from fenolite.model.rules import Selector

    work = tmp_path / "work"
    work.mkdir()
    args = ("export", str(root), "--out", "fab", "--altium-rul")
    code, env, _, _ = run(monkeypatch, work, *args, "--dry-run")
    assert code == 0, env
    assert [p["path"] for p in env["result"]["plan"]] == ["fab/board.RUL"] and list(work.iterdir()) == []
    code, env, _, _ = run(monkeypatch, work, *args, "--manifest", "--confirm")
    assert code == 0, env
    assert [w["path"] for w in env["receipt"]["written"]] == ["fab/board.RUL", "fab/fenolite-artifacts.json"]
    result = env["result"]
    assert (
        result["kinds"] == ["altium-rul"] and result["tool_version"] is None and result["tool_writes"] == []
    )
    assert result["rules"] == {
        "written": [{"kind": "clearance", "selector": "net VIN", "rule": "Clearance_net_VIN"}],
        "not_lowered": [],
    }
    assert [(a["path"], a["kind"]) for a in result["artifacts"]] == [("board.RUL", "altium-rul")]
    assert env["evidence"]["level"] == "INFERRED" and env["evidence"]["oracle"] is None
    assert set(env["evidence"]["hypotheses"]) == set(rulemap.EVIDENCE.hypotheses)
    data = (work / "fab" / "board.RUL").read_bytes()
    mapping = map_rules([r.fields for r in read_rule_file(data).records], origin="board.RUL")
    (rule,) = mapping.ruleset.rules
    assert (rule.kind, rule.min, rule.selector_a) == ("clearance", 200_000, Selector("net", "VIN"))
    listed = json.loads((work / "fab" / "fenolite-artifacts.json").read_text(encoding="utf-8"))
    (entry,) = listed["artifacts"]
    assert (entry["path"], entry["kind"], entry["evidence"]) == ("board.RUL", "altium-rul", "INFERRED")
    assert entry["tool"].startswith("fenolite ") and listed["tool"]["name"] == "fenolite"


def test_altium_rule_file_beside_the_tool_kinds(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path
) -> None:
    """``--all`` does not select the rule file; with a tool kind the envelope has the lower level."""
    work = tmp_path / "work"
    work.mkdir()
    base = ("export", str(root), "--out", "fab", "--kicad-cli", _fake(tmp_path), "--dry-run")
    code, env, _, _ = run(monkeypatch, work, *base, "--all")
    assert code == 0 and "rules" not in env["result"], env
    assert not [p for p in env["result"]["plan"] if p["path"].endswith(".RUL")]
    code, env, _, _ = run(monkeypatch, work, *base, "--pos", "--altium-rul")
    assert code == 0, env
    assert env["result"]["kinds"] == ["pos", "altium-rul"]
    assert [p["path"] for p in env["result"]["plan"]] == ["fab/board.RUL", "fab/pos/board-pos.csv"]
    assert env["evidence"]["level"] == "INFERRED" and env["evidence"]["oracle"].startswith("kicad-cli ")


def test_altium_rule_file_without_a_rule_that_lowers(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    hide_kicad(monkeypatch, tmp_path)
    work = tmp_path / "work"
    work.mkdir()
    for folder, rules in (("a", None), ("b", "one-rule")):
        root = authored_project(tmp_path / folder, major=10, rules=rules)  # type: ignore[arg-type]
        if rules is not None:  # a rule with a glob has no exact Altium form
            path = root / "board.kicad_dru"
            path.write_text(path.read_text(encoding="utf-8").replace("'VIN'", "'V*'"), encoding="utf-8")
        args = ("export", str(root), "--out", "fab", "--altium-rul", "--confirm")
        code, env, err, _ = run(monkeypatch, work, *args)
        assert code == 5 and err["code"] == "FEN-5001", env
        (failure,) = env["issues"]
        assert (failure["code"], failure["where"]) == ("export.failed", "altium-rul")
        assert "plan" not in env["result"] and not (work / "fab").exists()
        if rules is not None:
            assert env["result"]["rules"]["not_lowered"] == [
                {"kind": "clearance", "selector": "net V*", "reason": "scope-unsupported"}
            ]
            assert "clearance (scope-unsupported)" in failure["message"]


def test_no_kind_names_the_rule_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path) -> None:
    code, _, err, _ = run(monkeypatch, tmp_path, "export", str(root), "--out", "fab", "--dry-run")
    assert code == 2 and "--altium-rul" in err["hint"]


# -- document kinds (c0116)

DOCUMENT_FLAGS = ("--ipc2581", "--odb", "--step", "--pdf", "--dxf")
DOCUMENT_FILES = [
    "fab/3d/board.step",
    "fab/dxf/board-Edge_Cuts.dxf",
    "fab/ipc2581/board.xml",
    "fab/odb/board.zip",
    "fab/pdf/board-Edge_Cuts.pdf",
    "fab/pdf/board-F_Cu.pdf",
]


def _with_schematic(root: Path) -> None:
    """The authored two-sheet hierarchy as the schematic of the board."""
    (root / "board.kicad_sch").write_bytes((SCHEMATICS / "hier" / "top.kicad_sch").read_bytes())
    (root / "child.kicad_sch").write_bytes((SCHEMATICS / "hier" / "child.kicad_sch").read_bytes())


def _all_calls(fake: str) -> list[list[str]]:
    return [c["args"] for c in calls(Path(fake)) if c["args"][1:2] == ["export"]]


def test_documents_are_planned(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path) -> None:
    fake = _fake(tmp_path)
    args = ("export", str(root), "--out", "fab", *DOCUMENT_FLAGS, "--kicad-cli", fake, "--dry-run")
    code, env, _, out = run(monkeypatch, tmp_path, *args)
    assert code == 0, env
    result = env["result"]
    assert [p["path"] for p in result["plan"]] == DOCUMENT_FILES
    assert result["kinds"] == ["ipc2581", "odb", "step", "pdf", "dxf"]
    assert result["repeat"] == {
        "ipc2581": "none", "odb": "none", "step": "none", "pdf": "content", "dxf": "bytes",
    }  # fmt: skip
    # the footprints of the authored board name Mini models that no source holds: each is reported
    # as missing, with a warning, and the exit code stays 0
    assert result["models"] and all(
        m["source"] == "missing" and m["sha256"] is None for m in result["models"]
    )
    assert [m["path"] for m in result["models"]] == sorted(m["path"] for m in result["models"])
    assert {i["code"] for i in env["issues"]} == {"kicad.lib.missing-3d-model"}
    assert len(env["issues"]) == len(result["models"])
    layers = {a["path"]: a["layer"] for a in result["artifacts"]}
    assert layers["pdf/board-F_Cu.pdf"] == "F.Cu" and layers["dxf/board-Edge_Cuts.dxf"] == "Edge.Cuts"
    assert layers["3d/board.step"] is None
    hashes = {a["path"]: (a["sha256"], a["content_sha256"]) for a in result["artifacts"]}
    assert hashes["3d/board.step"][0] == hashes["3d/board.step"][1]  # nothing to leave out
    assert hashes["pdf/board-F_Cu.pdf"][0] != hashes["pdf/board-F_Cu.pdf"][1]  # the creation date
    assert [a[2] for a in _all_calls(fake)] == ["ipc2581", "odb", "step", "pdf", "dxf"]
    for needle in (str(tmp_path), str(Path.home()), "fenolite-kicad-"):
        assert needle not in out


def test_all_keeps_the_four_kinds(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path) -> None:
    fake = _fake(tmp_path)
    code, env, _, _ = run(
        monkeypatch, tmp_path, "export", str(root), "--out", "fab", "--all", "--kicad-cli", fake, "--dry-run"
    )
    assert code == 0
    assert [a[:3] for a in _all_calls(fake)] == [
        ["pcb", "export", "gerbers"],
        ["pcb", "export", "drill"],
        ["pcb", "export", "pos"],
        ["pcb", "export", "ipcd356"],
    ]
    assert env["result"]["kinds"] == ["gerbers", "drill", "pos", "ipcd356"]
    assert env["result"]["repeat"] == {
        "gerbers": "content", "drill": "content", "pos": "bytes", "ipcd356": "bytes",
    }  # fmt: skip
    assert env["result"]["models"] == []


def test_a_preset_leaves_a_document_kind_alone(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path
) -> None:
    work = tmp_path / "work"
    work.mkdir()
    (work / "fab.toml").write_text(PRESET, encoding="utf-8")
    fake = _fake(tmp_path)
    args = (
        "export",
        str(root),
        "--out",
        "fab",
        "--drill",
        "--dxf",
        "--preset",
        "fab.toml",
        "--kicad-cli",
        fake,
    )
    code, env, _, _ = run(monkeypatch, work, *args, "--manifest", "--dry-run")
    assert code == 0, env
    seen = _export_calls(fake)
    assert seen["drill"][seen["drill"].index("--excellon-units") + 1] == "in"
    assert seen["dxf"] == [
        "pcb", "export", "dxf", "-o", "dxf/", "--mode-multi", "--output-units", "mm", "--layers",
        "Edge.Cuts,F.Fab,B.Fab,F.CrtYd,B.CrtYd", "board.kicad_pcb",
    ]  # fmt: skip


def test_schematic_pdf_without_a_schematic(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path
) -> None:
    fake = _fake(tmp_path)
    args = ("export", str(root), "--out", "fab", "--sch-pdf", "--kicad-cli", fake, "--dry-run")
    code, _, err, _ = run(monkeypatch, tmp_path, *args)
    assert code == 3 and err["code"] == "FEN-3001"
    assert "board.kicad_sch" in err["message"] and "--pdf" in err["hint"] and "--step" in err["hint"]
    assert calls(Path(fake)) == []


def test_a_missing_sheet_writes_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path) -> None:
    _with_schematic(root)
    (root / "child.kicad_sch").unlink()
    work = tmp_path / "work"
    work.mkdir()
    fake = _fake(tmp_path)
    args = ("export", str(root), "--out", "fab", "--pdf", "--sch-pdf", "--kicad-cli", fake, "--confirm")
    code, env, err, _ = run(monkeypatch, work, *args)
    assert code == 5 and err["code"] == "FEN-5001", env
    (refusal,) = env["issues"]
    assert (refusal["code"], refusal["where"]) == ("export.sheet-missing", "child.kicad_sch")
    assert "plan" not in env["result"] and not (work / "fab").exists()
    assert not any(a[:3] == ["sch", "export", "pdf"] for a in _all_calls(fake))


def test_evidence_of_a_document_kind(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path) -> None:
    fake = _fake(tmp_path)
    args = ("export", str(root), "--out", "fab", "--gerbers", "--step", "--manifest", "--kicad-cli", fake)
    code, env, _, _ = run(monkeypatch, tmp_path, *args, "--confirm")
    assert code == 0, env
    assert DOCUMENTS_EVIDENCE.level.value == "INFERRED"
    assert env["evidence"]["level"] == "INFERRED" and env["evidence"]["oracle"] == "kicad-cli 10.0.6"
    assert "H-K-EXPORT-MODELS" in env["evidence"]["hypotheses"]
    assert "H-K-EXPORT-FILES" in env["evidence"]["hypotheses"]
    manifest = json.loads((tmp_path / "fab" / "fenolite-artifacts.json").read_text(encoding="utf-8"))
    levels = {e["path"]: e["evidence"] for e in manifest["artifacts"]}
    assert levels["3d/board.step"] == "INFERRED"
    assert levels["gerbers/board-F_Cu.gbr"] == EVIDENCE.level.value != "INFERRED"
    # a document kind alone carries the level of the document kinds
    code, env, _, _ = run(
        monkeypatch, tmp_path, "export", str(root), "--out", "x", "--odb", "--kicad-cli", fake, "--dry-run"
    )
    assert env["evidence"]["hypotheses"] == list(DOCUMENTS_EVIDENCE.hypotheses)


def test_document_manifest_joins_the_folder(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path
) -> None:
    _with_schematic(root)
    work = tmp_path / "work"
    work.mkdir()
    fake = _fake(tmp_path)
    base = ("export", str(root), "--out", "fab", "--manifest", "--kicad-cli", fake, "--confirm")
    assert run(monkeypatch, work, *base, "--gerbers")[0] == 0
    code, env, _, _ = run(monkeypatch, work, *base, "--step", "--sch-pdf", "--no-backup")
    assert code == 0, env
    manifest = json.loads((work / "fab" / "fenolite-artifacts.json").read_text(encoding="utf-8"))
    assert _schema.validate(manifest, _schema.load("fenolite.artifacts.v0.json")) == []
    entries = {e["path"]: e for e in manifest["artifacts"]}
    board_sha = hashlib.sha256((root / "board.kicad_pcb").read_bytes()).hexdigest()
    sheet_sha = hashlib.sha256((root / "board.kicad_sch").read_bytes()).hexdigest()
    assert "gerbers/board-F_Cu.gbr" in entries
    assert entries["3d/board.step"]["from"] == {"board": board_sha}
    assert entries["schematic/board.pdf"]["from"] == {"schematic": sheet_sha}
    for path in ("3d/board.step", "schematic/board.pdf", "gerbers/board-F_Cu.gbr"):
        assert entries[path]["state"] == "generated" and entries[path]["tool"] == "kicad-cli 10.0.6"
    assert entries["schematic/board.pdf"]["kind"] == "sch-pdf" and entries["3d/board.step"]["kind"] == "step"
    call = next(c for c in calls(Path(fake)) if c["args"][:3] == ["sch", "export", "pdf"])
    assert call["args"] == ["sch", "export", "pdf", "-o", "schematic/board.pdf", "board.kicad_sch"]
    assert {"board.kicad_sch", "child.kicad_sch"} <= set(call["tree"])


def test_document_manifest_layer_and_source(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path
) -> None:
    _with_schematic(root)
    work = tmp_path / "work"
    work.mkdir()
    args = (
        "export",
        str(root),
        "--out",
        "out",
        "--pdf",
        "--sch-pdf",
        "--manifest",
        "--kicad-cli",
        _fake(tmp_path),
    )
    code, env, _, _ = run(monkeypatch, work, *args, "--confirm")
    assert code == 0, env
    manifest = json.loads((work / "out" / "fenolite-artifacts.json").read_text(encoding="utf-8"))
    entries = {e["path"]: e for e in manifest["artifacts"]}
    board_sha = hashlib.sha256((root / "board.kicad_pcb").read_bytes()).hexdigest()
    sheet_sha = hashlib.sha256((root / "board.kicad_sch").read_bytes()).hexdigest()
    assert (
        entries["pdf/board-F_Cu.pdf"]["layer"] == "F.Cu"
        and entries["pdf/board-Edge_Cuts.pdf"]["layer"] == "Edge.Cuts"
    )
    assert entries["pdf/board-F_Cu.pdf"]["from"] == {"board": board_sha}
    assert entries["schematic/board.pdf"]["layer"] is None
    assert entries["schematic/board.pdf"]["from"] == {"schematic": sheet_sha}
    assert all(e["evidence"] == "INFERRED" for e in entries.values())
    data = (work / "out" / "pdf" / "board-F_Cu.pdf").read_bytes()
    assert data == PDF.encode("latin-1")
    assert (
        entries["pdf/board-F_Cu.pdf"]["content_sha256"]
        == content_sha256(data, "pdf")
        != entries["pdf/board-F_Cu.pdf"]["sha256"]
    )


def test_step_reports_its_models_and_a_warning_holds_nothing_back(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path
) -> None:
    board = root / "board.kicad_pcb"
    text = board.read_text(encoding="utf-8")
    refs = [
        line.split('"')[3] for line in text.splitlines() if line.strip().startswith('(property "Reference"')
    ]
    assert len(refs) >= 2
    absent = official("Fenolite.3dshapes/Absent.step")
    board.write_text(
        with_models(text, {refs[0]: official(), refs[1]: absent}), encoding="utf-8", newline="\n"
    )
    empty = tmp_path / "config-home"
    empty.mkdir()
    # a model folder that holds the authored box under its own name and under the name of the Mini
    # model that the first footprint already names, so that every model of that part is located
    folder = tmp_path / "models"
    for ref in board_models(text):
        if ref.ref == refs[0]:
            target = folder / ref.path.split("/", 1)[1]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(BOX.read_bytes())
    (folder / BOX_REL).parent.mkdir(parents=True, exist_ok=True)
    (folder / BOX_REL).write_bytes(BOX.read_bytes())
    monkeypatch.setenv("KICAD10_3DMODEL_DIR", str(folder))
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(empty))
    work = tmp_path / "work"
    work.mkdir()
    fake = _fake(tmp_path, export_output={"step": f"Could not add 3D model for {refs[0]}.\n"})
    args = ("export", str(root), "--out", "fab", "--step", "--kicad-cli", fake, "--confirm")
    code, env, _, out = run(monkeypatch, work, *args)
    assert code == 0, env  # warnings never change the exit code
    assert {i["code"] for i in env["issues"]} == {"export.model-unread", "kicad.lib.missing-3d-model"}
    assert [i["where"] for i in env["issues"] if i["code"] == "export.model-unread"] == [refs[0]]
    assert all(i["severity"] == "warning" for i in env["issues"])
    assert (work / "fab" / "3d" / "board.step").is_file()
    found = {m["path"]: m for m in env["result"]["models"]}
    assert found[absent] == {
        "path": absent,
        "source": "missing",
        "sha256": None,
        "bytes": None,
        "refs": [refs[1]],
    }
    assert found[official()] == {
        "path": official(),
        "source": "env",
        "sha256": hashlib.sha256(BOX.read_bytes()).hexdigest(),
        "bytes": BOX.stat().st_size,
        "refs": [refs[0]],
    }
    call = next(c for c in calls(Path(fake)) if c["args"][:3] == ["pcb", "export", "step"])
    assert f"3dmodels/{BOX_REL}" in call["tree"] and call["env"] == {"KICAD10_3DMODEL_DIR": "3dmodels"}
    assert "--subst-models" in call["args"]
    assert str(tmp_path) not in out
    assert not (root / "3dmodels").exists()  # the copies went into the run, never into the project
