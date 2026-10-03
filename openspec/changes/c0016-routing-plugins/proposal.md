## Why

A built board has no tracks, so KiCad's DRC reports every net as unconnected and v0.1's loop cannot close (acceptance item 3: routing leaves 0 unconnected items on the small example, judged by KiCad's DRC). Fenolite writes no router (plan D11): routers are plugins behind a protocol. The first one is KiCadRoutingTools (S-0215): MIT-licensed, a command-line A* router that reads and writes `.kicad_pcb` files for KiCad 9 and 10 without KiCad installed. It has no pip package, has heavy dependencies and changes fast, so it can only be a pinned external tool.

The roadmap makes this change a gate: if KiCadRoutingTools routes the blink cleanly on both majors, c0023 (Specctra and Freerouting) may leave v0.1.

## What Changes

- `routing/` (new package): `RoutingJob`, `RoutingResult` and the `Router` protocol on plain model data; a registry that reads the entry-point group `fenolite.routers`; `merge` adds routed tracks and vias to a design.
- `routing/direct.py`: a built-in router that joins two-pad nets with one straight track. It avoids nothing and exists for hermetic tests and examples.
- `routing/plugins/kicad/routingtools.py`: writes the board for its own major into a temporary folder with its project and rules files, runs `py_router/route.py` from a checkout the user names, reads the routed board, and lifts only the new tracks and vias.
- `fenolite route PATH --router NAME` (new, mutating): selects unrouted nets, runs the router, merges the copper and writes the board; results carry `UNVERIFIED`, because KiCad's DRC is the judge.
- `capabilities` lists routers; `doctor` reports the KiCadRoutingTools checkout.
- Feasibility gate first, on 9.0.9 and 10.0.6: the routed blink has 0 unconnected items and no new error; the tool's output loads and changes nothing but copper; two runs compared.
- CI: a `routing` smoke job, not required for merge, with the tool at a pinned tag.
- Sources S-0215 to S-0218; hypotheses `H-K-KRT-CLI`, `H-K-KRT-ROUTE`, `H-K-KRT-KEEP`, `H-K-KRT-REPEAT`.

Budget: 7.5 days against the roadmap's 6; the cut order is in the design.

## Capabilities

### New Capabilities
- `routing`: the protocol, the registry, net selection, merging, the built-in router, the KiCadRoutingTools plugin, issue codes, evidence.

### Modified Capabilities
- `cli-contract`: ADDED "Route command", "Routers in capabilities and doctor".
- `kicad-oracle`: ADDED "Routed boards pass the oracle".
- `ci-baseline`: ADDED "Routing smoke job", "Router resource".
- `package-layering`: MODIFIED "Allowed import edges" (a router plugin may also import `model` and `geometry`).

## Non-goals

- Specctra DSN/SES and Freerouting (c0023); a cloud router; any router that sends data off the machine.
- A router of Fenolite's own beyond `direct`; differential pairs, length matching, BGA fanout and plane creation, even where the tool offers them.
- Installing, building or vendoring the tool; importing it.
- Ripping up or optimising existing copper beyond `--rip` of the selected nets.
- Judging the result: `check` and KiCad's DRC do that.

## Evidence level required

- Protocol, registry, net selection and merging: mechanical (hermetic tests with `direct` and a fake tool).
- KiCadRoutingTools arguments and outputs: `KICAD-VERIFIED (9.0.x, 10.0.x)` for the pinned tag, in the sense that the routed boards pass `kicad-cli` (`H-K-KRT-CLI`, `H-K-KRT-ROUTE`, `H-K-KRT-KEEP`).
- Repeatability: recorded (`H-K-KRT-REPEAT`); a tool that is not repeatable is reported as such and gates nothing.
- Every `route` result: `UNVERIFIED`; the level of a routed board is what `check` gives it.

## Impact

- New `routing/`, `cli/cmd_route.py`; extended `cli/cmd_capabilities.py`, `cmd_doctor.py`, `pyproject.toml` (entry points only; `dependencies` stays empty), `.github/workflows/ci.yml`.
- No model or schema change. The `routing` rows of `package-layering` exist; the plugin row gains `model` and `geometry`.
- Depends on c0028 (`BoardFrame.board_pads`) and c0020 (DRC findings); the oracle proof also uses c0022 (`place`) and c0015 (`fill`), which archive first.
