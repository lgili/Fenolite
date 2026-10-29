## 0. Entry check

- [ ] 0.1 Read `openspec list`, the living specs `design-equivalence` and `corpus-policy`, and the state of
  c0275, c0276, c0277 and c0279. Write under this task the date, the base commit, and:
  - whether c0275 is archived, with the name of its importer entry and the schema and path of the
    `PROVENANCE.json` it creates (phase 5 waits for it);
  - whether c0276 is archived, with the names of `DrawnSchematic`, `extract` and `resolve` (task 2.4 waits
    for it);
  - which open change holds a delta of "Equivalence package", "Differences are located", "Equivalent
    command", "Level 5 in the equivalent command" or "Equivalence documentation"; if one was archived,
    regenerate the MODIFIED blocks from the living text;
  - whether `verify-source`, `fenolite.view.fidelity` and the use `rtf` are free names;
  - the maintainer's answers to the open questions of `design.md`.
  Entry check, 2026-10-29, base `7ed71d3f` (integration branch with c0246, c0247, c0249): c0275 is not
  archived and not merged (no importer `import --to python`, no `PROVENANCE.json` writer; phase 5 waits);
  c0276 is not archived and not merged (no `DrawnSchematic`, `extract`, `resolve`; task 2.4 waits); no other
  open change holds a delta of the five MODIFIED requirements; `verify-source`, `fenolite.view.fidelity` and
  the use `rtf` were free names; the open questions are decided in `design.md` (the maintainer delegated
  them). `make check-fast` passed on 2026-10-29; `openspec validate` cannot run here (no `openspec` CLI in
  this environment), so the task stays open for that one proof.

  Proof: `openspec validate c0278-fidelity-proof --strict`; `make check-fast`.

## 1. Package constants and kinds

- [x] 1.1 Extend `LEVELS`, `LEVEL_NAMES`, `PRESENTATION_LEVEL`, `SCHEMATIC_LEVEL`, `Difference.level`, the
  kinds table of `levels.py`, `EQUIVALENCE_CODES` and `explain.toml` (scenarios "Kinds table is closed",
  "Levels 6 and 7 on request"; the existing scenarios of "Equivalence package" keep passing). Proof:
  `uv run pytest tests/unit/checks/equivalence/test_codes.py tests/unit/checks/equivalence/test_package.py -q`.
  Done 2026-10-29: `LEVELS` 1 to 7, `PRESENTATION_LEVEL`, `SCHEMATIC_LEVEL`, `ALL_LEVEL_NAMES`, the kinds
  table with the placeholders `field` and `item`, the codes and their `explain.toml` entries; proof passed.
- [x] 1.2 Register `H-K-FID-ZONE-OUTLINE` and `H-K-FID-PLOT-AGREE` in `docs/hypotheses.md`. Proof:
  `uv run pytest tests/unit/test_hypotheses_register.py -q`.
  Done 2026-10-29: both rows rewritten with their statement, settling test and criterion; proof passed.

## 2. Levels

