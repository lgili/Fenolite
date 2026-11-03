# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""An unsupported project geometry parameter is an explicit target loss (c0340)."""

from __future__ import annotations

from pathlib import Path

import pytest

from fenolite import api
from fenolite.backends.altium import lower
from fenolite.dsl import Design, mm, to_model


def design(value: str | None = "0.01"):
    result = Design("authored_curve")
    result.board(mm(30), mm(20), max_curve_error=mm(value) if value is not None else None)
    return to_model(result)


def test_model_write_refuses_unsupported_project_curve_configuration() -> None:
    with pytest.raises(lower.LossyWriteError) as caught:
        lower.write_design(design(), pour="outline")
    assert any(issue.where == "project-curve-error" for issue in caught.value.issues)
    allowed = lower.write_design(design(), allow_lossy=True, pour="outline")
    assert len([issue for issue in allowed.issues if issue.where == "project-curve-error"]) == 1
    assert lower.write_design(design(None), pour="outline").files


@pytest.mark.parametrize("allow", (False, True))
def test_cli_build_reports_curve_loss_and_never_stages_strict_write(tmp_path: Path, allow: bool) -> None:
    script = tmp_path / "authored.py"
    script.write_text(
        "# SPDX-License-Identifier: CC0-1.0\n# Copyright (c) 2026 Fenolite contributors\n"
        'from fenolite.dsl import Design, mm\ndesign = Design("authored_curve")\n'
        'design.board(mm(30), mm(20), max_curve_error=mm("0.01"))\n'
    )
    reply = api.run(
        "build",
        str(script),
        "--target",
        "altium",
        "--out",
        "out",
        "--dry-run",
        *(["--allow-lossy"] if allow else []),
        cwd=tmp_path,
        seed=0,
    )
    if allow:
        assert reply.exit_code == 0, reply.error
        issues = (reply.envelope or {}).get("issues", [])
        assert (
            len(
                [
                    issue
                    for issue in issues
                    if issue["code"] == "altium.not-lowered" and issue["where"] == "project-curve-error"
                ]
            )
            == 1
        )
    else:
        assert reply.exit_code == 7 and reply.error and reply.error["code"] == "FEN-7001"
        assert not reply.result.get("plan")
    assert not (tmp_path / "out").exists()
