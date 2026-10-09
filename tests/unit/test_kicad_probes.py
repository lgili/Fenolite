# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The probe results file: write, compare and missing-file modes with a fake probe (capability
kicad-oracle, "Probe results per kicad-cli version"; change c0017). No ``kicad-cli`` is run.

What the first three tests are for: ``_probes`` imports every probe registration of the oracle, so a fake
test module that imports it must find every helper folder of ``tests/kicad``; the tests then prove that
``verify`` writes the results file, compares with it and names a drift. The folders are derived
(``helper_folders``), and ``test_helper_folders_are_those_of_the_oracle`` keeps them equal to the list of
``tests/kicad/conftest.py``. The last tests prove, without docker, that the oracle's runner follows the
``docker:<image>`` form of ``FENOLITE_KICAD_CLI``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parents[1]


def helper_folders() -> list[str]:
    """Where the oracle's helper modules live: ``tests/kicad``, each of its folders that holds a helper
    module (``_<name>.py``: a bench, a case table, a probe registration), and ``tests``. Derived, so a new
    folder of ``tests/kicad`` needs no edit here; ``tests/kicad/conftest.py`` puts the same folders on the
    path of the oracle run."""
    root = TESTS / "kicad"
    folders = sorted(p for p in root.iterdir() if p.is_dir() and any(p.glob("_*.py")))
    return [str(root), *(str(p) for p in folders), str(TESTS)]


FAKE = """
import sys
sys.path[:0] = {paths!r}
from pathlib import Path
import _probes

FOLDER = Path({folder!r})


def test_fake(monkeypatch):
    probes = {{
        "fake-probe": _probes.Probe(lambda: "load", (10,)),
        "nine-only": _probes.Probe(lambda: "reject", (9,)),
    }}
    monkeypatch.setattr(_probes, "PROBES", probes)
    _probes.run.cache_clear()
    found = _probes.outcomes(10)
    _probes.run.cache_clear()
    assert found == {{"fake-probe": "load"}}
    _probes.verify("1.2.3", found, FOLDER)
"""


@pytest.fixture
def fake(pytester: pytest.Pytester, tmp_path: Path) -> Path:
    folder = tmp_path / "probes"
    source = FAKE.format(paths=helper_folders(), folder=str(folder))
    pytester.makepyfile(test_fake=source)
    return folder


