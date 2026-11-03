# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Original CC0 font/anchor controls through the installed KiCad CLI process (c0326, S-0020).

This measures SVG text groups and source hashes, not a GUI save or native electrical round trip.
Every case records its actual tool version, command and artifact digests in pytest's temporary tree.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

import _drawn
import _drawn_fonts
import _kicad
import pytest
from _fidelity import snapshot

from fenolite.backends.kicad._fpmap import node
from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse
from fenolite.core.coords import Size
from fenolite.model.drawn import DrawnFont

pytestmark = pytest.mark.needs_kicad
SURFACES = ("field", "power", "local", "global", "hierarchical", "pin", "sheetname", "sheetfile")
MARKER = "AuthoredFontProbe"
NUMBER = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][-+]?\d+)?")


def _env(config: Path) -> dict[str, str]:
    env = _kicad.oracle_env(config)
    # wx's data directory is separate from KiCad configuration and private runtime/cache/state.
    for name, relative in (("XDG_CONFIG_HOME", "xdg-config"), ("XDG_DATA_HOME", "xdg-data")):
        folder = config.parent / relative
        folder.mkdir(parents=True, exist_ok=True)
        env[name] = str(folder)
    return env


def _replace(item: Node, old: Node, new: Node) -> Node:
    return item.with_children(tuple(new if child is old else child for child in item.children))


def _signature(data: bytes, marker: str) -> tuple[str, tuple[float, float, float, float]]:
    root = ET.fromstring(data)
    parents = {child: parent for parent in root.iter() for child in parent}
    matches = [item for item in root.iter() if item.tag.rsplit("}", 1)[-1] == "desc" and item.text == marker]
    if not matches:
        matches = [
            item
            for item in root.iter()
            if item.tag.rsplit("}", 1)[-1] == "desc" and marker in (item.text or "")
        ]
    assert matches, marker
    # Native output may plot the same field in several groups. Preserve every group and its
    # multiplicity/styles rather than selecting the first or deduplicating coincident glyphs.
    groups = [parents[match] for match in matches]
    rendered = []
    for group in groups:
        ancestry = []
        parent = group
        while parent in parents:
            ancestry.append(dict(parent.attrib))
            parent = parents[parent]
        rendered.append([ET.tostring(group, encoding="unicode"), ancestry])
    signature = json.dumps(rendered, sort_keys=True)
    points = []
    for group in groups:
        for item in group.iter():
            if item.tag.rsplit("}", 1)[-1] != "path":
                continue
            numbers = [float(value) for value in NUMBER.findall(item.attrib["d"])]
            assert len(numbers) % 2 == 0
            points.extend(zip(numbers[::2], numbers[1::2], strict=True))
    assert points, marker
    box = (
        min(p[0] for p in points),
        min(p[1] for p in points),
        max(p[0] for p in points),
        max(p[1] for p in points),
    )
    return signature, box


