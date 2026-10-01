## 1. Sources, hypotheses, provenance and format page

- [x] 1.1 Register sources and hypotheses. This is the first commit of the implementation, so c0014's cited-id guard sees the ids registered. c0014 lands first (batch order): the proof runs its `tests/unit/test_hypotheses_register.py`. Unticked in review on 2026-10-01, because that file does not exist yet and the proof exits 4. Rows already added stay; check them against the design tables, which review changed (`H-K-PCB-READ`, `H-K-PCB-POS`, `H-K-PCB-UUID`, `H-K-PCB-ZONE`, `H-K-UUID-KEEP`, S-0010), and tick only after the proof passes.
  - Add row S-0050 to `docs/evidence/sources.md` from the design table, with the consultation date and the licence the page states, or "not stated". If its URL is already registered, cite that id and leave S-0050 unused.
  - Widen the "used for" cells of S-0022 and S-0037 (`pcb export pos`, `pcb export ipcd356`, `pcb upgrade --force`), of S-0038 (the whole pcbnew 10.0 page: footprint attributes, layer types and user names, rule areas, zone properties) and of S-0010 (pcbnew 9.0 page: footprint attributes, layer types, rule areas).
  - Add rows `H-K-PCB-READ`, `H-K-PCB-POS`, `H-K-PCB-UUID`, `H-K-PCB-ZONE` and `H-K-UUID-KEEP` to `docs/hypotheses.md`, with backend `kicad`, level `INFERRED`, the test (placeholder ids included) and the criterion from `design.md`, and result `pending`.
  - Add the paragraph "Change c0009 (KiCad board backend, part 1) adds …".

  Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py`; `grep -c '^| H-K-PCB-' docs/hypotheses.md` prints `4`.
- [x] 1.2 Add rows to `src/fenolite/backends/kicad/PROVENANCE.md` with "how used" `facts only` or `oracle`:
  - board structure and common syntax (S-0001, S-0021);
  - layer numbering, net form and island flag (S-0030, S-0033);
  - token placement (S-0039);
  - footprint attributes, layers and rule areas (S-0010, S-0038);
  - 9.0 features (S-0050);
  - `pos`, IPC-D-356 and `pcb upgrade` (S-0019, S-0020, S-0022, S-0037).

  Add a `LEGAL-ANNEX.md` session row dated in the ISO week of the work. Proof: `uv run pytest tests/unit/test_provenance.py`.
- [x] 1.3 Write `docs/formats/kicad/board.md` in Fenolite's own words: the classification table of design Decision 4, both net forms, the layer-kind table (the `*.Adhes` row and the fallback labelled as Fenolite choices), the pad frame and angle pair, wildcard expansion, zones and island flags, rule areas, number rules, ids and the issue codes. Every fact carries a source id, a label and, below the verified levels, a hypothesis. No KiCad source file is read except S-0030 (version constants and dated feature notes) and S-0033 (single keyword names), for facts only. Code in groups 5 to 7 is written from this page. Proof: `uv run pytest tests/unit/test_format_facts.py tests/unit/test_provenance.py`.

## 2. Backend protocol, registry and capabilities

- [x] 2.1 Implement `src/fenolite/backends/base.py` (`BackendOperation`, `ReadResult` with its `design` property, `CapabilityReport` with `to_json`, `Backend`) and `src/fenolite/backends/registry.py` (`register`, `get`, `all_backends`, `for_path`, lazy built-in registration). Fix `tests/unit/test_import_graph.py::_pattern` so that `backends.base` and `backends.registry` map to the `backends` row. Write `tests/unit/backends/test_registry.py`, including `test_base_imports`. Proof: `uv run pytest tests/unit/backends/test_registry.py tests/unit/test_import_graph.py`, covering the scenario "Duplicate registration" of "Backend registry", "Base module stays neutral" of "Backend protocol", and "Backend modules in the layering test". The registry scenarios that need `KicadBackend` belong to task 2.2.
- [x] 2.2 Implement `src/fenolite/backends/kicad/backend.py` (`KicadBackend`, `CAPABILITIES`). For now `read` dispatches to `read_footprint` and `read_symbol_library`; the board path is wired in task 6.1. Fill `result.backends` in `cli/cmd_capabilities.py`, and describe it under "Discovery" in `docs/cli-contract.md`. Write `docs/adr/0002-kicad-file-backend.md` (Decision 21), add its row to `docs/adr/README.md`, and add it to `REQUIRED` in `tests/unit/test_adrs.py`. The tests pin this change's exact values (`read_kinds == ("kicad_pcb", "kicad_mod", "kicad_sym")`, `write_kinds == ()`, `targets == ()`, `default_target is None`, `downgrade == "unsupported"`, `operations == ("detect", "read")`); c0017, c0018 and c0010 update them. Proof: `uv run pytest tests/unit/backends/test_registry.py tests/unit/cli/test_capabilities_backends.py tests/unit/test_adrs.py tests/consistency -q` and `uv run pyright src`, covering "Backend protocol", the scenarios "Built-in backend listed", "Unknown backend" and "Backend for a path" of "Backend registry", "Capability reports" (its invariant scenario through task 7.2) and "Backends in capabilities" except the tool-path scenario (task 3.1).

## 3. `kicad-cli` runner and IPC-D-356 parser

- [x] 3.1 Implement `src/fenolite/backends/kicad/cli.py` per design Decision 2: `find_kicad_cli`, `KicadCli` (`version`, `major`, `run`), `CliRun`, the helpers, `KicadCliError` and `KicadCliVersionError`. Point `cli/cmd_capabilities.py` and `tests/_resources.kicad_cli()` at `find_kicad_cli`, and make `tests/unit/cli/test_capabilities.py` patch `cli.MACOS_KICAD_CLI` instead of the removed `cmd_capabilities._MACOS_KICAD_CLI`. Write `tests/unit/backends/kicad/test_cli_runner.py` against a fake `kicad-cli` script in `tmp_path`. Proof: `uv run pytest tests/unit/backends/kicad/test_cli_runner.py tests/unit/cli/test_capabilities_backends.py -k "runner or tool_path"`, covering every scenario of "Package kicad-cli runner" and "Same kicad-cli as before"; `uv run fenolite capabilities --json` reports the same `kicad-cli` path and version as before on the local machine.
- [x] 3.2 Move the IPC-D-356 parsing out of `tests/kicad/test_geometry_frame.py` into `src/fenolite/backends/kicad/ipcd356.py` (`read_ipcd356`, `Ipcd356`, `Ipcd356Record`), and make the test import it. Write `tests/unit/backends/kicad/test_ipcd356.py` with authored texts. Proof: `uv run pytest tests/unit/backends/kicad/test_ipcd356.py`; `uv run pytest tests/kicad/test_geometry_frame.py` on the local KiCad 10.0.6.

## 4. Model deltas

- [x] 4.1 Add `FootprintAttribute` and `FootprintInstance.attributes`, `ViaType` and `Via.via_type`, `ZoneFill.island` and `Zone.name` to `src/fenolite/model/board.py`. Add the `model.duplicate-ref` warning rule to `Design.validate()`. Regenerate `schemas/fenolite.model.v0/board.json`, and add a section "Boards read from a backend" to `docs/design-model.md` that links the normative text. Write `tests/unit/model/test_board_import.py`. Proof: `uv run python tools/gen_schemas.py --check`; `uv run pytest tests/unit/model tests/unit/test_schema_drift.py`, covering the model scenarios of "Board entities read from file backends" and the validation scenarios of "Components synthesised from a board".

## 5. Shared footprint mapping, layers and the authored board

- [x] 5.1 Move the pad, drill, padstack and graphic mapping and `_Ids` from `mod.py` to `src/fenolite/backends/kicad/_fpmap.py`, parameterised by root chain, graphic heads and kept-opaque code (Decision 18). Add `Context.kept_code` to `_libread.py`, and add the field emitters and `angle_atom`. Implement `src/fenolite/backends/kicad/layers.py` (`LAYER_KINDS`, `layer_kind`, `is_canonical`, `expand_layers`). Proof: `uv run pytest tests/unit/backends/kicad/test_mod.py tests/unit/backends/kicad/test_mod_pads.py tests/unit/backends/kicad/test_layers.py` with the two `mod` test files unchanged (`git diff --stat tests/unit/backends/kicad/test_mod*.py` is empty).
- [x] 5.2 Author `tests/data/kicad/board/two_layer.kicad_pcb` with the content of Decision 19, and declare it `origin = "authored"` in `tests/data/MANIFEST.toml`. Write `tests/kicad/board/test_board_loads.py::test_fixture_loads`, which uses `KicadCli.load_board_svg`. Proof: `uv run pytest tests/corpus/test_manifest.py tests/residue -q`; `FENOLITE_REQUIRE=kicad uv run pytest tests/kicad/board/test_board_loads.py -k fixture` on the local KiCad 10.0.6. The 9.0.9 load runs in the `kicad-9` job (image `kicad/kicad:9.0.9@sha256:e638b79b0321f29395a5b783e94bb9f3c73303e8da15da27b8f5cb4b67a37729`), checked by the proof of task 8.3, because that image has no `pytest` for a local run.

## 6. Board reader (`backends/kicad/pcb.py`)

- [x] 6.1 Implement the frame of `read_board`:
  - inputs and version policy;
  - header values in `Board.ext["kicad"]` and the root slot list;
  - the `layers` table;
  - nets in both forms, with `kicad.board.unknown-net`.

  Wire `KicadBackend.read` for boards. Proof: `uv run pytest tests/unit/backends/kicad/test_pcb_read.py tests/unit/backends/kicad/test_pcb_nets.py`, covering "Layer table and layer kinds" and the scenarios "Foreign root", "KiCad 7 board refused", "Future board read but not editable" and "Numbered table". Task 6.3 adds the scenarios that need mapped items to these files.
- [x] 6.2 Map footprints and their pads through `_fpmap` (pad frame and angle pair of Decision 5, wildcard expansion, attributes, lock and property projection), and synthesise the circuit (components, pins, pin-type table, net members) per Decision 12. Proof: `uv run pytest tests/unit/backends/kicad/test_pcb_footprints.py tests/unit/backends/test_registry.py`, covering "Board footprints and the pad frame", "Read results", the circuit scenarios of "Components synthesised from a board" and "Inventory rows match inside boards" of "Shared footprint mapping" (through task 7.2).
- [x] 6.3 Map `segment`, `arc`, `via`, `zone` (zones, rule areas, teardrop zones kept opaque, fills with island flags, opaque outlines), `gr_*` and `gr_text`, with `Board.outline = None`. Proof: `uv run pytest tests/unit/backends/kicad/test_pcb_items.py tests/unit/backends/kicad/test_pcb_read.py tests/unit/backends/kicad/test_pcb_nets.py`, covering "Modelled board content", "Zones, fills and rule areas", "Unmodelled board content is kept as slots", and every scenario of "Board file reading", "Board version policy" and "Nets in both forms".
- [x] 6.4 Implement the ids of Decision 11 (occurrence suffix, `kicad.board.duplicate-uuid`), the number policy of Decision 10 (inexact lengths and angles), and `ISSUE_CODES`. Proof: `uv run pytest tests/unit/backends/kicad/test_pcb_numbers.py`, covering "Exact numbers on boards", "Identifiers of board items" and "Board read issue codes".

## 7. Same-version rebuild

- [x] 7.1 Implement `ModelSource`, `EmitContext`, `model_source`, the read-time emitter check of Decision 7, `rebuild_board` (collections matched by locator index, entities without slots refused), `opaque_count` and `opaque_digests`. Proof: `uv run pytest tests/unit/backends/kicad/test_pcb_rebuild.py tests/unit/backends/kicad/test_slots.py`, covering "Modelled children are reproducible", "Same-version rebuild" and "Opaque count and digests".
- [x] 7.2 Apply the spec review of 2026-10-01 to the finished groups 2 to 7:
  - `tests/unit/backends/test_registry.py::test_capability_invariants` ("Unavailable operations are visible");
  - `upgrade_board` returns the copy's bytes when the re-save is byte-identical, with `test_cli_runner.py` covering "Unchanged re-save";
  - zone and rule-area wildcard layers expanded and projected, with `test_pcb_items.py` covering "Wildcard rule-area layers";
  - `test_pcb_footprints.py` covering "Inventory rows match inside boards" (file kind `kicad_pcb`, full chain);
  - `test_pcb_numbers.py::test_closed_set` limited to `read_board` issues, with `model.*` codes allowed only in `ReadResult.issues`;
  - RT1 (b) reading both sides from text in `test_pcb_rebuild.py`.

  Proof: `uv run pytest tests/unit/backends -q -k "capability_invariants or unchanged_resave or wildcard_rule_area or inventory_rows or closed_set or rt1"` and `uv run pytest tests/unit/backends -q`.

## 8. Corpus and oracle evidence

- [x] 8.1 Write the corpus tests:
  - `tests/corpus/test_board_read.py`: every non-heavy `rt0` board at format 8.0 or newer (the 16 non-heavy 10.0.6 demos and the 5 readable 9.0.9.1 demos, 21 boards) reads with no error issue from `read_board`. The third-party rows (`rt0`, below the read floor) raise `UnsupportedFormatError` with the `pcb upgrade` hint. The malformed row `kicad-demo-9-0-9-1-pcb-04` raises `FormatError` when it is cached; the `kicad-10` job fetches only `--uses rt0`, so this check is skipped there unless the fetch adds `--uses malformed`. `Design.validate()` findings are counted, not asserted (Decision 20).
  - `tests/corpus/test_board_rt1.py`: the three RT1 conditions on the same 21 boards.
  - `tests/corpus/test_board_census.py`: per origin, inexact numbers by context, kept-opaque reasons, uuid repeats, zone outlines, `Design.validate()` findings by code and severity, the 9.0.9.1 header census and the `pintype` values. Results go only to `FENOLITE_CENSUS_OUT`.

  Proof: `FENOLITE_CENSUS_OUT="$(mktemp -d)/census.json" uv run pytest tests/corpus/test_board_read.py tests/corpus/test_board_rt1.py tests/corpus/test_board_census.py -q` with the corpus fetched; `git status --porcelain` is unchanged afterwards.
- [x] 8.2 Write `tests/kicad/board/test_board_upgraded.py` (`kicad_min_major(10)`, `needs_corpus`). It makes `pcb upgrade --force` copies of the upgrade set of Decision 16 (the 16 non-heavy 10.0.6 demos and the 3 third-party boards; the 9.0.9.1 demos and the malformed row are not upgraded). `test_upgraded_read_rt1` reads every copy with no error issue from `read_board` and checks RT1. `test_uuid_keep` compares the 16 demos with their copies. `test_upgraded_census` runs the census of task 8.1 on the third-party copies as origin `third-party`, written only to `FENOLITE_CENSUS_OUT`. Extend `test_board_loads.py` to rebuilt corpus boards. Proof: `FENOLITE_CENSUS_OUT="$(mktemp -d)/census.json" FENOLITE_REQUIRE=kicad,corpus uv run pytest tests/kicad/board/test_board_upgraded.py tests/kicad/board/test_board_loads.py -q` on the local KiCad 10.0.6, covering "Upgraded copies keep their origin" and the scenarios "Rebuilt boards load" and "uuids survive a KiCad re-save"; `git status --porcelain` is unchanged afterwards.
- [x] 8.3 Write `tests/kicad/board/_frame.py` (`pos` CSV parsing, frame conversion, pad matching per Decision 17) and `tests/kicad/board/test_board_frame.py` (`test_pos`, `test_ipcd356`, the negative control with a wrong `D1` rotation). Pad matching counts and skips via records, takes the origin from a matched pad record, keys on the truncated reference and pin, and pairs ambiguous keys by nearest position. Run them on the demos (`needs_corpus`) and on the authored board. Record for the census the export frame, the bottom-rotation rule, the `R` fields, and the counts of via records, truncated keys and ambiguous keys. Proof: `uv run pytest tests/kicad/board -q` on the local KiCad 10.0.6 with the corpus, covering "Typed board reads agree with kicad-cli exports" and the `design-model` scenario "Absolute pad position of a bottom footprint"; `gh pr checks` shows `kicad-9` and `kicad-10` passing. The `kicad-9` job is the 9.0.9 run, because the pinned 9.0.9 image has no `pytest`.

## 9. Closing

- [x] 9.1 Run the residue and full test suites. Add a `LEGAL-ANNEX.md` row for every further ISO week in which `backends/` or `docs/formats/` changed. Proof: `make check`; `uv run pytest tests/residue` and `uv run pytest -q` exit 0; `uv run python tools/residue/scan.py` exits 0; `uv run python tools/gen_schemas.py --check` exits 0; `openspec validate c0009-kicad-board-backend --strict` passes.
- [x] 9.2 Update the evidence labels from the results:
  - `H-K-PCB-READ` becomes `CORPUS-VERIFIED` (origins `kicad-demos` and `third-party` through upgraded copies, as its result states) or is refuted. Its result also records the `Design.validate()` error counts per board.
  - `H-K-PCB-POS` (placements and pads) becomes `KICAD-VERIFIED (9.0.x, 10.0.x)`, or is refuted for bottom rotation only, with a successor row (suffix `-2`) that records the observed rule. Its result records the via, truncated-key and ambiguous-key counts of `test_ipcd356`.
  - `H-K-UUID-KEEP` records the demo half as `KICAD-VERIFIED (10.0.x)`, with the Fenolite-written half pending in c0017.
  - `H-K-PCB-UUID` and `H-K-PCB-ZONE` get their counts per origin (native demos; upgraded third-party copies). Each becomes `CORPUS-VERIFIED` only when both origins give 0; otherwise it stays `INFERRED` with the counts.
  - `H-K-UNIT` becomes `CORPUS-VERIFIED` only when both origins give 0 inexact lengths in length contexts. Otherwise it is refuted, with a successor row with suffix `-2`, limited to length contexts and carrying the counts per origin.
  - `H-G-ANGLE` and `H-K-SEXPR-NUM-CORPUS` get the census by context.
  - Supporting data goes to `H-G-BOTTOM-PLACE`, `H-G-PAD-ANGLE-ABS` (`R` fields), `H-G-FLIP` (bottom-rotation rule) and `H-K-TOK-CONSTANTS` (board 9 headers).
  - Copy the counts into `docs/evidence/kicad-board-read.md` (public numbers only), and update the labels in `docs/formats/kicad/board.md` to match. `pcb.EVIDENCE` stays `INFERRED`.

  Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_format_facts.py tests/unit/test_hypotheses_register.py`; the updated rows appear in `docs/hypotheses.md`.
- [x] 9.3 Add to `CHANGELOG.md` under Unreleased: "KiCad board backend, part 1: backend protocol and registry (`capabilities` lists backends), a package `kicad-cli` runner on temporary copies, and a typed `.kicad_pcb` reader for 8.0 and newer with lossless slots, same-version rebuild (RT1) over the demos and upgraded third-party boards, and placements and pads confirmed by `kicad-cli` exports on 9.0 and 10.0". Proof: `git diff CHANGELOG.md`.
