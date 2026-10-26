# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Every registered command honours the CLI contract (docs/cli-contract.md).

A new ``cmd_*.py`` is picked up automatically; if it breaks the contract, the failing test id
names it.
"""

from __future__ import annotations

import dataclasses
import json
import re
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import _schema
import pytest
from _cliexamples import PLANS_NOTHING, PREPARED, folder_snapshot, prepare_example
from _fakecli import EXAMPLE_NETLIST, fake_kicad_cli

from fenolite.cli.api import Command, Context, Result, discover, module_name_for
from fenolite.cli.main import main

COMMANDS = discover()
NAMES = sorted(COMMANDS)
SOURCE_WRITERS = frozenset({"sync"})
"""Mutating commands that write beside their input instead of under the working directory, so an example
would write into the package folder: each runs the mutation protocol in its own tests, on a copy."""
MUTATING = sorted(n for n, c in COMMANDS.items() if c.mutates and n not in SOURCE_WRITERS)
ENVELOPE = _schema.load("fenolite.envelope.v0.json")
ERROR = _schema.load("fenolite.error.v0.json")
CapSys = pytest.CaptureFixture[str]
EXAMPLE_TOOLS = frozenset({"kicad-cli"})
"""The external tools a command may name in ``example_tools``; the suites hold a fake for each."""


def unknown_tools(command: Command) -> list[str]:
    return sorted(set(command.example_tools) - EXAMPLE_TOOLS)


@pytest.fixture(autouse=True)
def example_tools(
    request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A command that names ``kicad-cli`` in ``example_tools`` runs its examples against the fake (capability
    cli-contract, "Tool-backed command examples"); the fake lives outside the test's ``tmp_path``."""
    callspec = getattr(request.node, "callspec", None)
    name = callspec.params.get("name") if callspec is not None else None
    if name in COMMANDS and "kicad-cli" in COMMANDS[name].example_tools:
        script = fake_kicad_cli(tmp_path_factory.mktemp("fake-kicad"), netlist=EXAMPLE_NETLIST)
        monkeypatch.setenv("FENOLITE_KICAD_CLI", str(script))
    if name in PREPARED:  # the examples of ``fmt`` and ``restore`` name files of the working directory
        work = tmp_path_factory.mktemp("example")
        prepare_example(name, work)
        monkeypatch.chdir(work)


def _invoke(capsys: CapSys, argv: list[str]) -> tuple[int, str, str]:
    code = main(argv)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _assert_envelope(name: str, out: str) -> dict[str, Any]:
    assert out.endswith("\n") and out.count("\n") == 1, "stdout must be one JSON document plus newline"
    data = json.loads(out)
    assert _schema.validate(data, ENVELOPE) == [], _schema.validate(data, ENVELOPE)
    assert data["command"] == name and data["schema"] == f"fenolite.{name}.v0"
    return data


def _assert_error(err: str, exit_code: int) -> dict[str, Any]:
    data = json.loads(err)
    assert _schema.validate(data, ERROR) == []
    assert int(data["code"][4]) == exit_code
    return data


@pytest.mark.parametrize("name", NAMES)
def test_example_tools_are_known(name: str) -> None:
    assert unknown_tools(COMMANDS[name]) == [], f"{name} names a tool the suites have no fake for"


def test_unknown_example_tool_is_named() -> None:
    command = dataclasses.replace(COMMANDS["_echo"], example_tools=("ngspice", "kicad-cli"))
    assert unknown_tools(command) == ["ngspice"]


def test_there_are_commands() -> None:
    assert "capabilities" in COMMANDS and "_echo" in COMMANDS


@pytest.mark.parametrize("name", NAMES)
def test_help(name: str, capsys: CapSys) -> None:
    code, out, _ = _invoke(capsys, [name, "--help"])
    assert code == 0 and f"usage: fenolite {name}" in out
    assert "--kicad-version" in out and "--allow-lossy" in out


@pytest.mark.parametrize("name", NAMES)
def test_json_envelope(name: str, capsys: CapSys) -> None:
    code, out, err = _invoke(capsys, [name, *COMMANDS[name].example_args, "--json"])
    assert code == 0, err
    data = _assert_envelope(name, out)
    assert data["ok"] is True and err == ""


