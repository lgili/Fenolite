# Tasks: c0481-step-surface-model-box

- [x] 1.1 `stepbox` measures the trimmed curves of a representation without edges, with the plane angle
  unit of its context (`_trimmed`, `_context_radians`, `_extremes`), with unit tests and the facts in
  `docs/formats/step/part21.md`.
  - Proof: `uv run --extra dev pytest tests/unit/backends/test_stepbox_surface_c0481.py tests/unit/backends/test_stepbox.py -q`
- [x] 1.2 Maintainer board (private, codes and counts only): F2 and F5 write 183 of 183 models.
  - Result 2026-11-11: F2 and F5 hold 183 bodies each; every one of the source's 175 STEP bodies is there.
