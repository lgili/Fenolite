## 1. Registers, documentation and format rows

- [x] 1.1 Register the hypotheses and re-check the consumed names. This is the first commit of the implementation, so c0014's cited-id guard sees the ids registered.
  - Add the rows `H-K-ZONE-DEFAULTS`, `H-K-ZONE-CONNECT`, `H-K-ZONE-GEOM`, `H-K-ZONE-FORM`, `H-K-ZONE-FAT9` and `H-K-ZONE-LOAD9` to `docs/hypotheses.md`, with backend `kicad`, level `INFERRED`, the test and criterion of `design.md`, and the result `pending; observed at proposal time (2026-10-02)` with the observation of design "Context". Add the paragraph "Change c0031 (zone settings) adds …".
  - Register S-0125 in `docs/evidence/sources.md` as design "Sources registered by this change" gives it, after opening the page and the specification: record the revision read and its licence or terms ("not stated" otherwise), and only the subset that the zone probe reads.
  - Widen the "used for" cells of S-0001, S-0010, S-0018, S-0020, S-0021, S-0022, S-0029, S-0033, S-0037, S-0038 and S-0058 as design "Sources registered by this change" lists. Open S-0001, S-0021, S-0010 and S-0038 first, and widen a cell only with what the page states; record "not stated" otherwise.
  - Re-check every name consumed from c0009, c0011, c0017, c0019 and c0028 (design "Files and public API") against the working tree, and list each divergence in the pull request description.

  Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py`; `grep -c '^| H-K-ZONE-' docs/hypotheses.md` prints `6`.
- [x] 1.2 Write the documentation rows the code is written from.
  - **`docs/formats/kicad/board.md`.** Add fact rows with source, label and hypothesis: the setting children and their forms per major, the `fill` order, `hatch_border_algorithm` values, the defaults table of design Decision 3, pad `zone_connect` codes and precedence, the target-9 `filled_areas_thickness` pitfall, the clearance combination, and the DRC fact on zone clearance. Update the `zone` and `pad` rows of the table under "What the reader models", and add the 13 new `FLOOR_HEADS` names with S-0033.
  - **`docs/formats/kicad/gerber.md` (new).** Write, in Fenolite's own words, fact rows with source, label and hypothesis for the Gerber subset that `tests/kicad/zones/_gerber.py` reads: the `%FS…*%` coordinate format and `%MO…*%` unit statements, `G36*`/`G37*` regions, and `D02`/`D01` coordinate words (S-0125), and what `pcb export gerbers -l B.Cu` writes on each major (S-0020, S-0029), labelled `INFERRED` with `H-K-ZONE-FAT9` until the probe runs.
  - **`src/fenolite/backends/kicad/PROVENANCE.md`.** Add a row for `zones.py` (format facts from S-0001, S-0021, S-0058; oracle use of `pcb drc --refill-zones --save-board`, `pcb upgrade --force` and `pcb export gerbers -l B.Cu`, which both majors have), and a row for the Gerber subset that the zone probe's test helper reads (S-0125, facts only).
  - **`LEGAL-ANNEX.md`.** Add a session row dated in the ISO week of the work.

  Proof: `uv run pytest tests/unit/test_format_facts.py tests/unit/test_provenance.py tests/unit/test_legal_docs.py`; `uv run python tools/residue/scan.py` exits 0.

## 2. Zone bench and probes first (`kicad-cli` 10.0.6 and 9.0.9)

- [x] 2.1 Write the zone bench and its measurement helpers, through the model API only.
  - `tests/kicad/zones/_zonebench.py` builds the canary of `kicad-oracle` "Zone settings pass the oracle": nets `GND` and `SIG`, pads, ring, channel, a case table, and `write_case(case, target)`. Each case inserts its setting children by token edit until group 5 writes them. `rect_probes`, `round_probes`, `in_fill`, `crossings` and `gap_to_pad` use `fenolite.geometry` exact predicates.
  - `tests/kicad/zones/_gerber.py::region_extents(text)` reads the region vertices of a `%FSLAX46Y46*%` Gerber in nanometres.
  - Add `tests/kicad/zones` to the `sys.path` list of `tests/kicad/conftest.py`.
  - Write the hermetic `tests/kicad/zones/test_zonebench.py`: the bench parses for both targets, the helpers give known answers on authored rings, and `region_extents` reads an authored Gerber text.

  Proof: `uv run pytest tests/kicad/zones/test_zonebench.py`.
- [x] 2.2 Write `tests/kicad/zones/test_zone_probes.py` with the probes `zone-defaults-t10`, `zone-fat9` (both majors) and `zone-clearance-drc` (10.0.6), and add their ids and majors to `PROBES` in `tests/kicad/_probes.py`.
  - `zone-defaults-t10` compares the re-saved children with the literal `DEFAULTS_T10` of the bench. Task 5.1 pins that literal to `emit_settings`.
  - Write the outcomes with `FENOLITE_PROBES_WRITE=1` to `docs/evidence/kicad/probes/10.0.6.json` and `9.0.9.json`.
  - Apply the stop rule of the requirement before group 3, and note each outcome and the rule applied under this task.

  Proof: `uv run pytest tests/kicad/zones/test_zone_probes.py -rA` and `uv run pytest tests/kicad/test_probe_results.py -q` on the local KiCad 10.0.6. Then the same two commands inside the pinned 9.0.9 image, run from the repository root as the `kicad-9` job runs them: `docker run --rm --platform linux/amd64 --user 0 -e HOME=/root -e UV_PROJECT_ENVIRONMENT=/root/venv -e FENOLITE_REQUIRE=kicad -v "$PWD":/w -w /w kicad/kicad:9.0.9@sha256:e638b79b0321f29395a5b783e94bb9f3c73303e8da15da27b8f5cb4b67a37729 sh -c 'apt-get update -qq && apt-get install -y -qq curl ca-certificates && curl -LsSf https://astral.sh/uv/0.8.14/install.sh | sh && export PATH="$HOME/.local/bin:$PATH" && uv sync --locked --extra dev && uv run pytest tests/kicad/zones/test_zone_probes.py -rA && uv run pytest tests/kicad/test_probe_results.py -q'` exits 0.

  Outcomes (2026-10-04), stop rule applied: no outcome differs, so neither the defaults nor the target-9 form were corrected before group 3.
  - `kicad-cli` 10.0.6 (macOS): `zone-defaults-t10` = `equal`, `zone-fat9` = `equal`, `zone-clearance-drc` = `present`.
  - `kicad-cli` 9.0.9 (pinned image, run on a snapshot of the commit): `zone-fat9` = `equal`; the two 10.0 probes are skipped there.
  - An exploratory refill of all 20 bench cases on 10.0.6 gave the patterns and measurements of design "Context". One addition: with `connect_pads no`, no pad connects the zone, and KiCad then keeps the island (the manuals S-0010 and S-0038 say that islands are removed only from zones with a connection), so the island cases use connected zones.

## 3. Zone settings in the model (`src/fenolite/model/board.py`)

- [x] 3.1 Add the vocabularies, `ZoneHatch`, `ZoneSettings` with `effective()`, and the fields `Zone.settings`, `Zone.filled`, `Zone.locked` and `Pad.zone_connection` (design Decision 3), and export them. Regenerate the schemas with `uv run python tools/gen_schemas.py`. Describe the settings in `docs/design-model.md`. Proof: `uv run pytest tests/unit/model/test_zone_settings.py tests/unit/test_schema_drift.py tests/unit/model`; `uv run python tools/gen_schemas.py --check` exits 0. These cover every scenario of "Zone settings in the board model".

## 4. Reading zone settings (`src/fenolite/backends/kicad/zones.py`, `pcb.py`)

- [x] 4.1 Write `zones.py` (design Decision 9): `CONNECT_ATOMS`, `PAD_CONNECT_CODES`, `ISLAND_CODES`, `HATCH_EDGE`, `SettingsRead`, `project_settings` and `emit_settings`, with the forms per major of design "Context". The exact area conversion goes through `fractions.Fraction`. Write `tests/unit/backends/kicad/test_zone_codec.py`: every form listed in design "Context" round-trips through `project_settings` and `emit_settings` for its major, and a 9-format `(island_removal_mode 0)` does not. Proof: `uv run pytest tests/unit/backends/kicad/test_zone_codec.py tests/unit/test_import_graph.py`.
- [x] 4.2 Integrate the reader.
  - Extend `ZONE_FIELDS` and exclude the new fields from `KEEPOUT_FIELDS`. Project into `Zone.settings`, `Zone.filled` and `Zone.locked`.
  - Make `_emit_zone` take the major, so c0009's reproducibility check uses the file's form. Keep failing children opaque with `kicad.board.kept-opaque` and the reason, and leave rule areas unchanged.
  - Write `tests/unit/backends/kicad/test_zone_settings_read.py`, with boards from `tests/_boards.py::board` and `zone`.

  Proof: `uv run pytest tests/unit/backends/kicad/test_zone_settings_read.py tests/unit/backends/kicad/test_pcb_items.py tests/unit/backends/kicad/test_pcb_rebuild.py tests/unit/backends/kicad/test_pcb_read.py`. These cover the scenarios of "Zone settings are read" except "Demo zones are modelled" (task 7.1), and those of the MODIFIED "Zones, fills and rule areas".

## 5. Writing zone settings (`pcb.py`)

- [x] 5.1 Write created zones (design Decisions 2, 6 and 7).
  - Extend `CANONICAL_ORDER` (zone order, `connect_pads`, `fill`) and `POSITIONAL`. Emit `(hatch edge 0.5)`, the setting children of `emit_settings` for the target, `(filled_areas_thickness no)` for target 9 and `(locked yes)`.
  - Add the 12 non-pad names to `FLOOR_HEADS`, each confirmed at tag 8.0.0 (S-0033) and listed in `board.md`. Add zone `GND_HATCH` to `tests/_boards.py::created_board()`.
  - Pin `DEFAULTS_T10` of the bench to `emit_settings(ZoneSettings(), filled=False, locked=False, major=10)`.
  - Update c0017's tests that pin the created zone's children.

  Proof: `uv run pytest tests/unit/backends/kicad/test_zone_settings_write.py -k created`; `uv run pytest tests/unit/backends/kicad/test_pcb_write.py tests/unit/backends/kicad/test_check_emittable.py tests/kicad/zones/test_zonebench.py`. These cover the scenarios "Created zone for target 10", "Created zone for target 9", "Fill flag follows the model" and "Created tokens stay known".
- [x] 5.2 Write read zones.
  - The writer's `items` emit the settings in the target's form. `absent()` leaves out an absent child whose part equals the defaults. `reconcile()` re-projects opaque setting children with `project_settings` and gives `kicad.board.projection-read-only` naming `settings`, `filled` or `locked`.
  - Extend `tests/unit/backends/kicad/test_zone_settings_write.py`.

  Proof: `uv run pytest tests/unit/backends/kicad/test_zone_settings_write.py tests/unit/backends/kicad/test_pcb_write_projections.py tests/unit/backends/kicad/test_pcb_write.py tests/unit/backends/kicad/test_pcb_write_lossy.py`. These cover the scenarios "Clearance edited on a read zone", "A zone without settings stays without them", "Projected settings are read-only" and "Upgrade to target 10 writes the island mode".

## 6. Pad zone connection (`_fpmap.py`)

- [x] 6.1 Model `(zone_connect N)` in the shared footprint mapping (design Decision 8).
  - `PAD_FIELDS`, `emit_pad` through `zones.read_pad_connect` and `zones.pad_connect_node`, and the kept-opaque code of each reader. Add `zone_connect` between `net` and `uuid` in `CANONICAL_ORDER["pad"]`, and add it to `FLOOR_HEADS`.
  - Give pad `"1"` of `U1` in `created_board()` `zone_connection="solid"`, and regenerate `library.json`.
  - Write `tests/unit/backends/kicad/test_pad_zone_connect.py`.

  Proof: `uv run pytest tests/unit/backends/kicad/test_pad_zone_connect.py tests/unit/backends/kicad/test_mod.py tests/unit/backends/kicad/test_mod_pads.py tests/unit/backends/kicad/test_mod_write.py tests/unit/backends/kicad/test_embed.py tests/unit/backends/kicad/test_embed_bottom.py`; `uv run pytest tests/unit/backends/kicad/test_pcb_write.py -k created_tokens`; `uv run python tools/gen_schemas.py --check` exits 0. These cover the scenarios of "Pad zone connection" except "Library footprints round trip" (task 7.1).

## 7. Corpus

- [x] 7.1 Add `test_zone_settings` to `tests/corpus/test_board_census.py`. It counts, per origin (native demos; upgraded third-party copies), the zones whose `connect_pads`, `min_thickness` and `fill` are `Modeled`, the zones with an opaque setting child and why, and the pads with a modelled `zone_connect`. It writes the counts only to `FENOLITE_CENSUS_OUT`, and asserts no opaque setting child. Proof: `FENOLITE_CENSUS_OUT="$(mktemp -d)/census.json" uv run pytest tests/corpus/test_board_census.py -k zone_settings tests/corpus/test_board_read.py tests/corpus/test_board_rt1.py tests/corpus/test_footprint_rt.py -q`; `git status --porcelain` prints the same before and after the run. These cover the scenarios "Demo zones are modelled" and "Library footprints round trip".

## 8. Zones in the DSL and the build

- [x] 8.1 Add the DSL surface (design Decision 10).
  - `Design.zone` and `ZoneSpec` go in `dsl/design.py`, `as_nm2` in `dsl/units.py`, and the `zone` row of `KEYS` and the zones of `to_model` in `dsl/convert.py`. Raise `DslError` in every case of "Zones in the DSL".
  - Add a "Zones" section to `docs/dsl.md`.
  - Check that the MODIFIED "Identifier derivation" still holds the full text of c0028's version, which copies c0011's, with exactly the two edits listed in design "Migration Plan". Re-copy it if that text changed before it was archived.

  Proof: `uv run pytest tests/unit/dsl/test_zones.py tests/unit/dsl tests/unit/test_import_graph.py`, with c0011's DSL tests unchanged except the closed `KEYS` set pinned by `tests/unit/dsl/test_ids.py`, which gains `zone`. This covers every scenario of "Zones in the DSL" and the scenario "Zone ids from the zone name".
- [x] 8.2 Write `tests/unit/lens/test_build_zones.py` with the blink pour variant (`tests/_buildhelp.py` gains `pour_variant()`). It builds for targets 9 and 10, reads the boards back, and builds twice into empty folders. Proof: `uv run pytest tests/unit/lens/test_build_zones.py tests/unit/lens`, with c0011's and c0019's lens tests unchanged. This covers the scenarios of "Zones in a build".

## 9. Zones in the layout lens (`backends/kicad/zones.py`, `lens/preserve.py`)

- [x] 9.1 Merge script zones in `merge_layout` (design Decisions 12 and 13).
  - Write `zones.merge_zones`, `ZoneMerge`, `script_zone_uuid` and `MERGE_ISSUE_CODES`: uuid matching, keep or force, additions, and orphans by the uuid of the zone's own name. `merge_layout` passes the zones to it. Pin `script_zone_uuid("GND")` to the uuid of the zone that `dsl.to_model` gives for a zone named `GND`. Write `tests/unit/backends/kicad/test_zone_merge.py`.
  - `zone_digest` takes `settings.effective()`, and `drop_stale_fills` clears `filled`.
  - Add a "Zones" section to `docs/lens.md`, and the zone row of the precedence table of c0028 Decision 20 (edited in place; locked script zones win; removed ones are orphans).
  - Check that the MODIFIED "Zone fills and the staleness digest" still holds c0019's archived text with exactly the edits of design "Migration Plan", and re-copy it if that text changed. The script-zone marker stays the uuid of the zone's own name (c0028 Decision 20).

  Proof: `uv run pytest tests/unit/backends/kicad/test_zone_merge.py tests/unit/lens/test_preserve_zones.py tests/unit/lens/test_preserve_fills.py tests/unit/lens/test_preserve_issues.py`, with c0019's closed-set test unchanged. This covers "Zones declared in the script" (its scenario "Zone merge codes are closed" included) and the MODIFIED digest requirement at the function level.
- [x] 9.2 Write `tests/unit/cli/test_build_zones_command.py`. Each scenario of "Zones declared in the script" and the new scenarios of "Zone fills and the staleness digest" runs the build command in-process, on a confirmed build of the pour variant in `tmp_path`, edited by token edit in the test. Proof: `uv run pytest tests/unit/cli/test_build_zones_command.py tests/unit/cli`, with c0019's command tests unchanged.

## 10. Oracle (`kicad-cli` 10.0.6 and 9.0.9)

- [x] 10.1 Write `tests/kicad/zones/test_zone_oracle.py`, now with the setting children written by `write_board`:
  - `-k connection`, `-k clearance` and `-k geometry`: refills on 10.0.6, judged with the bench's exact helpers;
  - `-k load`: every case board written for target 9 loads on 9.0.9;
  - `-k build`: the target-9 and target-10 blink pour variants load on their majors, and on 10.0.6 the refilled board holds a `GND` fill on `B.Cu`.

  Proof: `uv run pytest tests/kicad/zones/test_zone_oracle.py -rA` on the local KiCad 10.0.6, and the same command in the pinned 9.0.9 image with the `docker run` line of task 2.2. These cover every scenario of "Zone settings pass the oracle" except "Probe outcomes pinned".
- [ ] 10.2 Regenerate `docs/evidence/kicad/probes/10.0.6.json` locally and `9.0.9.json` inside the 9.0.9 image with `FENOLITE_PROBES_WRITE=1`, and commit both. Check that the `kicad-9` and `kicad-10` jobs run `tests/kicad/zones`. Proof: `uv run pytest tests/kicad/test_probe_results.py -q` on 10.0.6 and in the 9.0.9 image; `uv run python tools/residue/scan.py` exits 0; `gh pr checks` shows `kicad-9` and `kicad-10` passing. This covers the scenario "Probe outcomes pinned".

  Local part done on 2026-10-04; the task stays open for the CI proof.
  - `docs/evidence/kicad/probes/10.0.6.json` was regenerated locally and `9.0.9.json` inside the pinned image (on a snapshot of the commit); both hold the `zone-*` probes of their major, and `tests/kicad/test_probe_results.py` passes on both.
  - `tools/residue/scan.py` exits 0. The `kicad-9` and `kicad-10` jobs run `uv run pytest tests/kicad …` (`.github/workflows/ci.yml`), which collects `tests/kicad/zones`.
  - Open: `gh pr checks` showing `kicad-9` and `kicad-10` passing, after the branch is pushed (the implementing agent does not push).

## 11. Closing

- [ ] 11.1 Run the residue and full test suites. Add a `LEGAL-ANNEX.md` row for every further ISO week in which `backends/` or `docs/formats/` changed. Proof: `make check`; `uv run pytest tests/residue` and `uv run pytest -q` exit 0; `uv run python tools/residue/scan.py` exits 0; `uv run python tools/gen_schemas.py --check` exits 0; `uv run pytest tests/unit/test_import_graph.py tests/unit/test_hypotheses_register.py` passes with no `ALLOWED` change; `openspec validate c0031-zone-settings --strict --no-interactive` passes.
  Status on 2026-10-04: left open. `make check` passes lint, format and types, and its test step gives 5167 passed, 24 skipped and 1 failed. The failure is `tests/unit/geometry/test_transform.py::test_composition_rounds_once`, a Hypothesis property of the geometry kernel, which this change does not touch: Hypothesis found an input for which two transforms applied in sequence are 1.0000257 nm off, above the 1 nm the test allows, and replays it from the local example database. It is reported to the maintainer as a separate task. Every other proof of this task passes: `tools/residue/scan.py` exits 0, `tools/gen_schemas.py --check` exits 0, `tests/unit/test_import_graph.py` and `tests/unit/test_hypotheses_register.py` pass with no `ALLOWED` change, and `openspec validate c0031-zone-settings --strict --no-interactive` passes.
- [x] 11.2 Update the evidence labels from the results.
  - `H-K-ZONE-CONNECT` and `H-K-ZONE-GEOM` become `KICAD-VERIFIED (10.0.x)`.
  - `H-K-ZONE-DEFAULTS` becomes `KICAD-VERIFIED (10.0.x)` for the loader, and its result says that the GUI half rests on S-0020.
  - `H-K-ZONE-FAT9` becomes `KICAD-VERIFIED (9.0.x, 10.0.x)` and `H-K-ZONE-LOAD9` `KICAD-VERIFIED (9.0.x)`. `H-K-ZONE-FORM` becomes `CORPUS-VERIFIED`, with the counts of both origins.
  - A refuted row keeps its id and gets a successor with the suffix `-2`. The labels in `docs/formats/kicad/board.md` follow.

  Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_format_facts.py tests/unit/test_hypotheses_register.py`; the updated rows appear in `docs/hypotheses.md`.
- [x] 11.3 Add to `CHANGELOG.md` under Unreleased: "Zone settings: zones carry typed settings (clearance, minimum thickness, pad connection solid/thermal/none/thru-hole-only, thermal gap and spoke width, island removal, smoothing, hatched fill), read from KiCad 9.0 and 10.0 boards and written per target; pads carry a zone connection override; `Design.zone()` declares pours in design scripts, and rebuilds keep zones edited in KiCad unless the script locks them; created target-9 zones write `(filled_areas_thickness no)`, so their fills are plotted as written; checked by refills on `kicad-cli` 10.0 and loads on 9.0". Proof: `git diff CHANGELOG.md`.
