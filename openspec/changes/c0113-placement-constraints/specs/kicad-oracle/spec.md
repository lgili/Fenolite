## ADDED Requirements

### Requirement: Placement keep-outs are probed
`tests/kicad/place/test_place_keepout.py` (marker `needs_kicad`, major-aware) SHALL settle `H-K-PLACE-KEEPOUT` on the running `kicad-cli`, with the benches of `tests/kicad/place/_keepoutcases.py`: one per case, each built on `tests/kicad/rules/_rulebench.py`, written with `write_board` for the running major, holding the case's probed part, a control part outside every area and one rule area with `no_footprints`. DRC MUST run through c0009's `KicadCli` on copies with an empty `KICAD_CONFIG_HOME`, and MUST be judged only from the JSON report, by violation type and item uuid.
- **Canary.** Every bench MUST carry the canary scoped to its own net (c0071), and a run whose canary does not fire MUST fail.
- **Cases.** The 18 cases of the design's measurement 1. `place-keepout-<case>` MUST record `present` when an `items_not_allowed` violation names the probed footprint and `absent` otherwise; no violation may name the control part. The expected outcomes: `present` for `in`, `crt-only`, `over-10um`, `bot-back`, `bot-both` and `tht-front`; `absent` for `touch`, `gap-10um`, `gap-30um`, `text-only`, `rot-crt`, `bot-front`, `top-back`, `inner-only`, `tht-back`, `nocrt-in`, `nocrt-pad` and `nocrt-mid`.
- **Agreement.** `place-keepout-agree` MUST record `equal` when `placement.legality.check`, given each bench's extents (`KicadBackend().placed_extents` of the read board) and keep-outs, gives `place.keepout` for exactly the cases recorded `present`, and `different` otherwise.
- **Stop rule.** An outcome other than the expected one on a major is written into the register row, and the predicate of "Placement legality" (capability `placement`) follows the recorded outcomes before this change is archived.
- The outcomes MUST be recorded in `docs/evidence/kicad/probes/9.0.9.json` and `10.0.6.json`, and the facts written to `docs/formats/kicad/board.md` with their sources and labels. Built files MUST NOT be committed.

#### Scenario: Keep-outs on both majors
- **WHEN** `uv run pytest tests/kicad/place/test_place_keepout.py -rA` runs on the local KiCad 10.0.6 and in the `kicad-9` job
- **THEN** every `place-keepout-<case>` probe records the expected outcome, `place-keepout-agree` records `equal`, and the canary fires in every run

#### Scenario: Agreement without KiCad
- **WHEN** `uv run pytest tests/kicad/place/test_place_keepout.py -k hermetic` runs without `kicad-cli`
- **THEN** `placement.legality.check` gives `place.keepout` for exactly the six cases whose expected outcome is `present`
