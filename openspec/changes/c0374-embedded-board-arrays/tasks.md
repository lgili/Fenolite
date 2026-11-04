## 1. Explicit refusal

- [x] 1.1 Detection from the storage header/data length only (no record decoding).
- [x] 1.2 Refused `embedded-board` loss in convert and import; docs and CHANGELOG. Proof:
      `uv run pytest tests/unit/api/test_conversion_scope.py tests/unit/convert -q`.

## 2. Resolution (after c0173 Q7-Q9)

- [ ] 2.1 Record facts in `docs/formats/altium/pcb-document.md` with evidence labels.
- [ ] 2.2 Read instances and their documents; prove on kit cases.
