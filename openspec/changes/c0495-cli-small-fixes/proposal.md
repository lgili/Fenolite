# c0495: four small CLI fixes

Found on: reviewing a private maintainer board on 2026-11-11 (codes only; nothing from the board is in
this change).

## Why

Four small defects, each seen while using the CLI on that board:

- **(a) Argument names in `capabilities`.** `fenolite capabilities --command analyze` lists the power
  argument as `name: "power_paths"`, but the option is `--path`. `describe._argument` uses argparse's
  `dest` as the name. An agent that builds a call from `name` passes `--power-paths` and gets exit 2. On the
  current tree 25 options in 14 commands have a `dest` that differs from their flag, for example `--from`
  (`source`), `--tie` (`tie_parts`) and `--version` (`item_version`).
- **(b) `fenolite net` refuses a `.PcbDoc`.** `net` (and `ready`, `neighbors`, `region` and the reuse and
  layout helpers) loads the board with `cli._boardview.load_board`. That calls the KiCad-only
  `projectset.resolve_board`, which raises `FEN-2001` "is not a .kicad_pcb, a .kicad_pro or a folder". The
  message also holds the absolute path. The Altium backend gives a `BoardFrame`, and `check`, `inspect` and
  `convert` read the same file.
- **(c) `kicad.drc.isolated-copper` names `zone[N]`.** `checks.drc_json.item_locations` gives a zone its
  provenance locator, the s-expression path `/kicad_pcb/zone[N]`. That index counts every `zone` node,
  rule areas included. It matches neither the model's zone list nor anything the user sees. The finding
  does not say the zone's net, name or layer.
- **(d) A lossy import does not say what is lost.** Importing an Altium project with drawing items that
  the conversion cannot keep exits 7 with `FEN-7001`, "the conversion would lose items of the source
  (<kinds>)". The message names the kinds only. To learn the count and the reasons, the user has to accept
  the loss with `--allow-lossy` first.

## What Changes

- (a) An argument's `name` in `describe` is its first long flag without the leading dashes, for example
  `path`. A new field `dest` keeps argparse's name. Positionals keep their name. A test checks every command.
- (b) `load_board` resolves a `.PcbDoc` through the registry, as `check` does. `net` and the other
  `load_board` commands read Altium boards. The error for a file no backend reads names the file, not its
  absolute path, and lists the suffixes the backends read.
- (c) A zone's location in DRC findings is `zone <name> (<net>, <layers>)`, or `zone (<net>, <layers>)`
  without a name, with `#<k>` appended when two zones would read the same. `k` is the zone's index in the
  board model's `zones`, counted from 1. Rule areas get `rule area <name> (<layers>)`.
- (d) `FEN-7001` from a conversion lists, per refused kind, the count and the reasons with their counts.
  It also gives up to three examples with their layer, for example
  `drawing: 5 (3 on a mechanical layer with no KiCad layer, 2 dimension); for example Mech.20 line`.
  The same rows go in `issues`, each `convert.lossy` with `count` and `reasons`.

## Impact

- (a) `src/fenolite/cli/describe.py`; the generated agent guide pages (`tools/gen_agent_guide.py`);
  `docs/cli-contract.md`, "Discovery".
- (b) `src/fenolite/cli/_boardview.py`; the commands that call `load_board`.
- (c) `src/fenolite/checks/drc_json.py` (`item_locations`); waivers that name a zone by `zone[N]` stop
  matching. `fenolite.checks.waivers` reads the old form for one minor version and warns
  (`check.waiver-location-old`).
- (d) `src/fenolite/convert/__init__.py` (`LossyConversionError`), the `convert.lossy` issues.
