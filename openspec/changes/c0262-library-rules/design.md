## Context

- **Source.** `docs/research/component-library.md`: section 2 (a rules document with an automated
  checker, rendered previews and an old/new visual diff in CI, then human review; cross-checks catch what
  AI extraction gets wrong), section 4.2 (generated footprints, manufacturer pattern first), section 4.7
  (`fenolite library check`, `fenolite library review --accept`, the rendered review sheet as the
  evidence of the review) and the table of section 5 (c0262, size M, after c0260 and c0261).
- **What exists on `dev` (0.6.0).**
  - `fenolite.library` (change c0223) derives a footprint library from a board and reports drift; its
    package may import `model`, `geometry` and the backends (import-graph test).
  - `view/library.py` (c0179) builds library scenes: a footprint on a one-part board drawn by the board
    scene, a symbol on a sheet of its size. `fenolite catalog view` (catalog spec, "Installed catalog visual
    browser") makes one deterministic standalone page from resolved definitions and metadata, through plan
    and confirm.
  - `fenolite view NEW --compare OLD` (c0184, `visual-diff`) draws added, removed and moved primitives of
    two boards or two sheets.
  - The catalog spec already requires, for shipped footprints, courtyard containment of pads and body and
    positive clearance between pads of different numbers, enforced by catalog tests only.
  - c0248's `check_device(device, symbol, footprint)` reports a device that disagrees with its symbol or
    footprint (`build.device-mismatch`), and `device_digest` hashes a record without its provenance.
  - The evidence grammar accepts a scope after any label (`verification-evidence`, "Evidence label
    grammar"): `CORPUS-VERIFIED (review 2026-11-02)` parses.
- **From the batch.** c0259 gives records (`fenolite.package.v0`, `fenolite.pins.v0`,
  `fenolite.device.v0`, part rows) with stable ids, versions, licence, sources, evidence and a review
  key, plus a canonical writer. c0260 gives package families, the land calculator, manufacturer land
  override and generated footprints and bodies. c0261 gives generated symbols and the `library` action
  words.

## Goals / Non-Goals

**Goals**

- Every cross-check the research names runs on every record, in CI, in seconds, offline.
- A reviewer sees one page per item that holds everything needed to judge it against the datasheet.
- A change to a generator or a record shows, before merge, which items changed and how.
- Trust is recorded: who reviewed which exact bytes, when; and it is lost automatically when the bytes
  change.

**Non-Goals**

- See the proposal. In addition: no electrical simulation of a device, no check of ratings against a
  design (c0253), no supplier or lifecycle check (c0267).

## Decisions

### 1. The command and its targets

```
fenolite library check data/ --json                                  # findings; exit 5 on an error
fenolite library check devices/EXB6202 --sheets review/ --dry-run     # plans the sheets
fenolite library check data/ --compare base/data --sheets review/ --confirm
fenolite library check vendor/MyLib.pretty --json                    # a plain library: geometric rules only
```

- **Targets** (one or more): a record file (`*.toml` with a known schema), a folder of records (walked in
  code-point order of relative paths, `.toml` only), or a library file or folder (`.kicad_sym`,
  `.kicad_mod`, `.pretty`, `.SchLib`, `.PcbLib`), read with the existing readers. A library item has no
  record, so the rules that need a record (body against span, depopulated balls, land against
  pattern, envelope) do not run on it; the result says which rules ran per item (`rules_run`).
- **What is checked per record kind.** A package: its record, and the footprint and body that c0260
  generates from it. A pin table: its record and the symbol that c0261 generates. A device: its record,
  `check_device` against its resolved symbol and footprint, and its pins and package records. A part
  row: the fields c0259 requires.
- **An unreadable record** is the finding `library.record-invalid` (error), naming the file and carrying
  the `FEN-` code its parser raised; the walk continues. A target that does not exist is `FEN-3001`
  (exit 3), as for any command.
- **Options.**
  - `--sheets DIR` (decision 5).
  - `--compare OLD` (decision 6).
  - `--fail-on error|warning` (default `error`): the lowest severity that gives exit 5.
  - `--rules CODE,...` and `--skip CODE,...` select rules by code.
  - `--limit` and `--fields` work as the contract defines them.
- **Package placement.** `fenolite.library.rules` holds pure functions over model values: `PinTable`,
  the c0259 package record value, `DeviceDef`, `SymbolDef`, `FootprintDef` and `Range`. The CLI reads the
  records, calls the generators in `fenolite.catalog`, resolves definitions and passes them in. This
  needs no new import edge: `library` keeps `model`, `geometry` and the backends, and `cli` may import
  anything. *Alternative considered:* the rules inside `catalog`. Rejected: `catalog` is stdlib-only and
  imports only `model`, while containment needs `geometry`.

### 2. The rules

Codes, severities and what each needs. Constants are Fenolite-authored, recorded in
`docs/formats/library/rules.md` as `INFERRED`, with the public source of any fact they rest on.

| code | severity | needs | rule |
|---|---|---|---|
| `library.record-invalid` | error | record | the record does not parse (c0259 parser), with its `FEN-` code |
| `library.pad-count` | error | device, or package + footprint | the pads reached by the device's map, the footprint's numbered electrical pads (less `unused_pads`) and the pin table's numbers (with `stacked`) are the same set; the package's `pins` equals the generated footprint's terminal count as c0260 counts it. Missing numbers on each side are listed in natural order |
| `library.pin1-location` | error | footprint with ≥ 3 numbered pads, or 2 for a polarized package | pad `1` (or `A1` on a grid array) lies at or above-left of the centroid of all numbered pads: `x ≤ cx` and `y ≤ cy` (footprint frame, Y down), at least one strict. A Fenolite convention for zero orientation |
| `library.pin1-marker` | warning | footprint | some graphic on `F.SilkS` or `F.Fab` has a bounding-box centre strictly nearer to pad 1's centre than to any other pad's centre (skipped for a non-polarized two-pad package) |
| `library.courtyard-missing` | error | footprint | no closed outline on `F.CrtYd` (or `B.CrtYd` for a bottom-only footprint) |
| `library.courtyard-containment` | error | footprint | the courtyard does not contain every copper pad shape and the body outline (from `bodies`, else the `F.Fab` outline), by `geometry` containment |
| `library.pad-clearance` | error | footprint | two pads of different numbers touch or overlap (copper clearance 0 or less) |
| `library.body-span` | error | package | for a family with leads beyond the body (gull-wing, TO, DIP, as c0260 names families): `body.width.max < span.min`; for a no-lead family: `span`, when given, overlaps `body.width`; for all: `2 × lead.length.min < span.max − body.width.min + 2 × T` with `T = 0.05 mm`, and every range has `min ≤ max` |
| `library.depopulated` | error | grid-array package | `rows × columns − len(depopulated) == pins`; each depopulated position is inside the grid; the footprint has no pad at a depopulated position; ball names use row letters `A`…`Z` without `I`, `O`, `Q`, `S`, `X`, `Z`, then `AA`, `AB`… (the public JEDEC outline convention, source registered) |
| `library.land-mismatch` | error / warning | package with `[land]` | the footprint's pads differ from the manufacturer pattern: any difference is an **error** for a generated footprint (the generator must apply the pattern exactly), and a difference over `T = 0.05 mm` in size or position is a **warning** for an imported or hand-authored one |
| `library.land-calculator-delta` | info | package with `[land]` | the largest difference between the pattern and what the calculator would give, so a reviewer sees how unusual the pattern is |
| `library.pin-grid` | error / warning | symbol | a pin connection point or length off 0.254 mm (10 mil, the Altium writer's unit) is an **error**; off 2.54 mm (100 mil) is a **warning** |
| `library.footprint-filter-miss` | warning | symbol + device | no pattern of `ki_fp_filters` matches the device's footprint name (case-sensitive glob on the name without library) |
| `library.footprint-filter-broad` | warning | symbol | a filter pattern is empty, `*`, or matches every name |
| `library.pin-group-type` | warning | pin table | a `ground` or `supply` row whose type is not `power_in`, `power_out` or `passive`; an `nc` row whose type is not `no_connect` |
| `library.hidden-power` | error | symbol | a hidden `power_in` pin that is not stacked on a visible pin |
| `library.duplicate-pin` | error | symbol | two pins of one unit and body style share a number, except stacked pins |
| `library.source-unknown` | error | record | a source id that the tree's source register (c0259) does not hold; without a register, `library.sources-unchecked` (info) |
| `library.evidence-claim` | error | record | `evidence` above `CORPUS-VERIFIED`, or `CORPUS-VERIFIED` without a `[review]` |
| `library.review-stale` | error | reviewed record | the record digest or sheet digest of the review differs from the current one (decision 7) |
| `library.interface-changed` | error | `--compare` | a record keeps its id while its pin numbers, pad numbers or pin-to-pad map changed (c0259: an interface change takes a new id) |
| `library.removed` | warning | `--compare` | an id of OLD is missing from NEW and was not deprecated in OLD |
| `library.waiver-unused` | warning | record | a waiver names a code that produced no finding |
| `library.render-failed` | error | `--sheets` | a sheet could not be built; names the item and the reason |

- *Why `pin1-location` uses the centroid.* It holds for dual rows, quad packages, grid arrays, headers and
  polarized two-terminal parts in the zero orientation, needs no per-family table, and still catches a
  footprint rotated by 90° or 180°. A connector whose pin 1 is elsewhere waives the code with a reason.
- *Alternative considered:* a severity per rule configurable by the user. Rejected for v0: `--fail-on`
  and waivers cover the cases, and a fixed table keeps CI results comparable between repositories.

### 3. Waivers

Any record may hold:

```toml
[[waiver]]
code = "library.pin1-location"
reason = "pin 1 is at the cable end, datasheet S-0zzz figure 3"
```

A waived finding is reported with severity `info` and `waived = true`. `library.record-invalid`,
`library.evidence-claim` and `library.review-stale` cannot be waived (`FEN-3004` at parse). Waivers are
part of the record, so they are part of its digest and of what a reviewer accepts.

### 4. Result

`result.items[]`: `{id, kind, file, evidence, effective_evidence, rules_run, findings, review, sheet}`,
in code-point order of `id`. A device's `effective_evidence` is the lowest of its own label and those of
its pins and package records (lowest wins, as everywhere in Fenolite). `issues` holds every finding with
`where` naming the item id and the element (`pad 1`, `pin 7`, `body.width`). `summary` counts findings
by severity and items by evidence.

### 5. Review sheets

- `--sheets DIR` plans `DIR/<kind>/<name>.html` per item, `DIR/index.html` (a table of every item with
  its findings, evidence and a link) and `DIR/sheets.json` (`fenolite.library_sheets.v0`: per item its
  id, record digest, sheet path and sheet SHA-256). It uses dry-run, confirmation, staged plans and
  receipts.
- One sheet is one standalone page built by a new `view/review_sheet.py` from the existing library scenes
  of c0179. It holds:
  - every unit of the symbol;
  - the footprint with copper, `F.Fab`, `F.CrtYd` and silk layers, and the outline of the 3D body
    (c0260);
  - the pin table with each pin's side and unit;
  - the package dimensions with their ranges, sources and evidence;
  - the pin-to-pad map;
  - the findings, waivers included;
  - the review state;
  - with `--compare`, the overlay of decision 6.

  Like the catalog browser, the view module receives resolved definitions and metadata and imports no
  catalog.
- The bytes depend only on the inputs: no time, no absolute path, no host name. A sheet's SHA-256 is
  what a reviewer accepts (decision 7).
- *Alternative considered:* PNG images through `kicad-cli`. Rejected for this change: it needs KiCad on
  the CI runner of the data repository, would not show the pin table and sources, and the HTML page
  already gives exact measurements on click. PNG stays an open question.

### 6. Old/new diff

- `--compare OLD` takes a record tree or library of the same kind (in CI, the base branch checked out in a
  separate folder). Items are paired by stable id (c0259), plain library items by lib id.
- Per pair it reports `change`: `added`, `removed`, `changed` or `same`. A `changed` item also gets the
  canonical-JSON paths of the record fields that changed, and whether the generated symbol and the
  generated footprint changed (comparing their canonical JSON digests). The rules
  `library.interface-changed` and `library.removed` run on the pairs.
- For a changed footprint or symbol, the sheet holds the visual-diff overlay of c0184: footprints are
  placed alone on one-part boards, as the library scene does, and compared as boards; symbols are
  compared as sheets. Nothing new is drawn by this change: it reuses `view --compare`'s overlay and
  change list.
- `result.compare` lists the pairs in id order. A pair that is `same` has no sheet overlay.

### 7. The review record

```
fenolite library check devices/EXB6202 --sheets review/ --confirm   # prints each sheet's SHA-256
fenolite library review devices/EXB6202 --accept --reviewer jdoe --sheet 3f9a1c2e7b4d --dry-run
fenolite library review devices/EXB6202 --accept --reviewer jdoe --sheet 3f9a1c2e7b4d --confirm --plan <id>
fenolite library review devices/EXB6202 --revoke --dry-run
fenolite library review devices/EXB6202 --json                     # read-only: the review state
```

- **What `--accept` writes**, into each target record, through c0259's canonical writer:

  ```toml
  evidence = "CORPUS-VERIFIED"

  [review]
  reviewer = "jdoe"
  date = "2026-11-02"
  digest = "sha256:..."          # record without [review] and evidence, plus the generated outputs
  sheet = "sha256:..."           # the sheet the reviewer named with --sheet
  fenolite = "0.7.0"
  previous_evidence = "UNVERIFIED"
  accepted = ["library.land-calculator-delta"]   # warning and info codes present at review
  ```

- **Digest.** SHA-256 of the canonical JSON of the record with `evidence` and `review` cleared, of the
  canonical JSON of the definitions generated from it, and, for a device, of the digests of its pins and
  package records. So a hand edit, a referenced record's edit or a generator change all make the review
  stale. Formatting changes do not, because the record is canonicalised first (as `device_digest`).
- **Preconditions** (nothing is written when one fails):
  - the item has no error finding (exit 5 with the findings);
  - `--reviewer` is non-empty printable text without `@` (a handle or name, no e-mail address in shipped
    data), else `FEN-2001`;
  - `--sheet` is at least 12 hex digits and is a prefix of the current sheet's SHA-256, else `FEN-4002`
    ("the sheet changed: review again"). The sheet is rebuilt in memory, so the accepted bytes are those
    the reviewer opened;
  - the current evidence is `UNVERIFIED`, `INFERRED` or a stale `CORPUS-VERIFIED`. A record above
    `CORPUS-VERIFIED` is refused with `FEN-7001`, because a review never lowers a label.
- **Date.** From `--timestamp` when given (the contract's deterministic flag), else today's UTC date.
- **Per record.** A target folder reviews each record in it. A device review does not review its pins and
  package records; its `effective_evidence` stays the lowest of the three.
- **`--revoke`** removes `[review]` and restores `previous_evidence`.
- **Stale review.** `library check` reports `library.review-stale` (error), and the item's
  `effective_evidence` is `previous_evidence` until a new review. Builds that read the record (c0248)
  use the same effective label.
- **Agents.** `library review --accept` is excluded from the MCP server's tools (c0195), and the guide
  page says: never run it unless the person names themselves as reviewer and has opened the sheet. A CLI
  cannot prove who typed a command; the `--sheet` digest proves which bytes were accepted, and git
  history proves who committed them.
- *Alternative considered:* a separate `reviews.toml` beside the records. Rejected: a record copied to
  another tree (a project, the data repository) would lose its review, and two files would have to be
  kept in step.
- *Alternative considered:* a new evidence level `REVIEW-VERIFIED`. Rejected for now: it changes the
  evidence vocabulary of every package. The research and the batch use `CORPUS-VERIFIED`; the scope of
  the label and the `[review]` table say that it came from a review (open question 1).

### 8. CI usage

Documented in `docs/library-ci.md`. The c0266 data repository and Fenolite's own unit job (for the shipped
records that c0259 moves to data) run the same steps:

```yaml
- run: git worktree add ../base origin/${{ github.base_ref }}
- run: >
    fenolite library check data/ --compare ../base/data
    --sheets review/ --fail-on error --confirm --json > library-check.json
- uses: actions/upload-artifact@v4
  if: always()
  with: {name: library-review, path: "review/\nlibrary-check.json"}
```

The job fails on an error finding (exit 5). Reviewers download the artefact, open `review/index.html`,
and run `library review --accept` locally on the items they checked. CI never runs `--accept`. A pull
request that changes a reviewed record without a new review fails with `library.review-stale`. In the data
repository that is the intended gate. In Fenolite's repository the shipped records stay `INFERRED`, so
they are never stale.

## Codes introduced

The `library.*` codes of decision 2, each with an `explain.toml` entry, plus:

| code | severity / exit | when |
|---|---|---|
| `FEN-3001` | exit 3 | a target does not exist (existing code) |
| `FEN-3004` | exit 3 | a waiver of a code that cannot be waived (existing code) |
| `FEN-2001` | exit 2 | `review` without `--accept`/`--revoke` but with `--reviewer`; a bad `--reviewer` (existing code) |
| `FEN-4002` | exit 4 | `--sheet` is not the current sheet (existing code) |
| `FEN-7001` | exit 7 | a review would lower a label above `CORPUS-VERIFIED` (existing code) |

No new `FEN-` code.

## Hypotheses registered by this change

| id | statement | settled by |
|---|---|---|
| `H-G-LIBRARY-RULES` | each `library.*` rule fires on its authored bad record and stays silent on the authored good records and on every shipped catalog definition | `tests/unit/library/test_rules.py` |
| `H-G-LIBRARY-REVIEW` | a review's digest changes for every edit of the record, of a referenced record and of the generated output, and for no reformatting | `tests/unit/library/test_review.py` (hypothesis-based) |

## Evidence level per behaviour (before merge)

| behaviour | level |
|---|---|
| rules, waivers, result | `INFERRED` (`H-G-LIBRARY-RULES`) |
| sheets and the diff overlay | `INFERRED`; the overlay keeps visual-diff's own level |
| review record and staleness | `INFERRED` (`H-G-LIBRARY-REVIEW`) |
| a reviewed record's label | `CORPUS-VERIFIED (review <date>)` while not stale |

## Risks / Trade-offs

- **`CORPUS-VERIFIED` stretches the word "corpus".** A review compares against a datasheet, not a corpus of
  files. Mitigation: the scope says `review`, the `[review]` table says who and when, and open question 1
  offers a dedicated level.
- **The centroid rule for pin 1** can be wrong for unusual connectors. Mitigation: a waiver with a reason,
  visible on the sheet and accepted by the reviewer.
- **A generator change makes every reviewed item stale.** That is intended: the reviewed bytes changed. The
  old/new diff shows what changed, and a reviewer can accept a folder at once after reading the diff
  sheets.
- **Shipped catalog definitions may fail new rules** (for example `library.pin1-marker`). Mitigation:
  task 2.4 runs the rules on the catalog first and either fixes a definition or waives the code with a
  reason, before the CI step is required.

## Open questions

1. *Raise to `CORPUS-VERIFIED`, or add a level such as `REVIEW-VERIFIED`?* Recommended: `CORPUS-VERIFIED`
   with the scope `(review <date>)` now, as the research proposes, and revisit when the evidence
   vocabulary is next changed.
2. *PNG sheets for pull-request comments?* Recommended: later, as an option that uses `kicad-cli` only
   when it is installed. The HTML sheet stays the evidence.
3. *Should a device review require reviewed pins and package records?* Recommended: no; report the lowest
   label as `effective_evidence`. A package reviewed once serves many devices.
4. *Tolerance `T = 0.05 mm` for an imported footprint against the manufacturer pattern?* Recommended: yes,
   as one documented `INFERRED` constant; c0264 reuses it for its cross-check.
5. *Should the review sheet require that the reviewer opened it?* Recommended: the `--sheet` digest prefix
   is the proof Fenolite can give; nothing more is enforceable from a CLI.

## Relation to the batch

- **c0259** (data format): records, stable ids, canonical writer, the `review` key (this change defines its
  content), deprecation (read by `library.removed`) and the source register.
- **c0260** (footprints): families, the calculator (for `library.land-calculator-delta`), the manufacturer
  pattern and the generated footprint and body that the rules and sheets read.
- **c0261** (symbols): generated symbols and the `library` action words, under which `check` and `review`
  land.
- **c0264** (import): imported items are checked by the same rules; its cross-check against the family
  generator reuses `library.land-mismatch` and `T`.
- **c0265** (datasheet proposals): `propose`, then `check`, then `review` is the pipeline of research 4.7.
- **c0266** (device packs): its CI is decision 8; its releases contain records with their reviews.
- **c0248** (devices): `check_device` and `device_digest` are reused. **c0249** (lock): unchanged; the lock
  pins a data release, and a release holds the reviewed records.
