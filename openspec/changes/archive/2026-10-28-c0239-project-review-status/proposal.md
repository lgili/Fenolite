## Why

The viewer can locate check findings and compare revisions, but a user must infer which checks actually ran. An absent or skipped stage can look like a clean project, and messages lose their actionable hints. Review needs one entry point that preserves evidence and leads from a reported problem to its geometry.

## What Changes

- Add a project review panel with explicit not-run, passed, failed and limited states for reading, connectivity, ERC, DRC, clearance, placement, fills, conversion and fabrication export.
- Reuse `--check` and optionally load recorded convert/export replies with repeatable `view --report FILE`; display their scope, evidence and revision binding without running commands.
- Add severity/stage/text filters, previous/next review, original hints and geometry location using existing check markers. Reopening review does not claim a finding was fixed.
- Keep stale/unbound reports visibly limited and preserve report limits; refresh the classification when a live document changes.

## Impact

Touches viewer status composition, check-overlay metadata, view CLI, packaged page, guides and focused/browser tests. No core dependencies, CAD format changes or layout-reuse work. Complete CI remains a separate closing gate.
