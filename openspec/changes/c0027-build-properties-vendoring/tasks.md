## 1. Sources, hypotheses, provenance and format pages

- [x] 1.1 Register the source and the hypotheses, and re-check c0011. This is the first commit of the implementation, so c0014's cited-id guard sees the ids registered.
  - Re-check (2026-10-02): c0011 is archived (5d9b209) and the living `design-dsl` text is unchanged since; every line the six MODIFIED requirements drop from it is an edit of this change. The consumed names (`embed.with_property`, `PATH_PROPERTY`, `libs.write_lib_table`, `read_record`, `check_existing`, `build_design`, `tests/_buildhelp.build(…, config_home=…)`) exist as the design lists; no divergence.
  - Add the row S-0105 to `docs/evidence/sources.md` from the design table "Sources registered by this change", with the consultation date and the licence the page states, or "not stated". If the URL is already registered, cite that id and leave S-0105 unused.
  - Widen the "used for" cells of S-0020, S-0029, S-0046, S-0048 and S-0024 as the design lists.
  - Add the rows `H-K-VENDOR-GLOBAL`, `H-K-VENDOR-SHADOW`, `H-K-VENDOR-PROPS` and `H-K-VENDOR-DUPNAME` to `docs/hypotheses.md`, with backend `kicad`, level `INFERRED`, test and criterion from `design.md`, and result `pending`, plus the pre-proposal counts of the design's Context as supporting data. Add the paragraph "Change c0027 (build properties and vendoring) adds …".
  - Check that c0011 is archived, or that its committed design-dsl text still equals the base of the six MODIFIED requirements of this change; re-copy any text that changed. Re-check every name this change consumes from c0011 (design "Files and public API") against the tree, and list each divergence in the pull request description.

  Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py`; `grep -c '^| H-K-VENDOR-' docs/hypotheses.md` prints `4`; `grep -c '^| S-0105 ' docs/evidence/sources.md` prints `1` (or the reused id is named in the pull request); `openspec validate c0027-build-properties-vendoring --strict` passes.
- [x] 1.2 Add rows to `src/fenolite/backends/kicad/PROVENANCE.md`, with "how used" `facts only` or `oracle`:
  - the user-property form and order on board footprints (S-0058, S-0038);
  - vendoring of every row origin and the project-over-global rule (S-0045, S-0046, S-0048);
  - `pcb drc` and `pcb upgrade` on vendored and property boards (S-0020, S-0029, S-0022, S-0037; `oracle`).

  Add a `LEGAL-ANNEX.md` session row dated in the ISO week of the work. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_legal_docs.py`.
- [x] 1.3 Add fact rows in Fenolite's own words, `INFERRED` with their hypothesis.
  - To `docs/formats/kicad/board.md`: user properties after `fenolite.path` in code-point order, hidden on `F.Fab`/`B.Fab`, and their survival of a 10.0.6 re-save (`H-K-VENDOR-PROPS`); the merge of a duplicate field name and the case variants kept apart (`H-K-VENDOR-DUPNAME`).
  - To `docs/formats/kicad/libraries.md`: vendoring of every row origin under the same nickname; the project row hiding the global row and its items in the library check (`H-K-VENDOR-GLOBAL`, `H-K-VENDOR-SHADOW`).
  - Add the level-2 headings `## User properties` and `## Vendored libraries` to `docs/dsl.md`, with the reserved names and their reasons, and the licence note (S-0048, no legal advice).

  Code in groups 3 to 5 is written from these pages. Proof: `uv run pytest tests/unit/test_format_facts.py tests/unit/test_provenance.py`; `uv run python tools/residue/scan.py` exits 0.

## 2. Probes first (`kicad-cli` 10.0.6 and 9.0.9)

