## ADDED Requirements

### Requirement: Net names in KiCad's stored form
`fenolite.backends.kicad.netnames` SHALL define `stored_name(name) -> str`, which replaces each `/` by `{slash}`, and `model_name(stored) -> str`, its inverse, and the board reader and writer SHALL use them so that a net name with a slash is stored as KiCad stores a literal slash (`H-K-SCH-SLASH`).
- **Writing.** `write_board` MUST write a created net with `stored_name(net.name)`, in the net table and in every reference, for both targets. A net read from a file MUST be written with the spelling of its file, so a same-version rebuild stays tree-equal. `pcb.stored_net_name(net)` gives the written name: the stored spelling that the reader kept, else the name itself when the net's id is the one derived from `net:<name>` ("Identifiers of board items"), else `stored_name(net.name)`.
- **Reading.** `read_board` MUST give a net whose stored name holds `{slash}` the name `model_name(<stored name>)`, MUST keep its id derived from `net:<stored name>`, and MUST keep the stored spelling as the pair `stored` of the net's `kicad` extension bag. The id alone cannot give the spelling back: a net of a sub-sheet whose label text holds a slash is stored with both (`/cpu/A{slash}B`). A stored name without `{slash}` MUST be the net's name unchanged, a leading or inner `/` included: KiCad writes hierarchical net names with raw slashes.
- **Collision.** When `model_name(<stored name>)` is already the name of another net of the board, the net MUST keep its stored spelling as its name, with one `kicad.board.net-name-collision` info naming both. The code joins the closed table of "Board read issue codes".
- **Layout matching.** Layout preservation matches nets by model name (`layout-lens`, "Copper items follow their nets"), so copper on a net that an older build stored with a raw slash follows the design net of the same name, and the next write stores it with `{slash}`.
- No other character is changed by either function, and `model_name(stored_name(x)) == x` MUST hold for every string that holds no `{slash}`.

#### Scenario: Created net with a slash
- **GIVEN** a created design whose net `mod/LED_A` joins two pads
- **WHEN** it is written for target 10 and for target 9
- **THEN** the target-10 text holds `(net "mod{slash}LED_A")` on both pads, the target-9 text holds one table row named `mod{slash}LED_A`, and neither holds `mod/LED_A`

#### Scenario: Reads back with the slash
- **WHEN** either text is read with `read_board`
- **THEN** the net is named `mod/LED_A`, and writing the read design again gives a tree equal to the text that was read

#### Scenario: Hierarchical net untouched
- **GIVEN** a copy of `tests/data/kicad/board/two_layer.kicad_pcb`, built in the test, whose net `VCC` is renamed `/power/VCC`
- **WHEN** it is read and written for target 9
- **THEN** the net is named `/power/VCC` in the model and in the written text, and `roundtrip` passes

#### Scenario: A sheet path and a label slash in one name
- **GIVEN** a board, built in the test, with the net `/cpu/A{slash}B`
- **WHEN** it is read and written for target 9
- **THEN** the net is named `/cpu/A/B`, the written text holds `/cpu/A{slash}B`, and a rebuild is tree-equal

#### Scenario: Collision keeps the stored spelling
- **GIVEN** a board, built in the test, that holds the nets `a/b` and `a{slash}b`
- **WHEN** it is read with an `issues` list
- **THEN** the two nets are named `a/b` and `a{slash}b`, `issues` holds one `kicad.board.net-name-collision` info, and a rebuild is tree-equal

#### Scenario: Board of an older build
- **GIVEN** a confirmed blink variant with the net `mod/LED_A`, whose board text is then edited to store that net as `mod/LED_A` with one track on it
- **WHEN** the build runs again with `--confirm`
- **THEN** the written board stores the net as `mod{slash}LED_A` with the track on it, and `issues` holds no `layout.net-removed`