def result_schema(name: str) -> dict[str, Any] | None:
    """The schema of the ``result`` of command ``name``, when ``schemas/fenolite.<name>.v0.json`` exists
    (capability design-equivalence, "Equivalent result schema"; change c0158)."""
    path = _schema.SCHEMAS / f"fenolite.{name}.v0.json"
    return _schema.load(path.name) if path.is_file() else None


RESULT_SCHEMAS = sorted(name for name in NAMES if result_schema(name) is not None)


def test_equivalent_has_a_result_schema() -> None:
    assert "equivalent" in RESULT_SCHEMAS


@pytest.mark.parametrize("name", RESULT_SCHEMAS)
def test_result_validates(name: str, capsys: CapSys) -> None:
    """Scenario "Reply validates": the envelope against its schema, ``result`` against the command's."""
    code, out, err = _invoke(capsys, [name, *COMMANDS[name].example_args, "--json"])
    assert code == 0, err
    data = _assert_envelope(name, out)
    schema = result_schema(name)
    assert schema is not None and schema["$id"] == f"fenolite.{name}.v0"
    assert _schema.validate(data["result"], schema) == []


@pytest.mark.parametrize("name", RESULT_SCHEMAS)
def test_result_schema_refuses_an_unknown_key(name: str, capsys: CapSys) -> None:
    """Scenario "Unknown key refused"."""
    _, out, _ = _invoke(capsys, [name, *COMMANDS[name].example_args, "--json"])
    result = json.loads(out)["result"]
    schema = result_schema(name)
    assert schema is not None
    problems = _schema.validate({**result, "extra": 1}, schema)
    assert problems and any("extra" in problem for problem in problems), problems


@pytest.mark.parametrize("name", NAMES)
def test_text_mode(name: str, capsys: CapSys) -> None:
    code, out, _ = _invoke(capsys, [name, *COMMANDS[name].example_args, "--text"])
    assert code == 0 and out.strip()
    with pytest.raises(json.JSONDecodeError):
        json.loads(out)
    assert out.startswith(f"fenolite {name}: ok")


@pytest.mark.parametrize("name", NAMES)
def test_fields_projection(name: str, capsys: CapSys) -> None:
    args = [name, *COMMANDS[name].example_args, "--json"]
    _, out, _ = _invoke(capsys, args)
    keys = list(json.loads(out)["result"])
    if not keys:
        pytest.skip(f"{name} returns an empty result")
    code, out, _ = _invoke(capsys, [*args, "--fields", keys[0]])
    assert code == 0 and list(json.loads(out)["result"]) == [keys[0]]
    code, _, err = _invoke(capsys, [*args, "--fields", "no-such-field"])
    assert code == 2 and _assert_error(err, 2)["code"] == "FEN-2002"


@pytest.mark.parametrize("name", NAMES)
def test_unknown_flag_is_usage_error(name: str, capsys: CapSys) -> None:
    code, out, err = _invoke(capsys, [name, "--no-such-flag", "--json"])
    assert code == 2 and out == ""
    _assert_error(err, 2)


