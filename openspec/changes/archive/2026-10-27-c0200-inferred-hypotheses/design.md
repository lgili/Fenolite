## Context

`Evidence(level, oracle, hypotheses)` labels every reply; `Evidence.combine` keeps the lowest level and merges
the hypotheses. `docs/hypotheses.md` is the register, and `tests/unit/test_hypotheses_register.py` checks
that every cited id is a row.

## Decisions

1. **One row per kind of claim, not per site.** Six sites judge a built design or a model with Fenolite's own
   rules (`api/sides.py` twice, `checks/validate.py`, `checks/assignment_compare.py`, `cli/cmd_diff.py`,
   `cli/cmd_impedance.py`): they share `H-G-MODEL-OWN`. The others each get the row of their feature.
2. **The kit run that verifies nothing** (`cmd_kit.UNVERIFIED_RUN`) cites `H-A-KIT-STABLE`, the row of the
   kit's own files, like `BUILD_EVIDENCE` beside it.
3. **Altium row form.** A second-backend row that is `INFERRED` must start its result with `pending (author
   report)` (`tests/unit/test_altium_rows.py`). The schematic layout row does: its native acceptance is the
   author's. It is named `H-A-LAYOUT-REPLAY`, outside the `H-A-SCH-` stem whose rows are claims of the
   build.
4. **A source test, not a reply test.** The rule is about what the code may emit. The test reads the AST of
   every module, so a new bare `INFERRED` fails in `make check-fast`, before any reply exists. A cap inside
   `combine` is structural and allowed; `ALLOWED` names the one other exception, and a second test fails
   when that exception's call is gone.

## Risks / Trade-offs

- `dataclasses.replace(evidence, level=Level.INFERRED)` keeps the hypotheses of its base and is not read by
  the test; every such site today starts from an evidence that cites one.

## Open Questions

None.
