# Roadmap to 1.0

Status on 2026-10-02. Released: `0.0.1.dev0` (2026-09-30, pre-alpha). Next planned tag:
`v0.1.0-alpha1`, after c0019 and c0020. Next planned release: `v0.1.0`.

This page is a map, not a spec. What is built, and how, is decided change by change in
`openspec/changes/`. Every id after c0025 is an estimate, and so is every budget.

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
  | estimate | id range and scope are estimates (every id after c0025) |

- **Budgets** are working days of effort, estimated per change (in its `design.md`, section "Budget",
  once proposed). The project plan counts calendar weeks at about 60 % dedication, which is about
  3 working days a week.
- **Milestones** are releases (`v0.1`, `v0.2a`, …). A phase groups milestones.

## Milestones

| phase | milestone | changes | scope | state |
|---|---|---|---|---|
| 1. Foundations | — (`0.0.1.dev0` was cut after c0004) | c0001–c0005 | repository, CLI contract, IP hygiene, neutral model, geometry kernel | done |
| 2. KiCad PCB | v0.1 | c0006–c0025 | an agent closes the loop on a KiCad board | c0006–c0009, c0014 and c0017 done; c0010, c0011–c0013 and c0018 proposed; the rest roadmap |
| 3. KiCad complete | v0.2a | about c0026–c0031 | schematic write, ERC oracle, netlist, BOM, more commands | estimate |
| 3. KiCad complete | v0.2b | about c0032–c0035 | full layout lens, full rules, parity, interfaces | estimate |
| 4. Second backend | v0.3 | about c0036–c0043 | read, equivalence levels 1–4, analyses | estimate |
| 4. Second backend | v0.4 | about c0044–c0051 | write, equivalence level 5, verification kit | estimate |
| 5. To 1.0 | v0.5a, v0.5b, v0.6, v1.0 | about c0052–c0064 | conversion, MCP server, freeze | estimate |

