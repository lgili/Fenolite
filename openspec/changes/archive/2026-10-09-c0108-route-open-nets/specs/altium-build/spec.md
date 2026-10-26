## ADDED Requirements

### Requirement: Copper locks in an Altium build
`fenolite build --target altium` SHALL carry the `locked` of every track, arc and via it writes, from each copper source ("Copper in an Altium build": the model, script copper, a routed KiCad board), into the PCB document (`altium-pcb-writer`, "Locked copper records"), and SHALL never write a locked item unlocked without saying so.
- `result.copper` MUST gain `locked`: an object with `tracks`, `arcs` and `vias`, the numbers of locked items written locked.
- For each record kind that is not in `pcbrecords.LOCK_WRITTEN` and has a locked item, the build MUST give one `altium.not-lowered` (warning) with `where` `copper/locked`, whose message names the kind and the number of items written unlocked and whose hint says that Altium's lock can be set in the editor. Those items do not count in `result.copper.locked`.
- A build whose design holds no locked copper MUST give the files, the result and the issues it gave before this change, but for the key `locked` with three zeros.
- The stub of a locked via and the lock itself are otherwise not judged: no rule of the document depends on a lock.

#### Scenario: A locked track from a routed board
- **GIVEN** the routed blink board of `examples/blink_routed`, one of whose segments was given `(locked yes)`, and `LOCK_WRITTEN` holding `track`
- **WHEN** `uv run pytest tests/unit/lens/test_altium_copper.py -k locked` builds the script with `--target altium --copper-from <board> --dry-run --json`
- **THEN** `result.copper.locked` is `{"tracks": 1, "arcs": 0, "vias": 0}`, `issues` hold no `altium.not-lowered` with `where` `copper/locked`, and the planned document read back holds one locked track

#### Scenario: A kind whose fact is not recorded
- **GIVEN** the same board with a locked via, and a test that takes `via` out of `LOCK_WRITTEN`
- **WHEN** the build runs
- **THEN** the via is written unlocked, `issues` hold one `altium.not-lowered` warning with `where` `copper/locked` naming 1 via, and `result.copper.locked.vias` is 0
