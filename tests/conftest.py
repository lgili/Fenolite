# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Shared pytest configuration: helper import path and skip rules for optional resources."""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))
# the plane bench of change c0107 lives beside the routing gates and is shared with the unit suites
if str(TESTS_DIR / "routing") not in sys.path:
    sys.path.insert(1, str(TESTS_DIR / "routing"))

from _resources import (  # noqa: E402  (imported after the sys.path setup above)
    CORPUS_HINT,
    FREEROUTING_HINT,
    LIBS_HINT,
    corpus_cache_dir,
    freerouting_jar,
    kicad_cli,
    kicad_cli_version,
    kicad_library_dirs,
    required_resources,
)

pytest_plugins = ["pytester"]

if sys.platform == "win32":
    # The test helpers write their fixtures with ``Path.write_text`` and the code under test reads bytes.
    # Windows would write CR LF where the fixtures mean LF, so a helper's text keeps its own line ends.
    _write_text = Path.write_text

    def _write_text_lf(self: Path, data: str, encoding: str | None = None, errors: str | None = None,
                       newline: str | None = "\n") -> int:  # fmt: skip
        return _write_text(self, data, encoding, errors, newline)

    Path.write_text = _write_text_lf  # type: ignore[method-assign]

WRITE_MODES = {
    "FENOLITE_PROBES_WRITE": "1",
    "FENOLITE_GOLDEN_WRITE": "1",
    "FENOLITE_CENSUS_OUT": None,
    "FENOLITE_CHECK_EVIDENCE": None,
}
"""Variables that make tests write tracked or shared files, and the value that turns each on (``None``:
any non-empty value). Such a run is serial: two workers would write the same file."""


def active_write_modes() -> list[str]:
    found: list[str] = []
    for name, needed in WRITE_MODES.items():
        value = os.environ.get(name, "")
        if value and needed in (None, value):
            found.append(name)
    return found


def pytest_sessionstart(session: pytest.Session) -> None:
    """Refuse a write mode in a parallel run (capability ci-baseline, "Parallel test runs")."""
    config = session.config
    if hasattr(config, "workerinput") or not getattr(config.option, "numprocesses", None):
        return
    modes = active_write_modes()
    if modes:
        raise pytest.UsageError(
            f"{', '.join(modes)} writes shared files and needs a serial run: drop -n (or pass -n 0)"
        )


def _missing(resource: str, message: str) -> None:
    """Skip, or fail when ``FENOLITE_REQUIRE`` lists the resource (required-resource mode)."""
    if resource in required_resources():
        pytest.fail(message, pytrace=False)
    pytest.skip(message)


def pytest_runtest_setup(item: pytest.Item) -> None:
    if item.get_closest_marker("needs_corpus"):
        cache = corpus_cache_dir()
        if not cache.is_dir() or not any(cache.iterdir()):
            _missing("corpus", CORPUS_HINT)
    if item.get_closest_marker("needs_libs") and not kicad_library_dirs():
        _missing("libs", LIBS_HINT)
    if item.get_closest_marker("needs_router"):
        checkout = Path(os.environ.get("FENOLITE_KRT", ""))
        interpreter = Path(os.environ.get("FENOLITE_KRT_PYTHON", ""))
        if not (checkout / "py_router" / "route.py").is_file() or not interpreter.is_file():
            _missing("router", "KiCadRoutingTools not found (set FENOLITE_KRT and FENOLITE_KRT_PYTHON)")
    if item.get_closest_marker("needs_kicad") and kicad_cli() is None:
        _missing("kicad", "kicad-cli not found (install KiCad or set FENOLITE_KICAD_CLI)")
    if item.get_closest_marker("needs_freerouting") and freerouting_jar() is None:
        _missing("freerouting", FREEROUTING_HINT)
    minimum = item.get_closest_marker("kicad_min_major")
    if minimum is not None:
        version = kicad_cli_version()
        needed = int(minimum.args[0])
        if version is not None and version[0] < needed:
            # An older major is present, not missing: required-resource mode never turns this into a failure.
            pytest.skip(f"needs kicad-cli {needed}.x; running {version[0]}.x")


@pytest.fixture(autouse=True, scope="session")
def _tools_folder_of_the_run(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    """No test reads the user's tools folder: ``FENOLITE_TOOLS_DIR`` names a folder of the run, which is
    created only by a test that installs something there (capability routing, "Tools folder"; c0078). A
    jar that ``fenolite fetch`` installed on this machine would otherwise make the router available.
    Session-scoped, so that it changes the order of no test's own fixtures."""
    name = "FENOLITE_TOOLS_DIR"
    before = os.environ.get(name)
    os.environ[name] = str(tmp_path_factory.getbasetemp() / "fenolite-tools")
    yield
    if before is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = before
