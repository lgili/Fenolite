# Design: c0495

## D1 (a) Argument names

`describe._argument` builds `Argument(name=action.dest, flags=…)`. For an option it becomes
`name = first long flag lstrip("-")`, with `dest = action.dest` as a new field. `_placeholder` keeps using
`dest.upper()` where there is no metavar, so usage lines do not change. `fenolite.capabilities.v0` gains
`dest`. Adding a key is allowed in v0 (`docs/cli-contract.md`, "Stability"), and the meaning of `name`
changes for 25 options. The changelog says so.

The test walks `capabilities --command` for every command and asserts `"--" + name in flags` for every
option.

## D2 (b) Boards of any backend

`_boardview.load_board`:

1. `.kicad_pcb`, `.kicad_pro` or a folder: `resolve_board` as today.
2. else `registry.for_path(path)`: a backend that is a `BoardFrame` reads it. The Altium backend does.
3. else `FEN-2001` "`<name>` is not a board Fenolite reads", with a hint listing the suffixes of the
   registered `BoardFrame` backends.

`InputRef.kind` comes from the backend (`pcbdoc` for Altium) instead of the fixed `kicad_pcb`. A `.PrjPcb`
is out of scope: the user passes its PCB document.

## D3 (c) Zone locations

In `item_locations`, a zone's location is built from the model: its `name`, its net's name (`no net`
without one) and its layers joined by `,`. When two zones of the board give the same text, each gets
`#k`, where `k` is the zone's index, counted from 1, in `board.zones`, which the KiCad reader keeps in
file order. A rule area (`board.keepouts`) gets `rule area <name> (<layers>)`. The provenance locator stays
in the finding's `detail` for debugging.

Waivers (`checks.waivers`) match on locations. A waiver naming `zone[N]` is matched against the old
locator once and reported with `check.waiver-location-old` (warning). The old form is dropped in the next
minor version.

## D4 (d) What is lost

`ConversionReport` rows already count per kind and reason (the `report` of an accepted run). The error
builds its message and issues from the same rows:

- message: `the conversion would lose <total> item(s) of the source: <kind>: <n> (<n1> <reason1>, …); …`,
  with up to three examples per kind, each `<layer> <shape>`;
- `issues`: one `convert.lossy` per kind, as today, now with `count`, `reasons` (`{reason: count}`) and
  `examples` in `detail`.

The hint stays: re-run with `--allow-lossy` to accept it.
