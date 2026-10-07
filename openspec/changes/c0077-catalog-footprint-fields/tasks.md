## 0. Entry check

- [ ] 0.1 Check the prerequisites and reproduce the defect on the tip of `dev`. Write under this task, with the date and the commit:
  - that `0.3.0` is released and that c0126 and c0123 are archived (stop here otherwise);
  - the issue codes of `fenolite check` on the three-part design of `design.md` ("Reproduction"), built into a temporary folder, and whether a footprint authored with `fenolite.dsl.Footprint` shows the same defect;
  - the function of `src/fenolite/lens/preserve.py`, as it is after c0069, that takes the rule of Decision 4, and the place in `src/fenolite/lens/build.py` where `build.field-added` is reported;
  - every pinned digest that moves: run `grep -rln "Fenolite:" tests examples` and list each test, each entry of `tests/data/MANIFEST.toml` and each kit sample (`examples/kit`, `tests/unit/verify/kit/test_manifest.py`) that pins bytes of a KiCad file built from catalog or authored footprints. The kit pins Altium documents, which Decision 7 keeps; say so with the test that shows it.
  Proof: `openspec validate c0077-catalog-footprint-fields --strict --no-interactive` passes, and the notes hold the `netlist.*` codes of the run and the list of digests.

## 1. Register

- [ ] 1.1 Add the row `H-K-FP-FIELDS` to `docs/hypotheses.md` (backend `kicad`, level `INFERRED`, the test and criterion of `design.md`, result `pending`). Proof: `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/verify/test_cited_ids.py -q`; `grep -c '^| H-K-FP-FIELDS ' docs/hypotheses.md` prints `1`.

## 2. The two fields

- [ ] 2.1 Add `FieldDefault`, `default_fields`, `FIELD_GAP`, `FIELD_SIZE` and `FIELD_THICKNESS` to `src/fenolite/backends/kicad/embed.py`, and make `mod.prepare_authored_definition` add the two properties. Write `tests/unit/backends/kicad/test_embed_fields.py` (scenarios "Catalog footprint placed on top", "Bottom side", "Deterministic uuids", "Authored two-pad footprint", "Every catalog footprint"). Regenerate, in this commit, each pinned digest that task 0.1 listed. Proof: `uv run pytest tests/unit/backends/kicad/test_embed_fields.py tests/unit/catalog tests/unit/test_import_graph.py -q`; `uv run pyright src`.
- [ ] 2.2 Make `embed.place_footprint` add a field that a library footprint lacks, and make `lens/build.py` report `build.field-added`; document the code in `docs/cli-contract.md` and add its table to `src/fenolite/cli/data/explain.toml` (scenarios "Library footprint keeps its own fields", "Library footprint without a reference"). Proof: `uv run pytest tests/unit/backends/kicad/test_embed_fields.py -k library tests/unit/cli/test_explain_cmd.py tests/consistency -q`.
- [ ] 2.3 Make a kept footprint gain a missing `Reference` or `Value` field in `src/fenolite/lens/preserve.py` (scenarios of "Kept footprints gain missing mandatory fields"), and describe the rule in `docs/lens.md`. Proof: `uv run pytest tests/unit/cli/test_catalog_only.py -k "older_board or edited or second" tests/unit/lens -q`.
- [ ] 2.4 Prove `Part.field` on generated fields (scenario "Field request on a catalog part"). Proof: `uv run pytest tests/unit/backends/kicad/test_embed_fields.py -k field_request -q`.

## 3. Acceptance

- [ ] 3.1 Write `tests/_catalog_design.py::catalog_blink()` and `tests/unit/cli/test_catalog_only.py` (scenarios "Nets of the script and of the board agree", "A regression is caught" and "Altium documents are unchanged"). Proof: `uv run pytest tests/unit/cli/test_catalog_only.py tests/unit/cli/test_catalog.py -q`.
- [ ] 3.2 Write `tests/kicad/build/test_catalog_only.py` (scenario "KiCad accepts the project"). Proof: `uv run pytest tests/kicad/build/test_catalog_only.py -rA` on the local KiCad 10.0.6 and on KiCad 9.0.9.

## 4. Documentation

- [ ] 4.1 Describe the generated fields in `docs/dsl.md` ("Authored footprints" and "Field placement") and in `docs/catalog/README.md`: what is generated, where it is placed, and that `Part.field` moves or hides it. Say in `docs/altium.md`, in one sentence, that the Altium build is unchanged by the generated fields. Proof: `uv run pytest tests/consistency tests/unit/test_repo_layout.py tests/residue -q`.

## 5. Closing

- [ ] 5.1 Update the evidence labels: `H-K-FP-FIELDS` becomes `KICAD-VERIFIED (9.0.x, 10.0.x)` with the two runs, or records what KiCad reported. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py -q`.
- [ ] 5.2 Add to `CHANGELOG.md` under `## [Unreleased]`, in bold where behaviour changes: "**Footprints from the built-in catalog and from `dsl.Footprint` now carry `Reference` and `Value` on the board and in the project library, so a catalog-only board passes `check`. Projects built before gain the two properties on their next build: this is the first change of KiCad bytes since 0.2.0, and only for these footprints.** Altium projects do not change." Update the row of this change in `docs/roadmap.md`. Proof: `git diff --stat HEAD -- CHANGELOG.md docs/roadmap.md` lists both files.
- [ ] 5.3 Stop and report "ready for the long runs": `make check-fast`, the unit suite on Python 3.11 (`uv run --python 3.11 pytest tests/unit -q`), `uv run pytest tests/residue tests/corpus/test_manifest.py -q` after `git add -A`, `uv run python tools/residue/scan.py`, and `openspec validate --all --strict --no-interactive`. The full `make check` is run once by the coordinator on the rebased branch, not by the implementing agent. Proof: each command exits 0.
