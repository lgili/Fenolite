## ADDED Requirements

### Requirement: Altium build of an imported Altium project
An Altium build of a script that carries an Altium source's board records SHALL write what the
conversion of the same project writes.
- A script carries them when one of its `kicad_pcb` verbatim items is a property whose name starts with
  `Fenolite.Altium.` (`backends.kicad.boardcarrier.PREFIX`; `cli.cmd_build.altium_carried`).
- Without `--copper-from`, `build --target altium` of such a script MUST:
  - plan the KiCad build of the script in memory, without the `altium_*` options;
  - convert that project as `fenolite convert --to altium` does, with `--altium-pour`, `--altium-bodies`
    and `--allow-lossy`;
  - plan the conversion's files under `--out`.
- `result.through` MUST be `conversion`. `result.report` and `result.equivalence` MUST hold the
  conversion's report and equivalence.
- An error of the KiCad build MUST refuse the build with its issues and plan no file.
- A script without such an item MUST build as before, and `result` MUST hold no `through`.
- The texts and drawings of a board, and the drawings of a footprint, that lie on a user layer
  `lower.named_mechanical` maps MUST be written on that mechanical layer.
- A conversion to Altium MUST write a pad on no net when its net is named `unconnected-(…)` and holds that
  one pad and no copper.
- A `script` copper source MUST NOT report as uncopied an item whose id the design's board holds.

#### Scenario: Altium build of an imported Altium project
- **GIVEN** the blink example built for Altium and imported back to Python
- **WHEN** the imported script is built with `--target altium --confirm`
- **THEN** the exit code is 0, `result.through` is `conversion`, and the rules of the written PcbDoc read
  back as those of the first build's PcbDoc

#### Scenario: Drawing on a named user layer
- **GIVEN** a board line and text on `User.10`, which the document holds as Mechanical 13
- **WHEN** `lower_items` runs with that layer map
- **THEN** both are written and no issue names them