class Oracle:
    def __init__(self, folder: Path) -> None:
        self.folder = folder
        self.cli = _kicad.cli()
        version = subprocess.run(
            [self.cli, "--version"],
            env=_env(folder / "version-config"),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert version.returncode == 0, version.stderr
        self.version = version.stdout.strip()
        (folder / "version-receipt.json").write_text(
            json.dumps(
                {
                    "argv": [self.cli, "--version"],
                    "exit_code": version.returncode,
                    "stdout": version.stdout,
                    "stderr": version.stderr,
                },
                sort_keys=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        self.major = int(self.version.split(".")[0])
        assert self.major in (9, 10), self.version
        output = _drawn.build("full", self.major)
        assert output.files and not any(issue.severity == "error" for issue in output.issues), output.issues
        self.files = {name: data for name, data in output.files.items() if name.endswith(".kicad_sch")}
        self.name = _drawn.root_name(output)
        self.root = parse(self.files[self.name].decode())
        self.cache = {}
        print(f"drawn font SVG oracle: kicad-cli {self.version}")

    def sample(self, surface: str, angle: int, case: str, font: str | None, justify: str | None = None):
        key = f"{surface}-{angle}-{case}"
        if key in self.cache:
            return self.cache[key]
        folder = self.folder / key
        project = folder / "project"
        project.mkdir(parents=True)
        for name, data in self.files.items():
            path = project / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        effects = node(
            "effects",
            *([parse(font)] if font is not None else []),
            *(
                [node("justify", *(Atom.symbol(word) for word in justify.split()))]
                if justify is not None
                else []
            ),
        )
        root, marker = self._input(surface, angle, effects)
        source = project / self.name
        source.write_text(dumps(root), encoding="utf-8")
        before = snapshot(project)
        argv = [
            self.cli,
            "sch",
            "export",
            "svg",
            "--black-and-white",
            "--exclude-drawing-sheet",
            "-o",
            str(folder / "svg"),
            str(source),
        ]
        exported = subprocess.run(
            argv,
            env=_env(folder / "config"),
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert exported.returncode == 0, (argv, exported.stdout, exported.stderr)
        assert snapshot(project) == before
        outputs = list((folder / "svg").glob("*.svg"))
        (svg,) = [path for path in outputs if path.stem == source.stem]
        data = svg.read_bytes()
        signature, box = _signature(data, marker)
        receipt = {
            "tool": self.cli,
            "version": self.version,
            "argv": argv,
            "exit_code": exported.returncode,
            "stderr": exported.stderr,
            "source_sha256": before,
            "source_unchanged": True,
            "svg_sha256": hashlib.sha256(data).hexdigest(),
            "signature_sha256": hashlib.sha256(signature.encode()).hexdigest(),
            "box_mm": box,
        }
        (folder / "receipt.json").write_text(
            json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
        result = signature, box, svg
        self.cache[key] = result
        return result

    def _input(self, surface: str, angle: int, effects: Node) -> tuple[Node, str]:
        if surface in {"field", "power"}:
            symbol = next(
                item
                for item in self.root.nodes("symbol")
                if item.find("lib_id") is not None
                and any(
                    prop.atoms()[0].value == "Reference"
                    and prop.atoms()[1].value.startswith("#") == (surface == "power")
                    for prop in item.nodes("property")
                )
            )
            prop = next(prop for prop in symbol.nodes("property") if prop.atoms()[0].value == "Value")
            old = prop.find("effects")
            assert old is not None
            marked = prop.with_children((prop.children[0], Atom.string(MARKER), *prop.children[2:]))
            changed = _replace(symbol, prop, _replace(marked, old, effects))
            return _replace(self.root, symbol, changed), MARKER
        if surface in {"local", "global", "hierarchical"}:
            head = "label" if surface == "local" else surface + "_label"
            item = node(
                head,
                Atom.string(MARKER),
                *([] if surface == "local" else [node("shape", Atom.symbol("input"))]),
                node("at", Atom.from_nm(100_000_000), Atom.from_nm(100_000_000), Atom.integer(angle)),
                effects,
                node(
                    "uuid",
                    Atom.string(
                        str(
                            uuid.uuid5(uuid.NAMESPACE_URL, "https://example.invalid/fenolite-font/" + surface)
                        )
                    ),
                ),
            )
            return self.root.with_children((*self.root.children, item)), MARKER
        sheet = self.root.nodes("sheet")[0]
        if surface == "pin":
            pin = sheet.nodes("pin")[0]
            at, size = sheet.find("at"), sheet.find("size")
            assert at is not None and size is not None
            x, y = (atom.to_nm() for atom in at.atoms())
            width, height = (atom.to_nm() for atom in size.atoms())
            point = {
                0: (x + width, y + height // 2),
                90: (x + width // 2, y + height),
                180: (x, y + height // 2),
                270: (x + width // 2, y),
            }[angle]
            old = pin.find("effects")
            assert old is not None
            pin = _replace(pin, old, effects)
            changed = pin.with_children(
                tuple(
                    Atom.string(MARKER)
                    if i == 0
                    else node("at", Atom.from_nm(point[0]), Atom.from_nm(point[1]), Atom.integer(angle))
                    if isinstance(child, Node) and child.name == "at"
                    else child
                    for i, child in enumerate(pin.children)
                )
            )
            sheet = _replace(sheet, sheet.nodes("pin")[0], changed)
            return _replace(self.root, self.root.nodes("sheet")[0], sheet), MARKER
        key = "Sheetname" if surface == "sheetname" else "Sheetfile"
        prop = next(prop for prop in sheet.nodes("property") if prop.atoms()[0].value == key)
        old = prop.find("effects")
        assert old is not None
        changed = _replace(prop, old, effects)
        marker = prop.atoms()[1].value
        if surface == "sheetname":
            changed = changed.with_children((changed.children[0], Atom.string(MARKER), *changed.children[2:]))
            marker = MARKER
        else:
            marker = Path(marker).name  # Keep the actual linked filename; no alias or text override.
        sheet = _replace(sheet, prop, changed)
        return _replace(self.root, self.root.nodes("sheet")[0], sheet), marker


@pytest.fixture(scope="module")
def oracle(tmp_path_factory: pytest.TempPathFactory) -> Oracle:
    return Oracle(tmp_path_factory.mktemp("authored-native-fonts"))


@pytest.mark.parametrize("surface", SURFACES)
def test_native_asymmetric_axes_on_every_typed_surface(surface: str, oracle: Oracle) -> None:
    _, wide, _ = oracle.sample(surface, 0, "wide", "(font (size 1 2))")
    _, tall, _ = oracle.sample(surface, 0, "tall", "(font (size 2 1))")
    assert wide[2] - wide[0] == pytest.approx(2 * (tall[2] - tall[0]), abs=0.001)
    assert tall[3] - tall[1] == pytest.approx(2 * (wide[3] - wide[1]), abs=0.001)


@pytest.mark.parametrize("surface", ("local", "global", "hierarchical", "pin"))
@pytest.mark.parametrize("angle", (0, 90, 180, 270))
def test_native_missing_empty_and_explicit_anchors(surface: str, angle: int, oracle: Oracle) -> None:
    values = [
        oracle.sample(surface, angle, "justify-" + name, "(font (size 1.27 1.27))", justify)[0]
        for name, justify in (("missing", None), ("empty", ""), ("left", "left"), ("right", "right"))
    ]
    assert values[0] == values[1]
    assert len(set(values)) == 3


def test_native_flags_and_zero_thickness_have_proved_effective_defaults(oracle: Oracle) -> None:
    variants = {
        "default": "(font (size 1.27 1.27))",
        "font-empty": "(font)",
        "font-missing": None,
        "bold": "(font (size 1.27 1.27) bold)",
        "bold-yes": "(font (size 1.27 1.27) (bold yes))",
        "bold-no": "(font (size 1.27 1.27) (bold no))",
        "italic": "(font (size 1.27 1.27) italic)",
        "italic-yes": "(font (size 1.27 1.27) (italic yes))",
        "italic-no": "(font (size 1.27 1.27) (italic no))",
        "thickness-zero": "(font (size 1.27 1.27) (thickness 0))",
        "thickness-explicit": "(font (size 1.27 1.27) (thickness 0.15))",
    }
    values = {name: oracle.sample("field", 0, name, font)[0] for name, font in variants.items()}
    for name in ("font-empty", "font-missing", "bold-no", "italic-no", "thickness-zero"):
        assert values[name] == values["default"], name
    assert values["bold"] == values["bold-yes"] != values["default"]
    assert values["italic"] == values["italic-yes"] != values["default"]
    assert values["thickness-explicit"] != values["default"]


def _model_sample(oracle: Oracle, variant: str, font: DrawnFont):
    key = "model-" + variant
    if key in oracle.cache:
        return oracle.cache[key]
    folder = Path(tempfile.mkdtemp(prefix=f"{key}-", dir=oracle.folder))
    project = _drawn_fonts.styled_hierarchy(folder / "project", target=oracle.major, font=font)
    before = snapshot(project)
    # KiCad 10 can create project-local settings beside an exported drawing.
    # Run on a complete byte-identical copy, preserving every original input.
    exported_project = folder / "native-input"
    shutil.copytree(project, exported_project)
    assert snapshot(exported_project) == before
    source = exported_project / "drawn_full.kicad_sch"
    argv = [
        oracle.cli,
        "sch",
        "export",
        "svg",
        "--black-and-white",
        "--exclude-drawing-sheet",
        "-o",
        str(folder / "svg"),
        str(source),
    ]
    exported = subprocess.run(
        argv,
        env=_env(folder / "config"),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert exported.returncode == 0, (argv, exported.stdout, exported.stderr)
    assert snapshot(project) == before
    after = snapshot(exported_project)
    assert {name: after[name] for name in before} == before
    created = {name: digest for name, digest in after.items() if name not in before}
    assert set(created) <= {"drawn_full.kicad_prl"}
    svg = folder / "svg/drawn_full.svg"
    data = svg.read_bytes()
    signature, box = _signature(data, "MCU")
    receipt = {
        "method": (
            "actual DrawnFont lowering followed by CLI SVG on an exact copy; "
            "no GUI or named-font-installation claim"
        ),
        "version": oracle.version,
        "argv": argv,
        "exit_code": exported.returncode,
        "source_sha256": before,
        "source_unchanged": True,
        "native_created_files": created,
        "svg_sha256": hashlib.sha256(data).hexdigest(),
        "signature_sha256": hashlib.sha256(signature.encode()).hexdigest(),
        "box_mm": box,
    }
    (folder / "receipt.json").write_text(
        json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    result = signature, box, svg
    oracle.cache[key] = result
    return result


@pytest.mark.parametrize("variant", ("false-zero-defaults", "explicit-font"))
def test_actual_model_font_lowering_loads_without_source_changes(variant: str, oracle: Oracle) -> None:
    font = (
        DrawnFont(thickness=0, bold=False, italic=False)
        if variant == "false-zero-defaults"
        else DrawnFont(Size(750_000, 500_000), 150_000, True, True, "DejaVu Sans")
    )
    default = _model_sample(oracle, "baseline", DrawnFont(Size(1_270_000, 1_270_000)))[0]
    signature = _model_sample(oracle, variant, font)[0]
    assert (signature == default) == (variant == "false-zero-defaults")


def test_failed_model_export_can_retry_without_hiding_source_changes(oracle: Oracle, monkeypatch) -> None:
    font = DrawnFont(Size(1_270_000, 1_270_000))
    with monkeypatch.context() as patch:
        patch.setattr(
            subprocess,
            "run",
            lambda argv, **kwargs: subprocess.CompletedProcess(argv, 1, "", "authored failure"),
        )
        with pytest.raises(AssertionError, match="authored failure"):
            _model_sample(oracle, "retry-control", font)
    assert "model-retry-control" not in oracle.cache
    signature, _, svg = _model_sample(oracle, "retry-control", font)
    assert signature and svg.is_file()


@pytest.mark.parametrize(
    "variant,font",
    (
        ("stroke-thickness", DrawnFont(thickness=300_000)),
        ("stroke-bold", DrawnFont(bold=True)),
        ("stroke-italic", DrawnFont(italic=True)),
        ("stroke-combined", DrawnFont(thickness=100_000, bold=True, italic=True)),
    ),
)
def test_actual_authored_stroke_style_lowering_changes_native_output(
    variant: str, font: DrawnFont, oracle: Oracle
) -> None:
    baseline = _model_sample(oracle, "stroke-baseline", DrawnFont(Size(1_270_000, 1_270_000)))[0]
    changed = _model_sample(oracle, variant, font)[0]
    assert changed != baseline
