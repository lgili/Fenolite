# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Dispatcher behaviour: exit codes, typed errors, mutation protocol, determinism."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from fenolite import __version__
from fenolite.cli.main import main

CapSys = pytest.CaptureFixture[str]


def _run(capsys: CapSys, *argv: str) -> tuple[int, dict[str, Any] | None, dict[str, Any] | None]:
    code = main(list(argv))
    captured = capsys.readouterr()
    out = json.loads(captured.out) if captured.out.strip().startswith("{") else None
    err = json.loads(captured.err) if captured.err.strip() else None
    return code, out, err


def test_bare_invocation_prints_help(capsys: CapSys) -> None:
    assert main([]) == 0
    assert "usage: fenolite" in capsys.readouterr().out


def test_version(capsys: CapSys) -> None:
    assert main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == f"fenolite {__version__}"


def test_success_envelope(capsys: CapSys) -> None:
    code, out, err = _run(capsys, "_echo")
    assert code == 0 and err is None and out is not None
    assert out["ok"] is True and out["schema"] == "fenolite._echo.v0"


def test_usage_error_is_typed(capsys: CapSys) -> None:
    code, out, err = _run(capsys, "capabilities", "--no-such-flag", "--json")
    assert code == 2 and out is None and err is not None
    assert err["code"].startswith("FEN-2")


def test_unknown_command(capsys: CapSys) -> None:
    code, _, err = _run(capsys, "no-such-command", "--json")
    assert code == 2 and err is not None and err["code"] == "FEN-2001"


def test_internal_exception_maps_to_exit_1(capsys: CapSys) -> None:
    code, out, err = _run(capsys, "_echo", "--raise")
    assert code == 1 and out is not None and out["ok"] is False
    assert err is not None and err["code"] == "FEN-1001" and "RuntimeError" in err["message"]


def test_error_findings_exit_5(capsys: CapSys) -> None:
    code, out, err = _run(capsys, "_echo", "--issue", "error", "--issue", "warning")
    assert code == 5 and out is not None and out["ok"] is False
    assert [i["severity"] for i in out["issues"]] == ["error", "warning"]
    assert err is not None and err["code"] == "FEN-5001"


def test_warnings_do_not_fail(capsys: CapSys) -> None:
    code, out, err = _run(capsys, "_echo", "--issue", "warning", "--issue", "info")
    assert code == 0 and out is not None and out["ok"] is True and err is None


def test_unknown_field(capsys: CapSys) -> None:
    code, out, err = _run(capsys, "_echo", "--fields", "nope")
    assert code == 2 and out is None and err is not None and err["code"] == "FEN-2002"


def test_fields_projection_keeps_mandatory_keys(capsys: CapSys) -> None:
    code, out, _ = _run(capsys, "_echo", "--gen-id", "--fields", "id")
    assert code == 0 and out is not None
    assert list(out["result"]) == ["id"]
    assert {"ok", "command", "schema", "issues", "evidence", "receipt"} <= set(out)


def test_json_and_text_together(capsys: CapSys) -> None:
    code, _, err = _run(capsys, "_echo", "--json", "--text")
    assert code == 2 and err is not None and err["code"] == "FEN-2001"


def test_invalid_timestamp(capsys: CapSys) -> None:
    code, _, err = _run(capsys, "_echo", "--timestamp", "yesterday")
    assert code == 2 and err is not None and err["code"] == "FEN-2004"


def test_global_flags_before_the_command(capsys: CapSys) -> None:
    code, out, _ = _run(capsys, "--json", "--seed", "3", "_echo", "--gen-id")
    assert code == 0 and out is not None and "id" in out["result"]


