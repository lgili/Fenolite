# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``build`` command (capability design-dsl, "Build command" and "Edited outputs are not
overwritten"; change c0011)."""

from __future__ import annotations

import io
import json
import shutil
from pathlib import Path

import pytest

import fenolite.cli.main as cli_main

ROOT = Path(__file__).resolve().parents[3]
BLINK_DIR = ROOT / "examples" / "blink_2layer"
FOOTPRINTS = ("Mini_LED_THT_3mm", "Mini_QFP-32_7x7mm_P0.8mm", "Mini_R_0603")


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def run(monkeypatch: pytest.MonkeyPatch, *args: str) -> tuple[int, dict[str, object], str]:
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    code = cli_main.main(["build", *args, "--json"])
    return code, json.loads(out.getvalue()) if out.getvalue() else {}, err.getvalue()


def blink_copy(tmp_path: Path) -> Path:
    """The blink folder copied next to the test libraries' relative location."""
    target = tmp_path / "repo" / "examples" / "blink_2layer"
    shutil.copytree(BLINK_DIR, target)
    shutil.copytree(ROOT / "tests" / "data" / "libs", tmp_path / "repo" / "tests" / "data" / "libs")
    return target / "design.py"


def test_confirmation_required(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = tmp_path / "B"
    code, env, err = run(monkeypatch, str(BLINK_DIR / "design.py"), "--out", str(out))
    assert code == 4 and env["result"]["plan"] and not out.exists()  # type: ignore[index]
    assert json.loads(err)["code"] == "FEN-4001"


def test_fields_project_the_plan(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """``--fields`` restricts ``result``, the dispatcher's ``plan`` included (living cli-contract)."""
    script, out = str(BLINK_DIR / "design.py"), str(tmp_path / "B")
    code, env, _ = run(monkeypatch, script, "--out", out, "--dry-run", "--fields", "design")
    assert code == 0 and env["result"] == {"design": "blink"}
    code, env, _ = run(monkeypatch, script, "--out", out, "--dry-run", "--fields", "plan")
    assert code == 0 and list(env["result"]) == ["plan"] and env["result"]["plan"]  # type: ignore[index]


def test_confirmed_build_and_rebuild(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = tmp_path / "B"
    code, env, _ = run(monkeypatch, str(BLINK_DIR / "design.py"), "--out", str(out), "--confirm")
    assert code == 0
    written = sorted(Path(w["path"]).relative_to(out).as_posix() for w in env["receipt"]["written"])  # type: ignore[index]
    assert written == sorted(
        [
            "blink.kicad_dru", "blink.kicad_pcb", "blink.kicad_pro", "fp-lib-table",
            "blink.kicad_sch", "sym-lib-table", "lib/Mini.kicad_sym", "lib/fenolite.kicad_sym",  # c0061
            *(f"lib/Mini.pretty/{n}.kicad_mod" for n in FOOTPRINTS),
            *(f".fenolite/{n}.json" for n in ("board", "build", "circuit", "findings", "manufacturing")),
            ".fenolite/meta.json", ".fenolite/rules.json",
        ]
    )  # fmt: skip
    before = {p: p.read_bytes() for p in out.rglob("*") if p.is_file()}
    code, _, _ = run(monkeypatch, str(BLINK_DIR / "design.py"), "--out", str(out), "--confirm")
    assert code == 0
    after = {p: p.read_bytes() for p in out.rglob("*") if p.is_file()}
    assert {p: d for p, d in after.items() if p.suffix != ".bak"} == before
    result = env["result"]
    assert (
        result["design"] == "blink"
        and result["target"] == 10
        and result["libraries"]["Mini:Mini_R_0603"] == "project"
    )  # type: ignore[index]
    assert env["input"]["kind"] == "fenolite-dsl" and len(env["input"]["sha256"]) == 64  # type: ignore[index]


def test_output_folder_is_the_script_folder(monkeypatch: pytest.MonkeyPatch) -> None:
    code, _, err = run(monkeypatch, str(BLINK_DIR / "design.py"), "--out", str(BLINK_DIR), "--dry-run")
    assert code == 2 and json.loads(err)["code"] == "FEN-2001"


def test_edited_board_is_merged_not_refused(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """c0019: the board, project and rules files are merged instead of refused."""
    from _layout_edit import add_items, net_ref

    out = tmp_path / "B"
    design = str(BLINK_DIR / "design.py")
    assert run(monkeypatch, design, "--out", str(out), "--confirm")[0] == 0
    board = out / "blink.kicad_pcb"
    text = board.read_text(encoding="utf-8")
    uuid = "00000000-0000-4000-8000-0000000c1901"
    segment = (
        f'(segment (start 120 120) (end 125 120) (width 0.25) (layer "F.Cu") {net_ref(text, "GND")} '
        f'(uuid "{uuid}"))'
    )
    board.write_text(add_items(text, segment), encoding="utf-8")
    code, env, _ = run(monkeypatch, design, "--out", str(out), "--confirm")
    assert code == 0 and uuid in board.read_text(encoding="utf-8")
    assert "build.layout-exists" not in [i["code"] for i in env["issues"]]  # type: ignore[index]


def _edited_footprint(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[str, Path, bytes]:
    out = tmp_path / "B"
    design = str(BLINK_DIR / "design.py")
    assert run(monkeypatch, design, "--out", str(out), "--confirm")[0] == 0
    path = out / "lib" / "Mini.pretty" / "Mini_R_0603.kicad_mod"
    edited = path.read_bytes() + b" "
    path.write_bytes(edited)
    return design, path, edited


def test_edited_vendored_footprint_refused(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    design, path, edited = _edited_footprint(monkeypatch, tmp_path)
    out = tmp_path / "B"
    before = {p: p.read_bytes() for p in out.rglob("*") if p.is_file()}
    for flags in (["--confirm"], ["--dry-run"], ["--allow-lossy", "--confirm"]):
        code, env, err = run(monkeypatch, design, "--out", str(out), *flags)
        assert code == 7 and json.loads(err)["code"] == "FEN-7001"
        found = [i for i in env["issues"] if i["code"] == "build.layout-exists"]  # type: ignore[index, union-attr]
        where = str(found[0]["where"]).replace("\\", "/")  # an OS path: backslashes on Windows
        assert len(found) == 1 and where.endswith("lib/Mini.pretty/Mini_R_0603.kicad_mod")
        assert {p: p.read_bytes() for p in out.rglob("*") if p.is_file()} == before


def test_discarding_the_layout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    design, path, edited = _edited_footprint(monkeypatch, tmp_path)
    code, _, _ = run(monkeypatch, design, "--out", str(tmp_path / "B"), "--discard-layout", "--confirm")
    assert code == 0 and path.with_name(path.name + ".bak").read_bytes() == edited


def test_dsl_edit_needs_no_flag(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script = blink_copy(tmp_path)
    out = tmp_path / "B"
    assert run(monkeypatch, str(script), "--out", str(out), "--confirm")[0] == 0
    script.write_text(script.read_text().replace('value="330"', 'value="4k7"'))
    assert run(monkeypatch, str(script), "--out", str(out), "--confirm")[0] == 0
    assert '"4k7"' in (out / "blink.kicad_pcb").read_text()


def test_lost_record(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script = blink_copy(tmp_path)
    first, second = tmp_path / "B1", tmp_path / "B2"
    for out in (first, second):
        assert run(monkeypatch, str(script), "--out", str(out), "--confirm")[0] == 0
        shutil.rmtree(out / ".fenolite")
    before = {p.name: p.read_bytes() for p in first.iterdir() if p.is_file()}
    assert run(monkeypatch, str(script), "--out", str(first), "--confirm")[0] == 0
    after = {p.name: p.read_bytes() for p in first.iterdir() if p.is_file() and not p.name.endswith(".bak")}
    assert after == before
    table = second / "fp-lib-table"
    table.write_bytes(table.read_bytes() + b" ")
    code, env, _ = run(monkeypatch, str(script), "--out", str(second), "--confirm")
    assert code == 7 and any(i["where"].endswith("fp-lib-table") for i in env["issues"])  # type: ignore[index]


def test_errors_write_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script = blink_copy(tmp_path)
    script.write_text(script.read_text() + '\ndesign.add(Net("gnd"))\n')
    out = tmp_path / "B"
    code, env, _ = run(monkeypatch, str(script), "--out", str(out), "--confirm")
    assert (
        code == 5 and "build.name-case-collision" in [i["code"] for i in env["issues"]] and not out.exists()
    )  # type: ignore[index]


def test_help_warns_about_untrusted_scripts(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli_main.main(["build", "--help"]) == 0
    assert "untrusted script" in capsys.readouterr().out


def _variant(tmp_path: Path, extra: str) -> Path:
    """The blink copy with ``extra`` lines appended to its script (c0027)."""
    script = blink_copy(tmp_path)
    script.write_text(script.read_text(encoding="utf-8") + extra, encoding="utf-8")
    return script


def _global_row(tmp_path: Path) -> None:
    """Row ``G`` in the global footprint table of the test's ``KICAD_CONFIG_HOME``."""
    folder = tmp_path / "kicad-config" / "10.0"
    folder.mkdir(parents=True, exist_ok=True)
    uri = (ROOT / "tests" / "data" / "libs" / "Mini_v9.pretty").as_posix()
    row = f'(lib (name "G") (type "KiCad") (uri "{uri}") (options "") (descr ""))'
    (folder / "fp-lib-table").write_text(f"(fp_lib_table\n\t(version 7)\n\t{row}\n)\n", encoding="utf-8")


def test_vendoring_policy_on_the_command_line(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _global_row(tmp_path)
    script = _variant(tmp_path, '\nr1.footprint = "G:Mini_R_0603"\n')
    out = str(tmp_path / "B")
    code, env, _ = run(monkeypatch, str(script), "--out", out, "--dry-run")
    assert code == 0 and "lib/G.pretty/Mini_R_0603.kicad_mod" in env["result"]["vendored"]  # type: ignore[index]
    code, env, _ = run(monkeypatch, str(script), "--out", out, "--dry-run", "--vendor", "project")
    assert code == 0
    assert not any(v.startswith("lib/G.pretty/") for v in env["result"]["vendored"])  # type: ignore[index, union-attr]
    found = [i for i in env["issues"] if i["code"] == "build.global-library"]  # type: ignore[index, union-attr]
    assert found and "G:Mini_R_0603" in found[0]["message"]


def test_unknown_vendoring_policy_is_a_usage_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, _, err = run(
        monkeypatch, str(BLINK_DIR / "design.py"), "--out", str(tmp_path / "B"), "--vendor", "none"
    )
    assert code == 2 and "FEN-200" in err


def test_properties_and_vendoring_add_their_rows(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    plain = BLINK_DIR / "design.py"
    props = _variant(tmp_path / "p", '\nr1.properties = {"Part number": "PN-330"}\n')
    _global_row(tmp_path)
    glob = _variant(tmp_path / "g", '\nr1.footprint = "G:Mini_R_0603"\n')
    envelopes = []
    for script in (plain, props, glob):
        code, env, _ = run(monkeypatch, str(script), "--out", str(tmp_path / "B"), "--dry-run")
        assert code == 0
        envelopes.append(env["evidence"])
    hyps = [set(e["hypotheses"]) for e in envelopes]  # type: ignore[index]
    assert ["H-K-VENDOR-PROPS" in h for h in hyps] == [False, True, False]
    assert ["H-K-VENDOR-GLOBAL" in h for h in hyps] == [False, False, True]
    assert {e["level"] for e in envelopes} == {"INFERRED"}  # type: ignore[index]


def test_help_names_the_vendoring_licence(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli_main.main(["build", "--help"]) == 0
    text = " ".join(capsys.readouterr().out.split())
    assert "--vendor" in text and "licence" in text


# --- internal planes (change c0038, design-dsl "Planes in a build") ----------------------------------

BOARD_LINE = "design.board(mm(50), mm(30))"
PLANE_NET = "vin, gnd, led_drv, led_a = "


def plane_script(tmp_path: Path, board: str) -> Path:
    """The blink script with its nets declared before the board line ``board``."""
    script = blink_copy(tmp_path)
    lines = script.read_text(encoding="utf-8").splitlines()
    nets = next(line for line in lines if line.startswith(PLANE_NET))
    lines.remove(nets)
    lines[lines.index(BOARD_LINE)] = f"{nets}\n{board}"
    script.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return script


ZONE_LINE = '\ndesign.zone(gnd, layers=("In1.Cu",))\n'


def plane_codes(envelope: dict[str, object]) -> list[str]:
    return [i["code"] for i in envelope["issues"] if i["code"].startswith("build.plane-")]  # type: ignore[index, union-attr]


def built_board(monkeypatch: pytest.MonkeyPatch, script: Path, out: Path) -> tuple[dict[str, object], str]:
    code, env, _ = run(monkeypatch, str(script), "--out", str(out), "--confirm")
    assert code == 0
    return env, (out / "blink.kicad_pcb").read_text(encoding="utf-8")


def test_plane_in_a_kicad_build(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Plane in a KiCad build" (change c0107): the plane layer gets the row type ``power``, no
    plane issue is given, and the board differs from the one without ``planes`` in that row only."""
    plain = plane_script(tmp_path / "a", "design.board(mm(50), mm(30), copper=4)")
    plain.write_text(plain.read_text(encoding="utf-8") + ZONE_LINE, encoding="utf-8")
    expected, without = built_board(monkeypatch, plain, tmp_path / "A")
    assert plane_codes(expected) == []
    script = plane_script(tmp_path / "b", 'design.board(mm(50), mm(30), copper=4, planes={"In1.Cu": gnd})')
    script.write_text(script.read_text(encoding="utf-8") + ZONE_LINE, encoding="utf-8")
    code, dry, _ = run(monkeypatch, str(script), "--out", str(tmp_path / "B"), "--dry-run")
    assert code == 0 and plane_codes(dry) == []
    env, board = built_board(monkeypatch, script, tmp_path / "B")
    assert plane_codes(env) == []
    assert '(4 "In1.Cu" power)' in board and '(6 "In2.Cu" signal)' in board
    assert '(4 "In1.Cu" signal)' in without
    assert board == without.replace('(4 "In1.Cu" signal)', '(4 "In1.Cu" power)')
    for name in ("blink.kicad_pro", "blink.kicad_dru", "blink.kicad_sch"):
        assert (tmp_path / "A" / name).read_bytes() == (tmp_path / "B" / name).read_bytes(), name


def test_plane_without_its_zone(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Plane without its zone": one warning whose hint names the script call, and the type."""
    script = plane_script(tmp_path / "b", 'design.board(mm(50), mm(30), copper=4, planes={"In1.Cu": gnd})')
    code, env, _ = run(monkeypatch, str(script), "--out", str(tmp_path / "B"), "--dry-run")
    assert code == 0 and plane_codes(env) == ["build.plane-zone-missing"]
    (found,) = [i for i in env["issues"] if i["code"] == "build.plane-zone-missing"]  # type: ignore[index, union-attr]
    assert found["severity"] == "warning" and "In1.Cu" in found["message"] and "GND" in found["message"]
    assert "design.zone" in found["hint"] and "In1.Cu" in found["hint"]
    _, board = built_board(monkeypatch, script, tmp_path / "B")
    assert '(4 "In1.Cu" power)' in board and '(6 "In2.Cu" signal)' in board


def test_plane_declared_after_the_first_build(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenarios "Plane declared after the first build" and "A type set in KiCad stays"."""
    script = plane_script(tmp_path / "a", "design.board(mm(50), mm(30), copper=4)")
    out = tmp_path / "A"
    _, first = built_board(monkeypatch, script, out)
    assert '(4 "In1.Cu" signal)' in first and '(6 "In2.Cu" signal)' in first
    # KiCad's board setup gives In2.Cu the type power; the script still names no plane
    (out / "blink.kicad_pcb").write_text(
        first.replace('(6 "In2.Cu" signal)', '(6 "In2.Cu" power)'), encoding="utf-8", newline="\n"
    )
    _, kept = built_board(monkeypatch, script, out)
    assert '(6 "In2.Cu" power)' in kept and '(4 "In1.Cu" signal)' in kept
    text = script.read_text(encoding="utf-8")
    assert "copper=4)" in text
    script.write_text(text.replace("copper=4)", 'copper=4, planes={"In1.Cu": gnd})'), encoding="utf-8")
    _, second = built_board(monkeypatch, script, out)
    assert '(4 "In1.Cu" power)' in second and '(6 "In2.Cu" power)' in second
    assert second == kept.replace('(4 "In1.Cu" signal)', '(4 "In1.Cu" power)'), "the layout is kept"
    # the plane leaves the script: its type stays, as one set in KiCad would
    script.write_text(text, encoding="utf-8")
    _, third = built_board(monkeypatch, script, out)
    assert third == second


def test_unknown_plane_net_stops_the_build(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Unknown plane net stops the build"."""
    script = plane_script(tmp_path, 'design.board(mm(50), mm(30), copper=4, planes={"In1.Cu": "NOPE"})')
    out = tmp_path / "B"
    code, _env, err = run(monkeypatch, str(script), "--out", str(out), "--confirm")
    assert code == 3 and "FEN-3004" in err and "NOPE" in err and not out.exists()
    for target in ("kicad", "altium"):
        code, _env, err = run(monkeypatch, str(script), "--out", str(out), "--target", target, "--dry-run")
        assert code == 3 and "FEN-3004" in err


# --- copper layer counts (change c0100, design-dsl "Copper layer counts in a build") ------------------

SIX = ["F.Cu", "In1.Cu", "In2.Cu", "In3.Cu", "In4.Cu", "B.Cu"]
EIGHT = [*SIX[:-1], "In5.Cu", "In6.Cu", "B.Cu"]
VIA_IMPORT = "from fenolite.dsl import Design, Net, Part, Power, connect, mm, no_connect"
DEEP_TRACK = """
design.track(
    "led_a",
    r1.pad(2), (mm(36), mm(9)),
    via_step(mm(36), mm(14), to="In6.Cu", diameter=mm(0.6), drill=mm(0.3)),
    (mm(41.5), mm(14)),
    via_step(mm(41.5), mm(17), to="B.Cu", diameter=mm(0.6), drill=mm(0.3)),
    (mm(41.5), mm(20)), d1.pad(2),
    width=mm(0.3),
)
"""


def layers_script(tmp_path: Path, copper: int, extra: str) -> Path:
    """The blink copy declared with ``copper`` layers, ``via_step`` imported and ``extra`` appended."""
    script = _variant(tmp_path, extra)
    text = script.read_text(encoding="utf-8")
    assert BOARD_LINE in text and VIA_IMPORT in text
    text = text.replace(BOARD_LINE, f"design.board(mm(50), mm(30), copper={copper})")
    script.write_text(text.replace(VIA_IMPORT, f"{VIA_IMPORT}, via_step"), encoding="utf-8")
    return script


def test_plane_on_a_six_layer_board(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Plane on a six-layer board": any inner layer of the count takes the type, and the hint of
    the missing zone names the script call and not the KiCad editor."""
    plain = plane_script(tmp_path / "a", "design.board(mm(50), mm(30), copper=6)")
    _, without = built_board(monkeypatch, plain, tmp_path / "A")
    script = plane_script(tmp_path / "b", 'design.board(mm(50), mm(30), copper=6, planes={"In4.Cu": gnd})')
    env, board = built_board(monkeypatch, script, tmp_path / "B")
    (found,) = [i for i in env["issues"] if i["code"] == "build.plane-zone-missing"]  # type: ignore[index, union-attr]
    assert found["severity"] == "warning" and "In4.Cu" in found["message"] and "GND" in found["message"]
    assert (
        "design.zone(" in found["hint"] and "GND" in found["hint"] and 'layers=("In4.Cu",)' in found["hint"]
    )
    assert "KiCad" not in found["hint"]
    assert '(10 "In4.Cu" signal)' in without
    assert board == without.replace('(10 "In4.Cu" signal)', '(10 "In4.Cu" power)')


@pytest.mark.parametrize("target", [9, 10])
def test_six_layer_build_on_both_targets(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, target: int
) -> None:
    """Scenario "Six-layer build on both targets"."""
    from fenolite.backends.kicad.pcb import read_board

    script = layers_script(tmp_path, 6, '\ndesign.zone(gnd, layers=("In4.Cu",))\n')
    out = tmp_path / "B"
    code, _env, err = run(
        monkeypatch, str(script), "--out", str(out), "--kicad-version", str(target), "--confirm"
    )
    assert code == 0, err
    back = read_board(out / "blink.kicad_pcb")
    assert back.board is not None
    rows = [
        (
            layer.name,
            dict(layer.ext["kicad"].payload).get("number"),
            dict(layer.ext["kicad"].payload).get("user_name"),
        )
        for layer in back.board.layers
        if layer.kind == "copper"
    ]
    assert rows == [
        (name, number, None) for name, number in zip(SIX, ("0", "4", "6", "8", "10", "2"), strict=True)
    ]
    refs = {c.id: c.ref for c in back.circuit.components}
    (d1,) = [fp for fp in back.board.footprints if refs[fp.component_id] == "D1"]
    (pad,) = [p for p in d1.pads if p.number == "1"]
    assert [name for name in pad.layers if name.endswith(".Cu")] == SIX
    (zone,) = back.board.zones
    assert zone.name == "GND" and zone.layers == ("In4.Cu",)


def test_six_layer_pads_in_the_built_model() -> None:
    """The built model of the six-layer blink: a ``*.Cu`` pad covers the six copper layers."""
    from _buildhelp import blink, build

    design = blink()
    design.copper = 6
    for target in (9, 10):
        built = build(design, target).design
        assert built.board is not None
        assert [layer.name for layer in built.board.layers if layer.kind == "copper"] == SIX
        refs = {c.id: c.ref for c in built.circuit.components}
        (d1,) = [fp for fp in built.board.footprints if refs[fp.component_id] == "D1"]
        (pad,) = [p for p in d1.pads if p.number == "1"]
        assert [name for name in pad.layers if name.endswith(".Cu")] == SIX


def test_script_copper_on_the_deepest_layer_of_eight(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Script copper on the deepest layer of eight"."""
    from fenolite.backends.kicad.pcb import read_board

    script = layers_script(tmp_path, 8, DEEP_TRACK)
    out = tmp_path / "B"
    code, env, err = run(monkeypatch, str(script), "--out", str(out), "--confirm")
    assert code == 0, err
    assert not [
        i for i in env["issues"] if i["code"].startswith("kicad.copper.") and i["severity"] == "error"
    ]  # type: ignore[index, union-attr]
    back = read_board(out / "blink.kicad_pcb")
    assert back.board is not None
    assert [layer.name for layer in back.board.layers if layer.kind == "copper"] == EIGHT
    led_a = back.nets_by_name["LED_A"].id
    assert "In6.Cu" in {track.layer for track in back.board.tracks if track.net_id == led_a}
    assert len([via for via in back.board.vias if via.net_id == led_a]) == 2


def test_layer_outside_the_table(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Layer outside the table": ``In7.Cu`` is no layer of an eight-layer board."""
    extra = (
        DEEP_TRACK
        + 'design.track("deep", (mm(44), mm(5)), (mm(47), mm(5)), layer="In7.Cu", net=led_a, width=mm(0.3))\n'
    )
    script = layers_script(tmp_path, 8, extra)
    out = tmp_path / "B"
    code, env, _ = run(monkeypatch, str(script), "--out", str(out), "--confirm")
    found = [i for i in env["issues"] if i["code"] == "kicad.copper.bad-layer"]  # type: ignore[index, union-attr]
    assert code == 5 and len(found) == 1 and not out.exists()
    assert "In7.Cu" in found[0]["message"] and all(name in found[0]["message"] for name in EIGHT)
