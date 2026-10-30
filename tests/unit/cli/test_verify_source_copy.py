# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``verify-source`` on an imported board (capability fidelity-proof; change c0281, the board library's
conversion report): copy mode, one project per ``--against``, opaque items counted, skipped levels recorded.
Hermetic, on the authored fixture of c0278 and variants made here."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from test_verify_source import ORIGINAL, codes, variant
from test_verify_source import verify as run_verify

COPY = {"schema": "fenolite.import-provenance.v0", "design": "sensor", "copy": True}
VIA = 'design.via("gnd_tie", mm(20), mm(25), net=gnd, diameter=mm(0.6), drill=mm(0.3))'
SHORT = VIA + '\ndesign.via("vin_tie", mm(20.3), mm(25), net=vin, diameter=mm(0.6), drill=mm(0.3))'


@pytest.fixture
def verify(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):  # noqa: ANN201
    def call(script: Path, *flags: str, against: Path = ORIGINAL) -> tuple[int, dict[str, Any]]:
        code, env, _, _ = run_verify(monkeypatch, tmp_path, str(script), "--against", str(against), *flags)
        return code, env

    return call


def test_copy_compares_a_board_the_guard_refuses(tmp_path: Path, verify) -> None:  # noqa: ANN001
    """Scenario "Imported board with clearance findings is compared"."""
    script = variant(tmp_path / "copy", VIA, SHORT, provenance=COPY)
    code, env = verify(script)
    assert "fidelity.build-failed" not in codes(env)
    build = env["result"]["build"]
    assert (build["copper_check"], build["copy"]) == ("warn", True) and build["files"] > 0
    (short,) = [i for i in env["issues"] if i["code"] == "copper.short"]
    assert short["severity"] == "warning"
    assert code == 5  # the planted via is a level-5 difference, not a refusal
    assert any(d["kind"] == "via-missing" for d in env["result"]["differences"])


def test_copy_explicit_refuse_wins(tmp_path: Path, verify) -> None:  # noqa: ANN001
    """Scenario "Explicit refuse wins"."""
    script = variant(tmp_path / "copy", VIA, SHORT, provenance=COPY)
    code, env = verify(script, "--copper-check", "refuse")
    assert code == 5 and "fidelity.build-failed" in codes(env)
    assert env["result"]["build"]["copper_check"] == "refuse"


def test_copy_own_script_is_refused(tmp_path: Path, verify) -> None:  # noqa: ANN001
    """Scenario "Own script is refused"."""
    script = variant(tmp_path / "own", VIA, SHORT)
    code, env = verify(script)
    assert code == 5 and "fidelity.build-failed" in codes(env)
    assert env["result"]["build"]["copy"] is False
    code, env = verify(script, "--copper-check", "warn")
    assert "fidelity.build-failed" not in codes(env)


def test_copy_record_false(tmp_path: Path, verify) -> None:  # noqa: ANN001
    script = variant(tmp_path / "owned", VIA, SHORT, provenance={**COPY, "copy": False})
    code, env = verify(script)
    assert code == 5 and "fidelity.build-failed" in codes(env)


TEARDROP = """	(zone
		(net "GND")
		(layer "F.Cu")
		(uuid "c0281000-0000-4000-8000-0000000000{n:02d}")
		(name "$teardrop_padvia$")
		(hatch full 0.1)
		(priority 30000)
		(attr
			(teardrop
				(type padvia)
			)
		)
		(connect_pads yes
			(clearance 0)
		)
		(min_thickness 0.0254)
		(filled_areas_thickness no)
		(fill yes
			(thermal_gap 0.5)
			(thermal_bridge_width 0.5)
		)
		(polygon
			(pts
				(xy {x} 10) (xy {x}.5 10) (xy {x}.25 10.5)
			)
		)
	)
"""


def with_teardrops(folder: Path) -> Path:
    """A copy of the authored original whose board holds two teardrop zones the script does not build."""
    shutil.copytree(ORIGINAL, folder)
    board = folder / "sensor.kicad_pcb"
    text = board.read_text(encoding="utf-8").rstrip()
    assert text.endswith(")")
    drops = TEARDROP.format(n=1, x=10) + TEARDROP.format(n=2, x=12)
    board.write_text(text[:-1] + drops + ")\n", encoding="utf-8")
    return folder


def test_opaque_teardrops_left_out(tmp_path: Path, verify) -> None:  # noqa: ANN001
    """Scenario "Teardrops left out"."""
    original = with_teardrops(tmp_path / "original")
    script = variant(tmp_path / "code")
    code, env = verify(script, against=original)
    found = [d for d in env["result"]["differences"] if d["kind"] == "opaque-count"]
    assert code == 5
    assert found == [
        {
            "level": 7,
            "kind": "opaque-count",
            "where": "board:opaque:teardrop",
            "field": "teardrop",
            "a": "2",
            "b": "0",
        }
    ]
    accept = {
        "id": "A001", "level": 7, "kind": "opaque-count", "where": "board:opaque:teardrop",
        "reason": "teardrops are a DSL gap (c0277)", "attribution": "fenolite", "decided": "2026-10-30",
    }  # fmt: skip
    script = variant(tmp_path / "accepted", provenance={"fidelity": {"accepted": [accept]}})
    code, env = verify(script, "--levels", "1-7", against=original)
    assert code == 0, env["result"]["differences"]
    assert [row["rule"] for row in env["result"]["accepted"]] == ["A001"]


def test_project_two_projects_in_one_folder(tmp_path: Path, verify) -> None:  # noqa: ANN001
    """Scenario "Two projects in one folder"."""
    folder = tmp_path / "two"
    shutil.copytree(ORIGINAL, folder)
    for path in sorted(ORIGINAL.iterdir()):
        (folder / path.name.replace("sensor.", "sensor_v2.")).write_bytes(path.read_bytes())
    script = variant(tmp_path / "code")
    code, env = verify(script, against=folder / "sensor.kicad_pro")
    files = env["result"]["against"]["files"]
    assert sorted(files) == ["sensor.kicad_dru", "sensor.kicad_pcb", "sensor.kicad_pro", "sensor.kicad_sch"]
    assert not [d for d in env["result"]["differences"] if "sensor_v2" in d["where"]]
    assert code == 0, env["result"]["differences"]


def test_skipped_level_recorded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Level S recorded with its reason"."""
    script = variant(tmp_path / "rec")
    args = (str(script), "--against", str(ORIGINAL), "--record", "--timestamp", "2026-11-01T00:00:00Z")
    code, env, _, _ = run_verify(monkeypatch, tmp_path, *args, "--dry-run")
    assert code == 0
    code, env, err, _ = run_verify(
        monkeypatch, tmp_path, *args, "--confirm", "--plan", env["result"]["plan_id"]
    )
    assert code == 0, err
    proof = json.loads((tmp_path / "rec" / "PROVENANCE.json").read_text(encoding="utf-8"))["fidelity"][
        "proof"
    ]
    assert proof["levels"]["S"] == "skipped"
    assert proof["skipped"] == {"S": "drawn-unavailable"}