class TestMutationProtocol:
    @pytest.fixture(autouse=True)
    def _cwd(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        self.dir = tmp_path

    def test_dry_run_writes_nothing(self, capsys: CapSys) -> None:
        code, out, err = _run(capsys, "_echo", "--write", "out.txt", "--dry-run")
        assert code == 0 and err is None and out is not None
        plan = out["result"]["plan"]
        assert [p["path"] for p in plan] == ["out.txt"] and plan[0]["overwrite"] is False
        assert list(self.dir.iterdir()) == []

    def test_missing_confirmation(self, capsys: CapSys) -> None:
        code, out, err = _run(capsys, "_echo", "--write", "out.txt")
        assert code == 4 and out is not None and out["ok"] is False and out["result"]["plan"]
        assert err is not None and err["code"] == "FEN-4001"
        assert list(self.dir.iterdir()) == []

    def test_confirmed_write_with_receipt_and_backup(self, capsys: CapSys) -> None:
        (self.dir / "out.txt").write_text("old\n")
        code, out, _ = _run(capsys, "_echo", "--write", "out.txt", "--content", "new\n", "--confirm")
        assert code == 0 and out is not None
        assert (self.dir / "out.txt").read_text() == "new\n"
        assert (self.dir / "out.txt.bak").read_text() == "old\n"
        receipt = out["receipt"]
        assert receipt["written"] == [{"path": "out.txt", "sha256": hashlib.sha256(b"new\n").hexdigest()}]
        assert receipt["backup"] == ["out.txt.bak"]

    def test_receipt_identity(self, capsys: CapSys, tmp_path_factory: pytest.TempPathFactory) -> None:
        """ "Receipt identity" (c0066): equal writes have equal ids whatever the folder, seed and time, and
        ``undo`` is offered only when a backup was kept."""
        receipts = []
        for seed in ("1", "2"):
            folder = tmp_path_factory.mktemp("write")
            with pytest.MonkeyPatch.context() as patch:
                patch.chdir(folder)
                code, out, _ = _run(capsys, "_echo", "--write", "out.txt", "--confirm", "--seed", seed)
            assert code == 0 and out is not None
            receipts.append(out["receipt"])
        first, second = receipts
        assert first["id"] == second["id"] and len(first["id"]) == 16 and int(first["id"], 16) >= 0
        assert first["undo"] is None and set(first) == {"written", "backup", "id", "undo", "plan"}

        (self.dir / "out.txt").write_text("old\n")
        code, out, _ = _run(capsys, "_echo", "--write", "out.txt", "--confirm")
        assert code == 0 and out is not None
        assert out["receipt"]["undo"] == "fenolite restore - --confirm"
        assert out["receipt"]["id"] != first["id"]  # the backup list is part of the identity
        body = {"written": out["receipt"]["written"], "backup": out["receipt"]["backup"]}
        text = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        assert out["receipt"]["id"] == hashlib.sha256(text.encode()).hexdigest()[:16]

    def test_receipt_without_identity_still_validates(self) -> None:
        import _schema

        schema = _schema.load("fenolite.envelope.v0.json")
        envelope = {
            "ok": True, "command": "x", "schema": "fenolite.x.v0", "input": None, "result": {}, "issues": [],
            "evidence": {"level": "UNVERIFIED", "oracle": None, "hypotheses": []},
            "receipt": {"written": [], "backup": []}, "elapsed_ms": 0,
        }  # fmt: skip
        assert _schema.validate(envelope, schema) == []
        envelope["receipt"] = {"written": [], "backup": [], "id": "zz", "undo": None}
        assert _schema.validate(envelope, schema) != []

    def test_no_backup(self, capsys: CapSys) -> None:
        (self.dir / "out.txt").write_text("old\n")
        code, out, _ = _run(capsys, "_echo", "--write", "out.txt", "--confirm", "--no-backup")
        assert code == 0 and out is not None and out["receipt"]["backup"] == []
        assert not (self.dir / "out.txt.bak").exists()

    def test_conflicting_flags(self, capsys: CapSys) -> None:
        code, _, err = _run(capsys, "_echo", "--write", "out.txt", "--dry-run", "--confirm")
        assert code == 2 and err is not None and err["code"] == "FEN-2003"
        assert list(self.dir.iterdir()) == []


def test_determinism(capsys: CapSys) -> None:
    argv = ("_echo", "--gen-id", "--seed", "7", "--timestamp", "2026-01-01T00:00:00Z", "--json")
    _, first, _ = _run(capsys, *argv)
    _, second, _ = _run(capsys, *argv)
    assert first is not None and second is not None
    first.pop("elapsed_ms")
    second.pop("elapsed_ms")
    assert first == second
    assert first["result"]["timestamp"] == "2026-01-01T00:00:00+00:00"


def test_text_mode_stderr_line(capsys: CapSys) -> None:
    code = main(["_echo", "--issue", "error", "--text"])
    captured = capsys.readouterr()
    assert code == 5
    assert captured.out.startswith("fenolite _echo: FAILED")
    assert captured.err.startswith("error FEN-5001: ")
