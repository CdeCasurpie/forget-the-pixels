"""Phase 4 constructive export: solids, drawings and GLB.

Cada sólido se exporta como prisma cerrado e independiente (sin unión
booleana): las caras en contacto entre piezas quedan ocultas y el audit
verifica estanqueidad por pieza y solapes de volumen entre materiales. Las
elevaciones son proyecciones ortográficas de la malla real, no esquemas.
"""
import json
from pathlib import Path

import numpy as np
import trimesh
from shapely.geometry import shape
from shapely.strtree import STRtree

from planning.layered_mesh import layered_mesh
from planning.massing import polygons

MATERIAL_COLORS={
    'plaster':(226,220,208,255),
    'concrete':(198,198,196,255),
    'stone':(184,176,162,255),
    'wood':(172,126,80,255),
    'metal':(118,124,132,255),
    'pvc':(242,242,242,255),
    'glass':(176,206,218,255),
}
ROOM_COLORS={
    'circulation':(206,209,214),'stairs':(141,153,174),'bathroom':(127,179,213),
    'bedroom':(242,215,164),'living':(205,224,182),'kitchen_dining':(240,178,122),
    'service':(213,198,224),'garage':(176,176,176),'shop':(245,183,177),
    'open_ground':(232,240,216),'unassigned':(238,238,238),
}


def solids(plan):
    """One closed prism per part; audit overlap between different materials."""
    data=plan.to_dict()
    meshes=[]
    for part in data['parts']:
        for i,poly in enumerate(polygons(shape(part['geometry']))):
            mesh=layered_mesh([(poly,part['bottom_m'],part['top_m'])])
            meshes.append((part['id'] if not i else part['id']+f'/{i}',part['material'],mesh))
    overlap=0.;clashes=[]
    parts=data['parts'];tree=STRtree([shape(p['geometry']) for p in parts])
    for i,part in enumerate(parts):
        polygon=shape(part['geometry'])
        for j in tree.query(polygon):
            if j<=i:continue
            other=parts[j]
            if other['material']==part['material']:continue
            area=polygon.intersection(shape(other['geometry'])).area
            if area<1e-6:continue
            depth=min(part['top_m'],other['top_m'])-max(part['bottom_m'],other['bottom_m'])
            if depth<1e-6:continue
            overlap+=area*depth;clashes.append(dict(a=part['id'],b=other['id'],volume_m3=round(area*depth,6)))
    materials={}
    for part in parts:materials[part['material']]=materials.get(part['material'],0)+1
    checks={'group_overlap_m3':overlap,'group_overlap_pairs':clashes[:12],
            'watertight':all(mesh.is_watertight and mesh.volume>0 for _,_,mesh in meshes),
            'non_watertight':[name for name,_,mesh in meshes if not (mesh.is_watertight and mesh.volume>0)][:12],
            'materials':materials}
    return meshes,checks


def summary(plan):
    data=plan.to_dict()
    by_kind={};by_material={}
    for part in data['parts']:
        by_kind[part['kind']]=by_kind.get(part['kind'],0)+1
        by_material[part['material']]=by_material.get(part['material'],0)+1
    openings=data['openings']
    windows=[o for o in openings if o['kind']=='window']
    doors=[o for o in openings if o['kind']!='window']
    return dict(version=data['version'],parts=len(data['parts']),by_kind=by_kind,by_material=by_material,
                openings=len(openings),windows=len(windows),doors=len(doors),
                explicit_windows=sum(o['source']=='explicit' for o in windows),
                completed_windows=sum(o['source']=='completion' for o in windows),
                mechanisms={m:sum(o['mechanism']==m for o in windows) for m in
                            sorted({o['mechanism'] for o in windows})},
                styles={s:sum(o['style']==s for o in openings) for s in sorted({o['style'] for o in openings})},
                useful_heights=[round(data['request']['context']['levels_m'][f+1]-data['request']['context']['levels_m'][f]-.18,3)
                                for f in range(len(data['request']['context']['levels_m'])-1)],
                decisions=data['decisions'],pending=data.get('pending',[]),checks=data['checks'],
                 scope=('exterior envelope with stair reservation; no room partitions'
                        if 'interior' not in data else
                        'constructive envelope with metric apertures, joinery and slabs; no finishes, furniture or roof'))


