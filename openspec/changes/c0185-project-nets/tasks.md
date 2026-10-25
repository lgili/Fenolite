## 0. Entry check

- [ ] 0.1 Read the adapter's connectivity and `connectivity.md`; record the scopes it handles. Proof: `openspec validate c0185-project-nets --strict --no-interactive`.

## 1. Nets

- [ ] 1.1 Add `view/project_nets.py` (scenario "A net through a port"). Proof: `uv run pytest tests/unit/view/test_project_nets.py -q`.
- [ ] 1.2 Cross highlight between sheets and board in the page. Proof: `uv run pytest tests/unit/view -q`.

## 2. Closing

- [ ] 2.1 Browser review on a public hierarchical project. Proof: the record under this task.
- [ ] 2.2 Docs, fast gate. Proof: `make check-fast`.
