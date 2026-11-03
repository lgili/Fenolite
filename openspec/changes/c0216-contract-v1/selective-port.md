# Current-source selective port packet (review before runtime)

## Source and protected baseline

Target source is the current CAC model0/CLI0 branch, starting from 78c086be. The remote
bf6532a4 is historical implementation material only, not an authoritative model or schema freeze.
No wholesale merge, old goldens, old review.json, old public surface, frozen-v0 receipt, or generated
v1 schemas will be copied. Package version remains unchanged; active CLI CONTRACT_VERSION stays v0.

Remote model/design.py would delete the current model.bom-only validation and issue code. Remote
board/circuit/drawn classes also predate current font, BOM-only, max_curve_error and forthcoming
intersheet_refs fields. These whole files must never replace the current classes. The remote evidence
validation tail and producer changes are independent work and must not reappear through this port.

## Packet A: c0216 prerequisite

Selectively adapt the new cli.surface and cli.deprecation modules and surface-generator tool.
Patch current cli.api only for CONTRACT_VERSION, Command.schema and deprecation metadata.
Patch current CLI entry-point integration and capabilities only for the declared deprecation/contract
features. Preserve all current envelope, evidence, payload assembly, plans, errors, receipts and producer
behavior. Teach the added cli.deprecated issue and capabilities contract metadata with tested guide lines.

Generate the CLI surface from actual current commands and actual api/dsl exports, not the historical
46-command or 57-command receipt. Currently discover finds 58 modules including hidden _echo, hence
57 visible commands. New migrate is introduced by c0218 later. Before any stable release the surface
check remains current-source drift detection; the released baseline policy remains explicit.

Proof: authored surface comparison/deprecation/dual envelope tests; complete consistency examples;
current paging/capabilities/explain/guide controls; unchanged v0 schema bytes; lint/types/residue.
Capture the pre-freeze review externally for actual reviewer decisions; do not label an old list reviewed.

## Packet B: c0217 descriptors and public formats

Port new frozen result-description classes, the closed test-validator helper, explicit format
classifications and mirror descriptors. Add schema-id acceptance only at individually reviewed public
reader boundaries; preserve strict future-version and input type refusal, canonical identities and
source bytes. Compare existing producer outputs rather than modifying payloads to fit descriptors.

Adapt the generator from the current source. Existing active equivalent/convert/import/verify-source
v0 descriptors must first reflect current BOM/font/source changes, then final v0 bytes are captured.
No exemption for these actual targets. Existing unknown/free data maps retain documented typed
boundaries; there is no generic fallback for an unknown command or missing result type.

Current readers are patched in focused hunks; no cmd_library/view/build source file is replaced wholesale.
Generate prepared schemas from current descriptors only. Final frozen-v0/current surface inventories wait
for root's actual final model0 source including c0348, not dbfd/695 or any historical count receipt.

Proof: current-command schema coverage; actual CLI reply measurement with closed validation; public
planned-file and reader cases; model-independent schemas current; future/version/type negative controls.

## Packet C: c0218 migration (activation waits for final model0)

Port pure migration helpers and migration CLI with authored historical-folder/version/rollback controls.
Patch design.py only for schema marker/version functions and model.migrated registration while retaining
all existing validation; canonical.py only for raw-folder load, migration, in-memory notice and strict
decode. Keep existing canonical sorting/default omission and every current model field/type/default.
The migration Step contributes its four helper fields; they are metadata, not justification to remove
any field from model0. Keep all current source entities and extension keys.

The migration 0->1.0 changes only the schema marker and retains field and extension contents.
Historical release fixtures must be authentic original-tag outputs with SOURCE commits; do not invent
fixtures or silently refresh fixture content. Existing schema0 files are frozen from the final real source;
schema1 files are generated from that same source, including bom_only, max_curve_error, fonts and the
reviewed DrawnLabel.intersheet_refs field. No freeze or activation occurs before that field is final.

Proof: old folders load in memory without writes; current folders do not migrate; malformed/future
versions refuse before decoding unknown content; reviewed plans reject changed inputs; rollback/backup
behavior; new fields/defaults/opaque bytes survive migration; metadata-only byte delta of source0 vs1.
Then root owns exact-head check-fast/CI, final source capture, integration and archival.

## Review request

Approve the three bounded packets and the preserved-source constraints before runtime edits.
Remaining task checkboxes and historical proof receipts will not be imported as current passes.
