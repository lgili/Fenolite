## 0. Entry check

- [ ] 0.1 Pin the Chromium and font versions of the CI image; record them. Proof: `openspec validate c0191-viewer-visual-tests --strict --no-interactive`.

## 1. Tests

- [ ] 1.1 Fixtures and the screenshot harness (scenario "A changed colour fails"). Proof: `uv run pytest tests/visual -q`.
- [ ] 1.2 Interaction tests. Proof: `uv run pytest tests/visual -q`.
- [ ] 1.3 CI job and `tools/update_view_refs.py`. Proof: the job's run on the branch.

## 2. Closing

- [ ] 2.1 Docs (`CONTRIBUTING.md`), fast gate. Proof: `make check-fast`.
