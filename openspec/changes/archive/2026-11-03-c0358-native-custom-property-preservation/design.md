# Design

Status: root reviewed and approved native-owned fallback before runtime.

The native source is public author commit 89aacf5013fc0ffe4b988a2e3c5a227bce3c4983; no third-party fixture enters core. External v2 preserves its five-input partial-source run; v3 includes active author DRU as a sixth input. The sole v2 failure is L7 field-pose D1:Description_1 name present versus absent.

`emit.design._properties` excludes values failing isprintable(), as required by the current DSL contract. `vendor.library_footprint` then removes every non-library property. Correct this ownership hole: retain native custom properties which are not representable through the existing filtered Part declaration. Do not relax Part.properties/build.property-invalid, change typed model fields, normalize text, or alter equivalence. Source property duplication and unsupported malformed syntax must retain existing refusal behavior.

Authored controls must prove multiline native values survive vendor/import/build with exact field name/value/pose and full strict geometry equality, and Part.properties continues to refuse LF/tab/NUL. Representable properties still leave library definitions and are declared by Part. Two distinct per-instance retained payloads must remain distinct variants rather than one overriding another. Ordinary default75 complete output maps must remain unchanged outside the triggered case.

## Proposed symmetric native mirror fallback

Scope: ordinary, printable, uniquely named custom properties whose only Part.field representation limitation is mirror≠side (top mirrored or bottom unmirrored). Native fields already represent both states. Before selecting fallback, validate every other existing size/thickness/layer/anchor/font/effects constraint and reject malformed/unknown/duplicate/reserved inputs. No layer, size, style or mirror normalization.

Derivation first brings a bottom footprint to its local top frame; its property mirror toggles exactly once. Thus both source anomalies become local-mirrored native fields. Vendor retention and request emission must agree on that exact symmetric condition. Retain the native property in the existing definition/slots and omit only the unrepresentable Part.field request. Keep the ordinary printable Part.properties declaration: the existing library-equal-property rule avoids duplicate append; a changed value conflicts instead of silently overwriting native ownership. Normal representable properties still use the current generated Part.field path.

Reclassify only the old authored native mirror-negative as an explicit preservation positive after approval. Unknown font/effects/justify, duplicate names/nodes, reserved names, anisotropic/missing/nonpositive dimensions, unsupported layer, inexact anchor and text control-byte refusals remain. Original LF behavior remains. No new API, canonical field, schema, dependency, waiver or comparator change.

The proposed proof separates current production-import RED from a low-level existing derive/embed representation probe; the latter never counts as an implemented importer fix. Authored9/10 cases span both sides, cardinal rotations, hidden/visible and plain/styled forms, plus distinct native variants. Compare every existing strict geometry/name/value/pose operator and native originals/rebuilt safely; source hashes and default complete plans must remain unchanged. Public source material stays external; only its pinned corpus hash may enter this addendum. Runtime implementation awaits review.

## Native proof collection correction

Complete import/build levels8/S proofs require an actual KiCad executable. Move the existing eight authored mirror/TAB proof cases to `tests/kicad/board/test_import_native_properties.py`, marked `needs_kicad`; leave pure controls in unit. Both native jobs collect all eight. The four writer10 parameters use the existing `kicad_min_major(10)` capability marker: native9 executes four writer9 cases and reports four unsupported writer10 skips, while native10 executes all eight. Do not count those skips as passes. Assertions, source targets, exact values, native operators and all validation/CI requirements remain unchanged. Shared authored source helpers are reused; no public API, runtime or baseline change.
