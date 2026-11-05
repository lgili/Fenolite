# c0387: measure the Altium body records that stay declared

## Why

c0378 asked for kit measurements of the component bodies that the Altium adapter keeps with unknown
heights (`backends/altium/adapter/bodies.py`, `altium.import.body-unknown`): a `BODYPROJECTION` that
differs from the component's side or is neither 0 nor 1, a `MODEL.MODELTYPE` other than 0 and 1, and
overall or standoff heights that are not lengths or are reversed. No kit file measures them. The public
corpus proves only the cases already converted: projection 0 on top components and 1 on bottom ones
(`docs/formats/altium/pcb-bodies.md`, CORPUS-VERIFIED) and model types 0 and 1. c0378 tasks 2.1 and 2.2
moved here on 2026-11-04 because nothing more could be proved by their deadline.

## What Changes

- Author kit cases for the maintainer's Altium run: a body flipped to the other side of its component,
  each model type the user interface offers, and heights at the limits the interface accepts; save them
  and read them with Fenolite's own reader.
- Record each measured fact in `pcb-bodies.md` with its source and label, and convert only what a saved
  file proves; every other body stays a declared `altium.import.body-unknown` with its heights unknown.

## Impact

Altium body adapter, `docs/formats/altium/pcb-bodies.md`, the verification kit; no public name changes.