- [x] 2.1 Write the bench and the library probes.
  - `tests/kicad/build/_vendorcases.py` (design Decision 16) makes, in a temporary folder, the configuration folders `D` and `D_alt` from copies of `tests/data/libs/Mini_v9.pretty` and `Mini_v9.kicad_sym`. `D_alt` has `Mini_R_0603` pad `1` moved 0.05 mm along X.
  - It builds the blink from a folder without project tables, with c0011's `tests/_buildhelp.py::build(…, config_home=D)`, and makes the vendored variant by copying the placed footprints into `lib/Mini.pretty/` with a table from `libs.write_lib_table`.
  - `tests/kicad/build/test_vendor_probes.py` holds the probes `vendor-global-t9`, `vendor-global-t10`, `vendor-shadow-t9`, `vendor-shadow-t10`, `vendor-hide-t9` and `vendor-hide-t10`, with the outcomes of `kicad-oracle` "Vendored projects and user properties pass the oracle". Add their ids and majors to `PROBES` in `tests/kicad/_probes.py`.
  - Configuration folders reach `kicad-cli` only as the explicit `env` entry `KICAD_CONFIG_HOME` of `KicadCli.run`.

  Proof: `uv run pytest tests/kicad/build/test_vendor_probes.py -rA -k "global or shadow or hide"` on the local KiCad 10.0.6; and the same command inside the pinned 9.0.9 image, run from the repository root as the `kicad-9` job runs it: `docker run --rm --platform linux/amd64 --user 0 -e HOME=/root -e UV_PROJECT_ENVIRONMENT=/root/venv -e FENOLITE_REQUIRE=kicad -v "$PWD":/w -w /w kicad/kicad:9.0.9@sha256:e638b79b0321f29395a5b783e94bb9f3c73303e8da15da27b8f5cb4b67a37729 sh -c 'apt-get update -qq && apt-get install -y -qq curl ca-certificates && curl -LsSf https://astral.sh/uv/0.8.14/install.sh | sh && export PATH="$HOME/.local/bin:$PATH" && uv sync --locked --extra dev && uv run pytest tests/kicad/build/test_vendor_probes.py -rA -k "global or shadow or hide"'` exits 0.
- [x] 2.2 Add the property probes and pin the outcomes.
  - Outcomes (2026-10-02; 10.0.6 targets 9 and 10, 9.0.9 target 9): `vendor-global` `equal`, `vendor-shadow` `present`, `vendor-hide` `present`, `vendor-props` `equal` on both majors; `vendor-resave-t9` and `-t10` `present` and `vendor-dupname-t10` `present` on 10.0.6. Neither stop rule fires (`vendor-global` and `vendor-props` are `equal`), so groups 3 to 5 proceed unchanged.
  - Add `vendor-props-t9`, `vendor-props-t10`, `vendor-resave-t9` and `vendor-resave-t10` (major 10), and `vendor-dupname-t10` (major 10).
  - The property board is laid out through the model API like c0011's `tests/kicad/build/_probe_boards.py::probe_board`, with `embed.with_property` for `fenolite.path` and then each user property applied before `embed.place_footprint`, and written with `triad.write_triad`. User properties go on `R1`, one value holding `"`, `\` and `µ`, and on the bottom part `D1`. `vendor-dupname-t10` inserts its properties by text.
  - Write the outcomes with `FENOLITE_PROBES_WRITE=1` to `docs/evidence/kicad/probes/10.0.6.json` (locally) and `9.0.9.json` (in the image).
  - Apply the stop rules of design Decision 16 before group 3 starts: write each outcome and the rule applied as an indented note under this task.

  Proof: `uv run pytest tests/kicad/build/test_vendor_probes.py -rA` and `uv run pytest tests/kicad/test_probe_results.py -q` on the local KiCad 10.0.6 and inside the 9.0.9 image; covering the probe-first rules and the scenario "Probe outcomes pinned" of "Vendored projects and user properties pass the oracle".

## 3. DSL properties

- [x] 3.1 Add `properties` to `Part` in `src/fenolite/dsl/part.py` (design Decisions 2 to 4):
  - the keyword-only argument and its checks at the call;
  - `RESERVED_PROPERTIES` and `RESERVED_PREFIXES`, not re-exported;
  - a read-only `Part.properties` in code-point order.

  Make `to_model` in `dsl/convert.py` put the properties into `Component.properties` beside `fenolite.path`. Write `tests/unit/dsl/test_properties.py` and extend `tests/unit/dsl/test_to_model.py`. Proof: `uv run pytest tests/unit/dsl/test_properties.py tests/unit/dsl/test_to_model.py tests/unit/test_import_graph.py`; covering every scenario of "User properties in the DSL" except "Reserved sets agree" (task 4.1), and the scenario "User properties in the model" of "DSL to model".

## 4. Build: user properties

