## Why

The library cannot grow to thousands of real parts if each one is drawn by hand, and it must not grow by
trusting a model's drawing. Research section 2 of `docs/research/component-library.md` ("What AI can and
cannot do here") reports two public results: **pin tables extract well** from datasheets, while
**mechanical drawings do not** (footprint accuracy around 80 %, and pin and pad counts that fall to 0 %
on dense packages). Both sources reached the same fix: the model proposes **parameters**, a deterministic
generator draws the part, and cross-checks catch errors.

Section 4.7 turns this into a pipeline: an agent proposes a pin table and package parameters from a
datasheet, the generators of c0260 and c0261 draw, the rules of c0262 check, and a human review raises
the evidence. Fenolite must stay free of runtime dependencies and of any model: the agent works through
the MCP server or the shell with its own tools, and the core reads only a **structured proposal file**.

## What Changes

- **The proposal file** `fenolite.proposal.v0` (TOML): the datasheet's name and SHA-256, who proposed
  (agent, person or tool), the device identity, a package as a c0260 family with its parameters (ranges
  of c0246), an optional manufacturer land, a pin table, orderable parts, ratings, and a citation (page,
  table or figure) on every row. A `[[doubt]]` list holds what the proposer could not read. It holds
  **no geometry**: no coordinates, pads, outlines or polygons; such keys are refused.
- **`fenolite library propose --datasheet X.pdf`** without a proposal is read-only and returns a
  skeleton (the datasheet's SHA-256 filled in, every key and its meaning) and the guide page to follow.
- **`fenolite library propose --datasheet X.pdf --proposal P.toml [--proposal Q.toml] --out DIR`**
  under the mutation protocol: validates the proposal, checks that it names this datasheet, checks it
  against itself (pin count against the package, unique numbers, grid names, exposed pad, sides),
  converts it into c0259 records with `evidence = "UNVERIFIED"`, draws the footprint, body and symbol
  with c0260 and c0261, runs c0262's rules, and writes the device folder with the proposal beside it.
- **Dense packages need two proposals.** A grid array, or a package of more than 100 pins, needs two
  independent proposals that agree on every pin row and parameter; a disagreement is an error listing
  the rows.
- **Review gate.** c0262's `library review --accept` refuses a proposed device while a doubt is open, a
  row lacks a citation, or the datasheet given to the review has another SHA-256. Only a person accepts;
  the guide tells agents never to.
- **Guide page `datasheets`**: how an agent reads a datasheet into a proposal, what it must never do
  (draw geometry, guess a pin, accept its own proposal), the failure modes of dense packages, and the
  tested lines of `library propose`.

## Non-goals

- No model, PDF parser, OCR or network in the core, and no new extra. The core reads the PDF only to hash
  it and to check that it starts with `%PDF-`.
- No geometry from a proposal, ever: a land comes from the generator, or from the manufacturer land
  given as parameters (c0260's override).
- No raise of evidence by `propose`; review is c0262's.
- No alternate pin functions in the records (c0257 reserves `options`); they stay in the proposal file.
- No multi-package proposal: one proposal describes one package variant.

## Evidence level required

- Proposal parsing, self-checks and conversion: `INFERRED`, unit-tested on proposals and a datasheet
  authored for Fenolite (hypothesis `H-L-PROPOSAL`).
- Proposed devices: `UNVERIFIED` until a recorded review (c0262).

## Impact

- New: `src/fenolite/library/proposals/` (schema, checks, conversion), the `propose` subcommand of
  `cli/cmd_library.py`, the guide page `src/fenolite/agent/skill/references/datasheets.md`,
  `docs/datasheet-proposals.md`, authored test proposals and a small authored PDF under
  `tests/data/proposals/`, tests.
- Changed: `cli/cmd_library.py`, c0262's review (the gate), `docs/cli-contract.md`, the guide's start
  page index, `CHANGELOG.md`.
- Depends on: c0246 (ranges), c0259 (records), c0260 (families and generators), c0261 (symbol
  generator), c0262 (rules, render sheets, review). Shares the device writing of c0264.
- Size: about 6 design-days.
