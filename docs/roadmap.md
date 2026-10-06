# Roadmap to 1.0

Status on 2026-10-06. Released: `0.0.1.dev0` (2026-09-30, pre-alpha), `v0.1.0` (2026-10-05) and
`v0.2.0` (2026-10-06), one release for v0.2a (c0060–c0068) and v0.2b (c0069–c0074), with the
maintainer's verdict in `docs/release/v0.2.md` (change c0093).

This page is a map, not a spec. What is built, and how, is decided change by change in
`openspec/changes/`. An id that is not yet a folder there is an estimate, and so is every budget.

## How to read this page

- **Change ids.** Every change is `cNNNN-<slug>` in `openspec/changes/`. Done changes are archived
  in `openspec/changes/archive/`.
- **Plan items and split-offs.** Items of the project plan keep their numbers (c0009–c0016).
  Split-offs, follow-ups and changes for unowned plan deliverables (c0024, c0025) take c0017 and
  later, in implementation order. The id table is in [`openspec/README.md`](../openspec/README.md),
  section "Change ids" (c0014 design, Decision 14). A slug may still change until its change is
  proposed.
- **States.**

  | state | meaning |
  |---|---|
  | done | archived in `openspec/changes/archive/` |
  | being implemented | proposed, and tasks are being ticked in its `tasks.md` |
  | proposed | `proposal.md`, `design.md`, `specs/` and `tasks.md` exist; no task done |
  | being proposed | drafts exist; not yet in `openspec/changes/` |
  | roadmap | id and slug reserved in the id table (the slug may still change); dependencies and days are planning estimates; not proposed |
  | estimate | id range and scope are estimates (every id after c0031) |

