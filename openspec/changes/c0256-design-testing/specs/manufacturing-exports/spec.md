## ADDED Requirements

### Requirement: Net renders
`fenolite render PATH --net NAME [--net NAME ...] -o DIR` SHALL draw, with the region renderer and no tool, the board's bounding box grown by 1 mm, or the rectangle of `--region`, with every item of the named nets in the class `net-hi` and every other copper item in `net-dim`, into `DIR/net-<name>.svg` for one net or `DIR/nets.svg` for several, under the mutation protocol. `--layers L1,L2` MUST keep only those copper layers, the board edge and the holes.

#### Scenario: Ground highlighted
- **GIVEN** the authored bench of `tests/_regionviewbench.py`
- **WHEN** `uv run pytest tests/unit/cli/test_render_net.py -k ground` runs `fenolite render <board> --net GND -o views --confirm`
- **THEN** the exit code is 0, `views/net-GND.svg` exists, every element with `data-net="GND"` has the class `net-hi`, no other copper element has it, and no tool ran

### Requirement: Net render result
A net render SHALL add to `result.region` the highlighted net names, sorted, as `nets`, and the counts of highlighted `pads`, `tracks`, `arcs`, `vias` and `zones` as `highlighted`. The SVG root MUST carry `data-render="fenolite.region.v1"`, and the same board and options MUST give the same bytes.

#### Scenario: Counts and bytes
- **WHEN** `uv run pytest tests/unit/cli/test_render_net.py -k counts` renders the bench with `--net GND --net VCC` twice
- **THEN** `result.region.nets` is `["GND", "VCC"]`, `highlighted` gives the bench's counts, and both `nets.svg` files have the same SHA-256

### Requirement: Net render refusals
An unknown net SHALL exit 2 with `FEN-2001`, `where` `--net` and the three closest names in the hint; an unknown layer SHALL exit 2 with `FEN-2001` and `where` `--layers`; `--net` or `--layers` with `--svg` or `--png` SHALL exit 2 with `FEN-2001`. Nothing is written in each case.

#### Scenario: Unknown net
- **WHEN** `uv run pytest tests/unit/cli/test_render_net.py -k usage` runs `fenolite render <board> --net GDN -o views --dry-run` and the other refused forms
- **THEN** each exits 2 with `FEN-2001` and `where` naming the option, the first with a hint naming `GND`, and no folder is made

#### Scenario: Option names do not collide
- **WHEN** `uv run pytest tests/unit/cli/test_render_net.py -k option_names` parses `--region 0mm,0mm,9mm,9mm --nets` and `--net GND`
- **THEN** the first sets the labels and no highlight, and the second sets the highlight and no labels

### Requirement: Design scripts as render input
`fenolite render` with `--region` or `--net` SHALL accept a design script as `PATH`, built in memory as `fenolite build PATH --dry-run` builds it with the same `--seed` and `--timestamp`; `input` and `depends` MUST name the script, and a build failure MUST give the code and exit of `build`. Without `--region` or `--net`, a design script MUST exit 2 with `FEN-2001`.

#### Scenario: Render of a script
- **WHEN** `uv run pytest tests/unit/cli/test_render_net.py -k script` runs `fenolite render examples/testing/design.py --net GND -o views --confirm` twice into two folders
- **THEN** both exit 0, both files have the same SHA-256, and the working folder holds no build output

#### Scenario: Script without the model forms
- **WHEN** `fenolite render examples/testing/design.py -o views --svg --dry-run` runs
- **THEN** the exit code is 2 and stderr carries `FEN-2001`
