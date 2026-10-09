## ADDED Requirements

### Requirement: Net-tie groups in authored footprints
`Footprint.net_tie(*numbers)` SHALL declare one net-tie group of an authored footprint: pads of different nets that the footprint joins on purpose, through overlapping pads or a copper graphic (`line`, `rect`, `circle` or `polygon` on a copper layer). A group MUST hold at least two distinct non-empty pad numbers, else the call raises `DslError`.
- `definition` MUST raise `DslError` when a number of a group names no pad of the footprint, or when a number is in two groups; it MUST carry the groups in `FootprintDef.net_ties`, in call order, each in the order of its numbers.
- The KiCad footprint writer MUST emit one `(net_tie_pad_groups "<group>" …)` child right after `attr`, one string per group, its numbers joined with `", "`, as KiCad's own library writes it (S-0018, S-0042). A definition without groups MUST emit no such child, so an authored footprint written before this change keeps its bytes.
- The board that `build` writes MUST carry the child in the placed footprint, and KiCad 9.0.9 and 10.0.6 MUST load it and honour the group (`kicad-oracle`, "Net-tie facts are probed").
- The Altium build MUST NOT drop a group silently: it writes the pads and their copper as for any footprint, writes no net-tie mark, and reports the footprints that have groups in one `altium.not-lowered` info whose `where` is the kind `net-tie` (`backends.altium.lower`). The kind MUST NOT be in `LOSS_KINDS`: the pads are written, so the issue is an `info` and a write without `allow_lossy` is not refused. Its copper guard judges the tied pads; a `copper.short` waiver accepts them (`design-dsl`, "Waivers in the copper guard").

#### Scenario: Emitted form
- **GIVEN** a footprint with pads `1` and `2`, a copper line between them on `F.Cu`, and `fp.net_tie("1", "2")`
- **WHEN** `uv run pytest tests/unit/dsl/test_net_tie.py -k emit` writes its definition for targets 9 and 10
- **THEN** the text holds `(net_tie_pad_groups "1, 2")` as the child that follows `attr`, and the definition has `net_ties == (("1", "2"),)`

#### Scenario: Refused groups
- **WHEN** `net_tie("1")` is called, then `net_tie("1", "9")` on a footprint without pad `9`, then `net_tie("1", "2")` and `net_tie("2", "3")` on one footprint, and `definition` is read
- **THEN** the first call raises `DslError`, and `definition` raises `DslError` naming pad `9`, then pad `2`

#### Scenario: No group, same bytes
- **GIVEN** an authored footprint without `net_tie`
- **WHEN** it is written for targets 9 and 10
- **THEN** the bytes equal those written before this change, and no `net_tie_pad_groups` child appears

#### Scenario: A net tie in an Altium build
- **GIVEN** a design that places as `NT1` an authored footprint with two pads `1` and `2` 0.5 mm apart and `fp.net_tie("1", "2")`, its pads on nets `A` and `B`
- **WHEN** `uv run pytest tests/unit/cli -k "altium and net_tie"` builds it with `--target altium --dry-run --json`
- **THEN** the exit code is 0, the planned `.PcbLib` and `.PcbDoc` hold both pads, and `issues` holds one `altium.not-lowered` info whose `where` is `net-tie` and whose message counts one footprint
