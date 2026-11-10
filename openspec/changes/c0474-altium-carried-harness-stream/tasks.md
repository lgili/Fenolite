# Tasks: c0474-altium-carried-harness-stream

- [x] 1.1 Route opaque subtree items whose root `RECORD` is 215 or 218 (with their 216/217 children) into
      a new `SheetPlan.carried_additional` field (`drawn._Sheet`, `layout.SheetPlan`), append them in
      `schdoc.additional_records` behind its own records with the owner base captured once, omit a final
      owner of 0, refuse them in the ASCII form, count them in `harness_blocks` occupancy, and unit-test
      the written streams (`test_carried_harness_records_write_to_the_additional_stream`).
  - Proof: `uv run pytest tests/unit/backends/altium/test_drawn_altium.py tests/unit/backends/altium/test_schdoc.py tests/unit/backends/altium/test_drawn_harness.py -q`
- [x] 1.2 Add the `CHANGELOG.md` entry and the change docs (`proposal.md`, `design.md`,
      `specs/altium-schematic-writer/spec.md`).
  - Proof: `uv run ruff check . && uv run python tools/gen_agent_guide.py --check`
