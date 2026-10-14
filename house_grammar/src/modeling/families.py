"""Reference-inspired programs, independent of the number of street fronts.

All selections become explicit dataclass values before geometry generation.
"""
from dataclasses import replace
import numpy as np
from shapely.geometry import Polygon
from domain.models import Opening, FacadeMaterialRegion, FacadeProjection, MaterialSpecification

FAMILIES = ("quiet_house", "ribbon_windows", "balcony_apartments",
            "mixed_use", "workshop", "brick_courtyard")


def apply_family(spec, family):
    rng = np.random.default_rng(spec.seed)
    if family == "auto":
        candidates = FAMILIES if spec.height.floor_count <= 3 else FAMILIES[1:4]
        family = str(rng.choice(candidates))
    if family not in FAMILIES:
        raise ValueError(f"Unknown architectural family: {family}")
    parcel = Polygon(spec.parcel_xy, spec.parcel_holes)
    facades=[]
    for f in spec.facade_edges:
        if not f.is_front:
            facades.append(replace(f,ornamented=False,cladding="stucco"))
            continue
        width=f.width_m
        levels=f.floor_levels_m
        a=np.asarray(f.vertex_a)
        tangent=(np.asarray(f.vertex_b)-a)/width
        normal=np.array([tangent[1],-tangent[0]])
        ops=[]; regions=[]; projections=[]
        # Preserve tiny cadastral edges as blind piers.
        if width < 2.2:
            facades.append(replace(f,openings=(),ornamented=False,cladding="stucco",
                                  projections=(),material_regions=(),services=False))
            continue
        def feature(kind,u,v,w,h,d,mat="accent",border=.08):
            envelope=Polygon([a+tangent*x+normal*z for x,z in
                              [(u,0),(u+w,0),(u+w,d),(u,d)]])
            if w>0 and h>0 and parcel.covers(envelope) and v+h <= levels[-1]:
                projections.append(FacadeProjection(kind,u,v,w,h,d,mat,border,
                                                     source="family_rule"))
        bays=max(1,int(width/(3.8 if family=="ribbon_windows" else 3.1)))
        # A single rhythm per facade, repeated upstairs; base has its own use.
        pitch=(width-.5)/bays
        for floor,(z,znext) in enumerate(zip(levels[:-1],levels[1:])):
            fh=znext-z
            for bay in range(bays):
                left=.25+bay*pitch
                ww=pitch*(.85 if family=="ribbon_windows" else .70)
                u=left+(pitch-ww)/2
                v=z+.8; hh=min(1.65,fh-1.05)
                kind="window"; prefab="slim_window"
                grille=floor==0; columns=max(2,round(ww/.7)); rows=1
                if floor==0 and bay==0:
                    kind="door"; prefab=str(rng.choice(["wood_panel","metal_gate"])); ww=min(1.05,pitch-.24)
                    u=left+.06; v=.04; hh=min(2.25,fh-.3); grille=False
                if floor==0 and family in ("mixed_use","workshop"):
                    kind="gate" if family=="workshop" else ("door" if bay==0 else "window")
                    prefab="roller" if family=="workshop" else "storefront"
                    ww=pitch-.2; u=left+.1; v=.06; hh=min(2.35,fh-.42)
                    columns=2; grille=False
                if floor>0 and family=="balcony_apartments" and bay%2==0:
                    kind="balcony_window"; v=z+.16; hh=min(2.1,fh-.42)
                if family=="quiet_house" and floor>0:
                    ww=min(ww,1.45); u=left+(pitch-ww)/2; rows=2; grille=True
                
                if floor > 0 and kind == "window" and family != "balcony_apartments":
                    jitter = float(rng.uniform(-0.15, 0.15))
                    u = max(left + 0.05, min(left + pitch - ww - 0.05, u + jitter))
                
                ops.append(Opening(kind,u,v,ww,hh,frame_width_m=.028,recess_m=.12,
                                   prefab=prefab,curtain=float(rng.choice([.25,.55,.85])) if prefab=="slim_window" else 0,
                                   grille=grille,grille_pattern=str(rng.choice(["vertical","grid","diamond"])),
                                   mullion_columns=columns,mullion_rows=rows,
                                   balcony_depth_m=.65,source="family_rule"))
            if floor==0:
                regions.append(FacadeMaterialRegion(0,0,width,fh,"brick" if family=="brick_courtyard" else "plaster"))
            if family in ("ribbon_windows","mixed_use"):
                feature("ledge",.16,znext-.13,width-.32,.09,.16,"stone")
        if family in ("mixed_use","workshop"):
            # Sign substrate and relief lettering assembled by the signage prefab.
            sign_z=levels[1]-.33
            feature("panel",.25,sign_z,width-.5,.25,.07,"sign")
            if projections and projections[-1].material_slot=="sign":
                projections[-1]=replace(projections[-1],label="TALLER" if family=="workshop" else "TIENDA")
            # Thin corrugated shop awning, reserved above the shop opening.
            feature("canopy",.2,levels[1]-.40,width-.4,.035,.55,"roof")
        if family=="brick_courtyard":
            # Brick crown beneath the main roof; openings stop below it.
            regions.append(FacadeMaterialRegion(0,levels[-1]-.18,width,.18,"brick"))
        if family=="balcony_apartments" and len(levels)>2:
            # A vertical accent beside the openings, not pasted across glazing.
            regions.append(FacadeMaterialRegion(0,levels[1],.18,levels[-1]-levels[1],"accent"))
        if family in ("quiet_house","brick_courtyard"):
            door=ops[0]
            feature("canopy",max(.13,door.u_m-.08),door.v_m+door.height_m+.06,
                    door.width_m+.16,.07,.28,"accent")
        facades.append(replace(f,openings=tuple(ops),projections=tuple(projections),
                              material_regions=tuple(regions),ornamented=False,
                              services=False,cladding="stucco",ground_floor_material=None))
    palette=[(.83,.81,.70),(.67,.75,.77),(.76,.43,.32),(.77,.77,.59),(.89,.87,.81)]
    wall=palette[int(rng.integers(len(palette)))]
    existing=[replace(m,base_color_rgb=wall) if m.slot=="plaster" else m for m in spec.appearance.materials]
    existing += [MaterialSpecification("interior","interior",(.12,.105,.09),.95),
                 MaterialSpecification("curtain","fabric",(.78,.75,.65),.95),
                 MaterialSpecification("sign","paint",(.12,.29,.40),.65),
                 MaterialSpecification("frame","painted_aluminium",(.70,.70,.66),.38),
                 MaterialSpecification("metal","painted_steel",(.16,.17,.17),.5)]
    return replace(spec,facade_edges=tuple(facades),
                   appearance=replace(spec.appearance,materials=tuple(existing)),
                   roof=replace(spec.roof,terrace_room=family!="workshop",
                                water_tank=family in ("ribbon_windows","mixed_use","brick_courtyard"),
                                canopy=family in ("quiet_house","mixed_use","brick_courtyard")),
                   metadata={**spec.metadata,"architectural_family":family,"grammar_revision":4})
