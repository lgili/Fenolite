# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The run record, the archive and the kit label (capabilities altium-verification, "Kit run record", and
verification-evidence, "Kit label rows"). The runs here are simulated: none is a run of a tool, and no
record of them is committed."""

from __future__ import annotations

import dataclasses
import io
import json
import zipfile
from pathlib import Path

import pytest
from _simulate import DATE, VERSION, simulate, simulated_judge

from fenolite.cli._kit import kit_sources
from fenolite.core.errors import FormatError
from fenolite.core.evidence import Level
from fenolite.core.io import sha256_bytes
from fenolite.verify import parse_level
from fenolite.verify.hypotheses import HypothesisRow
from fenolite.verify.kit import record
from fenolite.verify.kit.manifest import KitSources, SampleFiles, kit_files, load_kit, read_kit
from fenolite.verify.kit.results import KitVerdict, verify_results

ROOT = Path(__file__).resolve().parents[4]
USERS = "Users"


@pytest.fixture(scope="module")
def run(built_kit: Path, tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, KitVerdict]:
    """A simulated run whose form does not say synthetic: only for the form of the record."""
    import shutil

    folder = tmp_path_factory.mktemp("recorded") / "kit"
    shutil.copytree(built_kit, folder)
    simulate(folder, synthetic=False, script=True)
    return folder, verify_results(folder, judge=simulated_judge)


def _row(ident: str, level: str, result: str = "") -> HypothesisRow:
    return HypothesisRow(ident, "altium", "s", parse_level(level), level, "kit request", "c", result, DATE)


def test_record_of_a_run(run: tuple[Path, KitVerdict]) -> None:
    """Scenario "Record of a run": the record is sound, names the archive by digest and holds no path."""
    folder, verdict = run
    archive = record.archive_bytes(folder, verdict)
    made = record.run_record(verdict, archive=archive)
    assert record.record_problems(made) == []
    assert made["schema"] == record.RUN_SCHEMA and made["altium_version"] == VERSION
    assert made["archive"] == {
        "name": f"altium-kit-{made['run_id']}.zip",
        "sha256": sha256_bytes(archive),
        "size": len(archive),
    }
    assert made["run_id"] == f"{DATE}-{sha256_bytes(archive)[:8]}" and record.RUN_ID.fullmatch(made["run_id"])
    assert made["kit_sha256"] == verdict.kit.digest and made["script_sha256"] == verdict.kit.script_sha256
    steps = {step["id"]: step for step in made["steps"]}
    assert steps["K2.1"] == {
        "id": "K2.1",
        "kind": "file",
        "outcome": "pass",
        "scripted": True,
        "pending": [],
        "source": verdict.kit.samples["flat"],
    }
    assert steps["K1.8"]["kind"] == "form" and not steps["K1.8"]["scripted"]
    assert steps["K6.1"]["pending"] == []
    assert steps["K8.1"]["source"] == verdict.kit.files["templates/iso5457_generic.SchDot"]
    text = record.record_bytes(made).decode("utf-8")
    for needle in (str(folder), str(ROOT), folder.parent.name, "/" + USERS + "/", "\\\\"):
        assert needle not in text
    assert all(entry["path"].startswith("results/") for entry in made["results"])
    assert json.loads(text) == made and text.endswith("}\n")


def test_the_archive_is_deterministic(run: tuple[Path, KitVerdict]) -> None:
    folder, verdict = run
    one, two = record.archive_bytes(folder, verdict), record.archive_bytes(folder, verdict)
    assert one == two
    with zipfile.ZipFile(io.BytesIO(one)) as archive:
        infos = archive.infolist()
        assert [info.filename for info in infos] == sorted(entry.path for entry in verdict.results)
        assert {info.date_time for info in infos} == {(1980, 1, 1, 0, 0, 0)}
        assert {info.compress_type for info in infos} == {zipfile.ZIP_STORED}
        assert {info.create_system for info in infos} == {3}
        assert archive.read("results/form.json") == (folder / "results" / "form.json").read_bytes()
    changed = dataclasses.replace(
        verdict, results=(dataclasses.replace(verdict.results[0], sha256="0" * 64), *verdict.results[1:])
    )
    with pytest.raises(ValueError, match="changed since"):
        record.archive_bytes(folder, changed)


def test_no_record_and_no_label_from_a_synthetic_run(kit: Path, run: tuple[Path, KitVerdict]) -> None:
    """A synthetic verdict gives no record, and a record that says synthetic supports no label."""
    simulate(kit)
    verdict = verify_results(kit, judge=simulated_judge)
    assert verdict.synthetic and verdict.passed and "synthetic" in record.refusal(verdict)
    with pytest.raises(ValueError, match="synthetic"):
        record.run_record(verdict, archive=record.archive_bytes(kit, verdict))
    folder, real = run
    made = record.run_record(real, archive=record.archive_bytes(folder, real))
    forged = {**made, "synthetic": True}
    assert "a record of a synthetic run supports nothing" in record.record_problems(forged)
    row = _row("H-A-KIT-RESAVE", record.kit_label(made), f"archive {made['archive']['sha256']}")
    assert record.label_problems([row], [made], None) == []
    assert record.label_problems([row], [forged], None) == [
        f"H-A-KIT-RESAVE: the record {made['run_id']} is synthetic"
    ]


def test_refusals(run: tuple[Path, KitVerdict]) -> None:
    _folder, verdict = run
    assert record.refusal(verdict) == ""
    assert "differ from kit.json" in record.refusal(dataclasses.replace(verdict, kit_problems=("x differs",)))
    assert "form is not sound" in record.refusal(dataclasses.replace(verdict, form_problems=("no date",)))


def test_a_record_with_a_path_is_refused(run: tuple[Path, KitVerdict]) -> None:
    folder, verdict = run
    made = record.run_record(verdict, archive=record.archive_bytes(folder, verdict))
    home = f"C:\\{USERS}\\jdoe"
    assert any("home folder" in p for p in record.record_problems({**made, "os_family": home}))
    for path in ("D:\\work\\kit", "\\\\fileserver\\share\\kit", "/srv/builds/kit"):
        assert any("absolute path" in p for p in record.record_problems({**made, "os_family": path})), path
    outside = [{"path": "../x", "sha256": "0", "size": 1}]
    assert any("leaves the kit" in p for p in record.record_problems({**made, "results": outside}))
    assert any("run_id" in p for p in record.record_problems({**made, "run_id": "2026-10-06-00000000"}))
    assert record.record_problems({**made, "host": "pc"}) == ["unknown field host"]
    assert record.record_problems({"schema": "x"}) == [f"the record's schema is not {record.RUN_SCHEMA}"]


def test_load_records(run: tuple[Path, KitVerdict], tmp_path: Path) -> None:
    folder, verdict = run
    made = record.run_record(verdict, archive=record.archive_bytes(folder, verdict))
    assert record.load_records(tmp_path) == ()
    target = tmp_path / "docs" / "evidence" / "altium-kit"
    target.mkdir(parents=True)
    (target / f"{made['run_id']}.json").write_bytes(record.record_bytes(made))
    (target / "README.md").write_text("not a record\n", encoding="utf-8")
    assert record.load_records(tmp_path) == (made,)
    (target / "other.json").write_bytes(record.record_bytes(made))
    with pytest.raises(FormatError, match="file name"):
        record.load_records(tmp_path)


def test_no_run_is_committed_yet() -> None:
    assert record.load_records(ROOT) == ()


def test_candidate_rows(run: tuple[Path, KitVerdict]) -> None:
    folder, verdict = run
    made = record.run_record(verdict, archive=record.archive_bytes(folder, verdict))
    rows = {row["id"]: row for row in record.candidate_rows(made)}
    label = f"ALTIUM-VERIFIED(kit; {VERSION}; {DATE}; {made['run_id']})"
    assert rows["H-A-KIT-RESAVE"]["label"] == label and parse_level(label) is Level.ALTIUM_VERIFIED_KIT
    assert made["archive"]["sha256"] in str(rows["H-A-KIT-RESAVE"]["result"])
    assert "form" not in str(rows["H-A-KIT-RESAVE"]["result"]) and rows["H-A-WRITE-SCHDOC"]["form"]
    assert "(form)" in str(rows["H-A-WRITE-SCHDOC"]["result"])
    assert "H-A-KIT-REPOUR" in rows and "H-A-KIT-DRC" in rows and "H-A-KIT-SCRIPT" in rows
    assert (
        record.label_problems(
            [_row(i, str(r["label"]), str(r["result"])) for i, r in rows.items()], [made], verdict.kit
        )
        == []
    )


def test_label_problems(run: tuple[Path, KitVerdict]) -> None:
    """Scenarios "Label without a record" and "Label with a record"."""
    folder, verdict = run
    made = record.run_record(verdict, archive=record.archive_bytes(folder, verdict))
    label, digest = record.kit_label(made), made["archive"]["sha256"]
    good = _row("H-A-KIT-RESAVE", label, f"confirmed by the kit run (archive {digest})")
    assert record.label_problems([good], [made], verdict.kit) == []
    assert record.label_problems([good], [], verdict.kit) == [
        f"H-A-KIT-RESAVE: no run record {made['run_id']}.json under docs/evidence/altium-kit"
    ]
    # a row that no step of the run settles: every row of a simulated run with the script passes
    unsettled = record.label_problems([_row("H-A-KIT-STABLE", label, digest)], [made], verdict.kit)
    assert unsettled and "holds no passing verdict" in unsettled[0]
    cases = {
        "does not name the archive digest": _row("H-A-KIT-RESAVE", label, "confirmed"),
        "does not say 'form'": _row("H-A-WRITE-SCHDOC", label, f"archive {digest}"),
        "the label is not": _row("H-A-KIT-RESAVE", label.replace(VERSION, "AD 24.0"), digest),
        "a kit label is": _row("H-A-KIT-RESAVE", "ALTIUM-VERIFIED(kit)", digest),
    }
    for text, row in cases.items():
        problems = record.label_problems([row], [made], verdict.kit)
        assert len(problems) == 1 and text in problems[0], (text, problems)
    author = _row("H-A-PRJ-OPEN", "ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-03; no artefact)")
    assert record.label_problems([author, _row("H-K-UNIT", "CORPUS-VERIFIED")], [], verdict.kit) == []


def test_a_stale_run(run: tuple[Path, KitVerdict]) -> None:
    """Scenario "A stale run": a writer change that alters a sample's bytes makes the rows of that sample
    stale, and no other."""
    folder, verdict = run
    made = record.run_record(verdict, archive=record.archive_bytes(folder, verdict))
    label, digest = record.kit_label(made), made["archive"]["sha256"]
    rows = [
        _row("H-A-KIT-RESAVE", label, digest),  # steps of flat, libs, tree, board6 and routed
        _row("H-A-PCBX-STACK", label, f"{digest} form"),  # board6 only
        _row("H-A-SCHDOT-OPEN", label, digest),  # the template, a kit file of no sample
        _row("H-A-KIT-COMPILE", "INFERRED", "pending"),
    ]
    assert record.stale_rows(rows, [made], verdict.kit) == ()
    sources = kit_sources()
    libs = sources.samples[-1]
    assert libs.name == "libs"
    edited = SampleFiles(libs.name, libs.script_sha256, {**libs.files, "libs.SchLib": b"changed by a writer"})
    after = read_kit(
        kit_files(KitSources((*sources.samples[:-1], edited), sources.extras, sources.fenolite_version))[
            "kit.json"
        ]
    )
    assert record.stale_rows(rows, [made], after) == ("H-A-KIT-RESAVE",)
    assert any("stale" in p for p in record.label_problems(rows, [made], after))
    template = read_kit(
        kit_files(KitSources(sources.samples, {"templates/iso5457_generic.SchDot": b"x"}))["kit.json"]
    )
    assert record.stale_rows(rows, [made], template) == ("H-A-SCHDOT-OPEN",)
    assert load_kit(folder).digest == verdict.kit.digest


def test_the_record_names_a_project_file_that_the_tool_saved_again(run: tuple[Path, KitVerdict]) -> None:
    """A sample's project file with other bytes and the same documents refuses nothing, and the record
    says which file it was (change c0139)."""
    folder, verdict = run
    assert verdict.resaved == ()
    made = record.run_record(verdict, archive=record.archive_bytes(folder, verdict))
    assert made["kit_resaved"] == []
    resaved = dataclasses.replace(verdict, resaved=("flat/flat.PrjPcb",))
    assert record.refusal(resaved) == ""
    again = record.run_record(resaved, archive=record.archive_bytes(folder, resaved))
    assert again["kit_resaved"] == ["flat/flat.PrjPcb"] and record.record_problems(again) == []
    assert "the field kit_resaved is missing" in record.record_problems(
        {key: value for key, value in made.items() if key != "kit_resaved"}
    )
