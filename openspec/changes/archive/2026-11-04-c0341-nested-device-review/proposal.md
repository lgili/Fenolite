# Resolve dependencies when reviewing a nested library device

A direct `library review .../devices/cc0/Namespace/Name/record.toml`
cannot find sibling symbol/footprint records although checking the library root
can. Resolve the enclosing library tree only for a valid, matching item manifest.
Keep the existing shallow catalog layout and exact-content review protocol.

No approval is inferred, no finding is waived, and no source payload is added.
