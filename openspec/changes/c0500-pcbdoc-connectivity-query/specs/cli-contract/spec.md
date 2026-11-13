## ADDED Requirements

### Requirement: Islands in the net command
`fenolite net PATH NAME --islands` SHALL add `result.net.island_list`, the islands of `NAME` from
`net_islands`. Each island SHALL hold `pads`, `members` (`kind`, `id`, `where`, `layers`) and `zones`
(change c0500).
- `--without ITEM[,ITEM…]` (repeatable) MUST imply `--islands`, compute the islands without those items
  (board-analyses, "Island members and removal by name"), and add `result.net.cut`: `removed` (the `where`
  of each removed item), `islands_before`, `islands_after`, `split` (`islands_after > islands_before`), and
  `note` "saved fills are not repoured" when the net has a zone.
- An unknown item name MUST exit 2 with `FEN-2001` and the three closest names in the hint. `--islands` or
  `--without` without `NAME` MUST exit 2 with `FEN-2001`.
- The command stays read-only and runs no tool. `paged` MUST name `net.island_list`. Without the new options the
  reply MUST be unchanged.
- It MUST read every board `load_board` reads, an Altium `.PcbDoc` included (change c0495).

#### Scenario: Islands of an Altium net
- **GIVEN** an authored PCB document whose net `GND` has more than one island
- **WHEN** `fenolite net <doc> GND --islands --json` runs
- **THEN** the exit code is 0, `result.net.island_list` has one entry per island (`islands`), and each member's `where` is a locator
  of the document (`<Storage>/Data#<n>`) or a `REF-PIN`

#### Scenario: Cutting a track
- **GIVEN** the authored board of "A cut splits the net"
- **WHEN** `fenolite net <board> GND --without t1 --json` runs
- **THEN** `result.net.cut` has `islands_before` 1, `islands_after` 2 and `split` true

#### Scenario: A name that is not on the board
- **WHEN** `fenolite net <board> GND --without t9` runs
- **THEN** the exit code is 2 with `FEN-2001`, and the hint names `t1`
