# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Declared contract drift and compatibility, without freezing implementation modules."""

from __future__ import annotations

import dataclasses
import importlib.util
import json
from pathlib import Path

import pytest

from fenolite import api, dsl
from fenolite.cli.api import Command, Result, discover
from fenolite.cli.surface import PUBLIC_MODULES, Surface, cli_surface, library_surface, surface_changes

ROOT = Path(__file__).resolve().parents[3]


def command(register=None):
    def options(parser):
        parser.add_argument("path")
        parser.add_argument("-o", "--out", default="out")
        parser.add_argument("--amount", type=int, choices=(1, 2), default=1)
        if register:
            register(parser)

    return Command("demo", "Authored contract fixture", False, options, lambda args, ctx: Result())


def minimal(register=None):
    return cli_surface({"demo": command(register)}, experimental=())


def test_declared_arguments_and_hidden_boundary():
    demo = command()
    surface = cli_surface(
        {"demo": demo, "_echo": dataclasses.replace(demo, name="_echo", help=None)}, experimental=()
    )
    data = surface.to_json()
    assert set(data["commands"]) == {"*", "demo"}
    options = data["commands"]["demo"]["options"]
    assert options["--amount"] == {
        "aliases": ["--amount"],
        "type": "integer",
        "default": 1,
        "required": False,
        "nargs": None,
        "choices": [1, 2],
        "positional": False,
        "experimental": False,
        "deprecated": None,
    }
    assert options["path"]["required"] and options["path"]["positional"]
    assert options["-o"] == options["--out"]
    assert "--fields" in data["commands"]["*"]["options"] and "--fields" not in options


def test_experimental_selector_does_not_exempt_stable_choices():
    def options(parser):
        parser.add_argument("--target", choices=("kicad", "altium"), default="kicad")

    surface = cli_surface(
        {"demo": command(options)}, experimental=({"command": "demo", "option": "--target altium"},)
    )
    option = surface.to_json()["commands"]["demo"]["options"]["--target"]
    assert option["experimental"] is False
    assert option["experimental_choices"] == ["altium"]


def test_only_explicit_public_python_exports_are_recorded():
    libraries = library_surface()
    assert set(libraries) == set(PUBLIC_MODULES)
    assert set(libraries["fenolite.dsl"]) == set(dsl.__all__)
    assert set(libraries["fenolite.api"]) == set(api.__all__)
    assert "parameters" in libraries["fenolite.api"]["convert"]
    assert "place" in libraries["fenolite.dsl"]["Part"]["methods"]
    assert "__getitem__" in libraries["fenolite.dsl"]["Part"]["methods"]
    assert all(not name.startswith("_") for name in libraries["fenolite.dsl"]["Part"]["fields"])
    assert "fenolite.model" not in libraries
    assert all(
        not parameter["name"].startswith("_")
        for parameter in libraries["fenolite.api"]["Board"]["parameters"]
    )


def test_public_fields_exclude_a_private_nested_implementation(monkeypatch):
    class Toy:
        marker = 7

        class _Internal:
            def __init__(self):
                self.internal_only = 1

        def __init__(self, public=3, _private=None):
            self.public_field = public

    monkeypatch.setattr(api, "__all__", [*api.__all__, "Toy"])
    monkeypatch.setattr(api, "Toy", Toy, raising=False)
    found = library_surface()["fenolite.api"]["Toy"]
    assert found["fields"]["marker"]["value"] == 7
    assert "public_field" in found["fields"] and "internal_only" not in found["fields"]
    assert [parameter["name"] for parameter in found["parameters"]] == ["public"]


def test_surface_json_roundtrip_has_no_addresses():
    data = minimal().to_json()
    text = json.dumps(data, sort_keys=True)
    assert " at 0x" not in text
    assert Surface.from_json(text).to_json() == data


