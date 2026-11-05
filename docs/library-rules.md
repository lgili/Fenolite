# Checking and reviewing library records

`fenolite library check TARGET... --json` checks records and plain KiCad/Altium libraries offline.
Directories are visited in path order; malformed records become `library.record-invalid` findings and
the walk continues. Missing targets are `FEN-3001`. Each item reports `rules_run`, findings, written and
effective evidence, and its current review and sheet digests. `--rules CODE,...` and `--skip CODE,...`
select checks. Error findings exit 5; `--fail-on warning` also fails on warnings.

The following diagrams describe the authored bad cases in `tests/data/library_rules/bad/` and the
adversarial geometry of `tests/unit/library/test_rules.py`. Dimensions are illustrative, in mm.

```text
Pin map: 1 -> 1, 2 -> 2, 3 -> ?        Courtyard: | pad | pad -> outside
Pin 1:   .---.       marker: absent    Clearance: [pad 1][pad 2] touching
         |   1  (below centroid)       Body/span: body [======], span [====]
Grid:    A1 A2, I1 I2 (I omitted)      Pin grid:  0----0.127 (off 10 mil)
Land:    specified [==], actual [===]  Hidden power: hidden VCC, no visible stack
```

| code | severity | what to inspect |
|---|---|---|
| `library.record-invalid` | error | TOML, schema, missing references and the parser's FEN code |
| `library.pad-count` | error | terminal count; missing pin numbers, pad numbers and map edges |
| `library.pin1-location` | error | pad 1/A1 against the numbered-pad centroid |
| `library.pin-order` | error (warning for a plain item with no record) | perimeter leads numbered clockwise in the top view: the land is the part's mirror image |
| `library.pin1-marker` | warning | silk/fab graphic centres nearest pad 1 |
| `library.courtyard-missing` | error | a closed top/bottom courtyard |
| `library.courtyard-containment` | error | copper and body outlines within the courtyard |
| `library.pad-clearance` | error | touching copper pads of different numbers on common layers |
| `library.body-span` | error | body, span, lead bounds and range ordering |
| `library.depopulated` | error | grid count, excluded balls, row letters and out-of-grid names |
| `library.land-mismatch` | error/generated; warning/imported | manufacturer's pad sizes/positions, exact for generated lands and tolerance 0.05 mm for imports |
| `library.land-calculator-delta` | info | largest manufacturer/calculator difference |
| `library.pin-grid` | error/10 mil; warning/100 mil | connection points and lengths |
| `library.hidden-power` | error | hidden power inputs stacked on visible pins |
| `library.duplicate-pin` | error | repeated pin numbers within a unit/body style |
| `library.pin-group-type` | warning | ground/supply power types and no-connect types |
| `library.footprint-filter-miss` | warning | supplied case-sensitive name globs against the device footprint |
| `library.footprint-filter-broad` | warning | supplied empty/all-name filters |
| `library.source-unknown` | error | S ids in the core/project register or D ids in the validated external library register |
| `library.sources-unchecked` | info | absence of a source register |
| `library.evidence-claim` | error | unsupported evidence promotion or missing review |
| `library.review-stale` | error | changed accepted record, output, dependencies or sheet |
| `library.interface-changed` | error | kept id with changed pin/pad numbers or map |
| `library.removed` | warning | removed id lacking an old deprecation |
| `library.waiver-unused` | warning | waiver that no longer matches a finding |
| `library.render-failed` | error | a sheet could not be rendered |

The constants and their evidence are in [the facts page](formats/library/rules.md). The checks are
Fenolite conventions labelled `INFERRED`. Existing shipped orientation and 50 mil layout conventions
have explicit compatibility waivers; their generated definitions remain unchanged. Change c0385 mirrored
the 55 catalog lands that had been drawn with Y up (numbered clockwise in the top view); the parts whose
source top view puts pad 1 at the lower left or the right keep that orientation with a waiver naming the
source.

An exceptional connector can record `[[waiver]]`, `code = "library.pin1-location"` and a nonempty
`reason`. A `library.pin-order` waiver is refused (`library.record-invalid`) unless its reason names the
S- or D- source whose top view numbers the part clockwise: a mirrored land swaps the pins of every part
fitted on it, so no generic reason may silence it (change c0385). A matched finding remains visible with `severity = "info"` and `waived = true`. Record-invalid,
evidence-claim and review-stale cannot be waived. With selected rules, omitted waivers are not called
unused. For devices, dependency findings retain their waivers and effective evidence is the weakest
current label, including stale or unreviewed dependencies.

Use `library check data --sheets review --dry-run --json`, inspect the plan, then use
`--confirm --plan PLAN_ID`. The receipt lists every written hash. Each filename uses a safe stable-id stem and an id-hash suffix to avoid namespace collisions.
`review/index.html` links the
standalone symbol/footprint sheets; `review/sheets.json` records their SHA-256 values. Sheets include
all symbol units, copper/fab/courtyard/silk, body outlines, pin rows, dimensions, sources, map and
findings. They show prepared review content; `library review TARGET --json` reports live acceptance.
Trust metadata is excluded from accepted content so accepting it cannot invalidate itself.

`--compare OLD` pairs stable ids, shows changed canonical field paths and generated definitions, and
embeds the existing visual-diff overlay on changed sheets. `artifact_sha256`/manifest `sha256` hashes
the full comparison artefact; `review_sha256` hashes the base sheet accepted by a human. Comparison
context is supplemental and does not make an existing base review stale.

After opening the base sheet, the person who checked it may run
`library review RECORD --accept --reviewer NAME --sheet HEX --dry-run`, then confirm the reviewed plan.
HEX must contain at least 12 matching hex digits. Acceptance requires no error finding, records
`[[reviewed_by]]` with date, content digest, sheet SHA-256, tool version, accepted warnings and previous
evidence, and raises the label to `CORPUS-VERIFIED (review DATE)`. A higher label cannot be lowered.
Accept records individually: distinct sheets have distinct acceptance hashes. `--revoke` removes the
review and restores its previous evidence. Reformatting preserves acceptance; edits require another
review. Review-stale can be replaced by a new acceptance of the edited, otherwise clean content.

Review acceptance and revocation are human CLI steps excluded from MCP schemas and rejected by its
runtime. An agent never runs either unless a person names themselves as reviewer and has opened the
sheet. CI only checks records and publishes review artefacts.
