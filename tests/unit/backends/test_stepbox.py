# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The box of a STEP model (capability design-conversion, "Models of a KiCad board in an Altium target";
change c0449, task 2.1; ``docs/formats/step/part21.md``, "Box of a model").

The assembly below is authored for Fenolite from the entity structure of ISO 10303-21 and the AP214
entities (S-2082): a part in inches holding half a circle of radius one inch, placed in an assembly in
millimetres turned by 90 degrees about Z and moved by 10 mm along X."""

from __future__ import annotations

import pytest

from fenolite.backends import stepbox
from fenolite.backends.step import Prism, write_solids

MM = 1_000_000
HEAD = """ISO-10303-21;
HEADER;
FILE_DESCRIPTION((''),'2;1');
FILE_NAME('assembly.step','2026-11-06T00:00:00',(''),(''),'','','');
FILE_SCHEMA(('AUTOMOTIVE_DESIGN'));
ENDSEC;
DATA;
#1=( LENGTH_UNIT() NAMED_UNIT(*) SI_UNIT(.MILLI.,.METRE.) );
#2=LENGTH_MEASURE_WITH_UNIT(LENGTH_MEASURE(25.4),#1);
#3=DIMENSIONAL_EXPONENTS(1.,0.,0.,0.,0.,0.,0.);
#4=( CONVERSION_BASED_UNIT('INCH',#2) LENGTH_UNIT() NAMED_UNIT(#3) );
#5=( GEOMETRIC_REPRESENTATION_CONTEXT(3) GLOBAL_UNIT_ASSIGNED_CONTEXT((#4))
REPRESENTATION_CONTEXT('part','') );
#6=( GEOMETRIC_REPRESENTATION_CONTEXT(3) GLOBAL_UNIT_ASSIGNED_CONTEXT((#1))
REPRESENTATION_CONTEXT('asm','') );
#10=CARTESIAN_POINT('',(0.,0.,0.));
#11=DIRECTION('',(0.,0.,1.));
#12=DIRECTION('',(1.,0.,0.));
#13=AXIS2_PLACEMENT_3D('',#10,#11,#12);
#14=CIRCLE('',#13,1.);
#15=CARTESIAN_POINT('',(1.,0.,0.));
#16=CARTESIAN_POINT('',(-1.,0.,0.));
#17=VERTEX_POINT('',#15);
#18=VERTEX_POINT('',#16);
#19=EDGE_CURVE('',#17,#18,#14,.T.);
#20=SHAPE_REPRESENTATION('part',(#13,#19),#5);
#30=CARTESIAN_POINT('',(10.,0.,0.));
#31=DIRECTION('',(0.,1.,0.));
#32=AXIS2_PLACEMENT_3D('',#30,#11,#31);
#33=SHAPE_REPRESENTATION('asm',(#32),#6);
#40=PRODUCT('asm','asm','',());
#41=PRODUCT('part','part','',());
#42=PRODUCT_DEFINITION('asm','',#40,$);
#43=PRODUCT_DEFINITION('part','',#41,$);
#44=PRODUCT_DEFINITION_SHAPE('','',#42);
#45=SHAPE_DEFINITION_REPRESENTATION(#44,#33);
#46=PRODUCT_DEFINITION_SHAPE('','',#43);
#47=SHAPE_DEFINITION_REPRESENTATION(#46,#20);
#48=NEXT_ASSEMBLY_USAGE_OCCURRENCE('1','part','',#42,#43,$);
#49=PRODUCT_DEFINITION_SHAPE('','',#48);
"""
# rep_1 the part, transform_item_1 in its context (EXPRESS WR2), as most exporters write it
PART_FIRST = """#50=( REPRESENTATION_RELATIONSHIP('','',#20,#33)
REPRESENTATION_RELATIONSHIP_WITH_TRANSFORMATION(#51)
SHAPE_REPRESENTATION_RELATIONSHIP() );
#51=ITEM_DEFINED_TRANSFORMATION('','',#13,#32);
"""
# rep_1 the assembly: the pair the other way round, as some exporters write it
ASSEMBLY_FIRST = """#50=( REPRESENTATION_RELATIONSHIP('','',#33,#20)
REPRESENTATION_RELATIONSHIP_WITH_TRANSFORMATION(#51)
SHAPE_REPRESENTATION_RELATIONSHIP() );
#51=ITEM_DEFINED_TRANSFORMATION('','',#32,#13);
"""
USAGE = "#52=CONTEXT_DEPENDENT_SHAPE_REPRESENTATION(#50,#49);\n"
TAIL = "ENDSEC;\nEND-ISO-10303-21;\n"
PLACED = (-15_400_000, -25_400_000, 0, 10 * MM, 25_400_000, 0)
"""The half circle (x in [-1, 1] in, y in [0, 1] in) turned by 90 degrees and moved by 10 mm."""


def _assembly(relation: str, *, usage: bool = True) -> bytes:
    return (HEAD + relation + (USAGE if usage else "") + TAIL).encode("ascii")


def test_box_of_a_prism() -> None:
    ring = ((0, 0), (2 * MM, 0), (2 * MM, MM), (0, MM))
    data = write_solids("box", [Prism(ring, -MM // 2, 3 * MM // 2)])
    assert stepbox.model_box(data) == (0, 0, -MM // 2, 2 * MM, MM, 3 * MM // 2)


@pytest.mark.parametrize("relation", [PART_FIRST, ASSEMBLY_FIRST], ids=["part-first", "assembly-first"])
def test_box_of_an_assembly(relation: str) -> None:
    """Inches, the span of an arc, and the placement in both orders of the pair."""
    assert stepbox.model_box(_assembly(relation)) == PLACED


def test_box_reads_the_order_from_the_product_structure() -> None:
    """Without the usage that names the component, ``rep_1`` is taken as the component: the assembly-first
    pair then puts the part at the assembly's origin."""
    assert stepbox.model_box(_assembly(PART_FIRST, usage=False)) == PLACED
    assert stepbox.model_box(_assembly(ASSEMBLY_FIRST, usage=False)) != PLACED


@pytest.mark.parametrize(
    "data",
    [
        b"solid cube\nendsolid cube\n",
        b"",
        b"ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\n#1=CARTESIAN_POINT('',(0.,0.,0.));\nENDSEC;\n",
    ],
    ids=["stl", "empty", "no-edge"],
)
def test_box_of_no_geometry(data: bytes) -> None:
    assert stepbox.model_box(data) is None
