## ADDED Requirements

### Requirement: KiCad net lengths
The module `fenolite.backends.kicad.lengths` SHALL compute the `LengthFacts` of `backend-protocol` ("Length facts source") for designs read or built by the KiCad backend, counting as KiCad of major `major` counts the length of a net in its DRC, and `KicadBackend.length_facts` MUST return what `lengths.length_facts` returns for the same arguments. The module MUST import only the standard library, `core`, `model`, `geometry`, `backends.base` and modules of `backends.kicad`, and every function MUST be pure: it reads no file and no environment variable, runs no subprocess, and returns new values.
- **Major.** `major` MUST be the argument when given; else the major of the project file of `project` (`copperrules.project_major`); else the major of the board's source format; else the default target.
- **Stack-up.** With `Board.stackup` (c0101), its copper and dielectric entries in table order MUST give the thicknesses, and `stackup` MUST be `board`. Without it, every copper layer MUST be `DEFAULT_COPPER_NM = 35_000` thick and the `n − 1` dielectrics of a board of `n` copper layers MUST share equally the board thickness less `DEFAULT_MASKS_NM = 20_000` and the copper; the board thickness is the `(general (thickness …))` of the file, else `pcb.DEFAULT_THICKNESS`. `stackup` is then `default`, with one `kicad.length.default-stackup` info (`H-K-NETLEN-STACKUP`). Mask, paste and silkscreen entries MUST NOT count.
- **Depths.** For major 9, the depth of every copper layer MUST be the thickness of the copper and dielectric layers above it plus half its own. For major 10 the same MUST hold for inner copper layers, while the first copper layer MUST have depth 0 and the last copper layer the sum of every copper and dielectric thickness. Each depth MUST be computed exactly and rounded half to even once.
- **Joined layers.** The joined layers of a via MUST be the copper layers of its span (every copper layer for a through via; the layers from its first to its last in table order for another kind) on which a track or an arc of its net, or a copper entry of a pad of its net (`board_pads`), touches its disc `Thick((position,), diameter)`. Zone fills MUST NOT join a via (`H-K-NETLEN-TOTAL`).
- **Via height.** For major 10 it MUST be the depth difference between the first and the last joined layer in table order, and 0 with fewer than two joined layers (`H-K-NETLEN-VIA10`). For major 9 it MUST be the depth difference between the via's own two end layers when both are joined, and 0 otherwise (`H-K-NETLEN-VIA9`). With `count_vias` false every height MUST be 0. `count_vias` MUST be false exactly when the project file of `project` sets `board.design_settings.rules.use_height_for_length_calcs` to `false`.
- **Die lengths.** A pad's die length MUST be the value of its opaque `(die_length X)` slot, `X` in millimetres converted exactly to nm. A value that is not a non-negative decimal MUST give one `kicad.length.bad-die` warning naming the pad, and MUST count as 0.
- **Nets.** `routed` MUST be the sum of `segment_length` and `arc_length` (`geometry-kernel`, "Path lengths") over the net's tracks and arcs on copper layers, `vias` the sum of its vias' heights, and `die` the sum of the die lengths of its pads. A through-hole pad adds no height.
- `LENGTH_ISSUE_CODES` MUST be the closed table `kicad.length.default-stackup` (info) and `kicad.length.bad-die` (warning). As `kicad.*` codes they pass through the closed tables of the build and of the lens unchanged.
- `lengths.EVIDENCE` MUST be `Evidence(Level.INFERRED, hypotheses=("H-K-NETLEN-STACKUP", "H-K-NETLEN-TOTAL", "H-K-NETLEN-VIA10", "H-K-NETLEN-VIA9"))`, and its level MUST stay `INFERRED` when the four rows are verified: they cover benches, not every board.

#### Scenario: Via heights per major
- **GIVEN** the four-layer bench of `tests/_lengthbench.py` with `Board.stackup` set to F.Cu 35 µm, dielectric 110 µm, In1.Cu 17.5 µm, dielectric 1230 µm, In2.Cu 17.5 µm, dielectric 155 µm, B.Cu 35 µm, whose nets each hold two 10 mm tracks joined by one via
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_lengths.py -k per_major` computes `length_facts` with `major=10` and with `major=9`
- **THEN** with 10 the through via between `F.Cu` and `In1.Cu` adds 153 750 nm and the one between `F.Cu` and `B.Cu` 1 600 000 nm; with 9 they add 0 and 1 565 000 nm, and the blind via between `F.Cu` and `In1.Cu` adds 136 250 nm

#### Scenario: Default stack-up
- **GIVEN** the two-layer bench, whose board holds no stack-up, and its net `L_VIA2`: 10 mm on `F.Cu`, a through via, 10 mm on `B.Cu`
- **WHEN** `length_facts` is computed with `major=10` and with `major=9`
- **THEN** `stackup` is `default`, one `kicad.length.default-stackup` info is given, and the net's `vias` is 1 580 000 with 10 and 1 545 000 with 9

#### Scenario: A pad joins a via
- **GIVEN** the four-layer bench with the stack-up of "Via heights per major", and its net `VIP`: a through via inside pad 2 of `R1`, 18.4 mm on `In1.Cu`, a through via inside pad 1 of `R2`
- **WHEN** `length_facts` is computed with `major=10` and with `major=9`
- **THEN** the net's `vias` is 307 500 with 10 and 0 with 9

#### Scenario: Die length and the project switch
- **GIVEN** the two-layer bench, whose pad 2 of `R12` holds `(die_length 1.5)` in the board text, and a project file that sets `use_height_for_length_calcs` to `false`
- **WHEN** `length_facts` is computed without and with that project file
- **THEN** the net `L_DIE` has `die == 1_500_000` and `total == 19_900_000`; with the project file `count_vias` is false and `L_VIA2` has `vias == 0`
