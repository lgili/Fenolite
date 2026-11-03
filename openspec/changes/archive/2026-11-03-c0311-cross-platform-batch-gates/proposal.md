## Why

The batch-six CI on `8d74a798` passes Linux, macOS and KiCad 9 but fails six Windows tests and cannot start the KiCad 10 corpus tests. Native rooted paths, Git checkout conversion, console newline conversion and host/container temporary paths invalidate existing portability and byte-fidelity promises.

## What Changes

- Reject native rooted output folders even when Windows does not call them absolute.
- Fetch library/upstream trees with explicit, portable Git line-ending settings.
- Make validation fixtures compare serialized bytes and parsed command/path values.
- Keep KiCad 10 corpus temporary files at a path available inside its container, with matching artifact collection.
- Record the measured heavy-board import census rows from exact-commit CI and check table coverage without loading corpus payloads.

## Impact

Existing commands and result schemas stay unchanged. Changes affect library generation/get/replay, focused portability tests and the CI workflow. No new dependency, FEN code, evidence promotion or third-party fixture is needed.
