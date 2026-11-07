# Design

A digest-bound native project may name supported relative .kicad_wks resources
through its two existing native page-layout pointers. Resolve only those exact
names beside the declared project; reject unsafe names, symlinks, missing files,
invalid UTF-8, wrong/future worksheet kinds and unsupported resources. Every
consumed resource is an explicit input hash/readset dependency. Preserve its raw
bytes and exact output-relative name, without rewriting either native pointer.
No ambient project, parent directory, search path, official library or arbitrary
JSON string is discovered. Case collisions and output collisions refuse.

Import records every resource in its original source input/provenance list,
emits it next to native/project.kicad_pro, and keeps both project scopes intact.
The build's checked resource bundle is threaded consistently through the existing
build boundary. Typed design.sheet remains authoritative: its existing explicit
managed frame overrides both scopes and does not require obsolete native resources.
Unrequested builds and all unrelated native/template guards retain their bytes.

Coordinator review 2026-11-03: approved this narrow transitive bundle after actual
Interf failure and peer review with the library owner. Global design.sheet is
rejected as a workaround because it changes the schematic frame. The public WKS
already appears in the corpus manifest as kicad-demo-10-0-6-wks-01; public CAD stays
external. No native comparison tolerance, evidence promotion or acceptance waiver.

## Native scope evidence controls

Task3.1 uses the existing independently authored two-sheet/resource helper,
with PCB-only, schematic-only, and two distinct resource payloads. Import and
build use reviewed plans. Export both original and generated PCB/schematic SVG
with the installed native9/10 process, using project declarations only (never
--drawing-sheet). Assert actual AUTHORED text presence and absence per scope,
preserve every pre-existing input hash and report tool/output hashes. Public
Interf is cloned externally and receives only its already manifested worksheet;
all nine strict operators must be equal without accepted findings. No runtime
change or retained public CAD is authorized by this evidence task.

### Necessary root-alias coordinate consistency follow-up

A caller may address a project through a root directory alias. Canonical containment protects the read boundary, while returned resource paths retain the caller’s lexical project-parent coordinate for Source.folder and declared input hashes. Interior resource-component symlinks remain refused. Canonical ReadSide board/project traces are relativized against the canonical original root before merging into portable proof keys; lexical original input dependencies remain intact so rebinding a root alias to changed board/resource bytes invalidates reviewed plans. This fixes path-coordinate consistency only; it adds no ambient search or broader resource acceptance.
