## Context

- **Source.** `docs/research/component-library.md`, section 2 ("What AI can and cannot do here": SFgen,
  arXiv 2607.19767, and a public vendor blog of 2024) and section 4.7 (datasheet to device, with review).
  Table of section 5: c0265 depends on c0260, c0261 and c0262.
- **What the public results say** (concepts only; nothing of their code, prompts or data is used):
  - a pin table of 95 rows was extracted right from an 820-page datasheet;
  - over 1 000 parts, about 86 % of symbols and 80 % of footprints were right, and pin and pad count
    accuracy fell to 0 % on dense packages;
  - both sources let the model propose parameters and let a deterministic generator draw.
- **What exists on `dev` (0.6.0).** An MCP server (c0195, c0196) that exposes every public command as a
  tool, generated from the command registry, and the agent guide (`fenolite guide`, pages under
  `src/fenolite/agent/skill/references/`). No library command reads a datasheet. The `pdf` and
  model-related tools are the agent's own, outside Fenolite.
- **What the batch proposes.** c0259: records (`package`, `pins`, `device`, `part`). c0260: families,
  generators, the land calculator and the manufacturer-land override. c0261: symbol from a pin table.
  c0262: `library check` (rules, rendered sheets, old/new diff) and `library review` (the record that
  raises evidence). c0264: the device folder with `[origin]`, written the same way from a download.

## Goals / Non-Goals

**Goals**

- An agent can turn a datasheet into a reviewable device without drawing a single pad.
- Every value in a proposed device is traceable to a page of a datasheet with a known SHA-256.
- What a model is known to get wrong (counts on dense packages, mechanical drawings) is either not
  asked of it, or cross-checked by a second proposal and by the generator.
- The core gains no dependency and calls no model.
- A person, with a rendered sheet, is the only one who raises the label.

**Non-Goals**

- See the proposal. In addition: no ranking of proposers, no confidence scores (a number from a model
  is not evidence), no automatic retry loop inside Fenolite (the agent loops; Fenolite answers).

## Decisions

### 1. Who does what

```
agent (own PDF tools, MCP client or shell)          Fenolite core (no model, no PDF parser)
──────────────────────────────────────────          ──────────────────────────────────────────
reads guide page `datasheets`  ◀──────────────────  fenolite guide datasheets --text
gets a skeleton                ◀──────────────────  library propose --datasheet X.pdf
reads the datasheet, fills P.toml
                               ──────────────────▶  library propose --datasheet X.pdf --proposal P.toml
                                                    --out devices/proposed --dry-run
fixes P.toml from the findings ◀──────────────────  findings (proposal.*, package.*, library.*), exit 5
                               ──────────────────▶  ... --confirm --plan <id>   (writes the folder)
person                         ──────────────────▶  library check devices/proposed/EXB6202  (c0262)
person, with the sheet         ──────────────────▶  library review ... --accept  (c0262; gate below)
```

- The core reads the PDF only to compute its SHA-256 and to check that it starts with `%PDF-`
  (`FEN-3004` otherwise). Page numbers in citations are checked to be positive integers, nothing more.
- *Alternative:* a `fenolite[ai]` extra that calls a model. Rejected: AGENTS.md keeps the core free of
  runtime dependencies; the agent already has a model and PDF tools, and a model call inside Fenolite
  would make outputs depend on a remote service, breaking byte identity.
- *Alternative:* the MCP server accepts the proposal inline as a tool argument. Not in this change: the
  CLI contract reads files, and the MCP tool is generated from it (open question 2).

### 2. The proposal file (`fenolite.proposal.v0`)