def test_missing_results_file(pytester: pytest.Pytester, fake: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FENOLITE_PROBES_WRITE", raising=False)
    result = pytester.runpytest("-p", "no:cacheprovider")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*no probe results for kicad-cli 1.2.3*FENOLITE_PROBES_WRITE=1*"])


def test_results_written_then_compared(
    pytester: pytest.Pytester, fake: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FENOLITE_PROBES_WRITE", "1")
    pytester.runpytest("-p", "no:cacheprovider").assert_outcomes(passed=1)
    data = json.loads((fake / "1.2.3.json").read_text(encoding="utf-8"))
    assert data == {"version": "1.2.3", "probes": {"fake-probe": "load"}}
    monkeypatch.delenv("FENOLITE_PROBES_WRITE")
    pytester.runpytest("-p", "no:cacheprovider").assert_outcomes(passed=1)


def test_drift_detected(pytester: pytest.Pytester, fake: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FENOLITE_PROBES_WRITE", raising=False)
    fake.mkdir(parents=True)
    (fake / "1.2.3.json").write_text(json.dumps({"version": "1.2.3", "probes": {"fake-probe": "reject"}}))
    result = pytester.runpytest("-p", "no:cacheprovider")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*fake-probe: recorded 'reject', now 'load'*"])


# -- the library table probes (c0021): the outcome rule and the registered ids, without kicad-cli


def _kicad_paths() -> None:
    import sys

    root = TESTS / "kicad"
    subfolders = sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith("_"))
    for folder in (str(root), *(str(p) for p in subfolders)):
        if folder not in sys.path:
            sys.path.insert(0, folder)


def _report(issues: int, mismatches: int, other: int = 0):  # type: ignore[no-untyped-def]
    from fenolite.backends.base import DrcReport, DrcViolation

    violations = (
        *(DrcViolation("lib_footprint_issues", "d", "warning") for _ in range(issues)),
        *(DrcViolation("lib_footprint_mismatch", "d", "warning") for _ in range(mismatches)),
        *(DrcViolation("clearance", "d", "error") for _ in range(other)),
    )
    return DrcReport("b.kicad_pcb", "", "10.0.6", "mm", violations=violations)


@pytest.mark.parametrize(
    ("issues", "mismatches", "wanted"),
    [(0, 1, "absent"), (1, 0, "present"), (2, 0, "present"), (0, 0, "different"), (1, 1, "different"),
     (0, 2, "different")],
)  # fmt: skip
def test_libtable_outcome_rule(issues: int, mismatches: int, wanted: str) -> None:
    _kicad_paths()
    import _libtables

    assert _libtables.outcome(_report(issues, mismatches, other=3)) == wanted
    assert _libtables.outcome(None) == "reject" and _libtables.outcome(None, timed_out=True) == "timeout"


def test_libtable_probes_are_registered() -> None:
    _kicad_paths()
    import _libtables
    import _probes

    ids = [_libtables.probe_id(layout) for layout in _libtables.LAYOUTS]
    assert len(ids) == 13 and all(i.startswith("pcb-libtable-") for i in ids)
    for pid in ids:
        assert _probes.PROBES[pid].majors == (9, 10), pid
    assert "pcb-libdrc-missing-table" in _probes.PROBES  # the guard of every library table probe


def test_libtable_rows_follow_the_major() -> None:
    _kicad_paths()
    import _libtables

    ten = _libtables.table(
        _libtables.row("Sub", "${KIPRJMOD}/sub/fp-lib-table", major=10, kind="Table"), major=10
    )
    assert "(version 7)" in ten and '(type "Table")' in ten and '(name "Sub")' in ten
    nine = _libtables.table(_libtables.row("Mini", "Mini_v9.pretty", major=9), major=9)
    assert "(version" not in nine and "(name Mini)(type KiCad)(uri Mini_v9.pretty)" in nine


def test_helper_folders_are_those_of_the_oracle() -> None:
    """Every folder that ``tests/kicad/conftest.py`` puts on the path is derived here, so the fake module
    imports ``_probes`` as the oracle run does."""
    text = (TESTS / "kicad" / "conftest.py").read_text(encoding="utf-8")
    listed = {str(TESTS / "kicad" / name) for name in re.findall(r'HERE / "([a-z_]+)"', text)}
    derived = set(helper_folders())
    assert listed and listed - derived <= {
        str(p) for p in (TESTS / "kicad").iterdir() if p.is_dir() and not any(p.glob("_*.py"))
    }
    missing = {p for p in derived if p.startswith(str(TESTS / "kicad") + "/")} - listed
    assert not missing, f"tests/kicad/conftest.py does not list {sorted(missing)}"


def test_runner_follows_the_docker_form(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """``FENOLITE_KICAD_CLI=docker:<image>`` gives the oracle the image runner, and the command line it
    would build runs ``kicad-cli`` in that image on the copied folder. Docker is not run."""
    _kicad_paths()
    import _probes
    import _resources

    from fenolite.backends.kicad.cli import DockerCli, KicadCli

    image = "kicad/kicad:9.0.9@sha256:" + "0" * 64
    monkeypatch.setenv("FENOLITE_KICAD_CLI", f"docker:{image}")
    assert _resources.kicad_cli() == f"docker:{image}"
    _probes.runner.cache_clear()
    try:
        found = _probes.runner()
        assert isinstance(found, DockerCli) and found.image == image and found.timeout == 600
        command = found._command(["pcb", "drc", "board.kicad_pcb"], tmp_path)  # pyright: ignore[reportPrivateUsage]
        assert command[:2] == ["docker", "run"] and f"{tmp_path}:/w" in command
        assert command[command.index(image) :] == [image, "kicad-cli", "pcb", "drc", "board.kicad_pcb"]
        binary = tmp_path / "kicad-cli"
        binary.write_text("", encoding="utf-8")
        monkeypatch.setenv("FENOLITE_KICAD_CLI", str(binary))
        _probes.runner.cache_clear()
        plain = _probes.runner()
        assert type(plain) is KicadCli and plain.path == binary
    finally:
        _probes.runner.cache_clear()


def test_version_of_the_docker_form_without_docker(monkeypatch: pytest.MonkeyPatch) -> None:
    """The version helper of the markers asks the image runner for the docker form, and gives ``None``
    when the runner fails, as for a binary that cannot be run."""
    import _resources

    from fenolite.backends.kicad import cli as cli_module

    asked: list[str] = []

    class Fake:
        def __init__(self, text: str | None) -> None:
            self.text = text

        def version(self) -> str:
            if self.text is None:
                raise cli_module.KicadCliError("no docker", cli_module.CliRun("exit", 125, "", "", {}))
            return self.text

    def fake_cli_for(path: Path, *, timeout: float = 120) -> Fake:
        asked.append(str(path))
        return Fake("9.0.9" if "good" in str(path) else None)

    monkeypatch.setattr(cli_module, "cli_for", fake_cli_for)
    _resources._version_of.cache_clear()  # pyright: ignore[reportPrivateUsage]
    try:
        assert _resources._version_of("docker:good") == (9, 0, 9)  # pyright: ignore[reportPrivateUsage]
        assert _resources._version_of("docker:bad") is None  # pyright: ignore[reportPrivateUsage]
        assert asked == ["docker:good", "docker:bad"]
    finally:
        _resources._version_of.cache_clear()  # pyright: ignore[reportPrivateUsage]
