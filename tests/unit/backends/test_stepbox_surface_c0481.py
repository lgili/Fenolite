# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The box of a STEP surface model (change c0481; ``docs/formats/step/part21.md``, "Box of a model"): a
representation that holds bounded surfaces and no edge is measured by its trimmed curves.

The model below is authored for Fenolite from the entities of ISO 10303-42 (S-2082): in millimetres with
angles in degrees, a line from (0, 0, 0) along +Y trimmed by the parameters 0 and 1 of a vector of length
5, and half a circle of radius 2 about (0, 5, 0) in the XY plane, trimmed from 0 to 180 degrees."""

from __future__ import annotations

from fenolite.backends import stepbox

MM = 1_000_000
SURFACE = b"""ISO-10303-21;
HEADER;
FILE_DESCRIPTION((''),'2;1');
FILE_NAME('surface.step','2026-11-11T00:00:00',(''),(''),'','','');
FILE_SCHEMA(('CONFIG_CONTROL_DESIGN'));
ENDSEC;
DATA;
#1=CARTESIAN_POINT('',(0.,0.,0.));
#2=DIRECTION('',(0.,1.,0.));
#3=VECTOR('',#2,5.);
#4=LINE('',#1,#3);
#5=TRIMMED_CURVE('',#4,(0.),(1.),.T.,.UNSPECIFIED.);
#6=CARTESIAN_POINT('',(0.,5.,0.));
#7=DIRECTION('',(0.,0.,1.));
#8=DIRECTION('',(1.,0.,0.));
#9=AXIS2_PLACEMENT_3D('',#6,#7,#8);
#10=CIRCLE('',#9,2.);
#11=TRIMMED_CURVE('',#10,(PARAMETER_VALUE(0.)),(180.),.T.,.UNSPECIFIED.);
#12=COMPOSITE_CURVE_SEGMENT(.CONTINUOUS.,.T.,#5);
#13=COMPOSITE_CURVE_SEGMENT(.CONTINUOUS.,.T.,#11);
#14=BOUNDARY_CURVE('',(#12,#13),.F.);
#15=GEOMETRIC_SET('',(#14));
#20=(LENGTH_UNIT()NAMED_UNIT(*)SI_UNIT(.MILLI.,.METRE.));
#21=(NAMED_UNIT(*)PLANE_ANGLE_UNIT()SI_UNIT($,.RADIAN.));
#22=PLANE_ANGLE_MEASURE_WITH_UNIT(PLANE_ANGLE_MEASURE(1.745329251994E-2),#21);
#23=DIMENSIONAL_EXPONENTS(0.,0.,0.,0.,0.,0.,0.);
#24=(CONVERSION_BASED_UNIT('DEGREE',#22)NAMED_UNIT(#23)PLANE_ANGLE_UNIT());
#25=(GEOMETRIC_REPRESENTATION_CONTEXT(3)GLOBAL_UNIT_ASSIGNED_CONTEXT((#20,#24))
REPRESENTATION_CONTEXT('',''));
#26=GEOMETRICALLY_BOUNDED_SURFACE_SHAPE_REPRESENTATION('',(#15),#25);
ENDSEC;
END-ISO-10303-21;
"""


def test_box_of_a_surface_model() -> None:
    """The line gives (0, 0)–(0, 5); the half circle above it reaches x = ±2 and y = 7."""
    assert stepbox.model_box(SURFACE) == (-2 * MM, 0, 0, 2 * MM, 7 * MM, 0)


def test_angles_in_radians_by_default() -> None:
    """A quarter circle trimmed at 90: in degrees it stays at x >= 0; without a plane angle unit the trims
    are radians, and 90 radians (90 - 28 pi, about 116.6 degrees) ends at x = 2 cos(90 - 28 pi), which is
    -0.896147 mm."""
    quarter = SURFACE.replace(b"(180.)", b"(90.)")
    assert stepbox.model_box(quarter) == (0, 0, 0, 2 * MM, 7 * MM, 0)
    radians = quarter.replace(
        b"GLOBAL_UNIT_ASSIGNED_CONTEXT((#20,#24))", b"GLOBAL_UNIT_ASSIGNED_CONTEXT((#20))"
    )
    box = stepbox.model_box(radians)
    assert box is not None and box[0] == -896_147 and box[3:] == (2 * MM, 7 * MM, 0)


def test_edges_win_over_trimmed_curves() -> None:
    """A representation that reaches an edge is measured by its edges alone, as before."""
    edge = SURFACE.replace(
        b"#15=GEOMETRIC_SET('',(#14));",
        b"#15=GEOMETRIC_SET('',(#14,#30));\n#30=EDGE_CURVE('',#31,#32,#4,.T.);\n"
        b"#31=VERTEX_POINT('',#1);\n#32=VERTEX_POINT('',#33);\n#33=CARTESIAN_POINT('',(0.,1.,0.));",
    )
    assert stepbox.model_box(edge) == (0, 0, 0, 0, 1 * MM, 0)
