# Cited datasheet proposals

The pipeline is: read a PDF with external tools, write a cited parameter proposal, check it, generate
deterministic definitions, inspect the library review sheet, and ask a person to accept it. Fenolite
does not run a model, OCR, a PDF parser or a network client. The only document inspection in the core
is the `%PDF-` prefix and SHA-256. Fixtures in `tests/data/proposals/` describe an invented component
and one authored page; no manufacturer document is shipped.

`fenolite library propose --datasheet FILE --json` returns a parseable unfilled skeleton and the
`datasheets` guide topic. Add one or two `--proposal FILE` arguments and `--out DIR` to generate a
reviewable project folder. Use `--dry-run`, inspect the plan, then use `--confirm --plan ID`. The folder
is `DIR/<device-name>/`; the source PDF is referenced by name and digest and is not copied. Corrected
proposals may replace an unreviewed, unedited folder. Reviewed, edited or shrinking folders require a
new destination (`FEN-7001`); `--allow-lossy` does not bypass this proposal rule.

The root TOML keys are closed:

| table | fields and meaning |
|---|---|
| root | `schema = "fenolite.proposal.v0"`; the tables below only |
| `datasheet` | `file` basename, `sha256`, optional printed `revision` and `title` |
| `proposer` | `kind` (`agent`, `person`, `tool`), nonempty `name`, ISO `date`; recorded claims |
| `device` | project `id` (`NS:NAME`), `manufacturer`, `mpn`, `summary`, `ref_prefix`, `cite` |
| `package` | `family`, that family's parameter keys from the [footprint schema](footprint-generators.md), `cite`, optional `land`; grids also have printed `row_labels` and optional stated `pins` |
| `package.land` | manufacturer parameter keys of that family, and `cite`; its source text is filled from the PDF and page |
| `pin` | `number`, primary `name`, `type`, optional `group`, `side`, `unit`, `bus`, `shape`, `hidden`, `stacked`, `alternates`, `cite` |
| `pin.alternates` | `name`, optional `type` and `shape`; retained only in the proposal |
| `ratings` | `vin`, `vout`, `voltage`, `current`, `power`, `temperature`; each has unit-text `min`/`max`, optional `limit` (`abs_max`, `operating`) and `cite` |
| `part` | `mpn`, optional `packing`, `manufacturer`, `summary`, `lifecycle`, `grade`, `datasheet`, `cite` |
| `doubt` | `field` path and `reason`; uncertainty is never filled automatically |
| `cite` | positive integer `page`, optionally one `table` or `figure` |

Pin types, groups and sides use [the pin-table vocabularies](symbols.md). Family parameters are the
installed c0260 schema: chip, molded, gullwing, nolead, grid, to, dip, header and connector. The skeleton
lists their exact keys. Only one connector position count belongs to a proposal. Lengths are parsed to
integer nanometres; ratings to integer micro-units (millikelvin for temperature). A reversed bound is
a finding. A floating-point TOML number or unknown key is refused. Manufacturer land `pad` dimensions
and grid `pad = "nsmd"` are parameters; coordinates and drawing primitives remain forbidden.

The generated `vin` limit becomes the device voltage rating. Other standard ratings retain their
model keys; `vout` is retained as a named record property because the device model has no independent
output-voltage field. Supply either `vin` or `voltage`, since both map to that one rating. The complete
cited source remains in the proposal. Bounded package dimensions
are shown in the record; open bounds and explicit nominal values remain in the cited proposal so an
unknown bound is not turned into an exact dimension.

| finding | meaning |
|---|---|
| `proposal.datasheet-mismatch` | the supplied document differs from the named hash |
| `proposal.unknown-family` | the family is not installed |
| `proposal.duplicate-pin` | a pin number occurs twice, including stacked entries |
| `proposal.pin-count` | pin rows/positions disagree with terminal count |
| `proposal.pin-outside` | a number, row label or excluded position is outside the declared grid |
| `proposal.depopulated-used` | an excluded ball is also a pin |
| `proposal.range` | inconsistent bounds/span, multiple connector variants or excessive input size |
| `proposal.exposed-pad` | exposed-pad geometry and a named/numbered row disagree |
| `proposal.sides` | an unexplained four-sided count |
| `proposal.uncited` | a factual row or parameter group lacks its citation |
| `proposal.doubt` | one unresolved question |
| `proposal.second-required` | a grid or package above 100 terminals needs a second reading |
| `proposal.not-independent` | both proposer identities are equal |
| `proposal.disagree` | a pin row or normalized package parameter differs; the finding gives both values and pages |
| `proposal.review-doubt` | a human review cannot accept an unresolved question |
| `proposal.review-uncited` | a human review cannot accept missing citations |
| `proposal.review-datasheet` | review needs the exact PDF |
| `proposal.review-unchecked` | the current files differ or have not passed checks |

The threshold of 100 terminals and the resource bound of 10,000 terminals are Fenolite conventions,
`INFERRED`. They are input checks, not manufacturer or industry limits. For grids, the proposer must
copy row labels rather than infer skipped letters. The generator's deterministic geometry is renamed
to those declared labels; the original proposal and map remain visible. Two proposals must agree after
unit normalization and pin-row ordering. Citation locations and doubts do not affect agreement, but
they still affect review acceptance. Fenolite cannot prove that two readings were independent.

The generator and library findings remain visible alongside proposal findings. Error findings plan no
writes. The records have `evidence = "UNVERIFIED"`, the chosen licence (default `see source terms`) and
a distinct `ProposalOrigin` with the document, each original proposal hash, proposer identities and
generated output checksums. `--licence CC0-1.0` does not grant review or publication approval.

Generate a base sheet with `library check --sheets` and open it. It contains the cited proposals and
open doubts as well as generated symbol units, footprint, body and pin map. The person who checked it
accepts `device.toml` individually through `library review --accept --reviewer NAME --sheet HEX
--datasheet FILE` and the plan protocol. The gate checks the PDF, citations, doubts and current sealed
records and outputs, and reruns the proposal's generator and library checks. A later proposal/model
edit makes the review stale. Review is excluded from the
MCP schema and rejected by its runtime. See [library rules](library-rules.md) and
[the CI workflow](library-ci.md); CI never accepts a review.

Consumers that already checked a record's human review can call
`proposal_outputs_current(device_record, folder)` to verify the three record seals and every raw-byte
native/model/proposal checksum without reading the PDF. Record seals canonicalize TOML and exclude
only evidence and review metadata; output checksums hash the exact file bytes. This helper does not
grant acceptance or establish a licence.
