## Why

Exact L10 `ea762411cbb24bc5f9ba5a16d8b372ae7c720568`, CI run `41421198968`,
KiCad 9 job `125196886139`, fails 41 drawn-corpus rows. Thirty-six are instances
of the VME owner whose per-sheet library snapshots share native IDs but differ
in complete property nodes. Five unrelated inputs remain below the reader floor.
The global source-symbol table refuses before comparison, even though native
KiCad loads the owner and its non-property definition content is identical.

The correction must preserve local metadata, not ignore it. An authored CC0
two-child witness reproduces the global refusal with identical logical pins,
body and native connectivity. Pin, geometry, core-default and flag mutations
provide closed-boundary controls. This packet proposes the implementation;
no decoder or guard is changed before review.

## What Changes

- Retain full source definitions by sheet context and content digest, including
  property values, effects, order and unknown slots.
- Admit only bounded property-local variants with identical complete
  non-property AST and unchanged protected core defaults. Retain refusal for
  pin, body, flag, core-default, missing-context and wrong-binding differences.
- Carry the context through imported assets and backend lowering; emit each
  sheet's original native ID and complete local definition. Add no model/S field.
- Bind every context input and asset into reviewed plans and receipts.
- Prove CC0 positive/negative cases, native property/semantic readback and
  default byte stability before replaying VME. Keep the five reader-floor
  refusals, naming warnings and exact whole/CI gates independent.

## Capabilities

### Modified Capabilities
- `drawn-schematic`: context-local source definitions and strict metadata preservation.
- `board-to-code`: deterministic assets and reviewed context binding.

## Non-goals

No reader-floor widening, corpus exception, loss/acceptance flag, global cache
sorting, metadata omission or pin-universe intersection. No name-election fix,
new FEN code, dependency, model/S field or native Altium claim. Native KiCad 10
and full validation belong to CI; the maintainer's PC receives focused local
tests only.