About 64 changes to 1.0 on this map, or about 55 with the proposed cuts (see
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

## Phase 2: KiCad PCB to v0.1 (c0006–c0025)

**v0.1 goal.** An agent closes the loop on a KiCad board, headless, for KiCad 9.0 and 10.0:
`build` → `place` → `route` → `fill` → `check` → `export` → `render`, with the layout kept across
rebuilds.

| id | slug | scope | state | depends on | days |
|---|---|---|---|---|---|
| c0006 | `kicad-sexpr-slots` | S-expressions, slots, corpus, `kicad-10` CI job | done | — | — |
| c0007 | `kicad-tokens` | format versions, token inventory, `kicad-9` CI job | done | — | — |
| c0008 | `kicad-libs` | footprint and symbol libraries, library tables | done | — | — |
| c0009 | `kicad-board-backend` | board reader, backend protocol, `kicad-cli` runner | done | c0014 | 7.75 |
| c0010 | `kicad-project-file` | `.kicad_pro` writer, net classes | proposed | c0017, c0018 | 6.5 |
| c0011 | `dsl-thin-build` | thin Python DSL and `build` | proposed | c0010, c0017, c0018 | 8.5 |
| c0012 | `sheet-templates-kicad` | sheet templates to `.kicad_wks` | proposed | c0010, c0017 | 9.5 |
| c0013 | `kicad-oracle-and-check` | read-only `check` v0, `inspect`, `doctor` | proposed | c0010, c0011 | 8.5 |
| c0014 | `verification-evidence` | hypothesis-register guard, label grammar, release rule | done | — | 3 |
| c0015 | `zone-fill` | zone fill through `kicad-cli` 10 for both targets | roadmap | c0013, c0019 | 5 |
| c0016 | `routing-plugins` | routing protocol, KiCadRoutingTools plugin | roadmap | c0015, c0020, c0022 | 6 |
| c0017 | `kicad-board-writer` | board writer for 9.0 and 10.0 | done | c0009, c0014 | 7.75 |
| c0018 | `kicad-rules-footprints` | footprint and custom-rules writers | proposed | c0017 | 5.75 |
| c0019 | `layout-preserve` | layout kept across rebuilds | roadmap | c0011 | 5 |
| c0020 | `check-netlist-drc` | DRC findings, netlist compare, corpus RT2, negative tests | roadmap | c0013 | 6.75 |
| c0021 | `kicad-libs-cache` | library fetch, cache, resolution probes | roadmap | c0017 | 5 |
| c0022 | `placement-grid` | manual and grid placement | roadmap | c0019 | 3.5 |
| c0023 | `specctra-freerouting` | Specctra DSN/SES, Freerouting plugin (time-boxed) | roadmap | c0016 | 10 |
| c0024 | `manufacturing-exports` | exports with manifest, render | roadmap | c0013, c0015 | 4.5 |
| c0025 | `release-v0-1` | agent loop, second example board, CI matrix, release gate | roadmap | c0012, c0016, c0024 | 5 |

- c0006–c0009 and c0014 were archived on 2026-10-01, and c0017 on 2026-10-02.
- The current batch is implemented in this order: c0014 → c0009 → c0017 → c0018 → c0010. c0014,
  c0009 and c0017 are done.
- Days of proposed and done changes (c0009–c0014, c0017, c0018) come from their designs ("Budget").
  Days of roadmap changes are the roadmap's planning estimates. The designs of c0011, c0012 and
  c0013 estimate 8.5, 9.5 and 8.5 days, 6 more than the roadmap's 20.5.

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

## Phase 3: KiCad complete (v0.2a, v0.2b; estimate)

**v0.2a, about c0026–c0031.**

- Schematic: `.kicad_sch` writer and reader, `sch build`.
- ERC through `kicad-cli` in `check`, replacing v0.1's three-rule ERC; schematic parity in DRC.
- `netlist` and `bom` through `kicad-cli`; pick-and-place.
- Fenolite's own netlist of the schematics it generates, compared with `kicad-cli`.
- The complete artefact manifest, with SHA-256 and a state per artefact.
- Commands `diff`, `roundtrip`, `fmt --check`, `explain`, `restore`; pagination; `net`, `region`
  and `neighbors` queries.
- The generated evidence and capability matrix.
- Any v0.1 change moved by the budget cut order (c0023, c0021; see Open decisions).

**v0.2b, about c0032–c0035.**

- Full layout lens (extract, adapt, `moved()`, sync) and `placements.toml`.
- Readable schematic autolayout, and one hierarchical sheet per module.
- Full rules lowered to `.kicad_dru` (courtyard, silkscreen, hole-to-hole, annular ring, creepage).
- Parity between schematic and board, and between symbol and footprint.
- Interfaces (I2C, SPI, UART, USB 2) and quantities.
- Import of a user's `.kicad_wks`.

## Where KiCad ends and the second backend starts

- **KiCad is complete at about c0035**, the end of v0.2b (estimate): board and schematic read and
  write for 9.0 and 10.0, `kicad-cli` as oracle for DRC, ERC, netlist and exports, full lens and
  rules.
- **After that, KiCad work is maintenance:** one pass per KiCad major (the project plan estimates
  about one week of format drift per major), and an optional IPC backend once KiCad 11 is released.
- **Second-backend changes start with v0.3, at about c0036.** The project plan keeps a
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

**v0.3 read, about c0036–c0043.**

- Compound-file reader.
- Readers for the four document kinds: schematic library, PCB library, schematic document, PCB
  document.
- Project files.
- Import into the neutral model.
- `inspect`, `check` and `diff` on second-backend files.
- Buses, padstacks and component bodies in the model. The model spec is additive-only from the end
  of v0.3.
- `equivalent`, levels 1–4.
- In parallel, an analyses track: current capacity, clearance and creepage distances.

**v0.4 write, about c0044–c0051.**

- Writers for the four document kinds, starting with the ASCII schematic format.
- Project-file and output-job writers.
- Rule lowering.
- A light DRC for the second backend.
- Sheet templates for the second backend, from the same sheet spec as c0012.
- `equivalent`, level 5.
- Verification kit, run by a user on their own machine (`ALTIUM-VERIFIED(kit)`).
- Footprint generator and a footprint library lint.

An author report never promotes an operation to verified. The rows `H-A-WRITE-*` and `H-A-PH-*`
wait for the kit to reproduce them.

**Equivalence levels** (`equivalent A B --level N`, project plan):

| level | compares | milestone |
|---|---|---|
| 1 | components | v0.3 |
| 2 | netlist (`REF-PIN`) | v0.3 |
| 3 | footprints and pads | v0.3 |
| 4 | placement | v0.3 |
| 5 | routing (tracks and vias per net) | v0.4 |
| 6 | rules | v0.6 |
| 7 | geometry (XOR) | v0.6 |
| 8 | presentation | after 1.0 |

## Phase 5: to 1.0 (estimate, about c0052–c0064)

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

- complete KiCad (to about c0035);
- second backend read and write (to about c0051);
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
| Specctra DSN/SES and Freerouting (c0023) | v0.1 | only if c0016's feasibility gate passes: KiCadRoutingTools (c0016) then covers routing for v0.1 acceptance item 3; otherwise c0023 stays in v0.1 |

\* Placed by this page with the rest of its milestone; the maintainer may keep any of them.

**Effect:** about 55 changes to 1.0 instead of about 64 (estimate).

Under the v0.1 cut order (Open decisions, row 2), if accepted, c0023 is the first change to move
to v0.2a when v0.1 overruns. This proposal would move it further, after 1.0.

## Time and budget

All numbers are estimates.

**To v0.1.**

| | working days |
|---|---|
| current batch: c0014 3, c0009 7.75, c0017 7.75 (these three done), c0018 5.75, c0010 6.5 | 30.75 |
| proposed next: c0011 8.5, c0012 9.5, c0013 8.5 (from their designs) | 26.5 |
| roadmap: c0015, c0016, c0019–c0025 (Phase 2 table) | about 50.75 |
| **total to v0.1** | **about 108** |
| the project plan's remaining v0.1 lines (12 weeks at about 60 %) | about 36 |

- The ratio is about 2.8 (102 / 36). The 36 days come from the project plan's lines without the
  milestone contingency. The ratio matches the overruns of c0006–c0008: c0008 alone was estimated
  at 7.25 days against a half-week line.
- The figure was about 102 when c0011–c0013 were still roadmap entries (20.5 days); their designs
  raised it to about 108. The ratio and percentages below use the earlier 102 and change little at 108.
- Moving c0023 and c0021 to v0.2a removes 15 days (about 93 left). No v0.1 acceptance item depends
  on c0021. c0023 can move only if c0016's feasibility gate passes; otherwise acceptance item 3
  depends on it.
- The re-baseline is an open question in c0014's design (Open decisions, row 1).

**Milestones in the project plan** (calendar weeks at about 60 % dedication, contingency included;
not yet re-baselined):

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

- **From c0009 to the end of KiCad (c0035), v0.1 is about 43–47 % of the work**, if v0.2a and
  v0.2b overrun by the same ratio of 2.8.
  - Same basis as the ratio (lines without contingency): v0.2a and v0.2b are 13.5 weeks × 3 days ×
    2.8 ≈ 113 days. v0.1: 102 / (102 + 113) ≈ 47 %.
  - With the contingency weeks of the table (16): 16 × 3 × 2.8 ≈ 134 days. v0.1: 102 / (102 + 134)
    ≈ 43 %.
- **The second backend is the largest single block after that:** v0.3 and v0.4 are 42 of the
  project plan's 101 weeks.

## Open decisions

| # | decision | recorded in | default |
|---|---|---|---|
| 1 | Re-baselined budget: about 31 days for the batch and about 102 to v0.1, against about 36 in the project plan's lines | Open Questions of c0009, c0014, c0017, c0018 | accepted |
| 2 | v0.1 cut order: c0023 to v0.2a first, then c0021 to v0.2a, then c0020's measurement-only items | same | accepted |
| 3 | Leaner 1.0 ([Proposed cuts](#proposed-cuts-for-a-leaner-10)) | this page | none; pending |

Change-level questions: see Open Questions in the designs of c0009, c0010, c0014 and c0018.

Later questions, asked when their change is proposed:

- c0015: if KiCad 9.0.9 rejects zone fills computed by 10.0, may v0.1 accept target-9 boards
  written unfilled, with a `zone.unfilled` warning?
- c0019: besides the automated stand-in, will the maintainer do one real GUI footprint move on
  10.0.6 and record it as supporting evidence?

Update this page when a change is proposed or archived, or when a decision above is taken.
