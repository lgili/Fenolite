## ADDED Requirements

### Requirement: Native layer names of an Altium board
For an Altium board the scene SHALL name each layer as its `Board6` record does: the user's name of a numbered layer when the record holds one, else Altium's default name. The model name SHALL stay the layer's id. The layers SHALL be ordered as Altium orders them.

#### Scenario: A board with renamed layers
- **GIVEN** an authored `.PcbDoc` whose `Board6` names layer 1 `Signal Top` and keeps the default name of layer 33
- **WHEN** `uv run pytest tests/unit/view/test_altium_layers.py -k names` builds its scene
- **THEN** the scene's layer `F.Cu` is named `Signal Top`, the layer `F.SilkS` is named `Top Overlay`, and `Signal Top` comes before `Top Overlay`

### Requirement: Mask and paste openings from the pads
For an Altium board the scene SHALL draw each pad's solder-mask and paste opening grown by the expansion its record gives: the manual value, the value of the governing rule, or the default, and the Properties panel SHALL name the source.

#### Scenario: Manual and rule expansions
- **GIVEN** an authored `.PcbDoc` with one pad of manual mask expansion 2 mil and one pad of mask mode "from the rules" under a `SolderMaskExpansion` rule of scope `All` and 4 mil
- **WHEN** `uv run pytest tests/unit/view/test_altium_layers.py -k openings` builds its scene
- **THEN** the first opening is the pad grown by 2 mil and the second by 4 mil, and their sources are `manual` and the rule's name

#### Scenario: Public boards
- **GIVEN** the public Altium boards of the corpus cache
- **WHEN** `uv run pytest tests/corpus/test_altium_layer_names.py` builds their scenes
- **THEN** every layer has a native name and every pad's opening is at least its copper less a negative expansion