- [x] 4.1 In `src/fenolite/lens/build.py` (design Decisions 1, 5, 6, 7 and 15):
  - add `RESERVED_PROPERTIES`, `RESERVED_PREFIXES` and the checks `build.property-reserved`, `build.property-invalid` and `build.property-conflict` with the build checks;
  - append the user properties with `embed.with_property` after `fenolite.path`, in code-point order, for placed and staged parts;
  - keep `Component.properties` equal to the projection;
  - add `PROPERTY_EVIDENCE` to the combined evidence when a user property is written, and the three rows to `BUILD_ISSUE_CODES`.

  Write `tests/unit/lens/test_build_properties.py`, and extend `test_build_place.py`, `test_build_readback.py` and `test_build_issues.py`. Proof: `uv run pytest tests/unit/lens/test_build_properties.py tests/unit/lens/test_build_place.py tests/unit/lens/test_build_readback.py tests/unit/lens/test_build_issues.py tests/unit/dsl/test_properties.py -k "properties or place or readback or closed_set or reserved_sets"`; covering every scenario of "User properties on built footprints", the scenario "Reserved sets agree" of "User properties in the DSL", the scenario "Staged parts carry their properties" of "Placement of built parts", and `PROPERTY_EVIDENCE` of "Build evidence" at the `build_design` level.

## 5. Build: vendoring

- [x] 5.1 In `src/fenolite/lens/build.py` (design Decisions 8 to 12 and 15):
  - add the keywords `vendor` (`VENDOR_MODES`; any other value raises `ValueError`) and `record`;
  - vendor the placed footprints of every row origin, or only project rows with `vendor="project"` (`build.global-library`);
  - add the `build.vendor-unsafe-name` check with the build checks, and `build.library-changed` from `record`;
  - add `VENDOR_EVIDENCE` when a non-project footprint is vendored, and the two rows to `BUILD_ISSUE_CODES`.

  Write `tests/unit/lens/test_build_vendor.py`: a global setup through `config_home`, a template setup through `tests/_libs.make_install`, an unsafe nickname, a changed library, a moved folder, and byte-identical rebuilds. In c0011's `tests/unit/lens/test_build_files.py`, replace "Global footprint not vendored" with the two scenarios of the MODIFIED "Built project files". Proof: `uv run pytest tests/unit/lens/test_build_vendor.py tests/unit/lens/test_build_files.py tests/unit/lens/test_build_issues.py tests/unit/lens/test_build_determinism.py`; covering every scenario of "Footprints of every row origin are vendored", the scenarios "Global footprint vendored", "Global footprint kept out on request" and "Unknown vendoring policy" of "Built project files", and `VENDOR_EVIDENCE` at the `build_design` level.
- [x] 5.2 Add `--vendor {all,project}` to `src/fenolite/cli/cmd_build.py`, with the help text of the MODIFIED "Build command".
  - Read `read_record(out)` once, and pass it to `build_design` and to `check_existing`.
  - Document the option in `docs/cli-contract.md`.
  - Extend `tests/unit/cli/test_build_command.py`: the policy on the command line with a `KICAD_CONFIG_HOME` authored in the test, and the three envelopes of "Properties and vendoring add their rows".

  Proof: `uv run pytest tests/unit/cli/test_build_command.py`; `REPO="$PWD"; (cd "$(mktemp -d)" && uv run --project "$REPO" pytest "$REPO/tests/consistency" -q)`; covering the scenarios "Vendoring policy on the command line" and "Consistency suite" of "Build command", "Properties and vendoring add their rows" of "Build evidence", and "Closed set enforced" of "Build issue codes", now that every new code is produced.

## 6. Oracle (`kicad-cli` 10.0.6 and 9.0.9)

