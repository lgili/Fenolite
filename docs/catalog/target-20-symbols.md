# Additional 20 schematic symbol families

This fixed expansion brings the independently authored catalog from 29 to 49 symbols. It fills generic functional gaps; it is not a measured top-20 popularity ranking. Public datasheets support functions and polarity only. All vectors and conceptual terminal numbers remain `INFERRED`. No footprint or purchasable part is selected automatically.

| Slot | Exact Fenolite name | Conceptual terminal roles | Drawing decision | Public sources |
|---|---|---|---|---|
| 1 | `BJT_NPN` | 1 B, 2 C, 3 E | Outgoing emitter arrow | S-0423 |
| 2 | `BJT_PNP` | 1 B, 2 C, 3 E | Incoming emitter arrow | S-0424 |
| 3 | `MOSFET_N_Channel` | 1 G, 2 D, 3 S | Enhancement; isolated gate, inward body arrow, S-to-D diode | S-0425 |
| 4 | `MOSFET_P_Channel` | 1 G, 2 D, 3 S | Enhancement; isolated gate, outward body arrow, D-to-S diode | S-0426 |
| 5 | `IGBT` | 1 G, 2 C, 3 E | Isolated gate and outgoing emitter arrow; no implied integrated diode | S-0427 |
| 6 | `SCR` | 1 A, 2 K, 3 G | Cathode-side gate | S-0428 |
| 7 | `TRIAC` | 1 MT2, 2 MT1, 3 G | Opposed conduction paths, MT1-side gate | S-0429 |
| 8 | `Schottky_Diode` | 1 A, 2 K | Continuous hooked cathode | S-0430 |
| 9 | `TVS_Bidirectional` | 1 A, 2 B | Back-to-back protection, non-polar terminals | S-0431 |
| 10 | `Potentiometer` | 1 A, 2 W, 3 B | Zigzag track, wiper touches track | S-0432 |
| 11 | `Thermistor_NTC` | 1 A, 2 B | Zigzag and negative T coefficient mark | S-0433 |
| 12 | `Thermistor_PTC` | 1 A, 2 B | Zigzag and positive T coefficient mark | S-0434 |
| 13 | `Crystal` | 1 X1, 2 X2 | Two electrodes separated from crystal body | S-0416 |
| 14 | `Switch_SPST` | 1 A, 2 B | Unactuated open contact | S-0435 |
| 15 | `Switch_SPDT` | 1 COM, 2 NC, 3 NO | Unactuated COM-NC contact | S-0435 |
| 16 | `Pushbutton_NO` | 1 A1, 2 A2, 3 B1, 4 B2 | Normally open; internal common pairs 1-2 and 3-4 | S-0417, S-0418 |
| 17 | `Relay_SPDT` | 1 COIL1, 2 COIL2, 3 COM, 4 NC, 5 NO | Unenergized COM-NC, isolated coil and mechanical coupling | S-0436 |
| 18 | `Transformer` | 1 P1, 2 P2, 3 S1, 4 S2 | Separate windings, core and conceptual phase markers | S-0437 |
| 19 | `Photodiode` | 1 A, 2 K | Diode with inward incident-light arrows | S-0438, S-0440 |
| 20 | `Phototransistor` | 1 C, 2 E | NPN detector, inward light arrows, outgoing emitter arrow | S-0439, S-0440 |

## Assignment constraints

BJT numbers are B/C/E conceptual roles, not the Nexperia B/E/C physical numbering. Explicit pad maps must resolve this difference. A crystal has two electrode roles; ABM8 also has case pads, which require an explicit device symbol or unused-pad treatment. The four-terminal pushbutton has common pairs 1-2 and 3-4: the SMT Würth variant matches those pairs, while its THT counterpart requires mapping 1→1, 2→3, 3→2, 4→4. The generic relay has five functional terminals; G5V-1 has duplicate physical COM pins. The two-winding transformer is a functional abstraction, not the cited multiple-winding part. IGBT diode integration depends on the chosen device.

Thermistor T marks describe coefficient class, not a transfer curve. Switches and relay are drawn at rest; SPST/pushbutton are open and SPDT/relay connect COM to NC. Arrows and phase marks use outline geometry supported by the existing symbol model. KiCad background fill is reproduced as white, without pretending the model supports foreground fill.

## Completion proof

All 20 entries are implemented, bringing offline discovery to 49 symbols alongside 100 footprints. Native galleries were rendered from the actual model and visually inspected, including the complete catalog and the relay/IC label-spacing corrections.

- `uv run pytest tests/unit/catalog tests/unit/cli/test_catalog.py tests/unit/lens/test_build_catalog_symbols.py tests/unit/lens/test_build_catalog_inventory.py -q`: 459 passed.
- `make check-fast`: 5771 passed, 10 skipped; lint, formatting, types and residue checks passed.
- `openspec validate c0076-component-catalog-coverage --strict`: valid.

The fixtures prove conceptual terminal maps, correct common-pair pad nets, local-library graphics and board readback for KiCad 9/10 writer targets. They do not promote independently authored geometry beyond `INFERRED`. The maintainer authorized local dev squash integration and spec archival on 2026-10-05. The full suite is deferred to later batched CI; no push or successful CI run is claimed by this archive.
