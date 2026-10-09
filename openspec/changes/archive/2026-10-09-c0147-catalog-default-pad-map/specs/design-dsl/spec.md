## ADDED Requirements

### Requirement: Default pin-to-pad map is reported
A build SHALL report each part that gets the catalog's default pin-to-pad map (`fenolite-component-catalog`, "Default pin-to-pad map of the cathode-first lands") with one warning, which joins the closed build set ("Build issue codes"), for the KiCad and the Altium target alike:

| code | severity | when |
|---|---|---|
| `build.pad-map-default` | warning | a part of an anode-first catalog symbol on a cathode-first catalog land gives no `pad_map`, and the build applied `{"1": "2", "2": "1"}` |

- The issue MUST have the part's path as `where`, and its message MUST name the reference, the symbol, the land and the map applied, as `pad_map={"1": "2", "2": "1"}`.
- The hint MUST name the `pad_map` that keeps the map and silences the warning, and the identity map `pad_map={"1": "1", "2": "2"}` that keeps the pad order of builds before change c0147.
- A part that gives a `pad_map`, and every other part, MUST give no such issue. The warning MUST NOT change the exit code of the build.
- `fenolite explain build.pad-map-default` and `docs/cli-contract.md` MUST explain the code.

#### Scenario: The default is reported
- **GIVEN** the script of "Part without a map" (`fenolite-component-catalog`)
- **WHEN** it is built with `--confirm --json` for either target
- **THEN** the exit code is 0 and `issues` hold exactly two `build.pad-map-default` warnings, at `D1` and `D2`, the first with the message `D1 (Fenolite:LED on Fenolite:LED0603_Kingbright_APT1608SURCK) gives no pad_map; the build applies the catalog's map pad_map={"1": "2", "2": "1"} (pin 1 on pad 2, pin 2 on pad 1): pad 1 of this land is the cathode`

#### Scenario: A map silences it
- **WHEN** both parts of that script give a `pad_map`
- **THEN** `issues` hold no `build.pad-map-default`
