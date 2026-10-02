# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite doctor`` with fake tools (capability cli-contract, "Doctor command"; change c0013)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from _checkcli import hide_kicad, run
from _fakecli import calls, fake_kicad_cli

from fenolite.cli.cmd_doctor import java_major

PAGES = {
    "": "Usage: kicad-cli [--version] [--help] {fp,jobset,pcb,sch,sym,version}",
    "pcb": "Usage: kicad-cli pcb [--help] {drc,export,upgrade}",
    "pcb export": "Usage: pcb export [--help] {ipcd356,pos,svg}",
    "pcb drc": "Usage: pcb drc [--help] [--format FORMAT] [--severity-all] INPUT_FILE",
    "fp": "Usage: kicad-cli fp [--help] {upgrade}",
    "sym": "Usage: kicad-cli sym [--help] {upgrade}",
    "sch": "Usage: kicad-cli sch [--help] {erc,export}",
    "sch export": "Usage: sch export [--help] {netlist}",
    "jobset": "Usage: kicad-cli jobset [--help] {run}",
}


@pytest.fixture(autouse=True)
def _no_tools(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    hide_kicad(monkeypatch, tmp_path)


def _missing(env: dict[str, object]) -> list[str]:
    return [i["where"] for i in env["issues"] if i["code"] == "doctor.tool-missing"]  # type: ignore[index, union-attr]


def test_matrix_from_synthetic_pages(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake = fake_kicad_cli(tmp_path / "bin", help_pages=PAGES)
    code, env, _, _ = run(monkeypatch, tmp_path, "doctor", "--kicad-cli", str(fake))
    (entry,) = env["result"]["kicad_cli"]
    assert code == 0
    assert (entry["source"], entry["major"], entry["supported"], entry["selected"]) == (
        "explicit",
        10,
        True,
        True,
    )
    matrix = entry["matrix"]
    assert matrix["pcb upgrade"] is True and matrix["pcb import"] is False
    assert matrix["pcb drc --format"] is True and matrix["pcb drc --refill-zones"] is False
    assert matrix["pcb export svg"] is True and matrix["pcb export gerbers"] is False
    assert entry["evidence"] == {
        "level": "INFERRED",
        "oracle": "kicad-cli 10.0.6",
        "hypotheses": ["H-K-CLI-HELP"],
    }
    assert env["evidence"]["oracle"] == "kicad-cli 10.0.6"
    assert env["result"]["by_major"] == {"10": [str(fake)]}
    assert all(c["args"][-1] in {"version", "--help"} for c in calls(fake))


def test_unparsed_page(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    pages = dict(PAGES)
    pages["pcb export"] = "no usage here"
    fake = fake_kicad_cli(tmp_path / "bin", help_pages=pages)
    code, env, _, _ = run(monkeypatch, tmp_path, "doctor", "--kicad-cli", str(fake))
    (entry,) = env["result"]["kicad_cli"]
    assert code == 0 and entry["matrix"]["pcb export svg"] == "unknown"
    assert [i["code"] for i in env["issues"] if i["code"].startswith("doctor.help")] == [
        "doctor.help-unparsed"
    ]
    assert entry["evidence"]["level"] == env["evidence"]["level"] == "UNVERIFIED"


def test_unsupported_major(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake = fake_kicad_cli(tmp_path / "bin", version="8.0.7", help_pages=PAGES)
    code, env, _, _ = run(monkeypatch, tmp_path, "doctor", "--kicad-cli", str(fake))
    assert code == 0 and env["result"]["kicad_cli"][0]["supported"] is False
    assert "doctor.tool-unsupported" in [i["code"] for i in env["issues"]]


def test_missing_java_and_docker(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _, _ = run(monkeypatch, tmp_path, "doctor")
    assert code == 0
    assert env["result"]["java"] is None and env["result"]["docker"] is None
    assert {"java", "docker", "kicad-cli"} <= set(_missing(env))
    assert env["evidence"]["level"] == "UNVERIFIED"


def test_no_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake = fake_kicad_cli(tmp_path / "bin", help_pages=PAGES)

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a subprocess was started")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    code, env, _, _ = run(monkeypatch, tmp_path, "doctor", "--no-run", "--kicad-cli", str(fake))
    (entry,) = env["result"]["kicad_cli"]
    assert code == 0 and entry["version"] is None and entry["matrix"] is None
    assert env["evidence"]["level"] == "UNVERIFIED"


def test_one_entry_per_binary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake = fake_kicad_cli(tmp_path / "real", help_pages=PAGES)
    linked = tmp_path / "linked"
    linked.mkdir()
    (linked / "kicad-cli").symlink_to(fake)
    monkeypatch.setenv("FENOLITE_KICAD_CLI", str(fake))
    monkeypatch.setenv("PATH", str(linked))
    code, env, _, _ = run(monkeypatch, tmp_path, "doctor")
    assert code == 0 and [e["source"] for e in env["result"]["kicad_cli"]] == ["env"]


def test_override_names_a_missing_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake = fake_kicad_cli(tmp_path / "bin", help_pages=PAGES)
    monkeypatch.setenv("FENOLITE_KICAD_CLI", str(tmp_path / "nowhere" / "kicad-cli"))
    monkeypatch.setenv("PATH", str(fake.parent))
    code, env, _, _ = run(monkeypatch, tmp_path, "doctor", "--no-run")
    (entry,) = env["result"]["kicad_cli"]
    assert code == 0 and entry["source"] == "path" and entry["selected"] is False
    assert _missing(env).count("FENOLITE_KICAD_CLI") == 1


def test_explicit_missing_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    missing = str(tmp_path / "gone" / "kicad-cli")
    code, env, _, _ = run(monkeypatch, tmp_path, "doctor", "--no-run", "--kicad-cli", missing)
    assert code == 0 and missing in _missing(env)


@pytest.mark.parametrize(
    ("line", "major"),
    [
        ('java version "1.8.0_402"', 8),
        ('openjdk version "17.0.2" 2022-01-18', 17),
        ("openjdk 21", 21),
        ("?", None),
    ],
)
def test_java_major(line: str, major: int | None) -> None:
    assert java_major(line) == major
