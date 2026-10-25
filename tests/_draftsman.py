# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""An Altium Draftsman document authored for Fenolite (change c0180): element names from
``docs/formats/altium/draftsman.md``, "Drawing geometry", values of the tests, stored in one chunk of flag 0.
"""

from __future__ import annotations

from fenolite.backends.altium.read.draftsman import NAMESPACE


def pt(name: str, x: float, y: float) -> str:
    return f"<{name}><X>{x}</X><Y>{y}</Y></{name}>"


def segment(kind: str, x: float, y: float, extra: str = "") -> str:
    return f"<Segment><Kind>{kind}</Kind>{pt('Point', x, y)}{extra}</Segment>"


ARC = pt("Center", 48, 96) + "<Radius>48</Radius><Angle1>0</Angle1><Angle2>180</Angle2>"
OUTLINE = (
    segment("Line", 0, 0) + segment("Line", 96, 0) + segment("Arc", 96, 96, ARC) + segment("Line", 0, 96)
)
BODY = segment("Line", -4, -2) + segment("Line", 4, -2) + segment("Line", 4, 2) + segment("Line", -4, 2)


def component(ref: str, side: str, rotation: float) -> str:
    return (
        f"<Component><Designator>{ref}</Designator><Comment>10k</Comment><BoardSide>{side}</BoardSide>"
        f"{pt('Location', 50, 50)}<Rotation>{rotation}</Rotation></Component>"
    )


PARTS = component("R1", "Top", 90) + component("R2", "Bottom", 0) + component("R3", "Bottom", 90)

DOCUMENT = f"""<Document xmlns="{NAMESPACE}" xmlns:i="http://www.w3.org/2001/XMLSchema-instance">\
<Id>0</Id><FormatVersion>22</FormatVersion><IsPanel>false</IsPanel><MeasurementSystem>Metric</MeasurementSystem>\
<Pages><Page><Id>1</Id><Items>\
<Item i:type="Text"><Id>2</Id><Rect><X>10</X><Y>20</Y><Width>100</Width><Height>12</Height></Rect>\
<Text>=Revision</Text><FontStyleId>f1</FontStyleId><HorizontalAlignment>Center</HorizontalAlignment></Item>\
<Item i:type="BoardAssemblyViewData"><Id>3</Id>{pt("Location", 100, 200)}\
<Scale><Denominator>2</Denominator><Numenator>1</Numenator></Scale><UseCustomScale>false</UseCustomScale>\
<Title>TOP</Title><ViewSide>Bottom</ViewSide></Item>\
<Item i:type="Callout"><Id>4</Id></Item>\
</Items><Margin><Bottom>4</Bottom><Left>1</Left><Right>3</Right><Top>2</Top></Margin>\
<ShowZones>true</ShowZones><HorizontalZoneCount>6</HorizontalZoneCount><VerticalZoneCount>4</VerticalZoneCount>\
<Size><Height>793.7</Height><Width>1122.5</Width></Size></Page></Pages>\
<FontStyles><FontStyle><Id>f1</Id><FamilyName>Arial</FamilyName><Size>8</Size></FontStyle></FontStyles>\
<LineStyles><LineStyle><Id>l1</Id><Color><A>255</A><B>0</B><G>0</G><R>255</R></Color>\
<Thickness>1.5</Thickness></LineStyle></LineStyles>\
<Parameters><DrawingDocumentParameterData><Name>Revision</Name><Value>B</Value></DrawingDocumentParameterData>\
</Parameters>\
<BoardAssemblyInformation><BoardOutline><Segments>{OUTLINE}</Segments></BoardOutline>\
<BoardOutlineBounds><Height>144</Height><Width>96</Width><X>0</X><Y>0</Y></BoardOutlineBounds>\
<BoardThickness>6</BoardThickness><ComponentTypes><ComponentType>\
<AssemblyDrawing><Contour><Segments>{BODY}</Segments></Contour></AssemblyDrawing>\
<TopLayerPads><Pad>{pt("CenterPoint", 10, 5)}</Pad></TopLayerPads>\
<Components>{PARTS}</Components>\
</ComponentType></ComponentTypes>\
<Holes><Hole>{pt("CenterPoint", 20, 20)}<HoleSize>3.5</HoleSize><Plated>true</Plated></Hole></Holes>\
</BoardAssemblyInformation></Document>""".encode()


def stored(text: bytes) -> bytes:
    """One chunk of flag 0: the flag, the length in the 7-bit form, the bytes."""
    out, value = bytearray([0]), len(text)
    while True:
        out.append((value & 0x7F) | (0x80 if value > 0x7F else 0))
        value >>= 7
        if not value:
            return bytes(out) + text
