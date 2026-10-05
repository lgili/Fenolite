# Catalog evidence map

| Catalog entries | Evidence | Sources | Facts supported |
|---|---|---|---|
| `Fenolite:Resistor` | `INFERRED` | S-0314, S-0343 | The resistor family and zigzag schematic convention; vertices and pin coordinates are authored by Fenolite. |
| `Fenolite:Capacitor`, `Fenolite:Capacitor_Polarized`, `Fenolite:Inductor` | `INFERRED` | S-0314 | The component kinds and existence of common schematic symbol examples; vector shapes and pin coordinates are authored by Fenolite. |
| `Fenolite:Chip_0402`, `Fenolite:Chip_0603`, `Fenolite:Chip_0805`, `Fenolite:Chip_1206` | `INFERRED` | S-0315, S-0333 | Yageo RC_L body sizes and Vishay document 28950 IPC-7351 reflow resistor/fuse land examples. The generic chip family is not a claim that the same lands fit every capacitor or bead. |
| `Fenolite:Ferrite_Bead` | `INFERRED` | S-0318 | Ferrite/chip bead is a common two-terminal noise-suppression component; the generic symbol is Fenolite-authored. |
| `Fenolite:Diode`, `Fenolite:LED` | `INFERRED` | S-0319 | Diode and LED categories and symbol relationships; Fenolite-authored generic vector graphics. |
| `Fenolite:Zener_Diode` | `INFERRED` | S-0319, S-0344 | The Zener family and bent-cathode convention; Fenolite-authored continuous cathode geometry. |
| `Fenolite:Bridge_Rectifier` | `INFERRED` | S-0329, S-0342 | Bridge rectifiers are a distinct four-terminal family; the four-diode topology is sourced, while all vector geometry is Fenolite-authored. |
| `Fenolite:Capacitor_Ceramic` | `INFERRED` | S-0328 | Ceramic/MLCC capacitor product family; generic symbol geometry is Fenolite-authored. |
| `Fenolite:Capacitor_Electrolytic` | `INFERRED` | S-0329 | Aluminum electrolytic capacitor product family; the generic symbol does not assert specific construction or ratings. |
| `Fenolite:Capacitor_Film` | `INFERRED` | S-0328 | Film capacitor product family; the generic symbol does not assert specific construction or ratings. |
| `Fenolite:Varistor`, `Fenolite:Surge_Suppressor` | `INFERRED` | S-0320 | MOV/varistor surge-suppression family; no rating or connection selection is implied. |
| `Fenolite:Optocoupler` | `INFERRED` | S-0325 | A public photocoupler example uses an LED and phototransistor; Fenolite's generic block is not the example's pinout. |
| `Fenolite:Fuse` | `INFERRED` | S-0326 | Fuse families provide overcurrent protection; no rating, package or trip characteristic is implied. |
| `Fenolite:Operational_Amplifier`, `Fenolite:Comparator`, `Fenolite:Linear_Regulator`, `Fenolite:Offline_Power_Controller`, `Fenolite:Microcontroller`, `Fenolite:Power_Module` | `INFERRED` | S-0316, S-0317, S-0341 | Public component categories and op-amp input signs; Fenolite's generic role-labelled symbols do not claim exact electrical pin numbers. |
| `Fenolite:Connector_2`, `Fenolite:Connector_3`, `Fenolite:Connector_4`, `Fenolite:Terminal_1Pin` | `INFERRED` | S-0324 | Generic circuit terminals and a public 2.5 mm-pitch connector family exist; the symbols do not assert the cited connector series. |
| `Fenolite:Common_Mode_Choke` | `INFERRED` | S-0345 | TDK's public example supports two separate coupled windings; Fenolite graphics and generic numbering are independent. |
| `Fenolite:Gas_Discharge_Tube` | `INFERRED` | S-0346 | Bourns' two-electrode tube is bidirectional and non-polar; Fenolite's generic symbol has no device rating. |
| `Fenolite:Dual_LED_Common_Cathode` | `INFERRED` | S-0347 | Kingbright's public example supports two anodes with one shared cathode; Fenolite's symbolic numbers are not the product's pinout. |
| `Fenolite:SOT23_3` | `INFERRED` | S-0322, S-0334 | Nexperia body outline; TI DBZ0003A top-view land example and pin sequence. Rectangular pads approximate the source's 0.05 mm corner radius. |
| `Fenolite:SOT23_5`, `Fenolite:SC70_5` | `INFERRED` | S-0323, S-0335 | TI DBV0005A and DCK0005A land examples give 1/2/3 left and 5/4 right, horizontal pad axes and non-touching pin pitch. Rectangular pads omit the 0.05 mm corner radius. |
| `Fenolite:SOT89_3` | `INFERRED` | S-0322, S-0338 | Diodes SOT89 reference T-shaped pad 2 is modelled as two overlapping same-number rectangles; pads 1 and 3 remain isolated. |
| `Fenolite:SOIC_8` | `INFERRED` | S-0323, S-0336 | TI D0008A example gives horizontal 1.55 by 0.6 mm pads, 1.27 mm pitch, 5.4 mm row spacing and top-view numbering. Rectangular corners are inferred. |
| `Fenolite:DO214AC` | `INFERRED` | S-0321 | Diodes Incorporated package dimensions and a suggested reference land. The source notes land layouts may vary; the catalog still requires process-specific review. |
| `Fenolite:LQFP32_P0.8` | `INFERRED` | S-0327, S-0337 | TI VF0032A example gives 1.5 by 0.55 mm lands, 0.8 mm pitch, 8.4 mm opposing-row center spacing and top-view numbering. Top/bottom pad axes are perpendicular to left/right. Rectangular corners are inferred. |
| `Fenolite:Header_1x2_P2.5`, `Fenolite:Header_1x3_P2.5`, `Fenolite:Header_1x4_P2.5` | `INFERRED` | S-0324 | JST XH public 2.5 mm circuit pitch and board drawing support pitch only; Fenolite-authored hole/pad sizes are not a JST recommended land pattern. |
| `Fenolite:Offline_Power_Controller` | `INFERRED` | S-0316, S-0330 | Offline switcher controllers are a product family; conceptual pin-role labels are not a particular pinout. |
| `Fenolite:Power_Module` | `INFERRED` | S-0316, S-0331 | Intelligent power modules and power integrated modules are distinct families; conceptual block labels do not define a package pin map. |
| `Fenolite:Linear_Regulator` | `INFERRED` | S-0316, S-0332 | Linear/LDO regulator is a product family; conceptual pin-role labels are not a particular part pinout. |

