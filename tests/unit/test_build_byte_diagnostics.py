# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Bounded same-run evidence for the authored Mac byte failure (c0323); comparisons stay strict."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import runpy
from pathlib import Path
from typing import Any

import pytest
from _buildbytes import ROOT, SEED, TABLE, TIMESTAMP, measure
from _builddiagnostics import DIRECTORY, ENV, MAX_BYTES, OUTPUT, capture_failure

from fenolite import api
from fenolite.backends.altium.read.cfb import open_compound
from fenolite.cli import plans
from fenolite.core.state import state_dir

ROW = "board_40parts@altium"
RECORDED = json.loads(TABLE.read_text(encoding="utf-8"))
PLAN = "0123456789abcdef"


@pytest.fixture(autouse=True)
def isolated_runtime(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv(ENV, raising=False)
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def _guard(monkeypatch: pytest.MonkeyPatch, *, mismatch: bool = True) -> Any:
    guard = runpy.run_path(str(ROOT / "tests/unit/test_build_bytes.py"))["test_example_keeps_its_bytes"]
    recorded = copy.deepcopy(RECORDED)
    if mismatch:
        recorded[ROW]["files"][OUTPUT] = "0" * 64
    monkeypatch.setitem(guard.__globals__, "RECORDED", recorded)
    return guard


def _capture(out: Path, reply: api.Reply, actual: dict[str, Any], *, source_root: Path) -> None:
    capture_failure(
        "board_40parts", "altium", out, reply, actual, {"exit": 0, "files": {OUTPUT: "0" * 64}},
        source_root=source_root, seed=SEED, timestamp=TIMESTAMP,
    )  # fmt: skip


def _staged_case(tmp_path: Path, *, bad: str = "") -> tuple[Path, Path, api.Reply, dict[str, Any]]:
    """A wholly authored staged file; private inputs and other outputs must never be copied."""
    source_root = tmp_path / "checkout"
    out = tmp_path / "out"
    data = b"authored diagnostic payload\n"
    digest = hashlib.sha256(data).hexdigest()
    args = {"design": str(source_root / "examples/board_40parts/design.py"), "out": str(out)}
    row = {"path": str(out / OUTPUT), "kind": "altium_pcbdoc", "bytes": len(data), "sha256": digest}
    if bad == "private-source":
        args["design"] = str(tmp_path / "private-input.py")
    elif bad == "other-output":
        row["path"] = str(tmp_path / "private-input.PcbDoc")
    elif bad == "oversized":
        row["bytes"] = MAX_BYTES + 1
    root = state_dir()
    assert root is not None
    plans.stage(
        root, PLAN, command="build", args=args, cwd=str(out.parent.resolve()), depends=[], writes=[row],
        payloads=[data], reply={"result": {"pcb": {"pour": {"mode": "outline", "poured": 0}}},
                               "issues": [{"code": "authored.code", "severity": "info",
                                           "message": str(tmp_path / "private-message")}]},
    )  # fmt: skip
    if bad == "damaged":
        (root / "plans" / PLAN / "files" / "0000").write_bytes(b"changed after staging")
    if bad == "oversized-payload":
        with (root / "plans" / PLAN / "files" / "0000").open("r+b") as stream:
            stream.truncate(MAX_BYTES + 1)
    if bad in ("damaged-reply", "private-staged-file"):
        path = root / "plans" / PLAN / "plan.json"
        meta = json.loads(path.read_text(encoding="utf-8"))
        if bad == "damaged-reply":
            meta["reply"]["issues"] = [{"message": "no code or severity"}]
        else:
            meta["writes"][0]["file"] = "../private-input.PcbDoc"
        path.write_text(json.dumps(meta), encoding="utf-8")
    return (
        source_root,
        out,
        api.Reply(0, {"result": {"plan_id": PLAN}}, None),
        {
            "exit": 0,
            "files": {OUTPUT: digest},
        },
    )


def test_original_assertion_fails_and_retains_exact_same_run_bytes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    folder = tmp_path / DIRECTORY
    monkeypatch.setenv(ENV, str(folder))
    monkeypatch.setenv("GITHUB_SHA", "1" * 40)
    replies: list[api.Reply] = []
    original = api.run

    def once(*args: Any, **kwargs: Any) -> api.Reply:
        reply = original(*args, **kwargs)
        replies.append(reply)
        return reply

    monkeypatch.setattr(api, "run", once)
    with pytest.raises(AssertionError):
        _guard(monkeypatch)(ROW, tmp_path)
    assert len(replies) == 1 and replies[0].exit_code == 0
    assert sorted(p.name for p in folder.iterdir()) == [OUTPUT, "receipt.json"]
    data = (folder / OUTPUT).read_bytes()
    staged = plans.load(state_dir(), replies[0].result["plan_id"])
    assert staged is not None
    row = next(row for row in staged.writes if Path(row["path"]).name == OUTPUT)
    assert data == staged.data(row)
    receipt_text = (folder / "receipt.json").read_text(encoding="utf-8")
    receipt = json.loads(receipt_text)
    digest = hashlib.sha256(data).hexdigest()
    assert receipt["status"] == "captured"
    assert digest == receipt["sha256"] == receipt["observed_sha256"] == row["sha256"]
    assert receipt["expected_sha256"] == "0" * 64
    assert (receipt["row"], receipt["output"], receipt["bytes"]) == (ROW, OUTPUT, len(data))
    assert (receipt["seed"], receipt["timestamp"]) == (SEED, TIMESTAMP)
    assert receipt["runtime"]["commit"] == "1" * 40
    trace = receipt["geometry_trace"]
    assert trace["seen"] >= 188 and len(trace["operations"]) == trace["seen"]
    assert trace["errors"] == 0 and trace["limited"] is False
    assert trace["index_base"] == 0
    assert [row["index"] for row in trace["operations"]] == list(range(trace["seen"]))
    assert all("sha256" in row["output"] for row in trace["operations"])
    assert len(receipt_text.encode()) <= 256 * 1024
    compound = open_compound(data)
    assert receipt["streams"] == {
        name: {"bytes": len(compound.read(name)), "sha256": hashlib.sha256(compound.read(name)).hexdigest()}
        for name in compound.streams()
    }
    assert receipt["pour"] == {key: staged.reply["result"]["pcb"]["pour"][key] for key in ("mode", "poured")}
    assert str(ROOT) not in receipt_text and str(tmp_path) not in receipt_text
    assert "message" not in receipt_text and "plan_id" not in receipt_text


def test_matching_real_row_never_creates_diagnostics(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(ENV, str(tmp_path / DIRECTORY))
    out = tmp_path / "board_40parts-altium"
    actual = measure("board_40parts", "altium", out)
    assert actual["exit"] == 0
    monkeypatch.setattr(plans, "load", lambda *_: pytest.fail("matching case read staging"))
    capture_failure(
        "board_40parts", "altium", out, api.Reply(0, None, None), actual, actual,
        source_root=ROOT, seed=SEED, timestamp=TIMESTAMP,
    )  # fmt: skip
    assert not (tmp_path / DIRECTORY).exists()


@pytest.mark.parametrize("boundary", ["disabled", "matching", "other-row"])
def test_unselected_cases_do_not_read_staging(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    boundary: str,
) -> None:
    if boundary != "disabled":
        monkeypatch.setenv(ENV, str(tmp_path / DIRECTORY))
    monkeypatch.setattr(plans, "load", lambda *_: pytest.fail("unselected case read staging"))
    actual = {"exit": 0, "files": {OUTPUT: "1" * 64}}
    expected = actual if boundary == "matching" else {"exit": 7, "files": {}}
    capture_failure(
        "blink_2layer" if boundary == "other-row" else "board_40parts", "altium", tmp_path / "out",
        api.Reply(0, {"result": {"plan_id": PLAN}}, None), actual, expected,
        source_root=ROOT, seed=SEED, timestamp=TIMESTAMP,
    )  # fmt: skip
    assert not (tmp_path / DIRECTORY).exists()


@pytest.mark.parametrize("destination", ["relative", "inside-checkout", "wrong-name", "symlink"])
def test_invalid_destinations_never_read_or_write_staging(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    destination: str,
) -> None:
    source_root = tmp_path / "checkout"
    folder = tmp_path / DIRECTORY
    if destination == "relative":
        folder = Path(DIRECTORY)
    elif destination == "inside-checkout":
        folder = source_root / DIRECTORY
    elif destination == "wrong-name":
        folder = tmp_path / "arbitrary-output"
    else:
        target = tmp_path / "symlink-target"
        target.mkdir()
        try:
            folder.symlink_to(target, target_is_directory=True)
        except OSError:
            pytest.skip("this platform does not permit directory symlinks")
    monkeypatch.setenv(ENV, str(folder))
    monkeypatch.setattr(plans, "load", lambda *_: pytest.fail("invalid destination read staging"))
    _capture(tmp_path / "out", api.Reply(0, {"result": {"plan_id": PLAN}}, None), {}, source_root=source_root)
    assert not any(path.is_file() for path in tmp_path.rglob("*"))


@pytest.mark.parametrize(
    ("bad", "reason"),
    [
        ("private-source", "plan-outside-authored-case"),
        ("other-output", "selected-write-unavailable"),
        ("oversized", "selected-write-too-large"),
        ("oversized-payload", "staged-data-unavailable"),
        ("private-staged-file", "staged-data-unavailable"),
        ("damaged", "staged-data-unavailable"),
        ("damaged-reply", "staged-data-unavailable"),
    ],
)
def test_invalid_staged_data_copies_no_pcb_or_private_inputs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    bad: str,
    reason: str,
) -> None:
    source_root, out, reply, actual = _staged_case(tmp_path, bad=bad)
    folder = tmp_path / DIRECTORY
    monkeypatch.setenv(ENV, str(folder))
    if bad in ("private-source", "other-output", "oversized", "oversized-payload", "private-staged-file"):
        monkeypatch.setattr(plans.StagedPlan, "data", lambda *_: pytest.fail("rejected payload was read"))
    _capture(out, reply, actual, source_root=source_root)
    assert sorted(p.name for p in folder.iterdir()) == ["receipt.json"]
    text = (folder / "receipt.json").read_text(encoding="utf-8")
    receipt = json.loads(text)
    assert (receipt["status"], receipt["reason"]) == ("unavailable", reason)
    assert str(tmp_path) not in text and "private-message" not in text


def test_missing_plan_is_explicit_without_copying_other_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    folder = tmp_path / DIRECTORY
    monkeypatch.setenv(ENV, str(folder))
    _capture(tmp_path / "out", api.Reply(0, {"result": {"plan_id": PLAN}}, None), {}, source_root=ROOT)
    assert sorted(p.name for p in folder.iterdir()) == ["receipt.json"]
    receipt = json.loads((folder / "receipt.json").read_text(encoding="utf-8"))
    assert (receipt["status"], receipt["reason"]) == ("unavailable", "plan-unavailable")


def test_valid_private_plan_still_captures_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    source_root, out, reply, actual = _staged_case(tmp_path)
    folder = tmp_path / DIRECTORY
    monkeypatch.setenv(ENV, str(folder))
    _capture(out, reply, actual, source_root=source_root)
    assert not folder.exists()


def test_receipt_limit_is_bounded_and_explicit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import _builddiagnostics
    import _buildgeometry

    source_root, out, reply, actual = _staged_case(tmp_path)
    folder = tmp_path / DIRECTORY
    monkeypatch.setenv(ENV, str(folder))
    # The payload is authored inline; production defaults refuse this private source above.
    monkeypatch.setattr(_buildgeometry, "authored_source", lambda *_: True)
    monkeypatch.setattr(_builddiagnostics, "MAX_RECEIPT_BYTES", 512)
    _capture(out, reply, actual, source_root=source_root)
    assert not (folder / OUTPUT).exists()
    data = (folder / "receipt.json").read_bytes()
    assert len(data) <= 512
    assert json.loads(data) == {"row": ROW, "status": "unavailable", "reason": "receipt-limit"}


@pytest.mark.parametrize("first", [OUTPUT, "receipt.json"])
def test_existing_evidence_is_preserved_without_reading_staging(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    first: str,
) -> None:
    folder = tmp_path / DIRECTORY
    folder.mkdir()
    (folder / first).write_bytes(b"first evidence")
    monkeypatch.setenv(ENV, str(folder))
    monkeypatch.setattr(plans, "load", lambda *_: pytest.fail("existing evidence read staging"))
    _capture(tmp_path / "out", api.Reply(0, {"result": {"plan_id": PLAN}}, None), {}, source_root=ROOT)
    assert [(p.name, p.read_bytes()) for p in folder.iterdir()] == [(first, b"first evidence")]


def test_capture_error_cannot_mask_the_original_assertion(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import _builddiagnostics

    def unavailable(*_args: Any, **_kwargs: Any) -> None:
        raise OSError("a private diagnostic path must not reach stderr")

    out = tmp_path / "board_40parts-altium"
    reply = api.Reply(0, {"result": {"plan": [{"path": str(out / OUTPUT), "sha256": "1" * 64}]}}, None)
    monkeypatch.setattr(api, "run", lambda *_args, **_kwargs: reply)
    monkeypatch.setattr(_builddiagnostics, "capture_failure", unavailable)
    with pytest.raises(AssertionError):
        _guard(monkeypatch)(ROW, tmp_path)
    assert capsys.readouterr().err == "authored byte diagnostic unavailable (OSError)\n"


def _workflow_problems(text: str) -> list[str]:
    """Textual policy witness; the dev extra intentionally has no YAML parser."""
    unit = re.search(r"^  unit:\n(.*?)(?=^  \S|\Z)", text, re.MULTILINE | re.DOTALL)
    if unit is None:
        return ["unit job missing"]
    steps = dict(
        re.findall(
            r"^      - name: ([^\n]+)\n(.*?)(?=^      - |\Z)",
            unit.group(1),
            re.MULTILINE | re.DOTALL,
        )
    )
    problems: list[str] = []
    tests = steps.get("Tests", "")
    enable = (
        "FENOLITE_BUILD_BYTE_DIAGNOSTICS: ${{ matrix.os == 'macos-latest' && "
        "format('{0}/fenolite-byte-diagnostics', runner.temp) || '' }}"
    )
    if enable not in tests:
        problems.append("capture must be Mac-only in the original test step")
    expected_run = (
        "run: uv run python tools/ci_tests.py run --suite unit-${{ matrix.os }}-py${{ matrix.python }} "
        '--out "${{ runner.temp }}/ci-tests/unit"'
    )
    if expected_run not in tests:
        problems.append("audited whole-suite unit invocation changed")
    upload = steps.get("Keep authored Mac byte-failure evidence", "")
    if "if: failure() && matrix.os == 'macos-latest'" not in upload:
        problems.append("upload must be Mac-only after failure")
    if "uses: actions/upload-artifact@v4" not in upload or "if-no-files-found: warn" not in upload:
        problems.append("scoped artifact action missing")
    paths = re.search(r"^          path: \|\n(.*)\Z", upload, re.MULTILINE | re.DOTALL)
    if paths is None or paths.group(1).split() != [
        "${{",
        "runner.temp",
        "}}/fenolite-byte-diagnostics/board_40parts.PcbDoc",
        "${{",
        "runner.temp",
        "}}/fenolite-byte-diagnostics/receipt.json",
    ]:
        problems.append("upload must list exactly the two fixed diagnostic files")
    probe = steps.get("Probe authored Mac byte guard", "")
    if "if: matrix.os == 'macos-latest'" not in probe or "id: authored_byte_probe" not in probe:
        problems.append("preprobe must be explicitly Mac-only")
    if "continue-on-error: true" not in probe or unit.group(1).count("continue-on-error:") != 1:
        problems.append("only the preprobe may tolerate failure")
    expected_probe = (
        "run: uv run pytest 'tests/unit/test_build_bytes.py::"
        "test_example_keeps_its_bytes[board_40parts@altium]' "
        '-q --basetemp "${{ runner.temp }}/fenolite-byte-probe"'
    )
    if (
        expected_probe not in probe
        or "FENOLITE_BUILD_BYTE_DIAGNOSTICS: ${{ runner.temp }}/fenolite-byte-diagnostics" not in probe
    ):
        problems.append("preprobe must run the strict original row with its own external basetemp")
    early = steps.get("Keep early authored Mac byte-failure evidence", "")
    if (
        "if: always() && matrix.os == 'macos-latest' && steps.authored_byte_probe.outcome == 'failure'"
        not in early
    ):
        problems.append("early upload must inspect the actual Mac preprobe outcome")
    early_paths = re.search(r"^          path: \|\n(.*)\Z", early, re.MULTILINE | re.DOTALL)
    if early_paths is None or paths is None or early_paths.group(1).split() != paths.group(1).split():
        problems.append("early upload must retain only the same two files")
    if (
        "name: authored-mac-byte-failure-early\n" not in early
        or "name: authored-mac-byte-failure\n" not in upload
    ):
        problems.append("early and late artifacts must have distinct fixed names")
    order = [
        unit.group(1).find("- name: " + name)
        for name in (
            "Probe authored Mac byte guard",
            "Keep early authored Mac byte-failure evidence",
            "Tests",
            "Keep authored Mac byte-failure evidence",
        )
    ]
    if any(position < 0 for position in order) or order != sorted(order):
        problems.append("early capture must precede the strict main tests and late capture")
    return problems


def test_workflow_retains_only_mac_failure_evidence() -> None:
    text = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert _workflow_problems(text) == []


@pytest.mark.parametrize("broaden", ["enable-everywhere", "upload-everywhere", "upload-tree"])
def test_workflow_refuses_broadened_capture_or_upload(broaden: str) -> None:
    text = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    if broaden == "enable-everywhere":
        text = text.replace("matrix.os == 'macos-latest' && format", "true && format")
    elif broaden == "upload-everywhere":
        text = text.replace("if: failure() && matrix.os == 'macos-latest'", "if: failure()")
    else:
        text = text.replace("}}/fenolite-byte-diagnostics/receipt.json", "}}/fenolite-byte-diagnostics/**")
    assert _workflow_problems(text)


@pytest.mark.parametrize(
    "change", ["main-tolerates-failure", "early-everywhere", "early-tree", "artifact-collision"]
)
def test_workflow_refuses_early_probe_scope_or_outcome_changes(change: str) -> None:
    text = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    if change == "main-tolerates-failure":
        text = text.replace("- name: Tests\n", "- name: Tests\n        continue-on-error: true\n", 1)
    elif change == "early-everywhere":
        text = text.replace("if: matrix.os == 'macos-latest'", "if: always()", 1)
    elif change == "early-tree":
        text = text.replace("}}/fenolite-byte-diagnostics/receipt.json", "}}/fenolite-byte-diagnostics/**", 1)
    else:
        text = text.replace("name: authored-mac-byte-failure-early\n", "name: authored-mac-byte-failure\n")
    assert _workflow_problems(text)
