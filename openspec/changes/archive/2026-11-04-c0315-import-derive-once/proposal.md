## Why

Library derivation serializes an instance's unchanged comparison signature once for
each earlier variant and again when storing a new variant. Boards with many differing
instances repeat the same expensive work. Corpus measurements exposed this path while
preparing the larger integration batch; no timing improvement is claimed yet.

## What Changes

Compute each instance's normalized signature once and reuse it for comparisons and
storage. Preserve native bytes, variants, ordering, issues and callbacks. Add an
authored variant stress case and run existing derivation/vendor compatibility proofs.

## Capabilities

- Modified: `design-conversion`.

## Impact

Only the existing derivation implementation and its regression tests change. There
is no public argument, file format, dependency or evidence-level change.