```toml
# tests/data/proposals/exb6202.proposal.toml   (authored for Fenolite; illustrative part)
schema = "fenolite.proposal.v0"

[datasheet]
file = "exb6202.pdf"                     # base name only
sha256 = "<64 hex>"                      # must equal the file given with --datasheet
revision = "C"                           # as printed, free text
title = "EXB6202 6 V 2 A step-down regulator"

[proposer]
kind = "agent"                           # agent | person | tool
name = "example agent"                   # free text, recorded, never trusted
date = "2026-10-29"

[device]
id = "Proposed:EXB6202"
manufacturer = "Example Semi"
mpn = "EXB6202"
summary = "6 V 2 A step-down regulator"
ref_prefix = "U"
cite = { page = 1 }

[package]
family = "gullwing"                      # a family of c0260; the keys below are c0260's for it
pins = 8
pitch = "1.27mm"
arrangement = "dual"
body = { length = "4.80mm..5.00mm", width = "3.80mm..4.00mm", height = "..1.75mm" }
span = "5.80mm..6.20mm"
lead = { length = "0.40mm..1.27mm", width = "0.31mm..0.51mm" }
cite = { page = 21, figure = "package outline D" }

[package.land]                           # optional: the manufacturer's recommended land, as parameters
pad = { width = "0.60mm", length = "1.55mm" }
row_spacing = "5.40mm"
cite = { page = 22, figure = "recommended land pattern" }

[[pin]]
number = "1"
name = "BST"
type = "passive"
group = "output"
cite = { page = 3, table = "pin functions" }

[[pin]]
number = "2"
name = "GND"
type = "power_in"
group = "ground"
alternates = []                          # kept in the proposal only (c0257 reserves `options`)
cite = { page = 3, table = "pin functions" }

# ... one [[pin]] per pin

[ratings]
vin = { max = "6V", cite = { page = 4, table = "absolute maximum ratings" } }

[[part]]
mpn = "EXB6202DR"
packing = "reel 2500"
cite = { page = 20, table = "ordering information" }

[[doubt]]
field = "package.lead.length"
reason = "minimum value illegible in the outline drawing"
```

- **Keys are closed.** Any other key gives `FEN-3004` naming it. The keys `pads`, `pad`, `x`, `y`,
  `at`, `position`, `outline`, `polygon`, `courtyard`, `silkscreen`, `graphics`, `vertices` and `points`
  outside `package.land` are refused with a message that says proposals carry no geometry
  (`proposal.geometry-refused` in the message, `FEN-3004`). `package.land` takes only the parameter
  keys c0260's manufacturer override defines.
- **Values.** Lengths and ratings are text with a unit, parsed exactly by `fenolite.core.quantities`,
  ranges in c0246's spelling; no float is created (`tomllib` with `parse_float=Decimal`).
- **Pin types and groups** use the vocabularies of c0259's pin table. A pin may repeat a name (several
  `GND` pins); numbers are unique.
- **Package keys are c0260's.** `package` holds `family` and exactly the keys that c0260 defines for
  that family in a package record (for example `ep` for an exposed pad of a `nolead` package), plus
  `cite`. `package.land` holds the parameters of c0260's `[land]`; its `source` is filled in by the
  conversion with the datasheet.
- **Grid arrays.** A `grid` package takes c0260's `rows`, `columns`, `pitch`, `ball` and `depopulated`,
  and one proposal-only key, `row_labels`: the row labels in order, as printed, for example
  `["A", "B", "C", "D", "E", "F", "G", "H"]`. The proposer copies the labels from the drawing; Fenolite
  does not assume which letters a manufacturer skips.
- **Citations.** `cite` holds `page` (required, ≥ 1) and at most one of `table` and `figure` (text).
  A row without `cite` is allowed in the file and reported (`proposal.uncited`).
- **Doubts.** A `[[doubt]]` names a field path of the proposal and a reason. Each gives
  `proposal.doubt` (warning) and blocks review acceptance until it is removed.
- The canonical writer gives a fixed key order and LF line ends, so a proposal written back by
  Fenolite into the device folder has stable bytes.

### 3. `library propose` without a proposal: the skeleton

`fenolite library propose --datasheet exb6202.pdf --json` is read-only (exit 0). `result.skeleton` is
the TOML text of an empty proposal with `datasheet.file` and `datasheet.sha256` filled in, a comment on
each key, and `result.guide = "datasheets"`. It gives the agent the schema in the version installed,
so the guide page does not have to repeat it.

### 4. `library propose` with proposals

```
fenolite library propose --datasheet exb6202.pdf --proposal exb6202.proposal.toml \
    --out devices/proposed --dry-run --json
```

Steps, each stopping at its first error finding (no write beside an error):

1. **Parse** each proposal (`FEN-3004` for a malformed file, `FEN-3002` for a newer schema).
2. **Bind**: `datasheet.sha256` equals the SHA-256 of `--datasheet`, else `proposal.datasheet-mismatch`
   (error).
3. **Self-checks** (decision 5).
4. **Agreement** of two proposals when two are given or required (decision 6).
5. **Convert** into c0259 records: `package.toml` (the family and parameters), `pins.toml`,
   `device.toml` (identity, ratings, parts, `evidence = "UNVERIFIED"`, `licence` from `--licence`,
   default `"see source terms"`, and an `[origin]` with `tool = "fenolite library propose"`, the
   datasheet name and SHA-256, the proposer and the SHA-256 of each proposal file).
6. **Draw** the footprint and 3D body with c0260 and the symbol with c0261. Package findings of c0260
   (`package.*`, for example `package.dimensions-inconsistent` or `package.land-impossible`) are
   reported as they are.
