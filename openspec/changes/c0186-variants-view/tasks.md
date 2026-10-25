## 0. Entry check

- [ ] 0.1 Find the public projects with variants and record the keys in `project.md`. Proof: `openspec validate c0186-variants-view --strict --no-interactive`.

## 1. Read and draw

- [ ] 1.1 Add `read/variants.py`. Proof: `uv run pytest tests/unit/backends/altium -k variant -q`.
- [ ] 1.2 Draw not-fitted parts and varied parameters (scenario "An authored variant"). Proof: `uv run pytest tests/unit/view/test_variants.py -q`.
- [ ] 1.3 Add `--variant` (scenario "Unknown variant"). Proof: `uv run pytest tests/unit/cli/test_view_cmd.py -q`.

## 2. Closing

- [ ] 2.1 Docs, fast gate. Proof: `make check-fast`.
- [ ] 2.2 The maintainer compares a variant of their own with Altium. Proof: the record under this task.
