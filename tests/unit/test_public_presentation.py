# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Public entry points and real release media (change c0208). No browser or CAD installation needed."""

from __future__ import annotations

import re
import struct
import tomllib
from pathlib import Path
from urllib.parse import unquote, urlparse

import pytest

ROOT = Path(__file__).resolve().parents[2]
PAGES = (
    "README.md",
    "docs/index.md",
    "docs/quickstart.md",
    "docs/launch/README.md",
    "docs/launch/v0.5.md",
    "docs/launch/validation.md",
    "docs/media/README.md",
)


def local_target(page: Path, url: str) -> Path | None:
    parsed = urlparse(url)
    if parsed.netloc == "github.com" and parsed.path.startswith("/lgili/Fenolite/blob/main/"):
        return ROOT / unquote(parsed.path.removeprefix("/lgili/Fenolite/blob/main/"))
    if parsed.netloc == "github.com" and parsed.path.startswith("/lgili/Fenolite/tree/main/"):
        return ROOT / unquote(parsed.path.removeprefix("/lgili/Fenolite/tree/main/"))
    if parsed.netloc == "raw.githubusercontent.com" and parsed.path.startswith("/lgili/Fenolite/main/"):
        return ROOT / unquote(parsed.path.removeprefix("/lgili/Fenolite/main/"))
    if not parsed.scheme and not parsed.netloc and parsed.path:
        return page.parent / unquote(parsed.path)
    return None


@pytest.mark.parametrize("relative", PAGES)
def test_local_links_and_image_alternative_text(relative: str) -> None:
    page = ROOT / relative
    text = page.read_text(encoding="utf-8")
    for url in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
        target = local_target(page, url)
        if target is not None:
            assert target.exists(), f"{relative}: broken link {url}"
    for alt in re.findall(r"!\[([^\]]*)\]\(", text):
        assert len(alt.strip()) >= 10, f"{relative}: describe the image"


def test_release_claims_and_entry_points() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "After 0.5" not in readme
    assert "second backend for another" not in readme
    assert readme.index("## Install") < readme.index("## Three ways")
    assert "**Conversions and Altium writes are experimental in 0.6.**" in readme
    assert "Draftsman writing and" in readme and "remain gated" in readme
    for page in ("docs/quickstart.md", "docs/launch/v0.5.md"):
        text = (ROOT / page).read_text(encoding="utf-8")
        assert "Python 3.11+" in text
        assert "fenolite init blink --confirm --json" in text
        assert "fenolite build blink/design.py --out blink/build --confirm --json" in text
        assert "fenolite view blink/build --serve" in text
    launch = (ROOT / "docs/launch/README.md").read_text(encoding="utf-8")
    assert "### English" in launch and "### Português" in launch
    assert "Preserve the tag, commit and published artifacts" in launch


@pytest.mark.parametrize("name", ("hero.png", "board.png", "schematic.png", "social-card.png"))
def test_media_dimensions(name: str) -> None:
    data = (ROOT / "docs/media" / name).read_bytes()
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    assert struct.unpack(">II", data[16:24]) == ((1280, 640) if name == "social-card.png" else (1280, 800))
    if name == "social-card.png":
        assert len(data) < 1_000_000


def test_demo_and_capture_provenance() -> None:
    data = (ROOT / "docs/media/viewer-demo.gif").read_bytes()
    assert data[:6] in (b"GIF87a", b"GIF89a")
    assert struct.unpack("<HH", data[6:10]) == (960, 600)
    assert b"NETSCAPE2.0" in data
    assert len(data) < 5_000_000
    provenance = (ROOT / "docs/media/README.md").read_text(encoding="utf-8")
    for source in ("examples/blink_routed/design.py", "tests/data/altium/blink/blink.PrjPcb"):
        assert source in provenance and (ROOT / source).is_file()
    assert "zero page errors" in provenance
    assert "prepare.py" in provenance and "capture.cjs" in provenance


def test_package_describes_shipped_workflows() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert "later Altium" not in project["description"]
    assert "browser viewer" in project["description"]
    assert project["dependencies"] == []
    assert project["urls"]["Documentation"].endswith("/blob/main/docs/index.md")


# --- third-party material in public assets (capability public-presentation; change c0279) -------------

GALLERY = re.compile(
    r"!\[[^\]]*\]\((https?://(?:lgili\.github\.io/fenolite-library|github\.com/lgili/fenolite-library)[^)]*)\)"
)
ATTRIBUTION = ("licence", "Not endorsed by the authors")


def library_image_problems(text: str, page: str) -> list[str]:
    """Each image of the fenolite-library gallery on a public page needs its attribution line (title,
    authors, link, licence and "Not endorsed by the authors") in the same paragraph."""
    problems: list[str] = []
    for paragraph in re.split(r"\n\s*\n", text):
        for url in GALLERY.findall(paragraph):
            if not all(word in paragraph for word in ATTRIBUTION):
                problems.append(f"{page}: the gallery image {url} has no attribution line")
    return problems


def test_library_images_carry_their_attribution() -> None:
    for relative in PAGES:
        assert library_image_problems((ROOT / relative).read_text(encoding="utf-8"), relative) == []


def test_library_image_without_attribution() -> None:
    """Scenario "Image without attribution"."""
    image = (
        "![Top view of a converted demo board](https://lgili.github.io/fenolite-library/boards/x/y/top.svg)"
    )
    problems = library_image_problems(f"# Launch\n\n{image}\n", "docs/launch/x.md")
    assert problems and "top.svg" in problems[0]
    line = ("Converted from the open-source design Y by Z (https://example.org/y), licence CERN-OHL-S-2.0. "
            "Rendered by Fenolite 0.7.0. Not endorsed by the authors.")  # fmt: skip
    assert library_image_problems(f"{image}\n{line}\n", "docs/launch/x.md") == []
