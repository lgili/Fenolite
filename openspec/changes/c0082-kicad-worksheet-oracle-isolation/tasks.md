## Local correction

- [x] 1. Record the failed CI diagnostics and reproduce missing rejection diagnostics in a parallel pinned Linux KiCad 10 probe as UID 1001 (24/24 baseline failures).
- [x] 2. Isolate the worksheet helper with the existing runner and retain strict rejection checks; proof: `uv run pytest tests/kicad/test_version_constants.py -q` — 8 passed after the final isolation change.
- [x] 3. Prove the boundary helper in parallel under pinned Linux KiCad 9 and 10 as UID 1001 and under the root environment used in CI: 24 accepted/future pairs per image/user combination, four parallel workers, all passed. The harness imports and calls the actual `test_worksheet_boundary` function on a fresh temporary directory per pair.
- [x] 4. Update CHANGELOG, validate this OpenSpec change strictly, and run `make check-fast`: all checks passed, 5936 tests passed and 10 skipped; residue scan has zero hits with the private gate enabled.
- [x] 5. Create a local commit with the maintainer's Signed-off-by; do not push. Proof: the local commit carries `Signed-off-by: Luiz Carlos Gili <luizcarlosgili@gmail.com>`; dev is one commit ahead of origin/dev.

## Later batch integration

- [ ] 6. Run `make check` on the final rebased integration tree before merging, and require the next authorized CI run to pass before archival.
