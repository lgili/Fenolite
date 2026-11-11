# Electronic placement rule catalogue

The recognizers operate on resolved pin connectivity and declared device semantics. Each result
identifies the instance paths, pad IDs, matched evidence, source, rule version, competing
interpretations and missing inputs. Recognition proposes intent for review. A confirmed or
declared rule supplies placement relationships. Hardness and numerical limits come from the
effective requirements and their sources. Examples below describe circuit shapes for authored
fixtures. They supply no universal numeric rules.

## Decoupling and energy storage

**Recognize.** For a fitted two-terminal capacitor, follow each pad to its resolved net. Match
the pair against the mapped supply and return terminals of compatible IC banks in the same
domain. Evidence can include an explicit binding, confirmed bank metadata or a declared
reference circuit. A capacitor across a widely shared rail and return remains ambiguous when
several ICs could own it. Keep the alternatives visible. Bulk storage, bootstrap, charge pump,
regulator stability, snubber, timing, coupling and crystal load capacitors have distinct
relationships. Use the declared function or matched terminal topology. Capacitance and the
reference prefix cannot select a role. Exclude DNP instances as fitted solutions.

**Place.** Anchor a confirmed bypass to the actual supply pad and return pad or declared return
attachment. Generate positions and rotations that bring the supply pad of the capacitor toward
the corresponding IC pad and leave a legal connection for return. Evaluate both legs. A closer
centre or shorter supply leg can be worse if it puts the return across an obstacle. Prefer
short paths and viable escape on the permitted face. If a profile allows vias or the opposite
face, include their route and via cost. Via-in-pad requires an explicit rule. A board with a
plane requires known coverage or a verified return route for that credit.

**Assign jointly.** For multiple banks and capacitors, solve a bounded assignment of confirmed
eligible relationships before final placement. Give each required bank explicit coverage.
Use one capacitor for more than one bank only if the intent says it can be shared. Keep both
the ownership rationale and pad-level pose checks. Handle an impossible assignment as an
unmet requirement. Place bulk capacitors with their declared supply entry or regulator group
and mechanical needs. Preserve which side of a ferrite or isolation barrier each bank uses.

**Prove.** An authored MCU with two supplies, a ferrite-separated analog rail, two local bypass
capacitors, one bulk capacitor and a second IC on a shared rail. Swapping schematic symbol
positions changes no relationships. Changing a logical rail binding changes the matching
suggestion. Rotating a decoupler changes both pad distances. A pose with shorter estimated
distance and a blocked return loses when compared under the same routing probe.

