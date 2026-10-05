# Catalog coverage matrix

This matrix tracks reusable generic definitions, not part-number coverage. Symbol pin labels and
numbers describe conceptual roles; they are not a package pinout for a purchasable device. A part
must name its footprint explicitly and use a device-specific symbol/pin map where its datasheet
requires one.

## Symbol families

| Family | Built-in symbols | Status | Limits |
|---|---|---|---|
| Passive: resistors, ceramic/electrolytic/film capacitors, inductors and ferrite beads | `Resistor`, `Capacitor`, `Capacitor_Ceramic`, `Capacitor_Electrolytic`, `Capacitor_Film`, `Capacitor_Polarized`, `Inductor`, `Ferrite_Bead` | covered | Generic schematic roles; no electrical value, rating or MPN is implied. |
| Discrete semiconductors: diode, Zener, LED and bridge rectifier | `Diode`, `Zener_Diode`, `LED`, `Bridge_Rectifier` | covered | Bridge terminal names are conceptual; check the selected device datasheet. |
| Optoelectronic isolation | `Optocoupler` | covered | The four pins describe a generic LED/photodetector block, not an exact optocoupler pinout or isolation rating. |
| Protection: fuse, varistor and surge suppressor | `Fuse`, `Varistor`, `Surge_Suppressor` | covered | Ratings, trip curves, polarity and certification are device-specific. |
| Power/control ICs: analog amplifier, comparator, linear regulator, offline power controller, MCU and power module | `Operational_Amplifier`, `Comparator`, `Linear_Regulator`, `Offline_Power_Controller`, `Microcontroller`, `Power_Module` | covered | Block pins are role labels only; exact pin maps must come from the selected part's public datasheet or a project-authored symbol. |
| Electromechanical: connectors and single-circuit terminals | `Connector_2`, `Connector_3`, `Connector_4`, `Terminal_1Pin` | covered | Symbol count does not select a connector series, pitch or mating part. |
| Two-winding common-mode choke | `Common_Mode_Choke` | covered | Conceptual winding terminals only; coupling, current and insulation are part-specific. |
| Two-electrode gas discharge tube | `Gas_Discharge_Tube` | covered | Bidirectional non-polar symbol; sparkover ratings and package remain part-specific. |
| Common-cathode dual LED | `Dual_LED_Common_Cathode` | covered | Two anodes share a cathode in this variant only; no physical pinout or color is implied. |

## Reusable package styles

The c0076 change now has a [100-variant footprint target](target-100-footprints.md) selected
from a fixed public-board usage proxy and official package-family sources. The table below lists
the 14 currently shipped definitions; the other 86 target slots remain planned.

| Package style | Built-in footprint IDs | Evidence | Scope or limitation |
|---|---|---|---|
| Two-terminal chip passive, 0402 through 1206 | `Chip_0402`, `Chip_0603`, `Chip_0805`, `Chip_1206` | `INFERRED` generic use | Rectangular lands follow a Vishay reflow resistor example; other component families and assembly processes need their own review. |
| Small-outline 3/5 lead and 8 lead | `SOT23_3`, `SOT23_5`, `SC70_5`, `SOT89_3`, `SOIC_8` | `INFERRED` corner/variant details | Rectangular pad size, pitch and top-view numbering follow official package examples; check the selected package variant and assembly process. |
| Surface-mount diode | `DO214AC` | source reference land; still `INFERRED` for Fenolite's implementation | The cited manufacturer calls its layout suggested/reference only. Verify against the selected diode and process. |
| Leaded IC | `LQFP32_P0.8` | `INFERRED` corner/variant details | TI VF0032A example sets four-side numbering and perpendicular pad axes; not a pin-compatible symbol or approved package for every 32-pin IC. |
| Single-row through-hole header, 2.5 mm pitch | `Header_1x2_P2.5`, `Header_1x3_P2.5`, `Header_1x4_P2.5` | `INFERRED` lands | Pitch is supported by a public connector drawing. Hole and pad sizes are Fenolite starting values; check the selected terminal. |

## Project-authored or separately specified geometry

The current model can describe many custom footprints, but the generic catalog does not guess a
physical pattern when public evidence does not define a reusable package. Create a project-authored
definition or a separately sourced catalog entry for:

- power modules with vendor-specific pin grids, exposed plates, slots, mounting holes or thermal
  interfaces;
- connector families whose shrouds, stakes, locating pegs, board locks, pitch or mating geometry
  differ from the generic 2.5 mm single-row header;
- ring terminals, quick-connect tabs and fuse holders, whose formed/mechanical interfaces and
  mounting dimensions are product-specific;
- radial electrolytic and film capacitors, radial MOVs, axial parts and custom chokes when a
  specific body, lead spacing or mounting form is required;
- optocoupler surface-mount variants with a specified creepage/clearance or lead-form requirement.

These limitations are about choosing a sufficiently evidenced reusable geometry. They do not mean
that the DSL cannot author a one-off footprint. The catalog makes no safety, thermal, interchange-
ability, assembly or fabrication qualification claim.
