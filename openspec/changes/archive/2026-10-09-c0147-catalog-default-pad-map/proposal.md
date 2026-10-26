## Why

Three catalog lands keep the manufacturer's numbering with pad 1 at the cathode: `LED0603_Kingbright_APT1608SURCK`, `LED0805_Kingbright_APT2012SURCK` and `SOD128_Nexperia_CFP5`. The generic diode symbols have pin 1 `A` and pin 2 `K`. Change c0144 documented the pair and left an open question: should the catalog apply a default pin-to-pad map when the part gives none (c0144, `design.md`, "Open question for the maintainer"; task 3.3)?

**The maintainer decided on 2026-10-08: yes, apply the default map automatically.** A script that connects the part by pin name, which is what an agent writes, then puts the anode's net on the anode's pad without having to know the land's numbering.

c0144 named the risk of that answer: a design of a 0.2.x user that wired one of these lands by pin number without a map (as the kit did before c0144: `GND` on `d1[1]`) has a right board today, and with a default map its two nets swap pads on the next build, on a board that may be made already. This change applies the map and makes the swap loud: every build that applies it reports the part.

## What Changes

- **A default map for the cathode-first pairs.** A part of an anode-first catalog symbol (`Diode`, `LED`, `Photodiode`, `Schottky_Diode`, `Zener_Diode`: every two-pin catalog symbol with pin 1 `A` and pin 2 `K`) on one of the three lands, that gives no `pad_map`, gets `{"1": "2", "2": "1"}`: the anode pin on pad 2, the cathode pin on pad 1. It is applied to the model that the KiCad and the Altium targets share, so both write the same pad nets.
- **An explicit `pad_map` always wins**, unchanged. A design that authors the symbol or the land under the same lib id is not using the catalog's definition and gets no default.
- **The default is reported.** A new build code `build.pad-map-default` (warning) per part, naming the part (`where`), the symbol, the land and the map, with a hint: write `pad_map={"1": "2", "2": "1"}` to keep the map and silence the warning, or `pad_map={"1": "1", "2": "2"}` to keep the pad order of earlier builds. Registered in `BUILD_ISSUE_CODES`, `fenolite explain`, `docs/cli-contract.md` and the closed set of `design-dsl`.
- The catalog pages, `docs/dsl.md` and the `CHANGELOG` say that the map is applied by default and that an explicit one wins.

Size: 0.25 design-days.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `fenolite-component-catalog`: MODIFIED "Lands numbered against the generic diode symbols are documented" (added by c0144); ADDED "Default pin-to-pad map of the cathode-first lands".
- `design-dsl`: ADDED "Default pin-to-pad map is reported" (joins "Build issue codes").

## Non-goals

- Renumbering the pads of the three lands: their numbering is the manufacturer's and released boards hold it.
- A default map for any other pair: every other catalog land keeps the identity map, which is right for its symbols (design, Context).
- A default map for a symbol or land of the user's own library, or for `fenolite.dsl.to_model` called directly from Python: the map is applied by the command line's build, kit and sync paths, which know the catalog (design, Decision 2).
- Refusing such a design: the warning does not fail the build, so a script that a user runs unattended still builds.

## Evidence level required

`INFERRED`. The polarity of the lands comes from the manufacturers' public datasheets (S-0375, S-0412, S-0413), as c0144 recorded; the pad nets are proved by Fenolite's own readers of the KiCad board and the Altium PCB document. Nothing was opened in KiCad or Altium for this change.
