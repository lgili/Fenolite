# Preserve original non-DSL custom footprint properties

## Why
An author-source OpenAir import silently loses D1 Description_1, whose native value contains line feeds. The importer filters non-printable values while vendorization removes all custom properties. Full strict proof reports exactly one missing field. The public Part.properties contract explicitly refuses line feeds; changing that contract is unnecessary.

## What changes
Preserve a custom source footprint property that cannot be declared through existing Part.properties in its original native footprint definition, with its exact name, value, pose, UUID and formatting slots. Keep representable user properties owned by the generated Part and unchanged public validation. Retain exact per-instance variants and collision guards. No new API, model field, comparison exclusion or accepted difference.

## Proposed mirror-ownership addendum, 2026-11-03

Investigate exact native ownership for an otherwise valid user-property pose whose mirror differs from the footprint side. Public Part.properties/Part.field behavior and the model remain unchanged. Preserve a valid native mirror through existing typed footprint fields/library slots instead of forcing a side-derived mirror. Runtime remains on hold until the authored RED and transform proof are reviewed. The existing source-mirror refusal is explicitly proposed to become a native-preservation positive; all other unsupported-pose/text/font/name refusals remain.
