# Explicit portable native project-template input

An authored strict import/build currently reports success and unexpressed=[] while
losing all five inter-sheet settings in a fresh output project. Original values
True/True/True/AUTH[/] become False/False/False/empty/empty. The original project
bytes remain unchanged, proving a real missing carrier rather than a source edit.
A separate public Royal replay also depends on unmanaged physical project knobs.

Add an explicit portable DSL request `design.kicad_project(path, sha256=...)`,
recorded only in DSL/build input state. The importer emits its checked original
project as a native sidecar and declares that input in generated Python. Build
uses the existing native project-update mechanism as an explicit baseline, then
applies typed managed settings and fresh file/root identities. No canonical field,
opaque model extension or output-directory seed is introduced.

This packet proposes the public name, precedence and strictness for coordinator
review; no implementation is authorized until task0.2 passes. It preserves native
project bytes/data as declared input and does not claim complete level6 semantic
coverage of every unmanaged rule.