@pytest.mark.parametrize("name", NAMES)
def test_internal_exception_maps_to_exit_1(
    name: str, capsys: CapSys, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(_args: object, _ctx: Context) -> Result:
        raise RuntimeError("forced failure")

    module = sys.modules[f"fenolite.cli.{module_name_for(name)}"]
    command: Command = module.COMMAND
    monkeypatch.setattr(module, "COMMAND", dataclasses.replace(command, run=boom))
    code, out, err = _invoke(capsys, [name, *command.example_args, "--json"])
    assert code == 1
    assert _assert_envelope(name, out)["ok"] is False
    assert _assert_error(err, 1)["code"] == "FEN-1001"


@pytest.mark.parametrize("name", MUTATING)
def test_mutation_protocol(
    name: str, capsys: CapSys, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    command = COMMANDS[name]
    assert command.mutation_example_args is not None, (
        f"{name} is mutating but declares no mutation_example_args"
    )
    monkeypatch.chdir(tmp_path)
    prepare_example(name, tmp_path)
    before = folder_snapshot(tmp_path)
    assert (before == {}) is (name not in PREPARED)
    args = [name, *command.mutation_example_args, "--json"]

    code, out, err = _invoke(capsys, args)
    if name in PLANS_NOTHING:  # nothing to write: no confirmation is asked, and every form exits 0
        assert code == 0 and folder_snapshot(tmp_path) == before
        assert not _assert_envelope(name, out)["result"].get("plan")
        for protocol in ("--dry-run", "--confirm"):
            code, out, _ = _invoke(capsys, [*args, protocol])
            assert code == 0 and folder_snapshot(tmp_path) == before
            assert not _assert_envelope(name, out)["result"].get("plan")
        code, _, err = _invoke(capsys, [*args, "--dry-run", "--confirm"])
        assert code == 2 and _assert_error(err, 2)["code"] == "FEN-2003"
        return
    assert code == 4 and folder_snapshot(tmp_path) == before
    assert _assert_envelope(name, out)["result"]["plan"]
    assert _assert_error(err, 4)["code"] == "FEN-4001"

    code, out, _ = _invoke(capsys, [*args, "--dry-run"])
    assert code == 0 and folder_snapshot(tmp_path) == before
    assert before or list(tmp_path.iterdir()) == []
    plan = _assert_envelope(name, out)["result"]["plan"]

    code, out, _ = _invoke(capsys, [*args, "--confirm"])
    assert code == 0
    receipt = _assert_envelope(name, out)["receipt"]
    assert [w["path"] for w in receipt["written"]] == [p["path"] for p in plan]
    assert all((tmp_path / w["path"]).is_file() for w in receipt["written"])

    code, _, err = _invoke(capsys, [*args, "--dry-run", "--confirm"])
    assert code == 2 and _assert_error(err, 2)["code"] == "FEN-2003"


WRITES_ON_ERROR = {"place": "--force", "manifest": "the manifest", "kit": "the record"}
"""The commands that may write beside an error finding, and the words their module says why with: ``place``
under ``--force``; ``manifest``, whose one write is the report of the check ("Manifest command": planned
whether or not the check found errors); ``kit record``, which records a run with failed steps (cli-contract,
"Error findings plan no write")."""


@pytest.mark.parametrize("name", sorted(n for n, c in COMMANDS.items() if c.mutates))
def test_error_no_write(name: str) -> None:
    """Scenario "The rule holds for every mutating command": a module that sets ``write_on_error`` and is
    not one of the named exceptions fails here."""
    source = Path(sys.modules[f"fenolite.cli.{module_name_for(name)}"].__file__ or "").read_text(
        encoding="utf-8"
    )
    assert ("write_on_error" in source) is (name in WRITES_ON_ERROR), name
    if name in WRITES_ON_ERROR:
        assert WRITES_ON_ERROR[name] in source


def test_error_no_write_in_the_dispatcher(
    capsys: CapSys, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    for protocol in (["--confirm"], ["--dry-run"], []):
        code, out, err = _invoke(
            capsys, ["_echo", "--issue", "error", "--write", "x.txt", "--json", *protocol]
        )
        data = _assert_envelope("_echo", out)
        assert code == 5 and _assert_error(err, 5)["code"] == "FEN-5001"
        assert data["receipt"] is None and "plan" not in data["result"] and "plan_id" not in data["result"]
        assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("name", MUTATING)
def test_depends_declared(name: str, capsys: CapSys, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Every mutating command declares its inputs": the dry run of the mutation example gives a
    plan id of 16 hex digits, and every declared input is an existing file. An example reads its input
    from the package's own data, so a declared path is inside the working folder or absolute."""
    command = COMMANDS[name]
    assert command.mutation_example_args is not None
    monkeypatch.chdir(tmp_path)
    prepare_example(name, tmp_path)
    seen: list[Result] = []
    module = sys.modules[f"fenolite.cli.{module_name_for(name)}"]

    def recording(args: Any, ctx: Context) -> Result:
        seen.append(command.run(args, ctx))
        return seen[-1]

    monkeypatch.setattr(module, "COMMAND", dataclasses.replace(command, run=recording))
    code, out, err = _invoke(capsys, [name, *command.mutation_example_args, "--json", "--dry-run"])
    assert code == 0, err
    data = _assert_envelope(name, out)
    (result,) = seen
    for path in result.depends:
        assert not Path(path).is_absolute() or ".." not in Path(path).parts
        assert (tmp_path / path).is_file(), f"{name} declares {path}, which is no file"
        if not Path(path).is_absolute():
            assert (tmp_path / path).resolve().is_relative_to(tmp_path.resolve())
    assert list(result.depends) == sorted(set(result.depends))
    if name in PLANS_NOTHING:
        assert "plan_id" not in data["result"]
        return
    assert re.fullmatch(r"[0-9a-f]{16}", data["result"]["plan_id"])


def test_depends_names_the_inputs_of_each_command() -> None:
    """The commands that read a design file declare one: only ``_echo``, ``fetch`` without ``--from`` and
    ``kit build`` from the packaged samples have nothing to declare in their examples."""
    assert "depends" in Result.__dataclass_fields__ and Result().depends == ()
    assert Result().write_on_error is False


@pytest.mark.parametrize("name", NAMES)
def test_non_mutating_commands_reject_protocol_flags(name: str, capsys: CapSys) -> None:
    if COMMANDS[name].mutates:
        pytest.skip("mutating")
    code, _, _ = _invoke(capsys, [name, "--confirm", "--json"])
    assert code == 2


def test_check_codes_documented() -> None:
    """Every check and doctor issue code appears in docs/cli-contract.md (``kicad`` for ``<oracle>``)."""
    from fenolite.checks.codes import ISSUE_CODES as CHECK_CODES
    from fenolite.cli.cmd_doctor import ISSUE_CODES as DOCTOR_CODES

    contract = (Path(__file__).resolve().parents[2] / "docs" / "cli-contract.md").read_text(encoding="utf-8")
    from fenolite.exports.codes import ISSUE_CODES as EXPORT_CODES

    for code in [*CHECK_CODES, *DOCTOR_CODES, *EXPORT_CODES]:
        assert f"`{code.replace('<oracle>', 'kicad')}`" in contract, code


CONTRACT = Path(__file__).resolve().parents[2] / "docs" / "cli-contract.md"


def undescribed_commands(names: Iterable[str], page: str) -> list[str]:
    """The commands the contract page does not describe: neither the text ``fenolite <name>`` nor a
    level-2 heading that is the name, with or without backticks (cli-contract, "Contract page names every
    command")."""
    headings = {
        match.group(1) for match in re.finditer(r"^## `?([A-Za-z_][A-Za-z0-9_-]*)`?\s*$", page, re.MULTILINE)
    }
    return [
        name
        for name in names
        if name not in headings and re.search(rf"\bfenolite {re.escape(name)}\b", page) is None
    ]


def test_contract_names_every_command() -> None:
    page = CONTRACT.read_text(encoding="utf-8")
    public = [name for name in NAMES if not COMMANDS[name].hidden]
    assert "template" in public
    assert undescribed_commands(public, page) == []


def test_contract_names_detects_a_missing_section() -> None:
    page = CONTRACT.read_text(encoding="utf-8")
    start = page.index("\n## template\n")
    following = page.find("\n## ", start + 1)
    without = page[:start] + (page[following:] if following != -1 else "\n")
    assert undescribed_commands(["template"], without) == ["template"]
    assert undescribed_commands(["build", "fill", "nope"], "## `build`\n\nrun `fenolite fill X`\n") == [
        "nope"
    ]
    assert undescribed_commands(["fill"], "see fenolite filling\n") == ["fill"]


def test_template_codes_documented() -> None:
    from fenolite.templates import ISSUE_CODES as TEMPLATE_CODES

    page = CONTRACT.read_text(encoding="utf-8")
    section = page[page.index("\n## template\n") :]
    for code, severity in TEMPLATE_CODES.items():
        assert f"| `{code}` | {severity} |" in section, code
