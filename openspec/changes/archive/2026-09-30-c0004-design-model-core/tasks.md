## 1. Specification and decision record

- [x] 1.1 Write `docs/adr/0001-neutral-model.md` (small now, frozen after the second backend; integer nm and microdegrees; uuid ids; ext bags; slots; authority; rejected 1/50 nm alternative). Proof: `uv run pytest tests/unit/test_adrs.py`.
- [x] 1.2 Write `docs/formats/units.md` (unit definitions of both target tools with public sources; conversion formulas; boundary table) and add rows `H-K-UNIT`, `H-A-UNIT`, `H-G-ANGLE` (level `INFERRED`) to `docs/hypotheses.md` and the two unit sources to `docs/evidence/sources.md`. Proof: rows present; review.

## 2. Core package

- [x] 2.1 Implement `src/fenolite/core/units.py` (parse/format lengths and angles; `u_to_nm`/`nm_to_u` integer-only; `Nm`/`Udeg` aliases). Proof: `uv run pytest tests/unit/core/test_units.py` (hypothesis boundary and symmetry tests).
- [x] 2.2 Implement `src/fenolite/core/ids.py` (`new_id`, `derived_id`, `content_id`, prefix table, `FENOLITE_NS`). Proof: `uv run pytest tests/unit/core/test_ids.py`.
- [x] 2.3 Implement `src/fenolite/core/evidence.py` (`Level` order, `min_level`, `Evidence.label()`) and `src/fenolite/core/errors.py` (`FormatError`, `ConsistencyError`, `Issue` with code validation). Proof: `uv run pytest tests/unit/core/test_evidence.py tests/unit/core/test_errors.py`.
- [x] 2.4 Implement `src/fenolite/core/provenance.py` and `src/fenolite/core/io.py` (`atomic_write` with temp+rename, `.bak`, receipt; `sha256_of`). Proof: `uv run pytest tests/unit/core/test_io.py` (simulated failure before rename leaves original intact).
- [x] 2.5 Wire `fenolite.cli.output` and `cmd__echo` to `core.evidence`, `core.errors.Issue` and `core.io` (replacing the interim definitions from c0002). Proof: `uv run pytest tests/consistency -q`.

## 3. Model package

- [x] 3.1 Implement `src/fenolite/model/base.py` (`Entity` header, `ExtBag`, `Modeled`/`Opaque` slot types) and `circuit.py` (`Component`, `Pin`, `Net`, `NetClass`, `Interface`, `Module`). Proof: `uv run pytest tests/unit/model/test_circuit.py`.
- [x] 3.2 Implement `board.py` (`Board`, `Layer`, `Stackup`, `StackLayer`, `FootprintInstance`, `Pad`, minimal `Padstack`, `Track`, `Arc`, `Via`, `Zone`, `Keepout`, `Text`, `Graphic`, `Hole`, `Outline`). Proof: `uv run pytest tests/unit/model/test_board.py`.
- [x] 3.3 Implement `rules.py` (`Rule`, `RuleSet`, selector algebra with `matches()` evaluator, six kinds), `manufacturing.py` (`Manifest`, `PnpRow`) and `findings.py`. Proof: `uv run pytest tests/unit/model/test_rules.py` (selector truth table).
- [x] 3.4 Implement `design.py` (`Design`, lazy indexes `by_id/by_ref/by_net/by_layer`, `validate()` producing `model.duplicate-ref`, `model.dangling-net`, `model.single-pin-net`, `replace_*` helpers). Proof: `uv run pytest tests/unit/model/test_design.py`.

## 4. Canonical serialisation and schemas

- [x] 4.1 Implement `model/canonical.py` (`dumps`, `loads`, `dump_dir`, `load_dir`; ordering; defaults omitted; integers only; `ext` verbatim; `meta.json`). Proof: `uv run pytest tests/unit/model/test_canonical.py` (idempotence and order-independence property tests; readable-diff test).
- [x] 4.2 Extend `tools/gen_schemas.py` for nested dataclasses, enums and `dict[str, ExtBag]`; generate `schemas/fenolite.model.v0/*.json`; extend `tests/unit/test_schema_drift.py`; implement schema validation with JSON-pointer errors in `canonical.loads`. Proof: `uv run python tools/gen_schemas.py --check`; `uv run pytest tests/unit/test_schema_drift.py tests/unit/model/test_schema_validation.py`.
- [x] 4.3 Write `tests/strategies.py` (hypothesis strategies for lengths, angles, ids, small designs) shared by all model tests. Proof: `uv run pytest tests/unit/model -q` completes in under 60 s.

## 5. Documentation

- [x] 5.1 Promote the normative text of this change's `design-model` spec into `docs/design-model.md` (one page: header, units, ids, provenance, ext/min_version, canonical, authority, slots) and link it from `README.md` and `AGENTS.md`. Proof: review; no internal identifiers.

## 6. Closing

- [x] 6.1 Run `uv run pytest tests/residue`. Proof: exit 0.
- [x] 6.2 Update evidence labels: `H-K-UNIT`, `H-A-UNIT`, `H-G-ANGLE` remain `INFERRED` until a corpus file confirms them (KiCad backend change). Proof: `docs/hypotheses.md` rows.
- [x] 6.3 `CHANGELOG.md`: "Design model v0: core units/ids/evidence/io, model layers circuit/board/rules/manufacturing/findings, canonical JSON, schemas". Proof: `git diff CHANGELOG.md`.

_Note: the design-model scenarios "Unknown child survives" (slots) and "Provenance attached on import" describe backend behaviour; they are verified by the first backend change (KiCad board backend), which implements slots and provenance on real files._
