## Context and decisions

The existing writer draws a neutral sheet through `schdot.sheet_frame`. Native templates take a
separate path after schematic generation, using Fenolite's own compound and property-list readers.
Public facts already registered in `docs/formats/altium/sheet-template.md` (S-0130, S-0261,
S-0264, S-0265) describe sheet record 31, template owner 39, fonts and embedded storage.

1. `--altium-template` is explicit, binary `.SchDot` only, with binary Altium output. Reject KiCad,
   ASCII output, a simultaneous neutral drawing sheet and templates containing circuit objects or
   additional schematic records. An empty Additional header is allowed.
2. Copy the template bytes unchanged as `templates/sheet.SchDot`. Every sheet references that portable
   relative name. Work only on caller-supplied bytes: no template is bundled with Fenolite.
3. Keep template record 0 and the original template records first, retaining their native coordinates,
   colors, strings, opaque properties and fonts. Insert record 39 immediately after record 0 and attach
   template graphic roots to it.
   Sheet parameters stay sheet parameters. Already-owned template children have their owner indices
   increased by one. Every owner precedes its children.
4. Append the generated circuit records, rebasing main-stream owners and extending the template font
   table with generated fonts. Remap FONTID and TEXTFONTID, including harness Additional records, whose
   owner indices are Additional-local. Preserve template Storage and other streams unchanged; reject
   colliding generated extra streams with actual template content.
5. Generated sheet parameters override a matching template parameter in place. Other template
   parameters remain unchanged. All files join the existing atomic build plan, and the template is a
   dependency, so changing it invalidates confirmation.
6. Evidence is INFERRED. Local readback verifies indices, fonts and embedded bytes, not the Altium UI.
   A caller's visual report is required before claiming its appearance is correct in Altium.

## Risks and scope

Unknown index-bearing constructs cannot be claimed universally supported. Rebase known template
owner indices and reject invalid owners, nested templates and circuit-bearing templates. Binary
records without property lists are refused. No fallback to flattening, no Altium automation and no
template data from private projects committed as tests. Authored tests exercise the generic format.
