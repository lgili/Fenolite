# Custom sheet properties

## Observed boundary

On `c129adba65bc0218f3ad5d2573cccb76f23c1d88`, native KiCad 10.0.6 and the
literal declared corpus driver refuse owner `kicad-demo-10-0-6-sch-106` during
extraction. Its declared SHA-256 is
`4cc3e74f2e47304bd3b360b18bab55d378573bc491b4f210aebe533890aa3dcb`.
A read-only exception observer identifies the unsupported property `Field2` on
sheet reference `slow_gpio`. No partition outcome exists for that execution.
Historical native 9.0.2 resolver differences remain separate evidence.

## Representation

`DrawnSheetProperty` carries name, literal text, point, rotation, justification,
hidden state and optional `DrawnFont`. It reuses DrawnField pose validation but
is a distinct typed value. `DrawnSheetRef.properties` is an appended optional
ordered tuple, empty by default. Names are nonempty, unique and cannot be
Sheetname or Sheetfile. Empty text is meaningful. Code continues to own the
sheet name and resolved filename; this addition creates no text override for
symbols, power symbols or built-in sheet fields.

The TOML form is `properties.<name> = { text = ..., at = ..., ... }` beside
existing `fields`. The closed property record requires text and at; length and
angle parsing follows existing exact rules. The writer preserves property order
and emits no new key for an empty tuple. Schemas and the final model-0 inventory
must describe the new type and carrier. The package/model/CLI versions remain
the development versions; model-1 activation is not part of this change.

## Native and comparison boundaries

Extract every supported custom property with its text and complete supported
pose/effects. Reject duplicate names, malformed values, unsupported native
attributes, unrepresented text-variable behavior and unsupported effects before
staging. Do not skip a property because it lacks a readable position. Preserve
all original input bytes. No native parser or grammar from another project is
used.

The existing private pose/font adapters carry the typed poses. A closed versioned
private record binds custom names to texts when passing through backend SheetRef;
it is not an opaque font placeholder or an extra public model. Native lowering
writes each property using the existing property writer, and ordinary sheets
retain identical output bytes. Level S compares text and every supported pose/
font attribute. The scene includes visible custom text using the existing font
support/refusal rules; hidden or empty text must not produce invented ink.

The same authored format-9 custom value `~` has conflicting native meanings:
9.0.9 exports literal stroked paths; 10.0.6 exports no tilde description or paths.
Extraction/scene therefore refuse this ambiguous legacy value. Format-10 literal
tilde remains supported, and writing literal tilde to target 9 refuses. This is
a measured cross-reader boundary, not a normalization to empty text.

## Proof and sequencing

Use original authored controls, including quotes/unicode, empty text, asymmetric
font axes, hidden state and duplicate/reserved-name negatives. Prove strict
import/build/all-nine equality and planted loss detection without accepted
differences or tolerance changes. Repeat the actual public VME owner only after
the authored controls pass; retain any subsequent resolver, naming or other
format refusal instead of treating extraction success as fidelity success.

Compare default output maps to the signed local repair source `11fa8594` under
the same runtime/recipe. The existing Mac authored byte mismatch stays a separate
failing immutable-table guard. No platform hash is selected as a correctness
oracle and no native gate or public corpus row is removed.
