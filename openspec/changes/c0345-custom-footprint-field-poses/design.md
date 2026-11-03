# Explicit code requests, existing typed fields

Allow `Part.field` for an exactly named user property already declared on that
part, in addition to Reference/Value. Unknown and reserved fields remain refused.
No new model field or opaque carrier is introduced. The normal field merge
precedence remains unchanged.

The importer emits source custom-property placement/style through that public
API after placement. Board-frame anchors and angles use the existing KiCad
field helpers. Preserve hidden state, square font size, thickness, horizontal/
vertical justification, bold/italic/face and the side-relative silk/fab layer.
Before planning, refuse a source pose that this API cannot represent exactly
(including anisotropic size, unsupported/cross-side layers, or a rounded
anchor whose inverse does not recover the original local integer point).
Do not silently normalize any such pose or weaken level7, S or pixel tolerances.

Authored original controls exercise body rotations and hidden/visible custom
fields through actual import, reviewed replay, fresh build and full proof;
planted changes must still fail. Existing default example plans stay unchanged.