An evidence level describes the weakest material claim attached to a catalog entry. Successful
serialization or readback checks consistency only; it does not promote the source evidence.

All SMD pad copper is rectangular. Body rectangles are fabrication-layer guides; no silkscreen line
crosses a pad. Courtyards enclose body and copper. Reflow examples and inferred corner details need
checking against the selected part and assembly process.

The c0076 symbol redraw follows public KiCad drawing and pin-direction guidance (S-0339, S-0340).
Fenolite authored every vector path and kept conceptual device pin maps. Diode anode/cathode
identities follow S-0319, and amplifier input signs follow S-0341. The positive mark on polarized
capacitors follows the generic polarity convention; the bridge's four branches follow the functional
topology in S-0342. The revised graphics, proportions, pin positions and 0.254 mm stroke do not
come from KiCad library files or a private board. Connector and terminal symbols have functional contacts;
passive and protection pin names are hidden when their numbers and body marks suffice. The
serialized KiCad symbol library now preserves that visibility setting.

The later c0076 visual revision keeps Toshiba's public LED-to-phototransistor functional example
(S-0325) as the optocoupler's source while authoring a larger horizontal LED and two optical arrows
within its generic block. The 2/3/4-circuit connector symbols now use independently drawn square
contacts with one pin stem each; JST's S-0324 supports only circuit count and physical pitch, not
the schematic contact shape. `Capacitor_Polarized` and `Capacitor_Electrolytic` use a thicker plate
on the negative side, opposite the positive mark, as a visual choice requested by the user. Neither
the thick-plate style nor these graphics assert a manufacturer's device pinout or package.

The complete c0076 gallery was reviewed again as 26 symbols, grouped by shared drawing path:
six capacitors and the resistor, inductor and ferrite; three diode forms, bridge and optocoupler;
fuse, varistor and generic suppressor; five functional IC blocks and two amplifier triangles;
and three multi-circuit connectors plus the single terminal. The user's schematic page images
informed broad presentation preferences only. The resulting smooth coil and fuse, centered
connector rows with grouped housings and inset square contacts, square terminal socket, clean
functional IC blocks and amplifier supply contact geometry are independently authored here. No
private drawing, circuit value, net or proprietary pin map is a source. The prior zigzag resistor,
continuous Zener cathode, explicit optocoupler interior and polarized plate weight are retained.
All these symbol geometries remain `INFERRED`.

Three additional generic symbols complete functional roles seen during the gallery review:
`Common_Mode_Choke` uses TDK's public two-winding topology (S-0345),
`Gas_Discharge_Tube` uses Bourns' two-electrode and non-polar facts (S-0346), and
`Dual_LED_Common_Cathode` uses Kingbright's shared-cathode variant (S-0347). Their
schematic shapes and conceptual numbering are Fenolite-authored; the cited datasheets do not
authorize a package choice or exact pin map for another device.
