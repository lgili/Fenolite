# Tasks: c0465

Rules for every task:

- Public sources only, each recorded with an S- id from S-2240..2249 and an evidence label.
- Authored boards, records and reports only; no corpus board in a unit test, and no private board data.
- Run each touched test file alone with `-n 0`. Heavy runs go through `fenolite-heavy` with `-n 2`.
- Depends on c0462 (its `check-relaxed` records). Rebase onto c0462 before task 5.

## 1. Evidence

- [x] 1.1 Record S-2240 (Altium Net Antennae constraints), S-2241 (Altium Short-Circuit constraint settings) and
  S-2242 (KiCad's custom rule constraint table, 9.0 and 10.0) in `docs/evidence/sources.md`. Add their facts
  to `docs/formats/altium/rule-file.md` and `docs/formats/kicad/rules.md`, with the hypotheses
  `H-A-RULE-ANTENNA`, `H-A-RULE-SHORT` and `H-K-SHORT-ALLOW`. Proof:
  `uv run pytest tests/unit/test_legal_docs.py tests/unit/test_format_facts.py -q -n 0`.
- [x] 1.2 S-2243: a census of the keys of the public ShortCircuit and NetAntennae records (counts only).
  Proof: the census script's output, recorded in the row.

## 2. Model

- [x] 2.1 `short` and `antenna` in `RuleKind`, with their limits checked in `Rule`. Get the model review's
  approval, then regenerate the schemas and update `docs/design-model.md`. Proof:
  `uv run pytest tests/unit/model/test_rule_allowances_c0465.py -q -n 0`, `uv run python tools/model_review.py --check`,
  `uv run python tools/gen_schemas.py --check`.
- [ ] 2.2 `design.rules.rule()` takes both kinds; agent guide lines. Proof:
  `uv run pytest tests/unit/dsl/test_rule_allowances_c0465.py tests/unit/agent/test_pages.py -q -n 0`,
  `uv run python tools/gen_agent_guide.py --check`.

## 3. Check

- [x] 3.1 `checks/allowances.py`: the governing `short` rule of a pair, and `stub(design, item)` on
  `CopperGraph`. Proof: `uv run pytest tests/unit/checks/test_drc_allowances_c0465.py -k stub -q -n 0`.
- [x] 3.2 The copper stage: allowed shorts, `summary["allowed"]`. Proof:
  `uv run pytest tests/unit/checks/test_copper_allowances_c0465.py tests/unit/checks/test_copper.py -q -n 0`.
- [x] 3.3 The DRC stage: `shorting_items`, `track_dangling` and `via_dangling` entries, and
  `check.allowance-unresolved`, which goes in `ISSUE_CODES`, `docs/cli-contract.md` and `explain`. Proof:
  `uv run pytest tests/unit/checks/test_drc_allowances_c0465.py tests/unit/checks/test_waivers.py -q -n 0`.

## 4. KiCad

- [ ] 4.1 Lowering (design D6): defaults written as nothing, an `all`/`all` allowance as
  `rule_severities.shorting_items`, the rest as `rules.kind-unchecked`. Proof:
  `uv run pytest tests/unit/backends/kicad/test_rule_allowances_c0465.py -q -n 0`.
- [ ] 4.2 Probe `dru-short-allow` on 9.0.9 and 10.0.6 (S-2244): two overlapping tracks of nets `A` and `B`,
  and a `clearance` rule between them with a negative `min`. Record whether `shorting_items` is still
  reported. If 10.0.6 records `present`, `KIND_SUPPORT["short"]` holds 10 and the net-pair allowance is
  written there. Proof: the probe files and `uv run pytest tests/unit/backends/kicad/test_rulemap.py -k kind_support -q -n 0`.

## 5. Altium

- [ ] 5.1 Rebase onto c0462. ShortCircuit and NetAntennae records map (design D5); `check-relaxed` is
  withdrawn; the kind table lists both as neutral. Proof:
  `uv run pytest tests/unit/backends/altium/test_rule_allowances_c0465.py tests/unit/backends/altium/read/test_rule_map.py tests/corpus/test_altium_rule_kinds_c0462.py -q -n 0`.
- [ ] 5.2 The Altium writer writes both kinds with the keys of S-2243. Proof: the same file, `-k write`, and
  `uv run pytest tests/unit/backends/altium/test_rulemap.py -q -n 0`.

## 6. Acceptance

- [ ] 6.1 Kit (S-2245). On an authored document in Altium Designer, run DRC on:
  - stubs of 40, 50 and 60 mil under a Net Antennae of 50 mil, and a stub that ends at a via joining nothing;
  - a short `AGND`–`DGND` under Short-Circuit `ALLOWED=TRUE`, and a short `VIN`–`DGND` under the default rule.
  Record which are reported, and set `H-A-RULE-ANTENNA` and `H-A-RULE-SHORT`. Proof: the agent's report.
- [ ] 6.2 CHANGELOG, `gen_evidence_matrix`, `gen_cli_surface` and the other generators with `--check`;
  `openspec validate c0465-check-allowances --strict`; each touched test file alone with `-n 0`.
