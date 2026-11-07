# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Combined block/device items preserve literal locks, preflight and reviewed source inputs."""

from __future__ import annotations

import shutil
from dataclasses import replace
from pathlib import Path

import pytest
from _blockitems import ITEM_PATH, VENDORED, get, project, release
from _checkcli import run
from _libdemo import no_network, unpublished_releases, write_release

from fenolite.cli._contracts import devices_of
from fenolite.cli._script import run_design_script
from fenolite.dsl.blockitem import from_record
from fenolite.dsl.devices import installed
from fenolite.dsl.lock import read_lock
from fenolite.model import canonical

ROOT = Path(__file__).resolve().parents[3]
DEVICE_RELEASE = ROOT / "examples/library-devices/release"
DEVICE = Path("fenolite_library/devices/FenoliteDevices/Demo900/record.toml")


@pytest.fixture(autouse=True)
def _unpublished(monkeypatch: pytest.MonkeyPatch) -> None:
    unpublished_releases(monkeypatch)  # the demo releases call themselves 1.0.0


def block_release(folder: Path, work: Path, *, version: str = "1.0.0") -> Path:
    from fenolite.cli._blocks_index import exported_block, item_module
    from fenolite.dsl.record import describe

    release(folder, version=version)
    repository = folder / "repository"
    item = repository / ITEM_PATH
    source = item / "__init__.py"
    source.write_text(
        source.read_text().replace(
            '"Mini:Mini_R", footprint="Mini:Mini_R_0603",', 'device="FenoliteDevices:Demo900",'
        )
    )
    scope = work / "scope.py"
    scope.write_text('from fenolite.dsl import Design\ndesign = Design("scope")\n')
    devices = run_design_script(scope).devices
    with installed(devices), item_module(item) as module:
        record = from_record(describe(exported_block(module)))
    (item / "block.json").write_text(record.text())
    destination = folder / "device-release"
    write_release(repository, destination, version)
    return destination