- **Sizes.** Each change has a size in design-days: the effort a person would need, estimated in its
  `design.md` (section "Budget") once proposed. Sizes rank changes and order cuts. They are not
  calendar time: the work is done by agents, and calendar time comes from the measured pace (see
  [Time and pace](#time-and-pace)). The project plan counts calendar weeks at about 60 % dedication,
  which is about 3 working days a week.
- **Milestones** are releases (`v0.1`, `v0.2a`, …). A phase groups milestones.

## Milestones

| phase | milestone | changes | scope | state |
|---|---|---|---|---|
| 1. Foundations | — (`0.0.1.dev0` was cut after c0004) | c0001–c0005 | repository, CLI contract, IP hygiene, neutral model, geometry kernel | done |
| 2. KiCad PCB | v0.1 | c0006–c0031 | an agent closes the loop on a KiCad board | every change archived; v0.1.0 released on 2026-10-05 |
| 3. KiCad complete | v0.2a | c0060–c0068 | schematic read and write, ERC oracle, netlist, BOM and placement tables, manifest, inspection commands, evidence matrix, v0.1 follow-ups | every change archived (2026-10-05 and 2026-10-06); released in `v0.2.0` on 2026-10-06 |
| 3. KiCad complete | v0.2b | c0069–c0074 | complete layout lens and `placements.toml`, one schematic sheet per module and a readable layout, full rule kinds, parity, typed interfaces and quantities, the user's drawing sheet, v0.1 follow-ups | every change archived; released in `v0.2.0` on 2026-10-06 |
| 4. Second backend | v0.3 | c0039–c0047 | read, equivalence levels 1–4, analyses | every change archived (c0039–c0047); in the `0.2.0` package, with no acceptance claimed for the milestone (`docs/release/v0.2.md`, “Also in this package”) |
| 4. Second backend | v0.4 | c0032–c0038 pulled forward; c0083–c0092 | write, equivalence level 5, verification kit | c0032–c0038, c0053, c0055 and c0056 done; c0083–c0092 proposed on 2026-10-06 |
| 5. To 1.0 | v0.5a, v0.5b, v0.6, v1.0 | not allocated | conversion, MCP server, freeze | estimate |

About 70 changes to 1.0 on this map, or about 61 with the proposed cuts (see
[Proposed cuts](#proposed-cuts-for-a-leaner-10)).

## Phase 1: foundations (done)

| id | slug | scope |
|---|---|---|
| c0001 | `repo-bootstrap` | repository layout, stdlib-only package, licence and notices, CI baseline |
| c0002 | `cli-contract` | JSON envelope, exit codes, `--dry-run`/`--confirm` (`docs/cli-contract.md`) |
| c0003 | `ip-hygiene` | clean-room rules, provenance, residue scan (`docs/provenance.md`) |
| c0004 | `design-model-core` | neutral model, ids, units, canonical JSON (`docs/design-model.md`) |
| c0005 | `geometry-kernel` | exact integer geometry (`docs/geometry.md`) |

c0001–c0004 were archived on 2026-09-30, c0005 on 2026-10-01.

## Phase 2: KiCad PCB to v0.1 (c0006–c0031)

**v0.1 goal.** An agent closes the loop on a KiCad board, headless, for KiCad 9.0 and 10.0:
`build` → `place` → `route` → `fill` → `check` → `export` → `render`, with the layout kept across
rebuilds.

| id | slug | scope | state | depends on | days |
|---|---|---|---|---|---|
| c0006 | `kicad-sexpr-slots` | S-expressions, slots, corpus, `kicad-10` CI job | done | — | — |
| c0007 | `kicad-tokens` | format versions, token inventory, `kicad-9` CI job | done | — | — |
| c0008 | `kicad-libs` | footprint and symbol libraries, library tables | done | — | — |
| c0009 | `kicad-board-backend` | board reader, backend protocol, `kicad-cli` runner | done | c0014 | 7.75 |
| c0010 | `kicad-project-file` | `.kicad_pro` writer, net classes | done | c0017, c0018 | 6.5 |
| c0011 | `dsl-thin-build` | thin Python DSL and `build` | done | c0010, c0017, c0018 | 8.5 |
| c0012 | `sheet-templates-kicad` | sheet templates to `.kicad_wks` | done | c0010, c0017 | 9.5 |
| c0013 | `kicad-oracle-and-check` | read-only `check` v0, `inspect`, `doctor` | done | c0010, c0011 | 8.5 |
| c0014 | `verification-evidence` | hypothesis-register guard, label grammar, release rule | done | — | 3 |
| c0015 | `zone-fill` | zone fill through `kicad-cli` 10 for both targets; fills read back from the saved board and merged by zone uuid, RT1 kept; `fill` command, `zone.fill` check stage, container runner | done | c0013, c0019, c0031 | 6 |
| c0016 | `routing-plugins` | routing protocol, `route` command, KiCadRoutingTools plugin and its feasibility gate | done; gate and full CI passed on KiCad 9.0.9 and 10.0.6 | c0015, c0020, c0022 | 7.5 |
| c0017 | `kicad-board-writer` | board writer for 9.0 and 10.0 | done | c0009, c0014 | 7.75 |
| c0018 | `kicad-rules-footprints` | footprint and custom-rules writers | done | c0017 | 5.75 |
| c0019 | `layout-preserve` | layout kept across rebuilds | done | c0011, c0013, c0027 | 8.25 |
| c0020 | `check-netlist-drc` | DRC findings, netlist compare, corpus RT2, negative tests | done | c0013 | 8.75 |
| c0021 | `kicad-libs-cache` | library fetch, cache, resolution probes | done | c0017, c0019, c0027 | 9.5 |
| c0022 | `placement-grid` | manual and grid placement; pre-write legality check (courtyard overlap, outside the outline, edge clearance) | done | c0019, c0028, c0030 | 6 |
| c0023 | `specctra-freerouting` | Specctra DSN/SES, Freerouting plugin (time-boxed; first in the cut order; needs ADR-0006) | done | c0016 | 10 |
| c0024 | `manufacturing-exports` | `export` and `render` through `kicad-cli`, the artefact manifest, opt-in `render` check stage | done | c0013 | 5.25 |
| c0025 | `release-v0-1` | second example board, acceptance loop on both majors, agent guide, CI matrix and `wheel` job, release record | done; v0.1.0 released on 2026-10-05 with the maintainer's verdict (`docs/release/v0.1.md`) | every v0.1 change | 5.75 |
| c0026 | `kicad-board-minimums` | board-setup minimums written from board-wide rules | done | c0010 | 6.5 |
| c0027 | `build-properties-vendoring` | user properties on built footprints; footprints of every library row vendored | done | c0011 | 5.25 |
| c0028 | `board-frame-copper` | pads and courtyards in the board frame; script copper (tracks, vias, stitching) | done | c0019, c0021 | 21.5 |
| c0029 | `copper-check` | Fenolite's own short and clearance check, build guard, via re-net probe | done | c0020, c0026, c0028 | 12 |
| c0030 | `footprint-fields` | Reference, Value and other footprint fields: placed, read, written, kept | done | c0019, c0028 | 10.25 |
| c0031 | `zone-settings` | typed zone settings, pad zone connection, target-9 fill outline fix | done | c0019, c0028 | 8 |
| c0049 | `test-speed` | parallel test runs, `make check-fast` | done | — | 2 |
| c0050 | `transform-composition-bound` | the true bound of two successive transforms | done | — | 0.5 |
| c0051 | `drc-canary-repeatability` | KiCad's clearance report limit; the two-run canary test | done | — | 2 |
| c0052 | `release-hygiene` | capability evidence, packaging metadata, contract and provenance docs | done | — | 1.5 |
| c0053 | `altium-script-copper` | script copper in the Altium build | done | c0038 | 2 |
| c0054 | `dsl-rule-constructor` | design minimums declared in the script | done | c0011 | 3 |
| c0055 | `dsl-footprint-authoring` | footprints authored in the design script | done | c0011 | — |
| c0056 | `dsl-pin-pad-map-slots` | symbol pin to pad maps, slotted pads | done | c0055 | — |

- c0006–c0009 and c0014 were archived on 2026-10-01; c0017, c0018, c0010, c0011 and c0012 on 2026-10-02.
- Implementation order from here: c0032 (the experimental Altium schematic writer, see Phase 4) →
  c0026 → c0027 → c0013 → c0019 → c0020 → c0021 → c0028 → c0029 → c0030 → c0031 → c0015 → c0022 →
  c0016 → c0023 → c0024 → c0025. Changes archive in
  the same order, because several of them modify requirements that an earlier one adds; each design
  states its archive-order dependencies.
- The last column is the size in design-days: from the designs ("Budget") for proposed and done
  changes, planning estimates for roadmap changes. On 2026-10-05 every v0.1 change is done and
  v0.1.0 is released. c0049 to c0056 joined v0.1 on 2026-10-04 (loose ends found by the v0.1
  audit, and DSL work of the other agent); c0055 and c0056 give no size in their designs.

**Gaps found by the dogfood board.** On 2026-10-02 a testing agent built a real board (a 12–24 V to
5 V / 3 A buck converter) only through Fenolite's public API. c0026–c0031 come from what it could not
do:

| finding | owner |
|---|---|
| Reference and Value fields cannot be moved, rotated, hidden or put on another layer | c0030 |
| no extent of a placed footprint; no pre-write check for courtyard overlap or parts off the board | c0028 (extent), c0022 (check) |
| no Fenolite check for shorts and clearance; reported: KiCad silently re-nets a via that touches a track of another net, and its DRC shows no short | c0029 |
| zone clearance, pad connection and thermal reliefs are not in the model | c0031 |
| pads only in the footprint frame; power copper drawn from hand-computed coordinates | c0028 |
| BOM and placement files in an assembly house's columns | c0064 (the user writes the column template; none ships) |
| part numbers and other user properties cannot be written onto footprints | c0027 |
| footprints from the official libraries fail the library check of an isolated `kicad-cli` | c0027 |
| how fills computed by `kicad-cli` come back into the model | c0015 |
| the fab's minimums are not written to the board setup | c0026 |

**v0.1 acceptance** (project plan, shortened):

1. Two example boards: DRC exit 0 on 9.0 and 10.0; netlist compare with 0 differences; two
   negative tests (a reassigned pad, a track between nets) caught with location; RT1 equals the
   model; `build` twice gives identical bytes, fill and routing kept; a footprint moved in the GUI
   survives a rebuild.
2. Every KiCad demo (9.0 and 10.0 tags) and the public third-party boards pass RT0, RT1 and RT2.
3. Routing by either plugin leaves 0 unconnected items on the small example, judged by KiCad's DRC.
4. One generated `.kicad_wks` is accepted by `--drawing-sheet` for A3 and A4.
5. CLI consistency 100 %; every output validates against the `v0` schemas; `pip install fenolite`
   pulls no dependency; `doctor` reports `kicad-cli`, Java or Docker, and the subcommand matrix.
6. `check` on a demo project is read-only.
7. An agent completes the loop on the small example in 10 turns or fewer, every output labelled.
8. Token fuzz on both KiCad images. Met in c0007.

Round-trip levels: RT0, the S-expression tree is identical; RT1, model → KiCad → model is
identical; RT2, `kicad-cli pcb drc` reports the same violations before and after.

Round-trip levels of the second backend (change c0044, `docs/evidence/altium-roundtrip.md`): RT-A0, a
copy of a compound file keeps every storage and every stream, byte for byte; RT-A1, reading a file and
encoding what was read gives equal records in every stream; RT-A2, model → Altium → model is equal on
what the writers write, within 2 nm, on Fenolite's own builds.

## Phase 3: KiCad complete (v0.2a, v0.2b)

**v0.2a goal.** A built project has a schematic that KiCad's ERC and its schematic parity test accept
on 9.0 and 10.0, `check` judges it with KiCad's own ERC, and the flow gets its tables, its manifest
and the commands an agent asks small questions with.

**v0.2a, c0060–c0068.** All nine were proposed on 2026-10-04 and 2026-10-05 and are archived: four on
2026-10-05 and five on 2026-10-06.

| id | slug | scope | state | depends on | days |
|---|---|---|---|---|---|
| c0060 | `kicad-schematic-reader` | `.kicad_sch` read into a sheet model, same-version rebuild, demo schematics in the corpus, load checks through `kicad-cli` | done; archived on 2026-10-05 | — | 11 |
| c0061 | `kicad-schematic-writer` | `build` writes `<name>.kicad_sch`, the project symbol libraries and `sym-lib-table`; no-connect flags from `Circuit.no_connects` (c0036), power flags, net names in KiCad's stored form, pad nets of unconnected pins | done; archived on 2026-10-05: ERC and parity without a finding on both examples and on both majors; the maintainer ran "Update PCB from Schematic" once in 10.0.6 (`H-K-SCH-UPDATE`, still `INFERRED`) | c0060 | 14 |
| c0062 | `erc-oracle` | KiCad's ERC as a stage of `check`, in place of the three-rule ERC stage; schematic parity in the DRC stage | done; archived on 2026-10-06: `erc.kicad` and the parity findings proved on 9.0.9 and 10.0.6; schematic RT2 compares the kinds of ERC violations, because KiCad names another item for one violation from run to run | c0060, c0061 | 8.5 |
| c0063 | `netlist-compare` | the schematic's netlist in `check`; Fenolite's own netlist of the schematics it generates, compared with the circuit at build and with `kicad-cli` in the oracle tests; `netlist` command | done; archived on 2026-10-06: the own netlist equals the export of `kicad-cli` on 9.0.9 and 10.0.6 | c0060, c0061 | 6.75 |
| c0064 | `bom-pnp-templates` | BOM and placement tables with a user-supplied column template (names, order, units, rotation offsets, side names, grouping); `bom` and `pnp` commands. No template of any assembly house ships with Fenolite | done; archived on 2026-10-05 (the BOM through `kicad-cli` came after c0061) | c0061 for the BOM through `kicad-cli` | 7 |
| c0065 | `artifact-manifest-states` | the project manifest, with SHA-256 and a state per artefact; `manifest` command | done; archived on 2026-10-06: the schematic reaches `native-verified` since the ERC stage of c0062 | c0062 for `native-verified` on the schematic side | 5 |
| c0066 | `cli-inspection-commands` | `diff`, `roundtrip`, `fmt`, `explain`, `restore`; paging and concise output; `net`, `region` and `neighbors` | done; archived on 2026-10-06: RT2 of a schematic followed c0062 | none | 13.5 |
| c0067 | `evidence-matrix` | the evidence matrix in `capabilities` and on a generated page; every backend module declares its evidence | done; archived on 2026-10-05; implemented before c0061 and c0065: a module they add meets the guard, whose message says what to declare | best last | 5 |
| c0068 | `v01-followups` | the shape offset of a pad in the board frame; a zone's own clearance in the copper check; pad zone connection, arcs and via kinds in the DSL; `pads` command; `macos-app` nightly job | done (archived on 2026-10-06: probes confirmed on 9.0.9 and 10.0.6, first `macos-app` run green) | — | 9.75 |

- Implementation order: c0060 → c0061 → c0062, c0063 and c0064 (independent of each other; c0063
  archives after c0061) → c0065. c0066 and c0068 depend on none of these for most of their parts and
  can run beside them. c0067 goes last, so that its audit covers the modules the others add.
- Requirements modified in chains: c0062 modifies `verification-loop` requirements that c0044
  also modifies, and c0063 modifies one that c0061 modifies. Each design states the rule: the change
  that lands second re-bases on the first. The two requirements that c0066 and c0044 both added are
  settled: c0044, implemented after c0066, adds requirements of other names that extend c0066's
  ("Model difference scope", "Diff of document inputs and the records view").
- Found while measuring for c0068: KiCad moves a pad's copper, not its hole, by the offset of the
  pad's drill. v0.1's board frame does the opposite, so `check` reports clearance errors that do not
  exist on boards with such pads. c0068 repairs it first.
- Follow-ups of v0.1 taken by c0068: the pad shape offset (35 false clearance findings on one demo
  board, none after the repair); the zone's own clearance between a fill and a track, an arc, a via or
  a pad (it adds one finding over the 21 demo boards, none on those of tag 10.0.6);
  `Part.zone_connection`; `arc_to` and `kind=` for vias; the `pads` command; the `macos-app` job.
- Follow-ups not taken by c0068 (its design, Decision 13), and where they go: the rule kinds for
  annular width, hole-to-hole, hole clearance, zone connection and silk clearance go to v0.2b with
  the full rules (c0071); export presets, the outline snapping tolerance with the edge items of
  footprints, and stitching that avoids zones and the board edge go to v0.2b (c0074); per-command
  result schemas go with the v1.0 freeze; `inspect` of `.kicad_pro` and `.kicad_dru` and
  `inspect --detailed` are unscheduled. Clearance overrides of pads and footprints stay out of the
  copper check: the census of c0068 found no finding that the zone's clearance adds on such a pad.
- CI jobs: `unit`, `wheel`, `kicad-9`, `kicad-10`, `routing` and `dco` run on every push and pull
  request (`.github/workflows/ci.yml`). `macos-app` (`.github/workflows/nightly.yml`, c0068) runs once a
  day and on `workflow_dispatch`: `tests/kicad` on the `kicad-cli` of the KiCad 10.0.6 macOS disk image,
  pinned by SHA-256. It is not a check of pull requests and not a merge gate; its first run settles
  `H-K-CI-MACOSAPP`.

**v0.2a acceptance** (project plan, shortened):

1. KiCad's ERC exits clean on the example projects, and its schematic parity test has no finding.
2. Fenolite's netlist equals `kicad-cli`'s on every schematic Fenolite generates.
3. RT0, RT1 and RT2 (through ERC) on every demo schematic without buses and without symbols placed
   in several sheet instances; the rows are listed in the corpus manifest.
4. `diff` of "one footprint moved by 1 mm" shows exactly one change, and `fmt --check` is a fixed
   point over the whole corpus.
5. A BOM with the user's columns, and a manifest with SHA-256 and a state for every artefact.

**Not in v0.2a** (project plan): readable schematic autolayout and one sheet per module (v0.2b),
buses (v0.3), symbols placed in several sheet instances (v0.5b).

**v0.2b goal.** The layout survives renames and lives in the source tree, the schematic reads
like a person drew it, the rule model holds every kind of the project plan, parity and buses are
checked, and a project carries its user's frame and fab options.

**v0.2b, c0069–c0074.** All six were proposed on 2026-10-05. All six are archived.

| id | slug | scope | state | depends on | days |
|---|---|---|---|---|---|
| c0069 | `layout-lens-complete` | module and net aliases, alias matches kept under the new identity, `lens/extract.py`, `placements.toml` and `fenolite sync --to-source [--check]`, the project plan's lens acceptance fixture | done (archived on 2026-10-05, with its schematic half after c0061) | c0060, c0061 for the schematic half | 12.5 |
| c0070 | `schematic-hierarchy-layout` | one pinless sheet per module under `sheets/`, 2-pin parts snapped to IC pins with one straight wire, hierarchical footprint paths, the own netlist over the sheet tree | done; archived on 2026-10-06, after a fix for a text overlap in the blink sheet and the maintainer's reading of the rendered sheets (task 6.2) | c0060, c0061, c0063 | 13 |
| c0071 | `rules-complete` | hole-to-hole, hole clearance, annular width, courtyard, silkscreen and creepage rules, per-kind selectors and per-major support, `design.rules.rule()` and `fenolite.dsl.select` | done (archived on 2026-10-06, after the green run 37311079171) | — | 10 |
| c0072 | `schematic-board-parity` | a backend-free comparison of schematic and board and of pins and pads, `parity` command and `check` stage, agreement with KiCad's parity test on the public demos | done; archived on 2026-10-06: the counts of the own comparison equal KiCad's parity test on the public demos of 9.0.9 and 10.0.6 | c0060, c0062, c0063 | 10 |
| c0073 | `interfaces-quantities` | exact `Quantity` values, typed `I2C`, `SPI`, `UART` and `USB2` interfaces with `attach` by role, checks for pair names and pull-ups | done (archived on 2026-10-06, after the green run 37311079171) | — | 8 |
| c0074 | `drawing-sheets-followups` | the user's drawing sheet and title block on board and schematic, export presets, outline joining below 10 µm with footprint edge items, stitching that avoids keep-outs and the edge | done (archived on 2026-10-05, with its schematic half after c0061) | c0061 for the schematic key | 11.5 |

- Implementation order, as it was: c0071 and c0073 needed nothing of v0.2a; c0069 and c0074 added
  their schematic halves after c0061; c0070 and c0072 waited for the v0.2a schematic changes they
  name.
- Requirements modified in chains: c0070 modifies requirements that c0060, c0061 and c0063 add, so
  it archives after them. All three are archived. Each design states the re-base rule for its other
  chains.
- Bench findings used in the designs: a sheet file resolves from the folder of the sheet that names
  it, and a missing one is dropped without an ERC finding; KiCad pairs nets by a last character
  `P`/`N` or `+`/`-`; the schematic drawing sheet comes from its own project key; outline endpoints
  closer than 10 µm are joined. KiCad 9.0.9 reports no creepage violation where 10.0.6 does.

**v0.2b acceptance** (project plan, shortened):

1. The lens test is fully preserved: five footprints moved and three tracks routed outside
   Fenolite, a part added and a module renamed with `moved()`, also after the stand-in for “Update
   PCB from Schematic” (c0069).
2. Two overlapping rules are resolved by `kicad-cli` as the emission order predicts, now also for a
   new rule kind (c0071).
3. Parity reproduces counts of disconnected nets, missing connections and references on one side.
   The reference counts from the project plan are replaced by comparisons with KiCad's own parity
   test on public demos and authored edits (c0072).

**The release of v0.2a and v0.2b: c0093 `release-v0-2`.** One release, `0.2.0`, cut from `dev`. The
change adds no feature: it writes the release record `docs/release/v0.2.md`, one row per acceptance item
above with the test that proves it, its CI job and its result, and the limits; a guard test holds the
record to what exists; the version and the changelog are its last commit. The tag, the pull request
from `dev` to `main` and the publication are the maintainer's.

## Where KiCad ends and the second backend starts

- **KiCad is complete at the end of v0.2b** (estimate): board and schematic read and
  write for 9.0 and 10.0, `kicad-cli` as oracle for DRC, ERC, netlist and exports, full lens and
  rules.
- **After that, KiCad work is maintenance:** one pass per KiCad major (the project plan estimates
  about one week of format drift per major), and an optional IPC backend once KiCad 11 is released.
- **Second-backend reading starts with v0.3, at c0039.** The project plan keeps a
  half-day-a-week reading track inside the v0.1 and v0.2 contingency.
- **KiCad comes first because it is the second backend's oracle.** `kicad-cli pcb import` (10.0
  only) gives an independent reading of the second backend's files. `H-A-UNIT` already names this
  test, and equivalence levels 1–4 compare against it.
- The neutral model becomes additive-only at the end of v0.3 and is frozen, with migrators, at 1.0
  (ADR-0001).
- Conversion, public equivalence and downgrade need both backends, so they are in phase 5.

## Phase 4: second backend, clean-room (v0.3, v0.4; estimate)

Public docs call it the second backend. The hypothesis register (`docs/hypotheses.md`) uses the
backend tag `altium`; the labels are `ALTIUM-VERIFIED(kit)` and `ALTIUM-VERIFIED(author-report)`
(`README.md`). It is written clean-room: format facts come from public sources only and are
recorded in `docs/formats/<backend>/` (`AGENTS.md`, `LEGAL.md`, ADR-0003).

**v0.3 read, c0039–c0047 (all nine archived).** They are on `dev` and ship in the `0.2.0` package. This
page gives v0.3 a scope and no acceptance list, so the release record of v0.2 claims none for it: it says,
per line below, which test proves it (`docs/release/v0.2.md`, “Also in this package”).

- Compound-file reader. Done as c0039.
- Readers for the four document kinds: schematic library, PCB library, schematic document, PCB
  document. Done as c0040 (schematic documents and libraries) and c0041 (PCB documents and libraries).
- Project files. Done as c0042 (`fenolite.backends.altium.read`: the project file, output jobs, rule
  files in both forms and stack-up files, read byte for byte; four rule kinds mapped onto the neutral
  rules exactly or listed with a reason; `load_project` as the entry point of the import). The net
  scope numbers wait for an author report (`docs/evidence/altium-project-read.md`).
- Import into the neutral model. Done as c0043, with one known defect: the components of a repeated
  sheet get no designator per channel, so they share one (annotation files are v0.5b).
- `inspect`, `check` and `diff` on second-backend files. Done as c0044: `check` and `inspect` take
  Altium documents, libraries, project files and project folders, read-only and without a tool, with
  the round-trip levels RT-A0, RT-A1 and RT-A2 as check stages; `diff` (added by c0066 with the model
  view and KiCad's tree view) reads Altium inputs in the model view and compares two Altium files
  record by record with `--view records`. The schematic kinds of `diff` stay with v0.2a. RT-A2 judges
  what the built model of an Altium build holds, which is the circuit and the net classes
  (`docs/evidence/altium-roundtrip.md`).
- Buses, padstacks and component bodies in the model. Done as c0043. The model spec is additive-only
  from the end of v0.3.
- `equivalent`, levels 1–4. Done as c0045 (`docs/equivalence.md`).
- Sheet templates read from the second backend's files and written as `.kicad_wks`. Done as c0046.
- In parallel, an analyses track: current capacity, clearance and creepage distances. Done as c0047
  (`fenolite analyze`, `docs/analyses.md`); it works on the neutral model, so an Altium board is
  analysable once its reader exists.

**Pulled forward: c0032 `altium-schematic-writer` (experimental, proposed 2026-10-02).** The
maintainer starts a real board in Altium Designer on 2026-10-05. c0032 lets
`fenolite build --target altium` write a project file and an ASCII schematic. The schematic has
generic component bodies, library and footprint links, and net labels and power ports. Altium then
creates the PCB with its engineering change order. Evidence: Fenolite's own readback, plus the
maintainer's Altium checks as author reports. Size: 5.75 design-days. The rest of v0.3 and v0.4 stays
as planned.

**Copper in the Altium PCB document: c0038 `altium-pcb-copper`.** The experimental `<name>.PcbDoc` holds
tracks, arcs, vias, unpoured polygons, a 2- or 4-layer stack with planes, net classes and rules. c0028
(script copper), c0016 and c0023 (router plugins) feed this writer; until they land, `--copper-from`
copies the copper of a routed KiCad board.

**v0.4 write, c0083–c0092 (proposed on 2026-10-06; the experimental writers c0032–c0038 were pulled forward).**

- Writers for the four document kinds, starting with the ASCII schematic format.
- Project-file and output-job writers.
- Rule lowering.
- A light DRC for the second backend.
- Sheet templates for the second backend, from the same sheet spec as c0012.
- `equivalent`, level 5.
- Verification kit, run by a user on their own machine (`ALTIUM-VERIFIED(kit)`).
- DSL footprint generator and assignment/resolution: c0055. A separate footprint-library lint remains planned.
- Offline built-in component catalog: c0075 starts with generic passive symbols and 0402–1206 chip footprints. c0076 expands it to 49 symbols and 100 distinct footprint variants with public provenance. All target slots are implemented and c0076 is archived on local dev; full-suite CI is deferred to the maintainer's next batch. Custom package geometry remains project-authored.

An author report never promotes an operation to verified. The rows `H-A-WRITE-*` and `H-A-PH-*`
wait for the kit to reproduce them.

The ten changes that remain, all proposed and none implemented. What exists when they start: every
Altium write is `experimental`, no Altium file is read and written back, three kinds of rule are
written, and the kit is named and not defined.

| id | slug | scope | status | depends on | design-days |
|---|---|---|---|---|---|
| c0083 | `altium-repeated-sheets` | the import instantiates repeated sheets: channels, their designators and nets; the annotation file; the pin-to-pad map | proposed | c0043, c0044 | 5.5 |
| c0084 | `altium-rule-lowering` | a closed table from the neutral rule kinds to Altium rule kinds, scoped rule records, the same kinds read back, a rule file export | proposed | c0038, c0042, c0071 | 7 |
| c0085 | `altium-pcb-complete` | stacks up to 16 signal layers, blind and buried vias, board texts, graphics, keep-outs, non-plated holes; polygons unpoured by contract; every item accounted (bodies cut and reported; the model has no slots) | implemented on 2026-10-06 but for bodies; Part X (Altium) open | c0035, c0038, c0041, c0043 | 10 |
| c0086 | `altium-schematic-complete` | symbol graphics, the module tree at any depth, port directions, buses, text outside ASCII, parameters | proposed | c0032–c0037, c0040, c0070 | 9.5 |
| c0087 | `altium-outjob-sheet` | an output job from the export preset; a `.SchDot` and the sheet on schematics from the sheet specification | proposed | c0032, c0042, c0046, c0074 | 7 |
| c0088 | `altium-light-drc` | `copper.clearance` and `parity` on Altium documents, an Altium parity adapter, a copper guard in the Altium build | proposed | c0029, c0072, c0044, c0084 | 5 |
| c0089 | `equivalence-level-5` | `equivalent --level 5`: connectivity, vias and length per net; the triangle at level 5 | implemented on its branch on 2026-10-06: the triangle holds at level 5 on `kicad-cli` 10.0.6 for the routed sample and the seven public documents (`docs/evidence/equivalence-triangle.md`); the full suite and the CI run are the maintainer's | c0045, c0029 | 4.25 |
| c0090 | `altium-roundtrip-write` | a model with a board written as Altium documents; RT-A2 on footprints and copper; the level RT-A3 over the corpus; the first round-trip notes in the claims | proposed | c0083–c0086, c0089 | 7 |
| c0091 | `altium-verification-kit` | `fenolite kit build`, `verify` and `record`: the acceptance run in Altium by checklist and by the kit's own script, its files checked by Fenolite, the run record and the rule for `ALTIUM-VERIFIED(kit)` | proposed | c0084–c0090 | 7.25 |
| c0092 | `altium-write-graduation` | the rule by which a write kind leaves `experimental`, the v0.4 acceptance run, capabilities and documentation | proposed | c0083–c0091 | 3.25 |

- **Total:** 65.75 design-days (sizes, not time).
- **Order:** c0083 first; it depends on nothing of v0.4 and repairs a read defect, so it can ship
  before the rest. Then c0084, c0085, c0086, c0087 and c0089 in parallel. c0088 after c0084. c0090
  after c0084, c0085, c0086 and c0089. c0091 can be written at any time; its first real run needs
  c0084 to c0090. c0092 last.
- **Roadmap bullets and their changes:** writers for the four document kinds → c0085, c0086 and
  c0090; project-file and output-job writers → c0087 (the project-file writer is c0032's); rule
  lowering → c0084; a light DRC → c0088; sheet templates → c0087; `equivalent` level 5 → c0089; the
  verification kit → c0091; what leaves `experimental` → c0092.
- **What only the maintainer can do:** one Altium session for each of c0084 (rules editor and rule
  check), c0085 (the six-layer board), c0086 (the hierarchical schematic) and c0087 (output job and
  sheet template), each written as numbered steps in the change's design; an optional one for c0083
  (channel naming formats) and for c0088; and the kit run of c0091 on his machine, which c0092 records.

**v0.4 acceptance (a proposal; the project plan's text for this milestone is not in these pages).**
Approved as the working target on 2026-10-06, to be reviewed by the maintainer before c0092 closes.

1. A project built for both targets is the same design: `equivalent` at level 5 between the KiCad
   board and the Altium documents, and between the KiCad board and KiCad's import of those documents
   (c0089, c0092).
2. A public Altium project is imported, written back and imported again with an equal model inside
   the written scope, and what the write leaves out is counted per record kind (RT-A3, c0090), on
   documents of at least three public repositories, the one with repeated sheets among them (c0083).
3. `fenolite check` on an Altium project finds a short, a clearance violation and a board that
   disagrees with its schematic, with no tool (c0088).
4. Every rule of a script reaches the Altium board exactly or is named with its reason (c0084).
5. One recorded kit run in Altium passes on the acceptance tree, and at least the PCB document and
   the schematic document writes leave `experimental` by the rule of c0092 (c0091, c0092).

**Equivalence levels** (`equivalent A B --level N`, project plan):

| level | compares | milestone |
|---|---|---|
| 1 | components | v0.3; delivered by c0045 (`docs/equivalence.md`) |
| 2 | netlist (`REF-PIN`) | v0.3; delivered by c0045 (`docs/equivalence.md`) |
| 3 | footprints and pads | v0.3; delivered by c0045 (`docs/equivalence.md`) |
| 4 | placement | v0.3; delivered by c0045 (`docs/equivalence.md`) |
| 5 | routing (per net: the pads joined, the vias, the length per layer) | v0.4; delivered by c0089 (`docs/equivalence.md`, "Level 5: routing") |
| 6 | rules | v0.6 |
| 7 | geometry (XOR) | v0.6 |
| 8 | presentation | after 1.0 |

## Phase 5: to 1.0 (estimate; ids not allocated)

| milestone | scope |
|---|---|
| v0.5a | conversion between KiCad and the second backend, with a report of what is kept or lost; controlled KiCad downgrade (capability resolver); public `equivalent`; annealing placer |
| v0.5b | multi-instance hierarchy; variants; layout reuse per module (KiCad groups); schematic editing that keeps presentation; MCP server |
| v0.6 | equivalence levels 6–7; an emulated-evidence category for corpus cases; matched-length and skew analysis; optional KiCad IPC, only if KiCad 11 is released; in the project plan also SPICE (optional) and an ASCII inspection format for the second backend's PCB documents |
| v1.0 | freeze: CLI, envelope and schemas `v1`; model schema version 1.0 with migrators; published conformance matrix (format × version × operation × evidence); no `INFERRED` without a hypothesis, no `UNVERIFIED` outside `experimental`; `LEGAL.md` reviewed; residue scan green over the whole history |

## Proposed cuts for a leaner 1.0

> **Proposal, pending the maintainer's decision.** Nothing in this section is decided. The project
> plan already allows moving v0.5b and v0.6 after 1.0 if dedication falls below 40 %.

**Keep for 1.0:**

- complete KiCad (to the end of v0.2b);
- second backend read and write (to the end of v0.4);
- conversion, with controlled KiCad downgrade (capability resolver) and public `equivalent` (v0.5a);
- equivalence levels 1–5;
- the MCP server (v0.5b): small, and central for agents;
- the v1.0 freeze, with model schema 1.0 and migrators, the `LEGAL.md` review and the residue scan
  over the whole history.

**Move after 1.0:**

| item | on this map | note |
|---|---|---|
| annealing placer | v0.5a | v0.1 ships manual and grid placement (c0022) |
| multi-instance hierarchy, variants | v0.5b | — |
| layout reuse per module (KiCad groups) * | v0.5b | goes with multi-instance hierarchy |
| schematic editing that keeps presentation * | v0.5b | — |
| equivalence levels 6–7 | v0.6 | levels 1–5 stay |
| emulated-evidence category for corpus cases * | v0.6 | — |
| matched-length and skew analysis * | v0.6 | — |
| KiCad 11 IPC | v0.6 | only possible once KiCad 11 is released |
| SPICE | v0.6 | — |
| ASCII inspection format | v0.6 | — |
| Specctra DSN/SES and Freerouting (c0023) | v0.1 | c0016's KiCadRoutingTools feasibility gate passed on KiCad 9.0.9 and 10.0.6; the maintainer's accepted decision in Open decisions row 5 keeps c0023 in v0.1 regardless |

\* Placed by this page with the rest of its milestone; the maintainer may keep any of them.

**Effect:** about 61 changes to 1.0 instead of about 70 (estimate).

Under the v0.1 cut order (Open decisions, row 2), if accepted, c0023 is the first change to move
to v0.2a when v0.1 overruns. This proposal would move it further, after 1.0.

## Time and pace

All numbers are estimates.

**Size to v0.1.**

| | design-days |
|---|---|
| first batch: c0014 3, c0009 7.75, c0017 7.75, c0018 5.75, c0010 6.5 (all done) | 30.75 |
| c0011 8.5 and c0012 9.5 (done), c0013 8.5 | 26.5 |
| c0019 8.25, c0020 8.75, c0021 9.5 | 26.5 |
| dogfood gaps: c0026 6.5, c0027 5.25, c0028 21.5, c0029 12, c0030 10.25, c0031 8 | 63.5 |
| proposed on 2026-10-03: c0015 6, c0016 7.5, c0022 6, c0023 10, c0024 5.25, c0025 5.75 | 40.5 |
| **total to v0.1** | **about 188** |
| done on 2026-10-05 (every change but c0025) | about 182 |
| **left** (c0025, the release change) | **about 6** |

**Size of v0.2a.**

| | design-days |
|---|---|
| schematic: c0060 11, c0061 14 | 25 |
| oracles and tables: c0062 8.5, c0063 6.75, c0064 7, c0065 5 | 27.25 |
| commands and evidence: c0066 13.5, c0067 5 | 18.5 |
| follow-ups: c0068 9.75 | 9.75 |
| **total** | **80.5** |

At the measured pace below that is about two calendar days of agent work, before CI time,
integration and the maintainer's decisions, which are the limits here as they are for v0.1.

**Size of v0.2b.**

| | design-days |
|---|---|
| lens and schematic: c0069 12.5, c0070 13 | 25.5 |
| rules and checks: c0071 10, c0072 10 | 20 |
| DSL: c0073 8 | 8 |
| drawing sheet and follow-ups: c0074 11.5 | 11.5 |
| **total** | **65** |

**Measured pace.** From the git history:

- On 2026-10-01 at 03:19 the proposals of c0005–c0008 were committed.
- By 2026-10-02 at 13:17, about 34 hours later, ten changes were implemented, checked by the CI
  oracles and archived: c0005–c0011, c0014, c0017 and c0018.
- Without c0005, which has no size, they add up to about 60 design-days.
- That is about 40 design-days per calendar day, with two agents writing and the maintainer
  reviewing.

**Forecast.**

- v0.1 was released on 2026-10-05, with its release change c0025.
- v0.2a (80.5 design-days) and v0.2b (65) were proposed on 2026-10-04 and 2026-10-05 and implemented by
  2026-10-06: about two calendar days for 145.5 design-days. v0.2.0 was released on 2026-10-06, with its
  release change c0093.
- The limits are not size:
  - CI time per change (`kicad-9` and `kicad-10`);
  - integration of proposals written in parallel (requirements modified in chains);
  - the maintainer's decisions;
  - external tools in c0016 and c0023.
- The pace was measured on file-format work. Routing and the release gate may be slower. Re-measure
  after each batch and update this section.

**Sizes before the measured pace.** The designs sized each change at about three times its project
plan line: c0008 was 7.25 design-days against half a week. That comparison set an estimate against an
estimate and measured no time, so it is not a forecast. The project plan's milestone weeks (below) are
calendar time for one person at about 60 %. They are kept for reference and are not re-baselined.

| milestone | weeks | cumulative |
|---|---|---|
| v0.1 | 20 | 20 |
| v0.2a | 9 | 29 |
| v0.2b | 7 | 36 |
| v0.3 | 18 | 54 |
| v0.4 | 24 | 78 |
| v0.5a | 7 | 85 |
| v0.5b | 6 | 91 |
| v0.6 | 5 | 96 |
| v1.0 | 5 | 101 |

- **By size, v0.1 is more than half of the work up to the end of KiCad (v0.2b).** v0.2a is 80.5
  design-days and v0.2b 65 as proposed, against about 188 for v0.1.
- **The second backend is the largest single block after that:** v0.3 and v0.4 are 42 of the
  project plan's 101 weeks.

## Open decisions

| # | decision | recorded in | default |
|---|---|---|---|
| 1 | Re-baselined budget: about 31 days for the batch and about 102 to v0.1, against about 36 in the project plan's lines | Open Questions of c0009, c0014, c0017, c0018 | accepted; superseded as a forecast by the measured pace ([Time and pace](#time-and-pace)) |
| 2 | v0.1 cut order: c0023 to v0.2a first, then c0021 to v0.2a, then c0020's measurement-only items | same | accepted |
| 3 | Leaner 1.0 ([Proposed cuts](#proposed-cuts-for-a-leaner-10)) | this page | none; pending |
| 4 | Dogfood gaps in v0.1: all of c0026–c0031 (about 63.5 design-days), or c0030 and c0031 moved to v0.2a (about −18 design-days, about half a calendar day at the measured pace; c0015 then writes the target-9 fill flag that c0031 adds) | this page; designs of c0026–c0031 | pending. Recommended: keep all six in v0.1 |
| 5 | c0023 in v0.1 or in v0.2a, and ADR-0006 (reading the Specctra reference for facts; running Freerouting as a subprocess) | designs of c0016 and c0023 | decided by the maintainer on 2026-10-03: c0023 stays in v0.1 whatever c0016's gate says, and the decision of ADR-0006 is accepted |
| 6 | `macos-app` nightly job of the project plan's CI matrix | design of c0025 | decided by the maintainer on 2026-10-03: left out of v0.1; proposed for v0.2a in c0068 |
| 7 | v0.2a: the id block c0060–c0068, taken as one block although c0057 is free | this page; `openspec/README.md` | pending. Recommended: keep the block |
| 8 | v0.2a: the schematic is written by `build` (`--schematic write\|skip`), with no `sch build` command, and a schematic edited in KiCad is replaced with a warning | design of c0061 | pending. Recommended: as proposed |
| 9 | v0.2a: built boards change once: net names hold `{slash}` for `/`, and pads of unconnected pins carry KiCad's net names in the written board only | design of c0061 | pending. Recommended: as proposed; both come from measurements on 9.0.9 and 10.0.6 |
| 10 | v0.2a: the three-rule ERC leaves `check` as a stage and stays as a function for the second backend's documents (c0044) | designs of c0062 and c0044 | pending. Recommended: as proposed |
| 11 | v0.2a: `restore` takes the receipt of a write as its undo token; no journal is kept on disk | design of c0066 | pending. Recommended: as proposed |
| 12 | v0.2a: the demo schematics join the corpus (about 43 MB more per KiCad tag in the fetch cache, nothing committed) | design of c0060 | pending. Recommended: yes |
| 13 | v0.2a: the pad shape offset is repaired in c0068, ahead of the zone clearance | design of c0068 | pending. Recommended: yes; it is a wrong verdict of `check` in v0.1 |
| 14 | follow-ups not taken by c0068: export presets, outline snapping, per-command result schemas, `inspect` of project and rules files | design of c0068, Decision 13 | proposed in c0074 for export presets, outline snapping and stitching; result schemas with the v1.0 freeze; `inspect` of project and rules files unscheduled |
| 15 | v0.2b: the id block c0069–c0074 | this page; `openspec/README.md` | pending. Recommended: keep the block |
| 16 | v0.2b: a footprint matched through `moved()` keeps its board node under the new identity (uuids, `fenolite.path`, group members), and `placements.toml` is written only by `sync --to-source` and survives `--discard-layout` | design of c0069 | pending. Recommended: as proposed |
| 17 | v0.2b: the schematic layout defaults to `readable` (module sheets and snapped 2-pin parts), so projects built in v0.2a change once; `--schematic-layout grid` keeps the v0.2a form | design of c0070 | decided on 2026-10-06: `readable` is the default |
| 18 | v0.2b: creepage rules are refused for KiCad 9, whose DRC reports no creepage violation on the measured bench; `--allow-lossy` drops them | design of c0071 | pending. Recommended: as proposed |
| 19 | v0.2b: the parity acceptance compares Fenolite's counts with KiCad's parity test on public demos and authored edits, in place of the project plan's reference counts | design of c0072 | pending. Recommended: as proposed |
| 20 | v0.2b: a user's `.kicad_wks` is re-written for the target rather than copied, and outline endpoints closer than 10 µm are joined, as both majors do | design of c0074 | pending. Recommended: as proposed |
| 21 | v0.4: the id block c0083–c0092, ten changes, although c0057 and c0077–c0081 are free | this page; `openspec/README.md` | ten, by the start of implementation on 2026-10-06 |
| 22 | v0.4: the verification kit is a checklist with files that Altium saves and exports, checked by `fenolite kit verify`, and may hold a script that runs inside Altium | proposal and design of c0091 | decided by the maintainer on 2026-10-06: checklist plus script. The script is authored for Fenolite from Altium's public scripting documentation, the user starts it from inside Altium, and the checklist works alone |
| 23 | v0.4: polygons are written unpoured and repoured in Altium; Fenolite writes no poured copper | proposal of c0085 | decided by the maintainer on 2026-10-06: as proposed |
| 24 | v0.4: c0083 (repeated sheets in the import) is inside v0.4, first and independent, or a v0.3 follow-up released earlier | proposal of c0083 | decided by the maintainer on 2026-10-06: inside v0.4 |
| 25 | v0.4: level 5 of `equivalent` compares connectivity, vias and length per net; exact geometry stays level 7 | proposal of c0089 | decided by the maintainer on 2026-10-06: as proposed |
| 26 | v0.4: variants stay in v0.5b | proposal of c0086 | decided by the maintainer on 2026-10-06: v0.5b |
| 27 | v0.4: the acceptance block above is a proposal derived from the roadmap's bullets | this page; design of c0092 | approved as the working target on 2026-10-06, to be reviewed by the maintainer before c0092 closes (a task of c0092) |
| 28 | v0.4: `fenolite check` on Altium input runs `copper.clearance` and `parity` by default, so it can exit 5 where it exited 0 | design of c0088 | decided by the maintainer on 2026-10-06: on by default; the changelog states it as a change of behaviour |
| 29 | v0.4: one kit run on one Altium version is enough for a write kind to leave `experimental`, the version named wherever the level is shown | design of c0092 | decided by the maintainer on 2026-10-06: yes |
| 30 | v0.4: the archive of a kit run is published as a release asset; the repository holds only its digest and size | design of c0091 | decided by the maintainer on 2026-10-06: yes |
| 31 | v0.4: an Altium build draws each symbol from its own graphics by default (`--altium-symbols graphics`); `generic` keeps the rectangles. The four samples his author reports covered are regenerated, their rectangle form is kept as golden copies, and the graphics form is not Altium-verified until Part Y | proposal and design of c0086 | decided by the maintainer on 2026-10-06: `graphics` is the default; the changelog states it as a change of the default output |

Change-level questions: see Open Questions in the designs of the proposed changes (c0025, c0039–c0046,
c0060–c0074 and c0083–c0092).

Later questions, asked when their change is proposed:

- c0015: if KiCad 9.0.9 rejects zone fills computed by 10.0, may v0.1 accept target-9 boards
  written unfilled, with a `zone.unfilled` warning? c0031 observed that 9.0.9 and 10.0.6 draw the
  fills of a target-9 zone 0.125 mm larger unless the zone says `(filled_areas_thickness no)`.
- c0019: besides the automated stand-in, will the maintainer do one real GUI footprint move on
  10.0.6 and record it as supporting evidence?

Update this page when a change is proposed or archived, or when a decision above is taken.