7. **Check** with c0262's rules on the drawn device (pin count against pad count, pin-1 position,
   courtyard, body against span, depopulated balls, land against the manufacturer pattern).
8. **Plan** the device folder under `--out`: the records, the drawn files, and each proposal copied as
   `proposal.toml` (`proposal-2.toml` for the second).

- `--out` follows c0264's target rule: a relative folder inside the project, never the shipped catalog
  or a pack; `--licence CC0-1.0` is allowed, because a pin table and package dimensions are facts, but
  only a reviewed device may enter a pack (c0262, c0266).
- Re-running with a corrected proposal over an unreviewed folder replaces it; over a reviewed or
  hand-edited folder it is `FEN-7001`, as in c0264.
- `mutates=True`; the MCP server exposes it as a tool by c0195's rule.

### 5. Self-checks of one proposal

| code | severity | rule |
|---|---|---|
| `proposal.unknown-family` | error | `package.family` is not a c0260 family |
| `proposal.duplicate-pin` | error | two rows with one `number` |
| `proposal.pin-count` | error | rows ≠ `package.pins` (+ the exposed pad when it is numbered), or, for a grid, ≠ rows × columns − depopulated |
| `proposal.pin-outside` | error | a number that the family's numbering cannot give (`9` on an 8-pin package; `J4` on a grid of rows A–H) |
| `proposal.depopulated-used` | error | a depopulated ball is also a pin row |
| `proposal.exposed-pad` | warning | a pin named like an exposed pad (`EP`, `PAD`, `THERMAL`, the family's `ep_number`) while the package has no `ep`, or an `ep` that no pin row names |
| `proposal.sides` | warning | a four-sided family whose pins do not divide by four and that gives no per-side counts |
| `proposal.range` | error | a range whose minimum exceeds its maximum, or a span not larger than the body width |
| `proposal.uncited` | warning | a row or parameter without `cite` |
| `proposal.doubt` | warning | one per `[[doubt]]` |

The checks are pure functions of the proposal and the family table of c0260; they need no drawing, so
an agent gets them at the first dry run. They check the pin rows against the package; c0260's own
`package.*` checks of the package alone (for example `package.pin-count` against the arrangement) run
again at step 6, so a proposal and a hand-written record are judged by the same rules.

### 6. Dense packages: what goes wrong and what Fenolite does

| failure mode (research section 2) | what Fenolite does |
|---|---|
| ball and pin counts wrong on large grids | the count is a stated parameter and checked against the rows (`proposal.pin-count`); grids need two proposals that agree |
| depopulated balls missed or invented | `depopulated` is explicit; `proposal.depopulated-used`; c0262 checks balls against the drawn grid |
| row labels misread (skipped letters) | `row_labels` are copied from the drawing, every ball name is checked against them (`proposal.pin-outside`) |
| pins shifted by one row of a long table | two proposals must agree row by row; the rendered sheet lists pins beside pads |
| mechanical dimensions read wrong | only parameters are proposed; the generator draws, and c0262 checks body against span and land against pattern |
| a datasheet with several packages | one proposal per package variant; `package.family` and `pins` must match one outline |
| multiplexed MCU pins | the primary name goes in `name`; alternates stay in the proposal file, not in the records |

- **Two proposals required** (`proposal.second-required`, error) when the family is `grid` or
  `package.pins > 100`. The threshold is Fenolite's choice (`INFERRED`), recorded in
  `docs/datasheet-proposals.md`, and matches the research's "units split above about 100 pins".
- **Agreement.** Both proposals must name the same datasheet SHA-256 and have different
  `proposer.name` or `proposer.kind` values (`proposal.not-independent`, error, otherwise). After
  normalisation (rows sorted by number, units parsed, citations and doubts ignored), every pin row and
  every package parameter must be equal. Each difference is one `proposal.disagree` (error) naming the
  field, both values and the pages cited. Independence cannot be proven by Fenolite; the guide asks for
  two separate runs that do not see each other's output, or an agent and a person.
- *Alternative:* refuse dense packages altogether. Rejected: the research puts MCUs in coverage step 5
  through this pipeline; two agreeing proposals plus the generator plus a review is the safeguard.

### 7. Review gate (extends c0262's review)

`fenolite library review DIR --accept` of c0262 calls `fenolite.library.proposals.review_gate(folder,
datasheet)` for a device whose `origin.tool` is `fenolite library propose`. It refuses (exit 5) with:

| code | when |
|---|---|
| `proposal.review-doubt` | a `[[doubt]]` remains in a proposal of the folder |
| `proposal.review-uncited` | a pin row, a package parameter or a rating has no citation |
| `proposal.review-datasheet` | `--datasheet` is missing or has another SHA-256 than the origin |
| `proposal.review-unchecked` | c0262's check of the current files has not passed |

- After acceptance, c0262 records the reviewer and raises the label to the level c0262 defines for a
  reviewed device (`CORPUS-VERIFIED` in the research).
- **Only a person accepts.** Fenolite cannot tell who runs a command. The guide page says an agent never
  runs `review --accept`, and c0262's review requires `--reviewer NAME`. Open question 1 asks whether
  the MCP tool list should leave `library review` out.

### 8. Guide page `datasheets`

A new tool page under `src/fenolite/agent/skill/references/datasheets.md`, within the page budget of
"Page budgets and writing rules". It teaches:

- the loop of decision 1 and the tested lines of `library propose` (skeleton and dry run);
- copy, do not compute: numbers as printed, with their page; ranges as `min..max`;
- what never goes in a proposal: coordinates, pads, outlines; a guessed pin; a value from another
  datasheet or from memory; a `[[doubt]]` deleted without reading the page again;
- dense packages: two separate runs, row labels from the drawing, depopulated balls listed;
- one proposal per package variant; alternates stay in the proposal;
- never run `library review --accept`; hand the folder and the rendered sheet to a person;
- `Read next:` `footprints`, `parts`, `checks`.

The start page index gains the line of `datasheets`.

## Codes introduced

| code | severity / exit | when |
|---|---|---|
| `proposal.datasheet-mismatch` | error | the proposal names another datasheet |
| `proposal.unknown-family` | error | decision 5 |
| `proposal.duplicate-pin` | error | decision 5 |
| `proposal.pin-count` | error | decision 5 |
| `proposal.pin-outside` | error | decision 5 |
| `proposal.depopulated-used` | error | decision 5 |
| `proposal.range` | error | decision 5 |
| `proposal.exposed-pad` | warning | decision 5 |
| `proposal.sides` | warning | decision 5 |
| `proposal.uncited` | warning | decision 5 |
| `proposal.doubt` | warning | decision 5 |
| `proposal.second-required` | error | decision 6 |
| `proposal.not-independent` | error | decision 6 |
| `proposal.disagree` | error | decision 6 |
| `proposal.review-doubt`, `-uncited`, `-datasheet`, `-unchecked` | error | decision 7 |
| `FEN-3004` | exit 3 | malformed proposal, a geometry key, a file that is not a PDF |
| `FEN-3002` | exit 3 | a newer proposal schema |
| `FEN-7001` | exit 7 | a corrected proposal over a reviewed or edited folder |

No new `FEN-` code. Each `proposal.*` code joins `fenolite.library.codes` and `explain.toml`.

## Risks / Trade-offs

- **Two agreeing proposals can share one mistake** (same model, same misreading). Mitigation: the
  generator and c0262's rules check what can be checked, the sheet puts pins beside pads for the
  reviewer, and the label stays `UNVERIFIED` until a person accepts.
- **Citations can be invented.** Fenolite checks only that they are present; the reviewer checks them
  against the pages. The review sheet lists every citation.
- **`proposer.name` is free text.** Independence is a claim, recorded and shown, not proven.
- **The threshold of 100 pins is arbitrary.** It is a named constant, documented, and easy to change.

## Open questions

1. *Should the MCP server leave `library review` out of its tool list?* Recommended: yes; review is a
   person's act, and a tool that an agent can call invites it. The CLI keeps it.
2. *Should the MCP tool accept a proposal inline (for clients without a file system)?* Recommended: not
   now; revisit with c0196's file handling, keeping the file as the record.
3. *Should a proposal with `--licence CC0-1.0` be allowed outside a pack workflow?* Recommended: yes; pin
   tables and dimensions are facts, but only a reviewed device enters a pack.
4. *Should the agent be allowed to propose a manufacturer land at all?* Recommended: yes, as parameters
   with a citation, because the datasheet's land wins over the calculator (research section 2); c0262
   compares the drawn land with it.

## Relation to the batch

- **c0246** gives the ranges the package parameters are written in.
- **c0259** gives the records the proposal is converted into.
- **c0260** gives the family table the self-checks read, the generators that draw, and the manufacturer
  land override that `package.land` feeds.
- **c0261** draws the symbol from the pin table, with its groups.
- **c0262** checks, renders the review sheet and records the review; this change adds the gate.
- **c0264** writes devices from downloads the same way; both share the device folder writer, the
  target rule and the re-import rule.
- **c0266** accepts only reviewed devices; a proposed device enters a pack only after review.
- **c0267** may propose identity and ordering data from suppliers; it never fills a pin table.