@pytest.fixture
def combined(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    no_network(monkeypatch)
    work = project(tmp_path / "project")
    code, env, error, _ = run(
        monkeypatch,
        work,
        "get",
        "device",
        "FenoliteDevices:Demo900",
        "--from",
        str(DEVICE_RELEASE),
        "--confirm",
    )
    assert code == 0, (env.get("issues"), error)
    get(monkeypatch, work, block_release(tmp_path / "one", work))
    return work


def test_block_using_vendored_device_keeps_all_pins(monkeypatch: pytest.MonkeyPatch, combined: Path) -> None:
    old = read_lock((combined / "design.lock").read_text(), file="design.lock")
    assert set(old.sections["library"]) == {
        "block/Demo:led",
        "device/FenoliteDevices:Demo900",
        "symbol/FenoliteDevices:DemoTwoPin",
        "footprint/FenoliteDevices:DemoTwoPad",
    }
    code, env, error, _ = run(monkeypatch, combined, "build", "design.py", "--out", "B", "--confirm")
    assert code == 0, (env.get("issues"), error)
    current = read_lock((combined / "design.lock").read_text(), file="design.lock")
    assert current.sections["library"] == old.sections["library"]
    assert current.sections["blocks"] == {"led1": "Demo:led@1.0.0"}
    (device,) = env["result"]["devices"]
    assert device["origin"] == "library" and device["item"]["id"] == "FenoliteDevices:Demo900"
    assert env["result"]["libraries"]["FenoliteDevices:DemoTwoPad"] == "library"
    assert run(monkeypatch, combined, "build", "design.py", "--out", "B", "--frozen", "--dry-run")[0] == 0


@pytest.mark.parametrize("verb", ("build", "upgrade"))
@pytest.mark.parametrize("item", ("block/Demo:led", "device/FenoliteDevices:Demo900"))
def test_missing_item_stops_before_design_execution(
    monkeypatch: pytest.MonkeyPatch, combined: Path, verb: str, item: str
) -> None:
    lock = read_lock((combined / "design.lock").read_text(), file="design.lock")
    shutil.rmtree(combined / lock.sections["library"][item]["path"])
    script = combined / "design.py"
    script.write_text('from pathlib import Path\nPath("executed").write_text("bad")\n' + script.read_text())
    command = ("build", "design.py", "--out", "B") if verb == "build" else ("blocks", "upgrade", "design.py")
    code, _, error, _ = run(monkeypatch, combined, *command, "--confirm")
    assert code == 6 and error["code"] == "FEN-6004"
    assert not (combined / "executed").exists() and not (combined / "B").exists()


def upgraded(monkeypatch: pytest.MonkeyPatch, work: Path, tmp_path: Path) -> None:
    assert run(monkeypatch, work, "build", "design.py", "--out", "B", "--confirm")[0] == 0
    get(monkeypatch, work, block_release(tmp_path / "two", work, version="1.1.0"))
    script = work / "design.py"
    script.write_text(
        "from pathlib import Path\n"
        'marker = Path("executions")\n'
        'marker.write_text((marker.read_text() if marker.exists() else "") + "1")\n' + script.read_text()
    )


def test_upgrade_keeps_device_pins_and_executes_once(
    monkeypatch: pytest.MonkeyPatch, combined: Path, tmp_path: Path
) -> None:
    upgraded(monkeypatch, combined, tmp_path)
    before = read_lock((combined / "design.lock").read_text(), file="design.lock")
    args = ("blocks", "upgrade", "design.py", "--out", "B")
    code, env, error, _ = run(monkeypatch, combined, *args, "--dry-run")
    assert code == 0, (env.get("issues"), error)
    assert [(row["path"], row["kind"]) for row in env["result"]["plan"]] == [("design.lock", "lock")]
    assert (combined / "executions").read_text() == "1"
    code, _, error, _ = run(monkeypatch, combined, *args, "--confirm", "--plan", env["result"]["plan_id"])
    assert code == 0, error
    assert (combined / "executions").read_text() == "1"
    after = read_lock((combined / "design.lock").read_text(), file="design.lock")
    assert after.sections["library"] == before.sections["library"]
    assert after.sections["blocks"] == {"led1": "Demo:led@1.1.0"}


def test_upgrade_replay_binds_used_device_bytes(
    monkeypatch: pytest.MonkeyPatch, combined: Path, tmp_path: Path
) -> None:
    upgraded(monkeypatch, combined, tmp_path)
    args = ("blocks", "upgrade", "design.py", "--out", "B")
    code, env, error, _ = run(monkeypatch, combined, *args, "--dry-run")
    assert code == 0, (env.get("issues"), error)
    before = (combined / "design.lock").read_bytes()
    source = combined / DEVICE
    source.write_text(source.read_text() + "\n# Authored edit after review.\n")
    code, _, error, _ = run(monkeypatch, combined, *args, "--confirm", "--plan", env["result"]["plan_id"])
    assert code == 4 and error["code"] == "FEN-4002"
    assert (combined / "design.lock").read_bytes() == before
    assert (combined / "executions").read_text() == "1"


@pytest.mark.parametrize("relative", (VENDORED / "__init__.py", DEVICE))
def test_build_replay_binds_block_and_device_bytes(
    monkeypatch: pytest.MonkeyPatch, combined: Path, relative: Path
) -> None:
    code, env, error, _ = run(monkeypatch, combined, "build", "design.py", "--out", "B", "--dry-run")
    assert code == 0, (env.get("issues"), error)
    source = combined / relative
    source.write_text(source.read_text() + "\n# Authored edit after review.\n")
    code, _, error, _ = run(
        monkeypatch,
        combined,
        "build",
        "design.py",
        "--out",
        "B",
        "--confirm",
        "--plan",
        env["result"]["plan_id"],
    )
    assert code == 4 and error["code"] == "FEN-4002"
    assert not (combined / "B").exists()


@pytest.mark.parametrize("authored", (False, True))
def test_block_runner_builds_and_instantiates_vendored_devices(
    monkeypatch: pytest.MonkeyPatch, combined: Path, authored: bool
) -> None:
    if authored:
        (combined / "devices").mkdir()
        shutil.copy(combined / DEVICE, combined / "devices/override.toml")
    root = combined / VENDORED
    usage = """from fenolite.dsl import Design, Part, connect, mm
from fenolite_library.blocks.Demo.led import led
design = Design("combined_usage")
design.board(mm(40), mm(20))
dut = design.use(led, "dut")
header = Part("J1", "Fenolite:Connector_2", footprint="Fenolite:Header_1x2_P2.54")
design.add(header)
connect(dut.POS, header[1])
connect(dut.NEG, header[2])
dut.part("R").place(mm(10), mm(10))
header.place(mm(20), mm(10))
"""
    test = """from fenolite_library.blocks.Demo.led import led
from fenolite.testing import instantiate
def test_device():
    with instantiate(led) as design:
        assert design.ref("dut/R").value == "1k"
"""
    for relative, text in (("usage/led.py", usage), ("tests/test_led.py", test), ("golden/led.json", "{}\n")):
        path = root / relative
        path.parent.mkdir(exist_ok=True)
        path.write_text(text)
    before = {p.relative_to(combined): p.read_bytes() for p in combined.rglob("*") if p.is_file()}
    code, env, error, _ = run(monkeypatch, combined, "blocks", "test", "Demo:led", "--golden", "--dry-run")
    assert code == 0, (env.get("issues"), error)
    (block,) = env["result"]["blocks"]
    assert block["usage"] == "passed" and block["tests"][0]["status"] == "passed"
    assert {p.relative_to(combined): p.read_bytes() for p in combined.rglob("*") if p.is_file()} == before
    if authored:
        source = combined / "devices/override.toml"
        source.write_text(source.read_text() + "\n# Authored edit after golden review.\n")
        code, _, error, _ = run(
            monkeypatch,
            combined,
            "blocks",
            "test",
            "Demo:led",
            "--golden",
            "--confirm",
            "--plan",
            env["result"]["plan_id"],
        )
        assert code == 4 and error["code"] == "FEN-4002"


def test_circuit_device_queries_keep_vendored_and_authored_precedence(
    monkeypatch: pytest.MonkeyPatch, combined: Path
) -> None:
    assert run(monkeypatch, combined, "build", "design.py", "--out", "B", "--confirm")[0] == 0
    model = canonical.load_dir(combined / "B/.fenolite")
    (original,) = devices_of(model, combined / "B").values()
    assert original.id == "FenoliteDevices:Demo900" and original.manufacturer == "Example Semi"
    (combined / "devices/proposed").mkdir(parents=True)
    (combined / "devices/proposed/unreviewed.toml").write_text(
        (combined / DEVICE).read_text().replace("Example Semi", "Unreviewed proposal")
    )
    assert devices_of(model, combined / "B") == {original.id: original}
    source = combined / "devices/override.toml"
    source.write_text((combined / DEVICE).read_text().replace("Example Semi", "Authored override"))
    (authored,) = devices_of(model, combined / "B").values()
    assert authored.manufacturer == "Authored override"
    (combined / "B/devices").mkdir()
    (combined / "B/devices/override.toml").write_text(
        source.read_text().replace("Authored override", "Closest authored override")
    )
    (closest,) = devices_of(model, combined / "B").values()
    assert closest.manufacturer == "Closest authored override"
    declared = replace(original, manufacturer="Design override")
    assert devices_of(model, combined / "B", {declared.id: declared}) == {declared.id: declared}


@pytest.mark.parametrize("authored", (False, True))
def test_check_reports_ambiguous_vendored_device_facts(
    monkeypatch: pytest.MonkeyPatch, combined: Path, authored: bool
) -> None:
    assert run(monkeypatch, combined, "build", "design.py", "--out", "B", "--confirm")[0] == 0
    folder = (combined / DEVICE).parent
    if authored:
        (combined / "devices").mkdir()
        shutil.copy(combined / DEVICE, combined / "devices/override.toml")
    shutil.copytree(folder, folder.with_name("Copy"))
    code, env, error, _ = run(monkeypatch, combined, "check", "B", "--stages", "circuit.rules")
    assert code == 5, (env.get("issues"), error)
    assert any(issue["code"] == "library.item-conflict" for issue in env["issues"])
    model = canonical.load_dir(combined / "B/.fenolite")
    facts = devices_of(model, combined / "B")
    assert set(facts) == ({"FenoliteDevices:Demo900"} if authored else set())


def test_private_device_copy_preserves_rejected_links(combined: Path, tmp_path: Path) -> None:
    from fenolite.catalog.vendored import load_vendored
    from fenolite.core.errors import FormatError
    from fenolite.testing._devices import copy_device_context

    source = combined / DEVICE
    target = combined / "authored-record.toml"
    source.rename(target)
    try:
        source.symlink_to(target)
    except OSError:
        pytest.skip("symlinks are unavailable")
    private = tmp_path / "private"
    copy_device_context(combined, private)
    assert (private / DEVICE).is_symlink()
    with pytest.raises(FormatError, match="symlink or path outside vendored library"):
        load_vendored(private)
