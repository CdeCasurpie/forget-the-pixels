"""Metric cross sections for continuous perimeter sweeps (depth, elevation)."""
import math

# Outer contour, bottom to top, normalised by projection and height.
CORNICES = {
    'republicano': ((.22,0),(.22,.16),(.40,.16),(.40,.34),(.65,.55),
                    (.65,.68),(1.,.68),(1.,.84),(.88,.84),(.88,1)),
    'clasico': ((.25,0),(.25,.18),(.40,.18),(.48,.34),(.62,.49),
                (.78,.60),(.90,.66),(.90,.76),(1.,.76),(1.,1)),
    'barroco': ((.22,0),(.22,.12)) + tuple(
        (.25+.58*(i/20)+.10*math.sin(i/20*2*math.pi), .12+.65*i/20)
        for i in range(21)) + ((1.,.77),(1.,.9),(.92,.9),(.92,1)),
    'madera': ((.35,0),(.35,.40),(.65,.40),(.65,.72),(1.,.72),(1.,1)),
    'moderno': ((1.,0),(1.,1)),
}


def cornice_section(control, style):
    profile=style if control.profile=='auto' else control.profile
    if profile not in CORNICES:raise ValueError('Cornice auto requires an architectural style or explicit profile')
    # CCW section. Rear face overlaps the substrate by 2 mm.
    return ((-.002,0.),) + tuple((x*control.projection_m,z*control.height_m)
                                  for x,z in CORNICES[profile]) + ((-.002,control.height_m),)


def plinth_courses(control):
    """(bottom, top, depth, stagger). Joints leave a shallow continuous backing."""
    h,d=control.height_m,control.relief_m
    if d==0:return ()
    if control.design=='smooth':return ((0.,h,d,0),)
    if control.design=='stepped':
        return ((0.,h*.25,d,0),(h*.25,h*.85,d*.65,0),(h*.85,h,d*.85,0))
    rows=math.ceil(h/control.course_height_m)
    if rows>128:raise ValueError('Plinth exceeds course budget')
    return tuple((i*control.course_height_m+(control.joint_width_m/2 if i else 0),
                  min(h,(i+1)*control.course_height_m-control.joint_width_m/2),d,i%2)
                 for i in range(rows)
                 if min(h,(i+1)*control.course_height_m-control.joint_width_m/2)>i*control.course_height_m)
