# Preserve original non-DSL custom footprint properties

## Why
An author-source OpenAir import silently loses D1 Description_1, whose native value contains line feeds. The importer filters non-printable values while vendorization removes all custom properties. Full strict proof reports exactly one missing field. The public Part.properties contract explicitly refuses line feeds; changing that contract is unnecessary.

## What changes
Preserve a custom source footprint property that cannot be declared through existing Part.properties in its original native footprint definition, with its exact name, value, pose, UUID and formatting slots. Keep representable user properties owned by the generated Part and unchanged public validation. Retain exact per-instance variants and collision guards. No new API, model field, comparison exclusion or accepted difference.