- [x] 6.1 Write `tests/kicad/build/test_vendor_oracle.py` on builds made by this change's code: `test_global_vendored`, `test_shadow`, `test_hidden_items`, `test_user_properties` (with the re-save on 10.0.6) and `test_duplicate_field_name` (10.0.6). Each asserts the outcome that the design table "Hypotheses registered by this change" expects, and uses the bench of task 2.1. Proof: `uv run pytest tests/kicad/build/test_vendor_oracle.py -rA` on the local KiCad 10.0.6 and inside the 9.0.9 image; covering the scenarios "Vendored global footprints pass the library check", "The project row wins over the global row", "Items missing from the vendored library are not taken from the global one", "User properties survive a re-save", "A duplicate field name is merged" and "9.0 job".
- [ ] 6.2 Extend c0011's `tests/libs/test_build_official.py`: the official-library blink built into `tmp_path` with the default vendoring holds its three footprints under `lib/`. With `needs_kicad` as well, `pcb drc` with an empty configuration gives no `lib_footprint_issues` and no `lib_footprint_mismatch`. Record counts only. Regenerate both probe files, and check that the `kicad-9` and `kicad-10` jobs run `tests/kicad/build`. Proof: `uv run pytest -m "needs_libs and needs_kicad" tests/libs/test_build_official.py -rA` with the local 10.0.6 libraries; `uv run pytest tests/residue/test_official_libs.py tests/kicad/test_probe_results.py -q`; `gh pr checks` shows `kicad-9` and `kicad-10` passing; covering the scenario "Official libraries where they are installed".

## 7. Documentation

- [x] 7.1 Complete the sections "User properties" and "Vendored libraries" of `docs/dsl.md`:
  - the keyword, the text rules, the reserved names with their reasons, the order and form, and the field placement that c0030 owns;
  - the vendoring policy, the nickname rule with its effect on a global library of the same nickname, only placed footprints (no 3D models, no symbols before v0.2a), library changes, stale copies, the licence note and `--vendor project`.

  Update the sentences of c0011's sections "Output layout" and "Libraries and pins" that state the old vendoring rule, and write the probe outcomes into the two new sections. Proof: `grep -c '^## User properties\|^## Vendored libraries' docs/dsl.md` prints `2`; `uv run pytest tests/unit/test_format_facts.py`; `uv run python tools/residue/scan.py` exits 0.

## 8. Closing

- [x] 8.1 Run the residue and full test suites. Add a `LEGAL-ANNEX.md` row for every further ISO week in which `backends/` or `docs/formats/` changed. Proof: `make check`; `uv run pytest tests/residue` and `uv run pytest -q` exit 0; `uv run python tools/residue/scan.py` exits 0; `uv run python tools/gen_schemas.py --check` exits 0 (model unchanged); `uv run pytest tests/unit/test_import_graph.py tests/unit/test_hypotheses_register.py` passes with no `ALLOWED` change; `git status --porcelain` lists no `.kicad_mod` file outside `tests/data`; `openspec validate c0027-build-properties-vendoring --strict --no-interactive` passes.
- [x] 8.2 Update the evidence labels from the results:
  - `H-K-VENDOR-GLOBAL` becomes `KICAD-VERIFIED (9.0.x, 10.0.x)`, or is refuted.
  - `H-K-VENDOR-SHADOW` becomes `KICAD-VERIFIED (9.0.x, 10.0.x)`, or is refuted, and `docs/dsl.md` follows.
  - `H-K-VENDOR-PROPS` becomes `KICAD-VERIFIED (9.0.x load, 10.0.x load and re-save)`, or is refuted.
  - `H-K-VENDOR-DUPNAME` becomes `KICAD-VERIFIED (10.0.x)`, or is refuted, and the reserved names stay.
  - `PROPERTY_EVIDENCE`, `VENDOR_EVIDENCE` and `BUILD_EVIDENCE` stay `INFERRED`. A refuted row keeps its id and gets a successor with the suffix `-2`. The labels in `board.md` and `libraries.md` are updated to match, and `H-K-LIB-CONFIGHOME` (c0021) gets the shadow controls as supporting data.

  Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_format_facts.py tests/unit/test_hypotheses_register.py`; the updated rows appear in `docs/hypotheses.md`.
- [x] 8.3 Add to `CHANGELOG.md` under Unreleased: "Build properties and vendoring: DSL parts take `properties={…}` (printable text, reserved KiCad and Fenolite names refused), written as hidden properties after `fenolite.path` and read back unchanged; `fenolite build` copies the placed footprints of every library row (project, global, template) into `lib/` with project rows, so built projects pass `kicad-cli`'s library check in isolation (`--vendor project` keeps the old rule); new codes `build.property-reserved`, `build.property-invalid`, `build.property-conflict`, `build.vendor-unsafe-name` and `build.library-changed`". Proof: `git diff CHANGELOG.md`.
