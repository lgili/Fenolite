## ADDED Requirements

### Requirement: Net-tie facts are probed
`tests/kicad/check/test_net_ties.py` (marker `needs_kicad`, major-aware) SHALL settle `H-K-NETTIE-DRC` on the running `kicad-cli` with the bench of `tests/kicad/check/_tiebench.py`, and DRC MUST be judged only from the JSON report.
- **Bench.** One board written by `write_board` for the running major, with one footprint per case on nets of its own, each an authored definition (`dsl-footprint-authoring`, "Net-tie groups in authored footprints"), a `{}` project (KiCad's Default class, 0.2 mm), and a control pair: two 0.25 mm tracks of their own nets 0.1 mm apart. A run whose report lacks the control pair's `clearance` violation MUST fail.
- **Cases.** The types expected between two items of each case, counting only `shorting_items`, `clearance`, `solder_mask_bridge` and `unconnected_items`, with its groups and, for the first four, in a copy without them:

| case | footprint | with the groups | without |
|---|---|---|---|
| `official` | two 0.5 mm round pads 0.5 mm apart, joined by a filled polygon on `F.Cu` | none | `shorting_items`, `solder_mask_bridge` |
| `touching` | two 1 mm square pads overlapping by 0.2 mm | none | `shorting_items`, `solder_mask_bridge` |
| `close` | the same pads 0.1 mm apart | none | `clearance` |
| `track-near` | `official`, and a track of pad 1's net ending 0.1 mm from pad 2 | `clearance` (the track and pad 2), `unconnected_items` (pad 1 and the track) | the same, `shorting_items`, `solder_mask_bridge` |
| `two-groups` | four pads in a row, each overlapping the next, groups `1, 2` and `3, 4` | `solder_mask_bridge` (pads 2 and 3) | — |
| `ungrouped-touching` | three pads in a row, each overlapping the next, group `1, 2` | `solder_mask_bridge` (pads 2 and 3) | — |
| `ungrouped-close` | group `1, 2`, pad 3 0.15 mm from pad 2 | none | — |
| `groups-close` | groups `1, 2` and `3, 4`, pads 2 and 3 0.15 mm apart | none | — |
| `spelling` | `touching`, its child edited to `"1,2"` | none | — |
| `three` | three pads in a row, each overlapping the next, group `1, 2, 3` | none | — |

- **Probes.** Each case MUST be recorded as `nettie-<case>`, and each copy without groups as `nettie-<case>-plain`, for majors 9 and 10: `equal` when the set of types reported between the case's items is the expected one, `different` otherwise.
- **Fallback.** A probe that records `different` on a major MUST stop the net-tie part of this change: "Pairs that are judged" is corrected to what the report shows before the part merges.
- The outcomes MUST be recorded in `docs/evidence/kicad/probes/9.0.9.json` and `10.0.6.json`, and the facts written to `docs/formats/kicad/drc.md` with S-0020 and S-0029.

#### Scenario: Net-tie facts on both majors
- **WHEN** `uv run pytest tests/kicad/check/test_net_ties.py -rA` runs on the local KiCad 10.0.6 and inside the pinned 9.0.9 image
- **THEN** every `nettie-*` probe records `equal`, and the control pair's violation is present

#### Scenario: The written token loads
- **GIVEN** the bench as written by Fenolite for the running major
- **WHEN** the test reads it back with `read_board`
- **THEN** every footprint of a case with groups holds `net_ties` equal to its declared groups, and `pcb drc` loads the board without an error

### Requirement: Net-tie parity canaries
`tests/kicad/copper/test_copper_parity.py` SHALL also compare `check_copper` with `kicad-cli pcb drc` on the bench of "Net-tie facts are probed", on 9.0.9 and 10.0.6, counting only `shorting_items` and `clearance` between two pads of one case (`H-K-NETTIE-DRC`).
- **Compared.** `touching`, `close`, `spelling` and `three` with their groups, and `touching` and `close` without: KiCad and `check_copper` MUST give the same verdict. The probe `copper-nettie-group` records `equal` when every one does, `different` otherwise.
- **Recorded.** `two-groups`, `ungrouped-touching`, `ungrouped-close` and `groups-close`: `check_copper` reports one finding naming the two pads that share no group, and KiCad none. The probe `copper-nettie-ungrouped` records that outcome as `different`; it is documented (`copper-check`, "Supported cases are documented against KiCad's DRC") and MUST NOT fail the test.
- **Hermetic half.** `tests/kicad/copper/test_parity_bench.py` MUST check without `kicad-cli`, for targets 9 and 10, that `check_copper` gives exactly these findings on the bench.
- The outcomes MUST be recorded in both probe files and copied into the supported-cases table of `docs/formats/kicad/copper.md`.

#### Scenario: Parity of grouped pads
- **WHEN** `uv run pytest tests/kicad/copper/test_copper_parity.py -k net_tie -rA` runs on 9.0.9 and on 10.0.6
- **THEN** `copper-nettie-group` records `equal` and `copper-nettie-ungrouped` records `different`

#### Scenario: Hermetic net-tie rows
- **WHEN** `uv run pytest tests/kicad/copper/test_parity_bench.py -k net_tie` runs without `kicad-cli`
- **THEN** on targets 9 and 10 the grouped cases give no finding, the copies without groups give a `copper.short` for `touching` and a `copper.clearance` for `close`, and each ungrouped case gives one finding naming its two ungrouped pads

### Requirement: Exclusion facts are probed
`tests/kicad/check/test_drc_exclusions.py` (marker `needs_kicad`, major-aware) SHALL settle `H-K-DRC-EXCL` on the running `kicad-cli` with a bench of `tests/kicad/rules/_rulebench.py`: two tracks 0.1 mm apart under the Default class, a lone via, and project files that differ only in `drc_exclusions`. Each key MUST be built from a first run's report: the type, the first item's `pos` in nm, and the item uuids in report order, the nil uuid for the via's second.
- `drc-excl-pair`: `[key, "test point"]` for the via; its entry has `excluded` true, its severity unchanged and `comment` `test point`.
- `drc-excl-plain`: the via's key as a string; excluded, with an empty comment.
- `drc-excl-moved`: the via's key with `x` + 1 nm; not excluded.
- `drc-excl-stale`: the via's key with another uuid; not excluded, and the report holds no entry about it.
- `drc-excl-first-position`: the clearance key; excluded. `drc-excl-reversed`: the same key with its uuids swapped; not excluded.
- `drc-excl-project-unchanged`: the project file's bytes are equal before and after each run.

Each probe MUST record `equal` when the outcome is the listed one, for majors 9 and 10, in both probe files, and the facts MUST be written to `docs/formats/kicad/drc.md` with S-0020, S-0029, S-0055 and S-0056.

#### Scenario: Exclusion facts on both majors
- **WHEN** `uv run pytest tests/kicad/check/test_drc_exclusions.py -rA` runs on the local KiCad 10.0.6 and inside the pinned 9.0.9 image
- **THEN** every `drc-excl-*` probe records `equal`

### Requirement: Severity keys are probed
`tests/kicad/check/test_severity_keys.py` (marker `needs_kicad`, major-aware) SHALL settle `H-K-PRO-SEV-KEYS` and SHALL prove that a script's severity reaches KiCad's report.
- `pro-sev-keys-10` (major 10 only): a bench project that sets every key of `SEVERITY_KEYS[10]`, `overlapping_pads` and `fenolite_not_a_check` to `ignore`; `ignored_checks` MUST equal `SEVERITY_KEYS[10]` and no entry may remain.
- `pro-sev-keys-9-bench` (major 9 only): a bench that gives `clearance`, `shorting_items`, `solder_mask_bridge`, `track_dangling`, `via_dangling` and `lib_footprint_issues` entries under a `{}` project, its control, gives none when every key of `SEVERITY_KEYS[9]` is `ignore`.
- `pro-sev-script` (majors 9 and 10): a project built from a design with `design.rules.severity("kicad.drc.via-dangling", "error")` gives its `via_dangling` entries severity `error`, where the template gives `warning`.

#### Scenario: Keys on both majors
- **WHEN** `uv run pytest tests/kicad/check/test_severity_keys.py -rA` runs on the local KiCad 10.0.6 and inside the pinned 9.0.9 image
- **THEN** `pro-sev-keys-10` records `equal` on 10.0.6, `pro-sev-keys-9-bench` records `absent` on 9.0.9, and `pro-sev-script` records `equal` on both
