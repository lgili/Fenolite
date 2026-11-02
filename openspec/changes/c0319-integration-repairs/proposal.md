## Why

The first complete local gate on combined commit `96d687d1` finished with 23
failures, 19173 passes and 55 skips. Focused branch proofs did not cover all
interactions among the new library, import, viewer and block features. Integration
closure waits until these failures are resolved and the complete gate and exact
published-head CI pass. Accumulated working branches may be published for CI.

## What Changes

Repair concrete backend, model/lens, registry, CLI and authored-data contract
inconsistencies exposed by that run. Keep native bytes and supported defaults
unless the failing case proves an actual defect. Preserve resource requirements,
licence roles, evidence levels and strict refusal/comparison semantics.

## Capabilities

- Modified: `verification-loop`, `licensing-and-notices`, `kicad-file-backend`.

## Impact

Only demonstrated integration failures and their direct proofs are in scope.
Independent import coverage additions and the pending version freeze remain in
their own changes. No release, history rewrite, runtime dependency, external
acceptance or native Altium verification is added.

The exact L8 Windows CI also exposes path-separator, ZIP creator metadata and
cross-drive authored-kit failures. Task 1.12 repairs those three bounded cases
without changing checked fixture archives or native acceptance gates.