Source: [MT-101, Decoupling Techniques, pp. 2–3](https://www.analog.com/media/en/training-seminars/tutorials/MT-101.pdf).
Use the actual component and board requirements for limits, capacitor selection and return policy.

## Clock and oscillator networks

**Recognize.** Match oscillator-specific terminal metadata and a two-terminal resonator on the
declared input/output pair. Match each load capacitor to the correct terminal and allowed
return. A clock module with a digital output has a different topology. A passive part near an
oscillator symbol in the sheet is insufficient evidence.

**Place.** Place the resonator with its pad orientation toward the oscillator pins and preserve
room for both load connections. Use a quiet area or exclusion from a switching corridor where
declared. Record any prescribed reference copper or guard requirements from the exact device
profile. The rule does not add a plane, split a return or generalize one part's layout note.

**Prove.** A multi-unit IC and a crystal on a repeated sheet with the same local net labels.
The two crystals keep distinct owners. An RC timing branch is not classified as a crystal
group. A closer pose whose load connection violates a declared exclusion is unavailable.

Source: [AN2867, oscillator design, section 7.1](https://www.st.com/resource/en/application_note/an2867-guidelines-for-oscillator-design-on-stm8afals-and-stm32-mcusmpus-stmicroelectronics.pdf).

## Switching power and current sensing

| Relationship | Recognition and placement policy | Authored proof case |
|---|---|---|
| High di/dt current loop | Use topology-specific ordered terminal groups and operating mode. For a declared buck input loop, jointly orient the high-frequency input capacitor and switching devices around the verified terminal path. Keep space for the required copper width and return. The bulk bank is a separate relationship. Use declared loop definitions for bridge or flyback topologies. | Two legal switch orientations with similar HPWL and different projected loop area and viable width. No loop-area credit when its path or return is unknown. |
| Gate drive and bootstrap | Follow output, series gate elements, gate and driver return terminals. Use declared Kelvin-source return if applicable. Position and orient the driver, gate resistor, supply bypass and bootstrap parts against their exact terminals. Keep drive and return close along a viable corridor. Component guidance controls resistor location and any allowed layer change. | Adjacent driver and switch with a blocked return, compared with a slightly farther legal pair of paths. A half-bridge's two high-side/low-side relationships stay distinct. |
| Kelvin and feedback | Match declared sense terminals or confirmed tap points through the allowed sense/filter chain. Prefer the filter near the receiver if specified. Keep force current, feedback and sense corridors distinct as required. Keep feedback return tied to its specified reference. Sense and power connectivity stay unchanged. | A four-terminal shunt and a two-terminal shunt with explicit tap intent. A short airwire that would attach a sense route through the power branch cannot earn credit. |
| Switching node and quiet area | Use confirmed noisy nets, path corridors and exclusions. Keep the switch-node connection compact when specified. Respect declared separation from oscillators, analog sense, feedback and other sensitive routes. Evaluate projected copper or route extent when available. | Moving a quiet group closer reduces HPWL but enters a declared switch-node exclusion. The hard checker rejects the move. |
| Input protection, isolation and output flow | Start at fixed ports and use explicitly mapped fuse/protection/filter/rectifier or regulator stages. Preserve the order of declared flows and space for power conductors. Match the isolation boundary from explicit domains and keep-outs. Ties between domains are those already resolved by the circuit. | Identically named local returns in two isolated sheets remain separate. Moving a component across a slot or reducing a declared clearance is rejected. |

Sources: [AN-139, power-supply layout and EMI](https://www.analog.com/en/resources/app-notes/an-139.html),
[SSZT533, gate drive and returns](https://www.ti.com/lit/pdf/sszt533) and
[SSZTAD8, differential current sense](https://www.ti.com/lit/pdf/ssztad8). These examples motivate
topology-specific paths and returns. They do not set isolation values, currents or thermal limits.

## Signal flow, dense packages and assemblies

- **Source termination, ESD and series chains.** Use explicit port direction and function to
  distinguish source termination, connector-side protection and receiver-side filters. Evaluate
  the intended physical pad chain and the branch/stub geometry. Do not infer source from drawing
  order or assume every series resistor is a termination. Include a bidirectional port fixture
  with ambiguous direction and an explicitly bound protection fixture.
- **Differential pairs and buses.** Use declared pairs, polarity and bus members. Reserve a joint
  escape corridor at both ends. Use per-layer width and gap and available reference copper when
  known. Favor compatible endpoint ordering and few crossings. Preserve the pin map. If the
  router cannot probe the whole coupled group, show unsupported evidence. Check with an authored
  mirrored connector case where HPWL alone prefers an unhelpful orientation. Source:
  [SLLA414A, sections 3–4](https://www.ti.com/lit/an/slla414/slla414.pdf).
- **RF and antenna.** Take edge alignment, facing direction, copper/height keep-outs and matching
  order from the supplied module constraints. Leave the feed and connector access available.
  Unknown module constraints are visible. Include an authored explicit keep-out with distinct
  restrictions on footprint, copper and enclosure geometry.
- **Heat and assembly.** Use measured or declared body volumes, dissipator anchors, heat-sensitive
  keep-outs, airflow or insertion direction, connector access and assembly side constraints.
  Reserve space for declared heat-spreading copper or thermal vias. Optional assembly alignment,
  polarity-mark visibility and consistent orientations are late preferences where measurable.
  Report missing height, volume and source measurements. Prove with a known tall body below an
  enclosure and a connector with a declared accessible face. No thermal model is inferred from
  footprint area, no assembly qualification follows from a planar courtyard fit.

## Review and provenance

Each rule presents its purpose, source, effective precedence and measured relationship at the
selected candidate. An inference may be accepted, rejected or replaced by exact bindings.
Rule confidence describes the match evidence, not electrical performance. Mark example inputs
as authored. Record the source URL, section, revision and consultation date when a rule is
implemented. Register evidence and use only paraphrased principles. Keep project-specific
values, private drawings and part relationships out of this repository.
