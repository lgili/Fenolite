## ADDED Requirements

### Requirement: Keep-out issue code
`fenolite.checks.codes.ISSUE_CODES` SHALL also hold the key `copper.keepout` with the severity `error`, as "Check issue codes" allows, and `docs/cli-contract.md` MUST document it. `check_copper` emits it (`copper-check`, "Keep-out findings"); the build guard emits it into the `build` envelope, where it passes through unchanged as `design-dsl` "Build issue codes" allows for codes that later requirements add.

| code | severity | when |
|---|---|---|
| `copper.keepout` | error | a track, arc, via or pad lies in a keep-out whose settings forbid its kind, on a layer of the keep-out |

- The stage `copper.clearance` keeps its name and its evidence; `copper.keepout` findings count as its errors, so `check` exits 5 when one is reported.

#### Scenario: Keep-out literal is a key
- **WHEN** `uv run pytest tests/unit/checks -k codes` collects every issue-code literal under `src/fenolite/checks/`
- **THEN** `copper.keepout` is a key of `ISSUE_CODES` with the severity `error`

#### Scenario: Keep-out code documented
- **WHEN** `uv run pytest tests/consistency` runs
- **THEN** `copper.keepout` appears in `docs/cli-contract.md`

#### Scenario: Check fails on copper in a keep-out
- **GIVEN** a built blink variant with `d.rule_area("ANT", …, forbid=("tracks",))` over one of its script tracks, written with `--copper-check warn`
- **WHEN** `fenolite check blink.kicad_pcb --json` runs
- **THEN** the exit code is 5, `issues` hold one `copper.keepout` naming the track and `ANT`, and the DRC stage holds `items_not_allowed` for the same track