def generator():
    spec = importlib.util.spec_from_file_location(
        "_fenolite_surface_generator", ROOT / "tools/gen_cli_surface.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_committed_surface_matches_registry():
    surface = cli_surface(discover())
    expected = surface.to_json()
    committed = json.loads((ROOT / "docs/cli-surface.json").read_text())
    changes = surface_changes(Surface.from_json(committed), surface)
    assert committed == expected, "surface drift: " + "; ".join(
        f"{change.kind}: {change.path}" for change in changes
    )
    assert generator().main(["--check"]) == 0


def test_generator_detects_an_unrecorded_option(monkeypatch, tmp_path):
    tool = generator()
    monkeypatch.setattr(tool, "discover", lambda: {"demo": command()})
    snapshot = tmp_path / "surface.json"
    assert tool.main(["--out", str(snapshot)]) == 0
    monkeypatch.setattr(tool, "discover", lambda: {"demo": command(lambda p: p.add_argument("--added"))})
    assert tool.main(["--check", "--out", str(snapshot)]) == 1


def test_review_is_explicit_about_static_mentions(monkeypatch, tmp_path):
    tool = generator()
    monkeypatch.setattr(tool, "discover", lambda: {"demo": command()})
    out = tmp_path / "review.md"
    assert tool.main(["--review", "--out", str(out)]) == 0
    text = out.read_text()
    assert "Static mentions only" in text and "demo --amount" in text
    assert "pending" in text and "not runtime coverage" in text
    assert "fenolite.api.convert" in text
    assert tool.main(["--review", "--keep-all", "--out", str(out)]) == 0
    assert ": pending." not in out.read_text() and " | pending |" not in out.read_text()
    assert " | keep |" in out.read_text()


def test_generator_checks_the_release_baseline_after_drift_check(monkeypatch, tmp_path):
    tool = generator()
    monkeypatch.setattr(tool, "discover", lambda: {"demo": command()})
    snapshot = tmp_path / "surface.json"
    assert tool.main(["--out", str(snapshot)]) == 0
    baseline = minimal(lambda p: p.add_argument("--released"))
    monkeypatch.setattr(tool, "release_baseline", lambda surface: baseline)
    assert tool.main(["--check", "--out", str(snapshot)]) == 1


def test_release_baseline_reads_only_the_last_reachable_stable_tag(monkeypatch):
    from types import SimpleNamespace

    tool = generator()
    data = minimal().to_json()
    data["version"] = "1.2.0"
    surface = Surface.from_json(data)
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(
            stdout="v0.7.0\nv1.0.0\nv1.1.0\nv2.0.0\nv1.2.0rc1\n" if args[1] == "tag" else json.dumps(data)
        )

    monkeypatch.setattr(tool.subprocess, "run", run)
    assert tool.release_baseline(surface).to_json() == data
    assert calls == [["git", "tag", "--merged", "HEAD"], ["git", "show", "v1.1.0:docs/cli-surface.json"]]


def test_missing_release_baseline_is_only_allowed_for_the_first_freeze(monkeypatch):
    from types import SimpleNamespace

    tool = generator()
    monkeypatch.setattr(tool.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(stdout=""))
    data = minimal().to_json()
    data["version"] = "1.0.0"
    assert tool.release_baseline(Surface.from_json(data)) is None
    data["version"] = "1.1.0"
    with pytest.raises(ValueError, match="restore the local release tags"):
        tool.release_baseline(Surface.from_json(data))


@pytest.fixture(scope="module")
def baseline():
    data = minimal().to_json()
    data["version"] = "1.0.0"
    data["issue_codes"]["authored.finding"] = {"severities": ["warning"], "experimental": False}
    data["library"]["fenolite.api"]["authored"] = {
        "kind": "function",
        "parameters": [
            {
                "name": "x",
                "kind": "POSITIONAL_OR_KEYWORD",
                "required": True,
                "default": None,
                "annotation": "str",
            },
            {
                "name": "name",
                "kind": "KEYWORD_ONLY",
                "required": False,
                "default": None,
                "annotation": "str | None",
            },
        ],
    }
    data["library"]["fenolite.api"]["Authored"] = {
        "kind": "class",
        "parameters": [],
        "fields": {"public": {"annotation": "str"}},
        "methods": {"read": {"parameters": []}},
    }
    return Surface.from_json(data)


def compare(baseline, change):
    after = baseline.to_json()
    after["version"] = "1.1.0"
    change(after)
    return surface_changes(baseline, Surface.from_json(after))


@pytest.mark.parametrize(
    "key,new,kind",
    [
        ("default", 2, "default-changed"),
        ("type", "string", "type-changed"),
        ("required", True, "required-added"),
        ("choices", [1], "narrowed"),
    ],
)
def test_argument_contract_changes_are_breaking(baseline, key, new, kind):
    found = compare(baseline, lambda data: data["commands"]["demo"]["options"]["--amount"].update({key: new}))
    assert [(c.kind, c.path, c.breaking) for c in found] == [(kind, "demo --amount", True)]


@pytest.mark.parametrize(
    "section,key,path",
    [
        ("commands", "demo", "demo"),
        ("exit_codes", "LOSSY", "exit_codes LOSSY"),
        ("fen_codes", "FEN-6004", "fen_codes FEN-6004"),
        ("issue_codes", "authored.finding", "issue_codes authored.finding"),
    ],
)
def test_removed_contract_items_are_breaking(baseline, section, key, path):
    found = compare(baseline, lambda data: data[section].pop(key))
    assert [(c.kind, c.path, c.breaking) for c in found] == [("removed", path, True)]


def test_removed_option_and_choice_experimental_exemptions(baseline):
    data = baseline.to_json()
    option = data["commands"]["demo"]["options"]["--amount"]
    option["experimental_choices"] = [2]
    before = Surface.from_json(data)
    found = compare(
        before, lambda after: after["commands"]["demo"]["options"]["--amount"].update(choices=[1])
    )
    assert len(found) == 1 and not found[0].breaking
    found = compare(
        before, lambda after: after["commands"]["demo"]["options"]["--amount"].update(choices=[2])
    )
    assert len(found) == 1 and found[0].breaking
    option["experimental"] = True
    found = compare(
        Surface.from_json(data), lambda after: after["commands"]["demo"]["options"].pop("--amount")
    )
    assert len(found) == 1 and not found[0].breaking


def test_optional_addition_and_required_alias_are_not_breaking(baseline):
    data = baseline.to_json()
    for alias in ("--out", "-o"):
        data["commands"]["demo"]["options"][alias]["required"] = True
    before = Surface.from_json(data)

    def change(data):
        options = data["commands"]["demo"]["options"]
        options["--optional"] = {**options["--amount"], "aliases": ["--optional"]}
        options["--new-out"] = {**options["--out"], "aliases": ["-o", "--out", "--new-out"]}

    found = compare(before, change)
    assert len(found) == 2 and all(c.kind == "added" and not c.breaking for c in found)


def test_new_required_argument_is_not_an_additive_change(baseline):
    def change(data):
        options = data["commands"]["demo"]["options"]
        options["--new-required"] = {**options["--out"], "aliases": ["--new-required"], "required": True}

    (found,) = compare(baseline, change)
    assert found.kind == "required-added" and found.breaking


@pytest.mark.parametrize(
    "levels,kind,breaking",
    [
        (["error"], "severity-raised", True),
        (["info"], "severity-lowered", False),
        (["warning", "error"], "severity-raised", True),
    ],
)
def test_severity_changes_include_multi_severity_codes(baseline, levels, kind, breaking):
    found = compare(baseline, lambda data: data["issue_codes"]["authored.finding"].update(severities=levels))
    assert len(found) == 1 and (found[0].kind, found[0].breaking) == (kind, breaking)


def test_public_library_parameter_and_field_removal_are_breaking(baseline):
    found = compare(baseline, lambda data: data["library"]["fenolite.api"]["authored"]["parameters"].pop())
    assert [(c.kind, c.path, c.breaking) for c in found] == [("removed", "fenolite.api.authored(name)", True)]
    found = compare(
        baseline, lambda data: data["library"]["fenolite.api"]["Authored"]["fields"].pop("public")
    )
    assert [(c.kind, c.path, c.breaking) for c in found] == [
        ("removed", "fenolite.api.Authored.public", True)
    ]


def test_new_public_required_parameter_and_optional_parameter(baseline):
    def change(data, required):
        data["library"]["fenolite.api"]["authored"]["parameters"].append(
            {
                "name": "added",
                "kind": "KEYWORD_ONLY",
                "required": required,
                "default": None,
                "annotation": "str | None",
            }
        )

    (required,) = compare(baseline, lambda data: change(data, True))
    (optional,) = compare(baseline, lambda data: change(data, False))
    assert required.kind == "required-added" and required.breaking
    assert optional.kind == "added" and not optional.breaking


def test_positional_binding_changes_are_not_hidden_as_optional_additions(baseline):
    data = baseline.to_json()
    parameters = data["library"]["fenolite.api"]["authored"]["parameters"]
    parameters[1]["kind"] = "POSITIONAL_OR_KEYWORD"
    before = Surface.from_json(data)
    found = compare(
        before,
        lambda after: after["library"]["fenolite.api"]["authored"]["parameters"].insert(
            0,
            {
                "name": "before",
                "kind": "POSITIONAL_OR_KEYWORD",
                "required": False,
                "default": None,
                "annotation": None,
            },
        ),
    )
    assert any(c.kind == "type-changed" and c.breaking and c.path.endswith("(x)") for c in found)


def test_deprecation_does_not_allow_removal_until_two(baseline):
    data = baseline.to_json()
    data["commands"]["demo"]["options"]["--out"]["deprecated"] = {"since": "1.0.0", "use": "--new"}
    before = Surface.from_json(data)
    found = compare(before, lambda after: after["commands"]["demo"]["options"].pop("--out"))
    assert len(found) == 1 and found[0].breaking

    def two(after):
        after["version"] = "2.0.0"
        after["commands"]["demo"]["options"].pop("--out")

    found = compare(before, two)
    assert len(found) == 1 and not found[0].breaking


def test_stable_item_cannot_be_relabelled_as_experimental_to_evade_the_judge(baseline):
    found = compare(
        baseline, lambda data: data["commands"]["demo"]["options"]["--amount"].update(experimental=True)
    )
    assert len(found) == 1 and found[0].kind == "type-changed" and found[0].breaking


def test_explicit_writer_ownership_keeps_shared_and_reader_codes_stable():
    from fenolite.backends.altium.adapter.codes import IMPORT_ISSUE_CODES
    from fenolite.cli.explain import table_codes

    codes = cli_surface(discover()).to_json()["issue_codes"]
    assert codes["altium.lib-id-form"]["experimental"]
    assert not codes["build.not-two-terminal"]["experimental"]
    assert all(not codes[code]["experimental"] for code in table_codes(IMPORT_ISSUE_CODES))


def test_widened_list_arity_is_additive_and_a_narrower_list_is_not(baseline):
    data = baseline.to_json()
    data["commands"]["demo"]["options"]["--amount"]["nargs"] = "+"
    before = Surface.from_json(data)
    (found,) = compare(
        before, lambda after: after["commands"]["demo"]["options"]["--amount"].update(nargs="*")
    )
    assert found.kind == "added" and not found.breaking
    (found,) = compare(before, lambda after: after["commands"]["demo"]["options"]["--amount"].update(nargs=1))
    assert found.breaking


def test_nargs_one_returns_a_list_even_when_cardinality_is_unchanged(baseline):
    (found,) = compare(
        baseline, lambda after: after["commands"]["demo"]["options"]["--amount"].update(nargs=1)
    )
    assert found.kind == "type-changed" and found.breaking


@pytest.fixture
def deprecated_echo(monkeypatch):
    from fenolite.cli import cmd_capabilities, main
    from fenolite.cli.api import deprecate

    commands = discover()
    original = commands["_echo"]

    def register(parser):
        original.register(parser)
        parser.add_argument("-x", "--legacy", action="append")
        deprecate(parser, "--legacy", since="0.7.0", use="--content")

    commands["_echo"] = dataclasses.replace(original, register=register)
    monkeypatch.setattr(main, "discover", lambda: commands)
    monkeypatch.setattr(cmd_capabilities, "discover", lambda: commands)
    return commands


@pytest.mark.parametrize("tokens", [("--legacy", "one"), ("--legacy=one",), ("--leg=one",), ("-xone",)])
def test_deprecated_option_actual_use_warns_once_and_keeps_behavior(deprecated_echo, tokens):
    reply = api.run("_echo", *tokens, *tokens)
    assert reply.exit_code == 0
    assert reply.result["echo"] == {"issues": [], "write": None}
    assert len(reply.envelope["issues"]) == 1
    issue = reply.envelope["issues"][0]
    assert issue["code"] == "cli.deprecated" and issue["severity"] == "warning"
    assert "--content" in issue["message"] and "0.7.0" in issue["message"]


def test_defaults_and_option_text_as_values_are_not_deprecated_use(deprecated_echo):
    assert api.run("_echo").envelope["issues"] == []
    assert api.run("_echo", "--text-body=--legacy").envelope["issues"] == []


def test_global_deprecation_is_one_item_before_and_after_the_command(monkeypatch):
    from fenolite.cli import main
    from fenolite.cli.api import deprecate

    original = main._add_global_options

    def globals(parser, *, top_level):
        original(parser, top_level=top_level)
        deprecate(parser, "--seed", since="0.7.0", use="a future seed option")

    monkeypatch.setattr(main, "_add_global_options", globals)
    reply = api.run("_echo", "--seed", "4")
    assert reply.exit_code == 0 and len(reply.envelope["issues"]) == 1
    assert reply.envelope["issues"][0]["where"] == "* --seed"
    found = api.run("capabilities", "--no-tools").result["deprecated"]
    assert found == [{"command": "*", "option": "--seed", "since": "0.7.0", "use": "a future seed option"}]
    code, envelope, _ = main.invoke(["--seed", "4", "_echo", "--seed", "4"], cwd=Path.cwd())
    assert code == 0 and len(envelope["issues"]) == 1


def test_deprecation_warning_is_present_on_cli_success_and_command_failure(deprecated_echo, capsys):
    from fenolite.cli.main import main

    assert main(["_echo", "-xone", "--json"]) == 0
    assert len(json.loads(capsys.readouterr().out)["issues"]) == 1
    failed = api.run("_echo", "-xone", "--raise")
    assert failed.exit_code == 1 and failed.envelope["issues"][0]["code"] == "cli.deprecated"


def test_deprecated_command_and_option_each_warn(deprecated_echo):
    deprecated_echo["_echo"] = dataclasses.replace(
        deprecated_echo["_echo"], deprecated="0.7.0", replacement="inspect"
    )
    reply = api.run("_echo", "--legacy=value")
    assert reply.exit_code == 0 and len(reply.envelope["issues"]) == 2
    assert {issue["where"] for issue in reply.envelope["issues"]} == {"_echo", "_echo --legacy"}


@pytest.mark.parametrize("view", [(), ("--brief",), ("--command", "_echo")])
@pytest.mark.parametrize("version", ["v0", "v1"])
def test_capabilities_keeps_contract_and_deprecations_in_every_view(
    deprecated_echo, monkeypatch, view, version
):
    from fenolite.cli import api as cli_api

    monkeypatch.setattr(cli_api, "CONTRACT_VERSION", version)
    reply = api.run("capabilities", "--no-tools", *view)
    assert reply.exit_code == 0 and reply.result["contract"] == version
    assert reply.result["deprecated"] == [
        {"command": "_echo", "option": "--legacy", "since": "0.7.0", "use": "--content"}
    ]
    if not view:
        assert all(entry["schema"].endswith("." + version) for entry in reply.result["commands"])


def test_surface_records_option_aliases_and_command_replacement(deprecated_echo):
    echo = dataclasses.replace(
        deprecated_echo["_echo"], name="demo", help="Authored", deprecated="0.7.0", replacement="inspect"
    )
    entry = cli_surface({"demo": echo}, experimental=()).to_json()["commands"]["demo"]
    mark = {"since": "0.7.0", "use": "--content"}
    assert entry["options"]["-x"]["deprecated"] == mark
    assert entry["options"]["--legacy"]["deprecated"] == mark
    assert entry["deprecated"] == {"since": "0.7.0", "use": "inspect"}


def test_deprecation_does_not_change_warning_failure_threshold(deprecated_echo):
    original = deprecated_echo["_echo"]
    deprecated_echo["_echo"] = dataclasses.replace(
        original, run=lambda args, ctx: dataclasses.replace(original.run(args, ctx), fail_on_warning=True)
    )
    assert api.run("_echo", "-xone").exit_code == 0
    assert api.run("_echo", "-xone", "--issue", "warning").exit_code == 5


def test_deprecation_does_not_change_library_warning_threshold(monkeypatch):
    from fenolite.cli import main
    from fenolite.cli.api import deprecate
    from fenolite.core.errors import Issue
    from fenolite.library import EVIDENCE

    def register(parser):
        parser.add_argument("--old", action="store_true")
        parser.add_argument("--finding", action="store_true")
        parser.add_argument("--fail-on", default="warning")
        deprecate(parser, "--old", since="0.7.0", use="--new")

    def run(args, ctx):
        return Result(
            evidence=EVIDENCE,
            issues=(Issue("authored.warning", "warning", "authored"),) if args.finding else (),
        )

    toy = Command("library", "Authored", False, register, run)
    monkeypatch.setattr(main, "discover", lambda: {"library": toy})
    assert api.run("library", "--old").exit_code == 0
    assert api.run("library", "--old", "--finding").exit_code == 5


def test_staged_deprecation_notice_is_not_duplicated_or_part_of_plan_arguments(
    deprecated_echo, monkeypatch, tmp_path
):
    monkeypatch.setenv("FENOLITE_STATE_DIR", str(tmp_path / "state"))
    preview = api.run("_echo", "-xone", "--write", "echo.txt", "--dry-run", cwd=tmp_path)
    assert preview.exit_code == 0
    plan = preview.result["plan_id"]
    original = deprecated_echo["_echo"]

    def refuse(args, ctx):
        raise AssertionError("staged replay ran the command")

    deprecated_echo["_echo"] = dataclasses.replace(original, run=refuse)
    written = api.run("_echo", "-xone", "--write", "echo.txt", "--confirm", "--plan", plan, cwd=tmp_path)
    assert written.exit_code == 0 and (tmp_path / "echo.txt").read_text() == "echo\n"
    assert len(written.envelope["issues"]) == 1 and written.envelope["issues"][0]["code"] == "cli.deprecated"


def test_deprecation_requires_a_release_replacement_and_registered_option():
    import argparse

    from fenolite.cli.api import deprecate

    parser = argparse.ArgumentParser()
    parser.add_argument("--old")
    with pytest.raises(ValueError, match="replacement"):
        deprecate(parser, "--old", since="later", use="")
    with pytest.raises(ValueError, match="no option"):
        deprecate(parser, "--missing", since="1.0.0", use="--new")
    with pytest.raises(ValueError, match="replacement"):
        dataclasses.replace(command(), deprecated="1.0.0")
