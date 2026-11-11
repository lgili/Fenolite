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
- [x] 2.2 `design.rules.rule()` takes both kinds; agent guide lines. Proof:
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

- [x] 4.1 Lowering (design D6): defaults written as nothing, an `all`/`all` allowance as
  `rule_severities.shorting_items`, the rest as `rules.kind-unchecked`. Proof:
  `uv run pytest tests/unit/backends/kicad/test_rule_allowances_c0465.py -q -n 0`.
- [x] 4.2 Probe `dru-short-allow` on 9.0.9 and 10.0.6 (S-2244): two overlapping pads of nets `A` and `B`
  (tracks without a pad are re-netted by `kicad-cli`, so they never short), and a `clearance` rule between
  them with a negative `min`. Record whether `shorting_items` is still reported, and with
  `dru-short-allow-clearance` whether pads of `A` and `B` closer than their clearance are still reported. If
  10.0.6 records `present` for both, `KIND_SUPPORT["short"]` holds 10 and the net-pair allowance is written
  there. Proof: the probe files and `uv run pytest tests/unit/backends/kicad/test_rulemap.py -k kind_support -q -n 0`.

## 5. Altium

- [x] 5.1 Rebase onto c0462. ShortCircuit and NetAntennae records map (design D5); `check-relaxed` is
  withdrawn. The c0465 native follow-up below changes NetAntennae to carried. Proof:
  `uv run pytest tests/unit/backends/altium/test_rule_allowances_c0465.py tests/unit/backends/altium/read/test_rule_map.py tests/corpus/test_altium_rule_kinds_c0462.py -q -n 0`.
- [x] 5.2 The Altium writer writes both kinds with the keys of S-2243. Proof: the same file, `-k write`, and
  `uv run pytest tests/unit/backends/altium/test_rulemap.py -q -n 0`.
  Done 2026-11-06: `short` is a ShortCircuit record (number 15) whose `ALLOWED` is its severity (`TRUE` for
  `ignore`, `FALSE` for `error`, a `warning` refused `value-unsupported`), `antenna` a NetAntennae record
  (number 56) whose `NETANTENNAETOLERANCE` is its `max`. Both join `KIND_ORDER` and `WRITTEN_KINDS`, so the
  import keeps only the records it does not map. A set that relaxes nothing is written and lifts back as
  `checked`; the generated round trip says so.

## 6. Acceptance

- [x] 6.1 Kit (S-2245). On an authored document in Altium Designer, run DRC on:
  - stubs of 40, 50 and 60 mil under a Net Antennae of 50 mil, and a stub that ends at a via joining nothing;
  - a short `AGND`–`DGND` under Short-Circuit `ALLOWED=TRUE`, and a short `VIN`–`DGND` under the default rule.
  Record which are reported, and set `H-A-RULE-ANTENNA` and `H-A-RULE-SHORT`. Proof: the agent's report.
  Deferred 2026-11-07 (coordinator's decision): three tries on Altium Designer 24.5.2.23, the third after a
  clean restart (S-2283), stopped before any DRC. The script stops at `Priority := 1` right after
  `AddPCBObject` with an error its Try/Except does not catch, so no allowance board is saved. Measured on the
  way: a new ShortCircuit rule defaults to NetScope 2 (any net) and LayerKind 0 (same layer), the values the
  writer writes. `H-A-RULE-SHORT` and `H-A-RULE-ANTENNA` stay `UNVERIFIED`. A fourth try sets `Priority`
  before `AddPCBObject` (the writer puts the allowance rule at priority 1, above the default rule) and reports
  each rule's priority as read back.
  Progress 2026-11-10 (S-2245): assigning priority before registration also raises the native script
  error. Fresh authored documents from the Fenolite writer ran actual DRC on Altium 24.5.2.23.
  The scoped short allowance agrees with the controls. Antenna results differ from centre-line length:
  the 50 mil rule reports the 40 mil via-ended branch but none of the three bare tracks; at 0 mil it
  reports all four. Width controls bracket the bare-track boundary at 60/61 mil for a 10 mil track
  and 70/80 mil for a 20 mil track. See the retained S-2245 report in `docs/evidence/altium-acceptance.md`.
  Follow-up 2026-11-10 (S-2298): Altium 24.5.2.23 ran the 56-case matrix at 0, 50 and 1000 mil.
  Reconcile the rules by keeping native NetAntennae records with explicit coverage diagnostics instead of
  applying portable centre-line allowances. Keep authored portable checks and the native writer. Prove
  both conversion legs and the legacy model guard. Completed 2026-11-10. Proof:
  `uv run pytest tests/unit/convert/test_altium_rule_fates.py -q -n 0` exercises strict and tolerant
  conversions and the Python import/build round trip. `uv run pytest
  tests/unit/checks/test_drc_allowances_c0465.py -q -n 0` confirms the legacy finding retains its
  severity and the authored allowance still works. S-2245 verifies the scoped short controls and
  S-2298 verifies the antenna differences on the stated Altium version. The native algorithm beyond
  these controls remains unverified.
  The public rule corpus verifies that NetAntennae is the only exportable kind outside the neutral
  import table and that the original record number, scope and tolerance are carried. All 51 rule
  corpus checks passed with `FENOLITE_HEAVY=1`, and the two public 1 mil conversion cases passed.
- [x] 6.2 CHANGELOG, `gen_evidence_matrix`, `gen_cli_surface` and the other generators with `--check`;
  `openspec validate c0465-check-allowances --strict`; each touched test file alone with `-n 0`.
  Done 2026-11-06 on lote-29 23e429393: the 26 test files c0465 touched, the docs tests, `test_pages`,
  `test_capabilities` and `test_manifest`, each alone with `-n 0`, pass; `tests/kicad/rules/test_rule_kinds_new.py`
  passes on KiCad 10.0.6 (local) and 9.0.9 (pinned image). `rulemap.EVIDENCE` no longer names
  `H-A-RULE-SHORT` and `H-A-RULE-ANTENNA`: they are `UNVERIFIED` until task 6.1, and a declared `INFERRED`
  may not name a weaker row. `gen_licences --check` differs on this Mac only by packages that the lock
  installs on Linux alone, which is not this change.
