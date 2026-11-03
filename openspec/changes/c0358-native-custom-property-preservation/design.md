# Design

Status: root reviewed and approved native-owned fallback before runtime.

The native source is public author commit 89aacf5013fc0ffe4b988a2e3c5a227bce3c4983; no third-party fixture enters core. External v2 preserves its five-input partial-source run; v3 includes active author DRU as a sixth input. The sole v2 failure is L7 field-pose D1:Description_1 name present versus absent.

`emit.design._properties` excludes values failing isprintable(), as required by the current DSL contract. `vendor.library_footprint` then removes every non-library property. Correct this ownership hole: retain native custom properties which are not representable through the existing filtered Part declaration. Do not relax Part.properties/build.property-invalid, change typed model fields, normalize text, or alter equivalence. Source property duplication and unsupported malformed syntax must retain existing refusal behavior.

Authored controls must prove multiline native values survive vendor/import/build with exact field name/value/pose and full strict geometry equality, and Part.properties continues to refuse LF/tab/NUL. Representable properties still leave library definitions and are declared by Part. Two distinct per-instance retained payloads must remain distinct variants rather than one overriding another. Ordinary default75 complete output maps must remain unchanged outside the triggered case.
