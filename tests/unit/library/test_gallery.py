# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite library gallery`` (capability fenolite-library, "Gallery with attribution", change c0279;
"Designed gallery pages", "Item images drawn by Fenolite" and "Image placeholders", change c0405;
"Authored and third-party attribution" and "Contradictory provenance fails the gallery", change c0418)."""

from __future__ import annotations

import io
import json
import re
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any

import pytest

from fenolite.cli import main as cli_main
from fenolite.library.gallery import attribution_line

BOARD = "boards/cern-ohl-s/demo-src/blink"
SVG = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="10" height="10"/></svg>\n'


def _cli(monkeypatch: pytest.MonkeyPatch, cwd: Path, *args: str) -> tuple[int, dict[str, Any]]:
    monkeypatch.chdir(cwd)
    out = io.StringIO()
    with redirect_stdout(out), redirect_stderr(io.StringIO()):
        code = cli_main.main([*args, "--json"])
    return code, json.loads(out.getvalue() or "{}")


def _release(monkeypatch: pytest.MonkeyPatch, demo: Path) -> None:
    code, _ = _cli(
        monkeypatch,
        demo.parent,
        "library",
        "release",
        str(demo),
        "--version",
        "1.0.0",
        "--out",
        "dist",
        "--confirm",
    )
    assert code == 0


def _renders(demo: Path, *, board: bool = True, block: bool = True) -> Path:
    """A ``--renders`` folder with the board's views and the block's schematic (authored stand-ins)."""
    renders = demo.parent / "renders"
    if board:
        (renders / "boards/demo-src/blink").mkdir(parents=True)
        for name in ("top.svg", "bottom.svg"):
            (renders / "boards/demo-src/blink" / name).write_bytes(SVG)
    if block:
        (renders / "blocks/Demo/buck").mkdir(parents=True)
        (renders / "blocks/Demo/buck/schematic.svg").write_bytes(SVG)
    renders.mkdir(exist_ok=True)
    return renders


def _site(
    monkeypatch: pytest.MonkeyPatch, demo: Path, *extra: str, mode: str = "--confirm"
) -> dict[str, Any]:
    _release(monkeypatch, demo)
    code, envelope = _cli(
        monkeypatch,
        demo.parent,
        "library",
        "gallery",
        str(demo),
        "--release",
        "dist",
        "--out",
        "site",
        *extra,
        mode,
    )
    assert code == 0, envelope
    return envelope


def _read(demo: Path, page: str) -> str:
    return (demo.parent / "site" / page).read_text(encoding="utf-8")


def test_card_attribution(monkeypatch: pytest.MonkeyPatch, demo: Path) -> None:
    """Scenario "Card attribution"."""
    envelope = _site(monkeypatch, demo, mode="--dry-run")
    assert not (demo.parent / "site").exists()
    assert "site/boards/demo-src/blink/index.html" in [row["path"] for row in envelope["result"]["plan"]]
    envelope = _site(monkeypatch, demo, "--renders", str(_renders(demo)))
    page = _read(demo, "boards/demo-src/blink/index.html")
    assert (
        "Converted from the open-source design Blink demo board by Demo Board Authors "
        f"(https://example.org/demo-src/tree/{'1' * 40}/blink), licence CERN-OHL-S-2.0. "
        "Rendered by Fenolite"
    ) in page
    assert "Not endorsed by the authors." in page and "pass-with-accepted" in page
    assert (
        "fenolite get board demo-src/blink --release 1.0.0 --accept-licence CERN-OHL-S-2.0 --dry-run" in page
    )
    assert 'src="top.svg"' in page and "tree/v1.0.0/boards/cern-ohl-s/demo-src/blink" in page
    device = _read(demo, "devices/Demo/EXB/index.html")
    assert "Authored for fenolite-library" in device and "Not endorsed" not in device
    assert envelope["result"]["hidden"] == []


SEEDED = "footprints/cc-by-sa/Demo/SA_PAD"


def test_authored_and_third_party_attribution(monkeypatch: pytest.MonkeyPatch, demo: Path) -> None:
    """Scenario "Authored and third-party attribution": the seeded CC-BY-SA-4.0 footprint (authored for the
    tests, recorded as seeded from example.org) names its upstream; only the authored device says
    "Authored for fenolite-library"."""
    _site(monkeypatch, demo, "--renders", str(_renders(demo)))
    device = _read(demo, "devices/Demo/EXB/index.html")
    assert "Authored for fenolite-library, licence CC0-1.0." in device
    footprint = _read(demo, "footprints/Demo/SA_PAD/index.html")
    line = (
        "Derived from Demo Pad Authors (https://example.org/demo-pads) at commit 000000000000, licence "
        "CC-BY-SA-4.0; converted to Fenolite&#x27;s formats, changes in its PROVENANCE.json. "
        "Rendered by Fenolite"
    )
    assert line in footprint and "Not endorsed by the authors." in footprint
    assert (
        '<a href="https://example.org/demo-pads">example.org/demo-pads</a> at <code>000000000000</code>'
        in footprint
    )
    assert "Authored for fenolite-library" not in footprint
    index = _read(demo, "index.html")
    card = index.split('href="footprints/Demo/SA_PAD/index.html"', 1)[1].split("</li>", 1)[0]
    assert "Derived from Demo Pad Authors" in card and "Authored for" not in card


@pytest.mark.parametrize(
    ("change", "field"),
    [
        ({"spdx": "CC0-1.0"}, "spdx 'CC0-1.0' and the release index spdx 'CC-BY-SA-4.0' differ"),
        ({"upstream": None}, "upstream is missing for a seeded item"),
        ({"origin": None}, "origin is None"),
        ({"authors": []}, "authors is empty for a seeded item"),
    ],
)
def test_contradictory_provenance_fails_the_gallery(
    monkeypatch: pytest.MonkeyPatch, demo: Path, change: dict[str, Any], field: str
) -> None:
    """Scenario "Contradictory provenance fails the gallery": no fallback to "Authored" or CC0, no write."""
    _release(monkeypatch, demo)
    path = demo / SEEDED / "PROVENANCE.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record.update(change)
    path.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    code, envelope = _cli(
        monkeypatch,
        demo.parent,
        "library",
        "gallery",
        str(demo),
        "--release",
        "dist",
        "--out",
        "site",
        "--confirm",
    )
    assert code == 5 and envelope["result"]["cards"] == []
    issues = [i for i in envelope["issues"] if i["code"] == "library.provenance-invalid"]
    assert issues and all(i["severity"] == "error" and i["where"] == SEEDED for i in issues)
    assert any(
        i["message"].startswith("Demo:SA_PAD: PROVENANCE.json") and field in i["message"] for i in issues
    )
    assert envelope["result"]["provenance"] == [i["message"] for i in issues]
    assert not (demo.parent / "site").exists()


def test_attribution_line_never_falls_back() -> None:
    """A caller that skips the check still cannot print "Authored" for a third-party record."""
    row = {"id": "X:Y", "spdx": "CC-BY-SA-4.0", "title": "Y"}
    with pytest.raises(ValueError, match="upstream is missing"):
        attribution_line(row, {"origin": "seeded", "spdx": "CC-BY-SA-4.0", "authors": ["A"]}, "0.0")
    with pytest.raises(ValueError, match="origin is 'vendor'"):
        attribution_line(row, {"origin": "vendor", "spdx": "CC-BY-SA-4.0"}, "0.0")


def test_restricted_marks_hidden(monkeypatch: pytest.MonkeyPatch, demo: Path) -> None:
    """Scenario "Restricted marks hidden"."""
    path = demo / BOARD / "PROVENANCE.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["trademarks"] = {"marks": ["Demo logo"], "restricted": True, "note": "logo on the silkscreen"}
    path.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    envelope = _site(monkeypatch, demo, "--renders", str(_renders(demo)))
    assert not any("blink" in name for name in envelope["result"]["cards"])
    assert envelope["result"]["hidden"] == ["demo-src/blink"]
    assert not (demo.parent / "site/boards").exists()
    assert "blink" not in _read(demo, "index.html").lower()


def test_index_page_structure(monkeypatch: pytest.MonkeyPatch, demo: Path) -> None:
    """Scenario "Index page structure"."""
    _site(monkeypatch, demo, "--renders", str(_renders(demo)))
    page = _read(demo, "index.html")
    cards = re.findall(r'<li class="card" data-kind="([a-z]+)" data-licence="([^"]+)"', page)
    assert sorted(cards) == sorted(
        [
            ("symbol", "CC0-1.0"),
            ("footprint", "CC-BY-SA-4.0"),
            ("footprint", "CC0-1.0"),
            ("device", "CC0-1.0"),
            ("block", "Apache-2.0"),
            ("board", "CERN-OHL-S-2.0"),
        ]
    )
    assert page.count('<div class="thumb') == 6 and page.count("<img ") >= 6
    assert '<input id="q" type="search"' in page and '<select id="licence"' in page
    for kind in ("symbols", "footprints", "devices", "blocks", "boards"):
        assert f'aria-pressed="false">{kind}</button>' in page
    assert '<option value="CERN-OHL-S-2.0">' in page and 'class="theme"' in page
    assert 'href="bench.html"' in page and 'href="assets/site.css"' in page
    assert "prefers-color-scheme:dark" in _read(demo, "assets/site.css")
    for name in ("index.html", "bench.html", "devices/Demo/EXB/index.html", "assets/site.css"):
        text = _read(demo, name)
        # Nothing is loaded from another origin: links to sources are anchors, never src or stylesheets.
        assert not re.search(r'(src|srcset)="(https?:)?//', text) and "@import" not in text
        assert not re.search(r'<link[^>]+href="(https?:)?//', text) and "url(http" not in text


def test_item_page_structure(monkeypatch: pytest.MonkeyPatch, demo: Path) -> None:
    """Scenario "Item page structure"."""
    _site(monkeypatch, demo)
    page = _read(demo, "footprints/Demo/SOT/index.html")
    assert '<img src="footprint.svg"' in page
    assert re.search(r'<th scope="row">Pads</th><td>2</td>', page)
    assert '<code id="get-command">fenolite get footprint Demo:SOT --release 1.0.0 --dry-run</code>' in page
    assert 'data-copy="get-command"' in page and '<th scope="row">Proof</th>' in page
    blob = "https://github.com/lgili/fenolite-library/blob/v1.0.0/footprints/cc0/Demo/SOT"
    assert f'href="{blob}/LICENSE"' in page and f'href="{blob}/NOTICE"' in page
    symbol = _read(demo, "symbols/Demo/EXB/index.html")
    assert "<th>Pin</th><th>Name</th><th>Type</th>" in symbol and "<td>A</td>" in symbol


def test_images_for_each_kind(monkeypatch: pytest.MonkeyPatch, demo: Path) -> None:
    """Scenario "Images for each kind"."""
    envelope = _site(monkeypatch, demo, "--renders", str(_renders(demo)))
    site = demo.parent / "site"
    for folder, names in (
        ("symbols/Demo/EXB", ("symbol.svg",)),
        ("footprints/Demo/SOT", ("footprint.svg",)),
        ("devices/Demo/EXB", ("symbol.svg", "footprint.svg")),
        ("boards/demo-src/blink", ("top.svg", "bottom.svg")),
        ("blocks/Demo/buck", ("schematic.svg",)),
    ):
        page = (site / folder / "index.html").read_text(encoding="utf-8")
        for name in names:
            assert (site / folder / name).read_bytes().startswith(b"<svg"), (folder, name)
            assert f'<img src="{name}"' in page, (folder, name)
        assert 'class="placeholder"' not in page, folder
    land = (site / "footprints/Demo/SOT/footprint.svg").read_text(encoding="utf-8")
    assert 'class="pin1"' in land and ">1</text>" in land and 'class="copper"' in land
    assert "<title>Symbol Demo:EXB</title>" in (site / "symbols/Demo/EXB/symbol.svg").read_text(
        encoding="utf-8"
    )
    assert envelope["result"]["placeholders"] == []


def test_deterministic_site(monkeypatch: pytest.MonkeyPatch, demo: Path) -> None:
    """Scenario "Deterministic site"."""
    renders = str(_renders(demo))
    first = _site(monkeypatch, demo, "--renders", renders, mode="--dry-run")["result"]["plan"]
    second = _site(monkeypatch, demo, "--renders", renders, mode="--dry-run")["result"]["plan"]
    assert first == second and any(row["path"].endswith("footprint.svg") for row in first)
    _site(monkeypatch, demo, "--renders", renders)
    once = {p: p.read_bytes() for p in sorted((demo.parent / "site").rglob("*")) if p.is_file()}
    _site(monkeypatch, demo, "--renders", renders, "--no-backup")
    assert once == {p: p.read_bytes() for p in sorted((demo.parent / "site").rglob("*")) if p.is_file()}


def test_missing_board_render(monkeypatch: pytest.MonkeyPatch, demo: Path) -> None:
    """Scenario "Missing board render"."""
    envelope = _site(monkeypatch, demo)
    placeholders = {row["id"]: row["reason"] for row in envelope["result"]["placeholders"]}
    assert placeholders["demo-src/blink"] == "the board render is missing: no render was supplied"
    assert placeholders["Demo:buck"] == "the block schematic is missing: no render was supplied"
    page = _read(demo, "boards/demo-src/blink/index.html")
    assert 'class="placeholder"' in page and "no render was supplied" in page and "<img " not in page


def test_failure_reason_and_broken_definition(monkeypatch: pytest.MonkeyPatch, demo: Path) -> None:
    """A reason from ``failures.json`` and an unreadable footprint both reach the page and the result."""
    _release(monkeypatch, demo)
    renders = _renders(demo, board=False)
    (renders / "failures.json").write_text(
        json.dumps({"demo-src/blink": "kicad-cli exited 3"}), encoding="utf-8"
    )
    (demo / "footprints/cc0/Demo/SOT/SOT.toml").write_text('schema = "fenolite.package.v0"\n[[pad]\n')
    code, envelope = _cli(
        monkeypatch, demo.parent, "library", "gallery", str(demo), "--release", "dist", "--out", "site",
        "--renders", str(renders), "--confirm",
    )  # fmt: skip
    assert code == 0, envelope
    placeholders = {(row["kind"], row["id"]): row["reason"] for row in envelope["result"]["placeholders"]}
    assert placeholders[("board", "demo-src/blink")] == "the board render is missing: kicad-cli exited 3"
    assert placeholders[("footprint", "Demo:SOT")].startswith(
        "Fenolite could not draw this footprint (SOT.toml: "
    )
    assert placeholders[("device", "Demo:EXB")].startswith("Fenolite could not draw this footprint")
    assert ("symbol", "Demo:EXB") not in placeholders
    assert "kicad-cli exited 3" in _read(demo, "boards/demo-src/blink/index.html")
    device = _read(demo, "devices/Demo/EXB/index.html")
    assert '<img src="symbol.svg"' in device and "Fenolite could not draw this footprint" in device


SHEET = """(kicad_sch (version 20250114) (generator "authored") (uuid "00000000-0000-4000-8000-000000000301")
\t(paper "A4")
\t(wire (pts (xy 25.4 25.4) (xy 50.8 25.4)) (stroke (width 0) (type default))
\t\t(uuid "00000000-0000-4000-8000-000000000302"))
\t(label "OUT" (at 50.8 25.4 0) (effects (font (size 1.27 1.27)) (justify left bottom))
\t\t(uuid "00000000-0000-4000-8000-000000000303"))
)
"""


def test_block_sheet_drawn_by_fenolite(monkeypatch: pytest.MonkeyPatch, demo: Path) -> None:
    """Scenario "Block sheet drawn by Fenolite"."""
    renders = _renders(demo, block=False)
    sheet = renders / "blocks/Demo/buck/schematic.kicad_sch"
    sheet.parent.mkdir(parents=True)
    sheet.write_text(SHEET, encoding="utf-8")
    envelope = _site(monkeypatch, demo, "--renders", str(renders))
    assert envelope["result"]["placeholders"] == []
    drawn = (demo.parent / "site/blocks/Demo/buck/schematic.svg").read_text(encoding="utf-8")
    assert "<title>Block Demo:buck, usage schematic</title>" in drawn and ">OUT</text>" in drawn
    assert '<img src="schematic.svg"' in _read(demo, "blocks/Demo/buck/index.html")
    sheet.write_text("(kicad_sch (version 20250114)\n", encoding="utf-8")
    envelope = _site(monkeypatch, demo, "--renders", str(renders), "--no-backup")
    placeholders = {row["id"]: row["reason"] for row in envelope["result"]["placeholders"]}
    assert placeholders["Demo:buck"].startswith("Fenolite could not draw the block schematic (")
    assert "Fenolite could not draw the block schematic" in _read(demo, "blocks/Demo/buck/index.html")
