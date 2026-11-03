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