- [x] 2.1 Add `strict.py` and `strict=` (scenarios of "Level 5 strict compares copper items" and "Level 5
  strict matching"; "Five planted edits" keeps passing). Proof:
  `uv run pytest tests/unit/checks/equivalence/test_strict.py tests/unit/checks/equivalence/test_level5.py -q`.
  Done 2026-10-29: `strict.py` (`compare_strict`, `STRICT_RULE`), `compare_designs(..., strict=True)`;
  proof passed.
- [x] 2.2 Add `rules.py`, level 6 (scenarios of "Level 6 compares rules"). Proof:
  `uv run pytest tests/unit/checks/equivalence/test_level6.py -q`.
  Done 2026-10-29: `rules.py` (`level_rules`, `fields`); proof passed.
- [x] 2.3 Add `shapes.py` and level 7 (scenarios of "Level 7 compares exact geometry" and "Level 7
  normalisation"). Proof: `uv run pytest tests/unit/checks/equivalence/test_level7.py tests/unit/checks/equivalence/test_shapes.py -q`.
  Done 2026-10-29: `shapes.py` (normalisation and `level_geometry`); proof passed.
- [ ] 2.4 Add `drawn.py` with `compare_drawn` (scenarios of "Level S compares drawn schematics"); waits for
  c0276. Proof: `uv run pytest tests/unit/checks/equivalence/test_level_s.py -q`.
  Open 2026-10-29: waits for c0276 (`DrawnSchematic`, `extract`, `resolve`), not merged in the integration
  branch. Until then `equivalent --level S` exits 2 naming side `a`, and `verify-source` skips level S with
  the reason `drawn-unavailable`.
- [x] 2.5 Add `view/fidelity.py` with `render_masks` and `compare_masks`, and the level-8 kinds (scenarios
  "Grid shared", "Located change", "Same board, no difference", "Moved logo on silkscreen"). Proof:
  `uv run pytest tests/unit/view/test_fidelity_masks.py -q`.
  Done 2026-10-29: `view/fidelity.py` (`render_masks`, `compare_masks`, `compare_scenes`, `board_scene`);
  `view` imports no `checks`, so it gives plain findings that `cli/_presentation.py` turns into the level's
  differences; proof passed.

## 3. The equivalent command

- [x] 3.1 Add `--level 6|7|8|S`, `--strict`, `--pixel-ppm` and `--render-pitch-um` to
  `cmd_equivalent.py` and the API, and update `schemas/fenolite.equivalent.v0.json` (scenarios "Geometry
  level on request", "Schematic level on a board", "Strict copy", "Usage errors"; every existing scenario of
  "Equivalent command" keeps its output). Proof:
  `uv run pytest tests/unit/cli/test_equivalent_cmd.py tests/unit/api/test_equivalence_api.py tests/consistency -k equivalent -q`.
  Done 2026-10-29: `--level 1..8|S`, `--strict`, `--pixel-ppm`, `--render-pitch-um`;
  `fenolite.api.equivalent(..., strict=, presentation=)` (level 8 needs the renderer of `view`, which `api`
  may not import, so the caller passes it); schema regenerated; proof passed.

## 4. verify-source

- [ ] 4.1 Author `tests/data/fidelity/sensor/` (a KiCad 10 project authored for Fenolite, CC0, saved by the
  KiCad GUI per "Project fixtures saved by the KiCad GUI": four layers, net classes, a custom rule, zones,
  arcs, vias, board text, a drawn hierarchical schematic with a bus, a repeated sheet and junctions) and its
  converted script `tests/data/fidelity/sensor_code/`; declare both in `tests/data/MANIFEST.toml`. Until
  the GUI save, an authored text fixture stands in and task 4.1 stays open. Proof:
  `uv run pytest tests/residue tests/corpus/test_manifest.py -q`.
  Open 2026-10-29: `tests/data/fidelity/sensor_code/` (the script) and `tests/data/fidelity/sensor/` are
  authored and declared; `sensor/` is the target-10 build of the script, a text stand-in until a KiCad GUI
  save (maintainer). It holds four layers, net classes, a custom rule, a zone, an arc and vias, board text
  and a flat schematic; the hierarchical drawn schematic with a bus waits for c0276. The proof passes.
- [x] 4.2 Add `cmd_verify_source.py`: inputs, the temporary build, the levels, tolerances, result schema
  `fenolite.verify-source.v0`, exit codes and `ISSUE_CODES` (scenarios of "Verify-source command",
  "Verify-source inputs", "Build in a temporary folder", "Verify-source levels", "Verify-source
  tolerances", "Verify-source result", "Verify-source exit codes", "Fidelity issue codes"). Proof:
  `uv run pytest tests/unit/cli/test_verify_source.py tests/consistency -k verify_source -q`.
  Done 2026-10-29: `cmd_verify_source.py`, `schemas/fenolite.verify-source.v0.json`, `ISSUE_CODES` with
  `explain.toml` entries; proof passed.
- [x] 4.3 Accepted differences, `accepted_rules`, unused entries, `--record` and `--accept` (scenarios of
  "Accepted differences in the provenance file", "Unused accepted differences", "Recording the proof").
  Proof: `uv run pytest tests/unit/cli/test_verify_source.py -k "accepted or record" tests/unit/checks/equivalence/test_exclusions.py -q`.
  Done 2026-10-29: `accepted_rules` in `exclusions.py`, unused entries, `--record` and `--accept`; proof
  passed.

## 5. Round-trip category (waits for c0275)

- [ ] 5.1 Add `tests/_fidelity.py::roundtrip` and `tests/fidelity/` over the authored fixtures (scenarios
  "Authored fixtures", "A regression shows"), and add `tests/fidelity` to the hermetic set of
  `make check-fast`. Proof: `uv run pytest tests/fidelity -q`; `make check-fast`.
  Open 2026-10-29: waits for c0275 (`fenolite import --to python`), not merged.
- [ ] 5.2 Tag the demo project rows with `rtf` by the licence rule and add the manifest check (scenarios of
  "Round-trip fidelity use"). Proof: `uv run pytest tests/corpus/test_manifest.py -k rtf -q`.
  Open 2026-10-29: the `rtf` use and its manifest check come with the round trip, which waits for c0275.

## 6. Evidence

- [ ] 6.1 KiCad CI job: upgrade and refill the authored fixture with `kicad-cli` and compare at level 7
  (`H-K-FID-ZONE-OUTLINE`); raise the row to `KICAD-VERIFIED (9.0.x, 10.0.x)` only after the job passes.
  Proof: the KiCad job of the commit on GitHub CI is green;
  `uv run pytest tests/kicad/fidelity/test_zone_outline.py -rA` there.
  Open 2026-10-29: needs the KiCad CI job and the GUI-saved fixture of task 4.1.
- [ ] 6.2 Add `tests/kicad/fidelity/test_corpus_roundtrip.py` and `accepted.toml`, run it on the `rtf`
  rows, record counts and timings in `docs/evidence/fidelity.md` (scenarios "Demo rows", "Ratchet", "Page
  matches the run"). Proof: `uv run pytest tests/kicad/fidelity -rA` in the KiCad job;
  `uv run pytest tests/unit/test_fidelity_docs.py -q`.
  Open 2026-10-29: needs c0275 and the `rtf` rows (tasks 5.1 and 5.2).

## 7. Documentation and guide

- [x] 7.1 Write `docs/fidelity.md`; update `docs/equivalence.md` (eight levels and S), `docs/cli-contract.md`
  (`verify-source`, the new `equivalent` options) and `docs/roadmap.md` (scenarios "Codes are documented",
  "Codes documented"). Proof: `uv run pytest tests/consistency tests/unit/checks/equivalence/test_codes.py -k docs -q`.
  Done 2026-10-29: `docs/fidelity.md`, `docs/equivalence.md` (levels 6 to 8, S, strict),
  `docs/cli-contract.md` (`equivalent`, `verify-source`), `docs/roadmap.md`; proof passed.
- [x] 7.2 Agent guide (AGENTS.md rule 6): a tested line for `verify-source` and its codes, and for the new
  levels of `equivalent`, on the page `checks`; run `uv run python tools/gen_agent_guide.py` after the
  argument change. Proof: `uv run python tools/gen_agent_guide.py`; `uv run pytest tests/unit/agent/test_pages.py -q`.
  Done 2026-10-29: the page `checks` teaches `verify-source`, its codes and the new levels; `commands.md`
  regenerated; proof passed.

## 8. Changelog and CI

- [ ] 8.1 `CHANGELOG.md`: one entry under `## [Unreleased]`. This waits until `dev` is at `0.7.0.dev0`,
  because the v0.6 guard requires `[Unreleased]` to be empty. Proof: `uv run pytest tests/unit -k changelog -q`.
  Open 2026-10-29: waits for `0.7.0.dev0` (the v0.6 guard needs `[Unreleased]` empty).
- [ ] 8.2 `make check-fast` passes locally; publish the batch to its working branch and confirm the unit
  and KiCad jobs on the exact commit. Proof: `make check-fast`; the required CI jobs are green on the
  commit.
  Open 2026-10-29: `make check-fast PYTEST_WORKERS=2` passed locally; CI runs with the batch.
