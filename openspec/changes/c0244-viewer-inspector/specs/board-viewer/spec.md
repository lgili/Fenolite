## ADDED Requirements

### Requirement: Docked inspector
The page SHALL show the selection's properties in a dock beside the drawing, never over it, in sections by kind: Part, Pad, Track, Arc, Via, Zone, Net, Keep-out and Finding. Each value MUST show in the page unit, follow a unit change and have a copy control; "Copy all" MUST copy every row as text. A value the scene does not hold MUST be left out. Sheets, libraries and drawings MUST use the same dock.

#### Scenario: A pad's size, copied
- **GIVEN** the exported page of `two_layer.kicad_pcb`
- **WHEN** `uv run pytest tests/visual/test_inspector.py -k pad` clicks pad 1 of `R1`, copies its size, presses `Q` and reads the dock
- **THEN** the dock holds a Pad and a Part section, the clipboard holds the size in millimetres as displayed, the size then reads in mil, and nothing of the dock overlaps the canvas

#### Scenario: Missing values are left out
- **WHEN** `uv run pytest tests/unit/view/test_page.py -k inspector` renders an authored inspector model under Node with a pad that has no drill
- **THEN** the rendered rows hold no drill row and each row has a copy control

### Requirement: Inspector actions
The inspector SHALL offer actions on the selection: Zoom to, Highlight net, Select part, Find similar, Show in schematic or Show on board, and Open finding. An action that cannot apply MUST be hidden. Each action MUST also be reachable from the command palette, and a cross-probe MUST keep the guards of "Current browser navigation owns the view".

#### Scenario: Show in schematic
- **GIVEN** the exported page of `tests/data/altium/blink/blink.PrjPcb` with its board open
- **WHEN** `uv run pytest tests/visual/test_inspector.py -k cross_probe` selects a part and runs Show in schematic
- **THEN** the sheet holding the part opens with that part selected

### Requirement: Net emphasis
While a net or part is selected, its items SHALL be drawn in their own layer colours at full opacity and outlined in the emphasis colour, and every other item SHALL be drawn at the opacity of the highlight mode. Zone fills of a selected net MUST be outlined and drawn lighter, so its tracks and pads stay visible over the pour. The selected items MUST NOT be lightened towards white.

#### Scenario: A ground net stands out
- **GIVEN** the exported page of `two_layer.kicad_pcb`
- **WHEN** `uv run pytest tests/visual/test_inspector.py -k emphasis` selects net `GND` and samples pixels
- **THEN** a pixel of a `GND` track equals its layer colour, and a pixel of a track of another net is darker than before the selection

### Requirement: Layers panel
On boards and footprints the page SHALL list the layers in a panel grouped as copper, mask and paste, silkscreen, mechanical and fabrication, and view layers. Each row MUST show the swatch, the full name, visibility, opacity and whether it is current, and the layer sets MUST be presets. `Shift+S`, `+` and `-` MUST keep their effect, and sheet tabs MUST stay in the bottom bar.

#### Scenario: Long names are not cut
- **GIVEN** the exported page of `tests/data/altium/blink/blink.PcbDoc` at 1440 by 900 pixels
- **WHEN** `uv run pytest tests/visual/test_layers.py -k names` reads the Layers panel
- **THEN** every row shows its layer's full name, `Board Outline` included, the panel has no horizontal overflow, and the bottom bar lists no layer

#### Scenario: Opacity and shortcuts
- **WHEN** the test sets `F.Cu` to 30 % opacity, then presses `Shift+S` and `+`
- **THEN** the drawing of `F.Cu` changes, only the current layer is shown, and the next visible layer becomes current

### Requirement: 3D view controls
In 3D the page SHALL hide the controls that act only in 2D, show a view cube whose faces and corners set the camera, light the scene with an ambient and two directional lights, and draw a body without a model in Fenolite's body colour with a lighter top face. Bodies with a model MUST keep the model's colours.

#### Scenario: The view cube
- **GIVEN** the exported page of `two_layer.kicad_pcb`
- **WHEN** `uv run pytest tests/visual/test_3d.py` switches to 3D and clicks the cube's Front face
- **THEN** Measure, Mark and the Layers panel are hidden, the camera shows the front view, and the page reports no error

### Requirement: Inspector in narrow windows
At viewport widths of 760 CSS pixels or below the dock SHALL become a bottom sheet of at most 60 % of the viewport height that a selection opens and `Esc` or its close control dismisses, and the canvas SHALL keep the viewport width.

#### Scenario: A 390-pixel window
- **WHEN** `uv run pytest tests/visual/test_inspector.py -k narrow` opens the page at 390 pixels, selects a pad and presses `Esc`
- **THEN** the sheet opens below the canvas within 60 % of the height, the canvas keeps the full width, and `Esc` closes the sheet

## MODIFIED Requirements

### Requirement: Viewer page
`fenolite.view.export.template()` SHALL give one HTML file with inline styles and scripts and no external URL, assembled from the committed bundles of `src/fenolite/view/static/`, drawing a scene in 2D and 3D with the project tree at the left, the inspector and Layers panel docked at the right, Top and Bottom views, highlight, search, measurement and overlays; `page(tree, scenes)` SHALL embed a tree and its scenes.
- It MUST read a scene embedded (export) or from "Live server".
- Texts MUST use Fenolite's single-stroke font.

#### Scenario: Standalone page round-trips
- **GIVEN** the tree and the scene of `two_layer.kicad_pcb`
- **WHEN** `uv run pytest tests/unit/view/test_page.py` exports the page and reads the embedded JSON back
- **THEN** the JSON equals the scene, and the page holds no `http://` or `https://` URL

#### Scenario: The served page is the assembled page
- **GIVEN** the committed shell, `viewer.js` and `viewer.css`
- **WHEN** `uv run pytest tests/unit/view/test_viewer_bundle.py -k assembled` builds `page(live=True)`
- **THEN** the page holds the CSS bundle inside its `<style>` element and the JS bundle inside its last `<script>` element, and no placeholder of the shell is left
