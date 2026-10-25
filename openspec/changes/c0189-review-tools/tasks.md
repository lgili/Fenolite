## 0. Entry check

- [ ] 0.1 Read the measure code and the server; write `fenolite.review.v0` under this task. Proof: `openspec validate c0189-review-tools --strict --no-interactive`.

## 1. Tools

- [ ] 1.1 Edge measurement (scenario "Two pads"). Proof: `uv run pytest tests/unit/view/test_edge_measure.py -q`.
- [ ] 1.2 Deep links and `--select`. Proof: `uv run pytest tests/unit/view tests/unit/cli/test_view_cmd.py -q`.
- [ ] 1.3 Review marks and `--marks` (scenario "Marks for an agent"). Proof: `uv run pytest tests/unit/view/test_server.py tests/unit/cli/test_view_cmd.py -q`.
- [ ] 1.4 Print and SVG. Proof: the record of task 2.1.

## 2. Closing

- [ ] 2.1 Browser review: an edge measure, a link, a mark, a print to PDF. Proof: the record under this task.
- [ ] 2.2 Docs, agent guide, fast gate. Proof: `make check-fast`.