def export_envelope(plan, output, preview=True):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    data=plan.to_dict()
    (output/'plan.json').write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n')
    report=summary(plan)
    meshes,audit=solids(plan)
    walls=None;catalogue=None;site=None;crowns=None;pilasters=None;roofs=None
    if 'interior' not in data:
        from planning.catalogue_openings import (materialize_openings,
                                                materialize_contoured_walls, mesh_items)
        walls=materialize_contoured_walls(plan)
        meshes+=list(mesh_items(walls, prefix='contoured_wall'))
        report['contoured_walls']=dict(faces=len(walls.faces), hosts=len(data.get('contoured_walls', ())))
        catalogue=materialize_openings(plan)
        meshes+=list(mesh_items(catalogue))
        report['catalogue_openings']=dict(
            faces=len(catalogue.faces),
            semantics=sorted({part['name'] for part in catalogue.parts}))
        from planning.site_catalogue import materialize_site, mesh_items as site_items
        site=materialize_site(plan)
        meshes+=list(site_items(site, prefix='site'))
        report['site']=dict(faces=len(site.faces),
                            semantics=sorted({part['name'] for part in site.parts}))
        from planning.crown_catalogue import materialize_crowns, mesh_items as crown_items
        crowns=materialize_crowns(plan)
        meshes+=list(crown_items(crowns, prefix='crown'))
        report['crowns']=dict(count=len(data.get('crowns', ())), faces=len(crowns.faces),
                              semantics=sorted({part['name'] for part in crowns.parts}))
        from planning.pilaster_catalogue import materialize_pilasters, mesh_items as pilaster_items
        pilasters=materialize_pilasters(plan)
        meshes+=list(pilaster_items(pilasters, prefix='pilaster'))
        report['pilasters']=dict(count=len(data.get('pilasters', ())), faces=len(pilasters.faces),
                                 semantics=sorted({part['name'] for part in pilasters.parts}))
        from planning.roof_catalogue import materialize_roofs, mesh_items as roof_items
        roofs=materialize_roofs(plan)
        meshes+=list(roof_items(roofs, prefix='roof'))
        report['roofs']=dict(count=len(data.get('roofs', ())), faces=len(roofs.faces),
                             semantics=sorted({part['name'] for part in roofs.parts}))
    report['audit']=audit
    (output/'summary.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    scene=trimesh.Scene()
    palette=dict(MATERIAL_COLORS)
    for model in (walls, catalogue, site, crowns, pilasters, roofs):
        if model is None:
            continue
        for material in model.materials:
            palette[material['name']]=tuple(round(255*c) for c in material['color'])+(255,)
    for name,material,mesh in meshes:
        mesh.visual.face_colors=np.tile(np.asarray(palette.get(material,(200,200,200,255))),(len(mesh.faces),1))
        scene.add_geometry(mesh,node_name=name,geom_name=name)
    scene.apply_transform(trimesh.transformations.rotation_matrix(-np.pi/2,[1,0,0]))
    scene.export(output/'envelope.glb')
    if preview:
        _render(meshes,output/'preview.png',view=(27,-125),palette=palette)
        render_drawings(data,meshes,output,palette=palette)
    return report


def _render(meshes, output, view, direction=None, ortho=False, palette=None):
    """Depth-tested raster preview.

    Replaces the matplotlib 3D collection, whose per-triangle paint order and
    camera-independent culling produced diagonal streaks and floating panels.
    See ``modeling/software_render.py`` for the rasteriser and its rationale.
    """
    from modeling.software_render import render
    render(meshes,output,view=view,direction=direction,ortho=ortho,palette=palette or MATERIAL_COLORS)


def render_drawings(data, meshes, output, palette=None):
    if 'interior' in data:
        render_plan(data,output/'floors')
        fronts=data['interior']['massing']['fronts']
    else:
        # The default route has no room diagram to draw. Show the facade only.
        fronts=data['massing']['fronts']
    primary=max(fronts,key=lambda name:fronts[name]['length_m'])
    render_elevation(meshes,fronts[primary],output/'front.png',palette=palette)
    directory=output/'elevations';directory.mkdir(parents=True,exist_ok=True)
    for name,frame in sorted(fronts.items()):
        render_elevation(meshes,frame,directory/f'{name}.png',palette=palette)


def render_elevation(meshes, frame, output, palette=None):
    inward=np.asarray(frame['inward'],dtype=float)
    direction=np.array([-inward[0],-inward[1],0.])
    _render(meshes,output,view=(0,0),direction=direction/np.linalg.norm(direction),ortho=True,palette=palette)


def render_plan(data, floors_dir):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.path import Path as PlotPath
    from matplotlib.patches import PathPatch
    from shapely.geometry.polygon import orient
    from shapely.geometry import LineString

    def ring(ax,poly,**kwargs):
        poly=orient(poly);verts=[];codes=[]
        for item in [poly.exterior,*poly.interiors]:
            points=list(item.coords);verts.extend(points)
            codes.extend([PlotPath.MOVETO]+[PlotPath.LINETO]*(len(points)-2)+[PlotPath.CLOSEPOLY])
        ax.add_patch(PathPatch(PlotPath(verts,codes),**kwargs))

    floors_dir=Path(floors_dir);floors_dir.mkdir(parents=True,exist_ok=True)
    for row in data['interior']['floors']:
        floor=row['floor']
        fig=plt.figure(figsize=(6.4,6.4));ax=fig.add_subplot(1,1,1)
        ax.plot(*shape({'type':'Polygon','coordinates':[data['request']['context']['parcel']]}).exterior.xy,
                color='#666666',linestyle='--',linewidth=1)
        for room in row['rooms']:
            color=[c/255 for c in ROOM_COLORS.get(room['kind'],(238,238,238))]+[.7]
            for poly in polygons(shape(room['usable_geometry'])):
                ring(ax,poly,facecolor=color,edgecolor='none')
        for part in data['parts']:
            if part['floor']!=floor or part['kind'] not in ('wall','partition'):continue
            for poly in polygons(shape(part['geometry'])):
                ring(ax,poly,facecolor=(.35,.33,.31,.92),edgecolor='none')
        for poly in polygons(shape(row['service_shaft'])):
            ring(ax,poly,facecolor=(.3,.3,.3,.95),edgecolor='none')
        for opening in data['openings']:
            if opening['floor']!=floor or opening['kind']!='window':continue
            line=shape(opening['geometry']);x,y=line.xy
            style='-' if opening['source']=='explicit' else (0,(3,2))
            ax.plot(x,y,color='#1f6feb',linewidth=3.2,linestyle=style,solid_capstyle='butt')
        for opening in data['openings']:
            if opening['floor']!=floor or opening['kind']=='window':continue
            line=shape(opening['geometry']);x,y=line.xy
            color='#2e8b57' if opening['kind'] in ('entrance','vehicle_entry','exterior_space') else '#b03a2e'
            ax.plot(x,y,color=color,linewidth=2.6,solid_capstyle='butt')
        levels=data['request']['context']['levels_m']
        ax.set_aspect('equal');ax.autoscale_view()
        ax.set_title(f"Piso {floor} — altura útil {levels[floor]-levels[floor-1]-.18:.2f} m")
        ax.set_xlabel('X (m)')
        fig.tight_layout();fig.savefig(floors_dir/f'floor{floor}.png',dpi=130);plt.close(fig)
