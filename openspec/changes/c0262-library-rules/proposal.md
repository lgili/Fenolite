## Why

The library of c0259–c0261 is generated from facts, but facts can be wrong and generators can regress:
a pin table with one pin too few, a package whose body is wider than its lead span, a ball grid that
forgets a depopulated ball, a footprint whose pad 1 sits in the wrong corner. Today nothing checks a
library item as such: the catalog has its own tests, `fenolite check` checks boards, and every item stays
`INFERRED` or `UNVERIFIED` forever because no step can record that a person looked at it.

`docs/research/component-library.md` (sections 2, 4.2 and 4.7) describes how the best libraries keep trust
at scale: a rules document with an **automated checker**, **rendered previews**, an **old/new visual
diff** in CI, then **human review**. AI-extracted parts make this mandatory: the research cites pin and pad
count accuracy falling to 0 % on dense packages, caught only by cross-checks (pin count, depopulated balls,
body against span).

## What Changes

- **`fenolite library check TARGET...`**: rules over library records and definitions, reported as
  findings with `library.*` codes (exit 5 on an error finding). Targets are c0259 records, folders or a
  whole data tree, and also plain libraries (`.kicad_sym`, `.pretty`, `.kicad_mod`, `.SchLib`,
  `.PcbLib`), for which only the rules that need no record run.
- **Rules**, each with a code, a severity and the inputs it needs:
  - pad count against the pin map;
  - pin-1 location and marker;
  - courtyard presence and containment;
  - body against lead span;
  - depopulated balls and ball names of grid arrays;
  - land against the manufacturer's pattern;
  - the symbol pin grid;
  - footprint filter sanity;
  - pin group and type agreement, and hidden power pins;
  - record envelope, sources and evidence claims;
  - interface changes under a kept id.
- **Waivers**: a record may waive a code with a reason. A waived finding is reported as info, and an
  unused waiver is a warning.
- **Review sheets** (`--sheets DIR`): one standalone HTML page per record, built with the existing library
  viewer. Each page holds the symbol units, the footprint layers, the 3D body outline, the pin table, the
  package dimensions with their sources, the pin-to-pad map, the findings and the review state.
  `sheets.json` lists every sheet with its SHA-256. Plan and confirm, deterministic bytes.
- **Old/new diff** (`--compare OLD`): pairs records by stable id. It lists added, removed and changed
  records and what changed (record fields, generated symbol, generated footprint), and puts the
  existing visual-diff overlay (`view --compare`, c0184) on the sheet of each changed item.
- **Review record** (`fenolite library review TARGET --accept --reviewer NAME --sheet SHA256`):
  - It writes a `[review]` table into the record (reviewer, date, record digest, sheet digest, Fenolite
    version, previous evidence, accepted warnings) and raises `evidence` from `UNVERIFIED` or `INFERRED`
    to `CORPUS-VERIFIED`.
  - It is refused while an error finding remains, or when the sheet digest is not the current one.
  - `--revoke` undoes it, and a later edit makes the review stale (`library.review-stale`).
  - It is a writing command: plan, confirm, receipt. The MCP server does not expose it.
- **CI usage**: a documented workflow (check, sheets, compare against the base branch, artefact upload,
  fail on errors), used by Fenolite's own unit job for the shipped data and by the c0266 data repository.

## Non-goals

- No image (PNG/SVG) sheets and no PR comment bot: the sheet is HTML. PNG is an open question.
- No automatic fix of a finding. No change of `fenolite check` (boards) or of the KiCad DRC.
- No rules copied from a third-party rules document: each rule is stated here from public facts or as a
  Fenolite convention labelled `INFERRED`.
- No evidence above `CORPUS-VERIFIED` from a review, and no review by an agent.

## Evidence level required

- Rules, sheets and the diff: `INFERRED`, unit-tested with authored good and bad records
  (`H-G-LIBRARY-RULES`). The rule constants live in `docs/formats/library/rules.md` as `INFERRED`.
- The review record: `INFERRED` (`H-G-LIBRARY-REVIEW`). A record's own label is raised only by a recorded
  review, only to `CORPUS-VERIFIED`, and falls back when the review goes stale.

## Impact

- New:
  - `library/rules.py`, `library/review.py`, `library/sheets.py`;
  - `cli/cmd_library.py` actions `check` and `review`;
  - `docs/formats/library/rules.md`, `docs/library-rules.md`, `docs/library-ci.md`;
  - authored test records under `tests/data/library/`;
  - tests.
- Changed: `cli/data/explain.toml`, `docs/cli-contract.md`, the MCP tool list's exclusions, the guide page
  `parts.md`, `.github/workflows` (unit job step), `CHANGELOG.md`.
- Depends on:
  - c0259: records, stable ids, the canonical writer, the `review` key and the source register;
  - c0260: package families, the land calculator and generated footprints;
  - c0261: pin tables, generated symbols and the `library` action words;
  - c0248: `check_device` and the device digest.

  c0264 (import cross-check), c0265 (datasheet proposals) and c0266 (data repository CI) build on it.
- Size: about 7 design-days.
