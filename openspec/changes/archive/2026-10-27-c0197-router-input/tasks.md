## 1. Router input fidelity

- [x] 1.1 Write a board-wide `track_width` rule with `opt` as the width of classes without one, and keep or clamp class widths (scenario "Board-wide preferred width keeps class widths"). Proof: `uv run pytest tests/unit/backends/specctra/test_dsn_rules.py -k width_all -q`.
  - 2026-10-26: proof passed (2 tests: the scenario on the bench with PWR 1.0 mm, SIG 0.25 mm and HV without a
    width; and a clamp into `[min, max]`). A class holds a width of its own when its model class sets one or an
    earlier named rule set `opt` (design, decision 1); the default rule takes `opt`.
- [x] 1.2 Write one-sided clearance rules as class pairs, and resolve a class against itself by the board's rule order (scenario "One-sided clearance writes pairs"). Proof: `uv run pytest tests/unit/backends/specctra/test_dsn_rules.py -k "one_sided or class_class" -q`.
  - 2026-10-26: proof passed (3 tests). A one-sided rule pairs its classes with every other written class; a
    rule on `netclass Default` alone still raises the default rule (the nets without a class), which changes no
    class; nets without a class get one `specctra.rule-not-sent` against a one-sided rule. `test_clearance_of_named_classes`
    asserted the old raise and now asserts the pairs. Specctra, routing and backend suites: 6204 passed.
- [x] 1.3 Accept comma-separated globs in `--order` (scenario "Several globs in one tier"). Proof: `uv run pytest tests/unit/cli/test_route_cmd.py -k order -q`.
  - 2026-10-26: proof passed (5 tests: the two old scenarios, "Several globs in one tier" with a blank after the
    comma, and three empty globs refused with `FEN-2001`). The guide's command page is regenerated (`GLOBS`).
- [x] 1.4 Bench: route an authored dense board with Freerouting before and after 1.1 and 1.2. Record the share routed and the new DRC findings in `docs/evidence/routing.md`, and register the two hypotheses of c0175's decision 1 in `docs/hypotheses.md`. Proof: `uv run pytest tests/routing/test_freerouting_planes.py -k router_input -rA` with the pinned jar and `kicad-cli`, or the job `routing` in CI.
  - 2026-10-26: proof passed locally (pinned jar `251101c3eeac`, OpenJDK 25.0.5, `kicad-cli` 10.0.7). The bench lives in
    `tests/routing` (the job `routing` runs that folder with Freerouting; c0175 named `tests/kicad/routing`, which
    no job runs with a jar). Outcome `dsn-router-input` = `better`: before, 3 connections open (`HV1`, `HV2`,
    `SIG5`); after, none; 0 clearance findings on both. `H-G-DSN-WIDTH-ALL` and `H-G-DSN-ONE-SIDED` are
    registered; the evidence row was recorded without the environment's `JAVA_TOOL_OPTIONS` line.

## 2. Closing

- [x] 2.1 `docs/formats/specctra/dsn.md` (the rule table), `docs/cli-contract.md` (`--order`), the guide page `routing` if it names `--order`, `openspec/README.md`, `CHANGELOG.md` under `## [Unreleased]`. Proof: `uv run pytest tests/unit/agent tests/unit/test_format_facts.py -q`.
  - 2026-10-26: proof passed (117 tests). The rule table of `docs/formats/specctra/dsn.md`, `--order GLOBS` in the
    contract, the row of `openspec/README.md` (new changes start at c0198), an entry under Fixed of `[Unreleased]`.
    The guide page `routing` names no `--order`. The branch carries the commit that opens `0.6.0.dev0` (the same
    as on `c0195-mcp-server`), so that `[Unreleased]` may hold entries.
- [x] 2.2 `make check-fast`. Proof: `make check-fast`.
  - 2026-10-26: exit 0, 13 984 passed, 34 skipped. The first run failed one count in
    `tests/unit/verify/test_register.py` (the `H-G-DSN-*` rows, now 24 with c0197's two).
