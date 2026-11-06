# Tasks: c0462

Rules for every task:

- Public sources only, each recorded in `docs/formats/altium/rule-file.md` with an S- id from S-2210..2219
  and an evidence label.
- No private board data in tests, fixtures, commits or messages; report codes and counts only.
- Run each touched test file alone with `-n 0`. Heavy runs go through `fenolite-heavy` with `-n 2`.

## 1. Grammar

- [x] 1.1 Record S-2211 (precedence) and S-2212 (functions) in `rule-file.md`, "Closed scope grammar".
  Replace S-0296's mixed-operator note. Proof: `uv run pytest tests/unit/agent tests/unit/docs -q -n 0`.
- [x] 1.2 A typed precedence-climbing `parse_scope`: `Xor`, boolean comparisons, units (`AsMils`, `AsMM`),
  the `type` and `unit` refusals, escaped `InNet` values. Every existing scope test still passes.
  Proof: `uv run pytest tests/unit/backends/altium/test_scope_c0462.py tests/unit/backends/altium/read/test_scope.py -q -n 0`.

## 2. Functions

- [x] 2.1 The layer functions and `OnMid` (`applies-to-nothing` with no internal layer). Proof: the same
  file, `-k layer`.
- [x] 2.2 The pair, xSignal and class expansions from the document. Proof: the same file, `-k pair`.
- [x] 2.3 Rooms read as rule areas, and `WithinRoom` refused (`room-membership`; option 2 of the coordinator, 2026-11-06). Proof:
  `uv run pytest tests/unit/backends/altium/test_rooms_c0462.py -q -n 0`.
- [x] 2.4 Component expansions (`HasFootprint`, `IsComponent`, `IsNetTieComponent`, `InNamedUnion`) and
  `read/packages.py` (`IsSOIC`, `IsBGA`, `IsLCC`). Proof:
  `uv run pytest tests/unit/backends/altium/test_scope_packages_c0462.py -q -n 0`.

## 3. Neutral leaves

- [x] 3.1 `zone`, `hole` and `pad_type` in `model.rules`, `RuleSubject`, `selector_rank`, the checks'
  subjects and `fenolite.dsl.select`. Model review approval, then regenerate the schemas and the agent
  guide. Proof: `uv run pytest tests/unit/model/test_selector_leaves_c0462.py -q -n 0`,
  `uv run python tools/model_review.py --check`, `uv run python tools/gen_schemas.py --check`,
  `uv run python tools/gen_agent_guide.py --check`.
- [ ] 3.2 The KiCad writer for the three leaves, from S-2213. Proof:
  `uv run pytest tests/unit/backends/kicad/test_rulemap_leaves_c0462.py -q -n 0`.
- [x] 3.3 `IsNamedPolygon`, `InNamedPolygon`, `HoleDiameter` and `PadIsPlated` onto the leaves. Proof:
  `tests/unit/backends/altium/test_scope_c0462.py -k "polygon or hole or plated"`.

## 4. Record keys and kinds

- [ ] 4.1 Per-layer Width and DiffPairsRouting values, and Width impedance keys. Proof:
  `uv run pytest tests/unit/backends/altium/test_rule_keys_c0462.py -k "layer or impedance" -q -n 0`.
- [ ] 4.2 RoutingVias templates. Proof: the same file, `-k template`.
- [ ] 4.3 `OBJECTCLEARANCES` matrices of Clearance and BoardOutlineClearance. Proof: the same file,
  `-k matrix`.
- [ ] 4.4 MatchedLengths onto `skew` and `length`; mask and paste expansions; `check-relaxed`. Add the
  "Rule kinds and their reading" table. Proof:
  `uv run pytest tests/corpus/test_altium_rule_kinds_c0462.py -q -n 0`.
- [ ] 4.5 PolygonConnect through the full grammar in `connectstyle`. Proof:
  `uv run pytest tests/unit/backends/altium/test_connectstyle.py -q -n 0`.

## 5. Acceptance

- [ ] 5.1 Kit run (S-2214): for each distinct mapped scope of the 8 public rows, Altium's PCB filter
  counts per object kind. Record it in `tests/data/altium/kit/scope-oracle-c0462.json`, declared in
  `tests/data/MANIFEST.toml`. Proof:
  `uv run pytest tests/corpus/test_altium_scope_oracle_c0462.py -q -n 0`.
  Note (2026-11-06): `PCB:RunQuery` from the script selected nothing on 24.5.2.23, so the scopes are applied
  by hand in the PCB Filter panel and counted by `FenoliteCountSelection` (one `.counts-<n>.txt` each).
- [ ] 5.2 Repin the censuses. Pour: no `rule-scope`, `rule-unmapped` or `connect-scope`. Conversion:
  record losses per kind. Proof: `FENOLITE_HEAVY=1 uv run pytest tests/corpus/test_altium_pour_census.py tests/corpus/test_convert_altium_census.py tests/corpus/test_convert_census.py -q -n 2`.
  Known item (2026-11-06): rows `-04` and `-07` now pour every polygon that has an outline, and every one of
  them fails M2 against the saved regions, 7 of 9 in `-04` and 1 of 4 in `-07` also M1. Pouring without the
  newly read Clearance rule turns no failure into a pass, and with it one polygon per row passes M1 that fails
  without it, so the failures are the pour's geometry, for change c0463; they are pinned, not fixed here.
- [ ] 5.3 CHANGELOG, `gen_evidence_matrix`, `gen_cli_surface` and `gen_altium_graduation` checks;
  `openspec validate --all --strict`. Proof: `make lint format types residue` and each `--check`.
