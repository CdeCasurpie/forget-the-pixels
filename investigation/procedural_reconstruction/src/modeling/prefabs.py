"""Small architectural assemblies in facade metres. No random choices here."""
import numpy as np

from .detail import DEFAULT_BUDGET


def sign_letters(mb,a,t,n,feature):
    """Small vector-style sign alphabet; unsupported characters are rejected."""
    glyphs={
        "L":["100","100","100","100","111"],
        "O":["111","101","101","101","111"],
        "C":["111","100","100","100","111"],
        "A":["010","101","111","101","101"],
        "T":["111","010","010","010","010"],
        "E":["111","100","110","100","111"],
        "R":["110","101","110","101","101"],
        "I":["111","010","010","010","111"],
        "N":["101","111","111","111","101"],
        "D":["110","101","101","101","110"],
        " ":["000"]*5,
    }
    label=feature.label.upper()
    if any(c not in glyphs for c in label):
        raise ValueError("Sign glyph unavailable; supported: LOCAL TALLER TIENDA")
    unit=min(feature.width_m/(len(label)*4+2),feature.height_m/7)
    origin=feature.u_m+(feature.width_m-unit*(len(label)*4-1))/2
    for index,char in enumerate(label):
        for row,line in enumerate(glyphs[char]):
            for col,value in enumerate(line):
                if value=="1":
                    u=origin+(index*4+col)*unit
                    z=feature.v_m+(feature.height_m-5*unit)/2+(4-row)*unit
                    mb.box(a,t,n,u,u+unit*.88,z,z+unit*.88,feature.depth_m,
                           feature.depth_m+.006,"frame","sign_letter")


def build_opening(mb, a, t, n, op):
    allowed = {"slim_window", "wood_panel", "metal_gate", "roller", "storefront", "louver"}
    if op.prefab not in allowed or not 0 <= op.curtain <= 1:
        raise ValueError("Invalid opening prefab/curtain")
    if op.grille_pattern not in ("vertical", "grid", "diamond"):
        raise ValueError("Invalid grille pattern")
    budget = getattr(mb, "budget", DEFAULT_BUDGET)
    u,v,w,h = op.u_m,op.v_m,op.width_m,op.height_m
    f,r = min(op.frame_width_m,w/6,h/6),op.recess_m
    def b(x1,x2,z1,z2,d1,d2,mat,part):
        mb.box(a,t,n,x1,x2,z1,z2,d1,d2,mat,part)
    # Plaster reveals, then thin aluminium or wood frame; no exterior stone surround.
    for x in (u-f,u+w):
        b(x,x+f,v,v+h,-r,0,"plaster","opening_reveal")
    for x in (u,u+w-f):
        b(x,x+f,v,v+h,-r,-r+.035,"frame","slim_jamb")
    for z in (v,v+h-f):
        b(u+f,u+w-f,z,z+f,-r,-r+.035,"frame","slim_frame")
    if op.prefab in ("slim_window","storefront"):
        b(u+f,u+w-f,v+f,v+h-f,-r-.018,-r,"glass","glazing")
        # Backing and curtains provide depth behind glass, without a full interior.
        b(u+f,u+w-f,v+f,v+h-f,-r-.40,-r-.38,"interior","interior_backing")
        if op.curtain and budget.wants_curtains:
            span=(w-2*f)*op.curtain/2
            fold=budget.curtain_fold_m
            for left in (u+f,u+w-f-span):
                for x in np.arange(left,left+span,fold):
                    d=-r-.14+.012*np.cos((x-left)*2*np.pi/.11)
                    b(x,min(x+fold,left+span),v+f,v+h-f,d-.014,d,"curtain","curtain_fold")
        for j in range(1,max(1,op.mullion_columns)):
            x=u+w*j/op.mullion_columns
            b(x-.012,x+.012,v+f,v+h-f,-r-.008,-r+.035,"frame","slim_mullion")
        for j in range(1,max(1,op.mullion_rows)):
            z=v+h*j/op.mullion_rows
            b(u+f,u+w-f,z-.012,z+.012,-r-.008,-r+.035,"frame","slim_transom")
    elif op.prefab in ("roller","louver"):
        b(u+f,u+w-f,v+f,v+h-f,-r-.03,-r-.02,"metal","shutter_back")
        pitch=.085 if op.prefab=="roller" else .14
        for z in np.arange(v+f,v+h-f,pitch):
            b(u+f,u+w-f,z,min(z+pitch*.83,v+h-f),-r-.01,-r+.018,"metal",op.prefab+"_slat")
    else:
        mat="wood" if op.prefab=="wood_panel" else "metal"
        b(u+f,u+w-f,v+f,v+h-f,-r-.03,-r,mat,"door_leaf")
        if op.prefab=="wood_panel":
            for z in np.linspace(v+.18,v+h-.55,3):
                b(u+.12,u+w-.12,z,z+.34,-r,-r+.016,mat,"door_raised_panel")
        else:
            for x in np.arange(u+.12,u+w-.08,.18):
                b(x,x+.014,v+.06,v+h-.06,-r,-r+.018,mat,"gate_seam")
        b(u+w-.13,u+w-.105,v+.9,v+1.04,-r+.025,-r+.06,"metal","door_handle")
    if op.grille:
        def p(x,z):
            xy=a+t*x+n*.045
            return (*xy,z)
        for x in np.arange(u+.07,u+w-.03,budget.grille_spacing_m):
            mb.beam(p(x,v+.03),p(x,v+h-.03),.007,semantic="security_bar")
        for z in np.arange(v+.15,v+h-.03,.35 if op.grille_pattern=="grid" else .8):
            mb.beam(p(u+.03,z),p(u+w-.03,z),.009,semantic="security_crossbar")
        if op.grille_pattern=="diamond":
            for x in np.arange(u+.04,u+w-.27,.28):
                for z in np.arange(v+.08,v+h-.43,.42):
                    for start,end in [((x,z+.2),(x+.13,z+.4)),((x+.13,z+.4),(x+.26,z+.2)),
                                      ((x+.26,z+.2),(x+.13,z)),((x+.13,z),(x,z+.2))]:
                        mb.beam(p(*start),p(*end),.005,semantic="grille_diamond")
