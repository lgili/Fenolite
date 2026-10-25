## 0. Entry check

- [ ] 0.1 Record the parameter forms the readers give for Altium and KiCad parts. Proof: `openspec validate c0187-review-panels --strict --no-interactive`.

## 1. Panels and filter

- [ ] 1.1 Parameters and routed lengths in the board scene. Proof: `uv run pytest tests/unit/view/test_scene.py -q`.
- [ ] 1.2 The query parser and the Nets and Components panels (scenario "Parts of a footprint on the bottom"). Proof: `uv run pytest tests/unit/view/test_filter.py -q`.
- [ ] 1.3 Highlight modes and Find similar. Proof: `uv run pytest tests/unit/view -q`.

## 2. Closing

- [ ] 2.1 Browser review on S-0187's board: panel speed and a filter. Proof: the record under this task.
- [ ] 2.2 Docs, fast gate. Proof: `make check-fast`.
