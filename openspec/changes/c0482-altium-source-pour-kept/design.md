# Design: c0482

## D1 All or nothing

Polygons pour in order, and a later polygon's copper depends on the earlier ones. A mix of kept and
computed polygons would need the engine to take a kept polygon's regions as given. The writer therefore
keeps the source's pour only when every polygon has one. Otherwise it computes all of them, as before.

## D2 Records as read

A region record is written as read, except for its prefix's polygon index (bytes 5 and 6 of the body;
`pcbrecords.prefix`). Its vertices are doubles in file units. Taking them through the model's integer
nanometres would round some of them.

## D3 Match by vertices, net and layer

The KiCad zone uuid changes when a script is built, so the key is the polygon's own data:
- its vertices as read, exact fractions of the file unit;
- its net's name;
- its record's `LAYER` text.

A written polygon whose vertices differ (an edited outline) or whose net differs finds no pour. One
outline and net can be poured on two layers, so the layer is part of the key.

## D4 The copper check against the source's own

The written document is read back and checked as a computed pour is (`pour.check_pour`). On the
maintainer's board, the source's own saved pour fails that check for 10 of its 28 polygons, and the
written document fails it for the same 10. Either Fenolite's check is stricter than Altium's, or the
source was not poured again after an edit. The carrier records the source's result per polygon. A written
polygon that fails is accepted only when its source failed too, so an edit that brings new copper into a
kept pour makes the writer compute the pour.

shortcut: a polygon that failed in the source is not judged again. A later edit that adds a second fault
to it is not caught. Comparing the faults themselves would close that.
