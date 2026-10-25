## 0. Entry check

- [ ] 0.1 Measure the public `.BomDoc` and the side views of S-0786; record the facts. Proof: `openspec validate c0190-documentation-views --strict --no-interactive`.

## 1. Views

- [ ] 1.1 Output jobs (scenario "Public output jobs"). Proof: `uv run pytest tests/unit/view/test_documentation.py -k outjob -q`.
- [ ] 1.2 BOM table. Proof: `uv run pytest tests/unit/view/test_documentation.py -q`.
- [ ] 1.3 Draftsman side views and callouts. Proof: `uv run pytest tests/unit/view/test_drawing.py tests/corpus/test_draftsman_draw.py -q`.

## 2. Closing

- [ ] 2.1 Browser review of S-0786's project. Proof: the record under this task.
- [ ] 2.2 Docs, fast gate. Proof: `make check-fast`.
