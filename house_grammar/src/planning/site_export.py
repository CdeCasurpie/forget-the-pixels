"""Phase-5 GLB, ground plan and material/mesh audit."""
import json
from pathlib import Path

import numpy as np
import trimesh
from shapely.geometry import Point, shape
from shapely.geometry.polygon import orient
from shapely.strtree import STRtree

from planning.envelope_export import MATERIAL_COLORS, _render, render_elevation, solids as envelope_solids
from planning.layered_mesh import layered_mesh
from planning.massing import polygons


COLORS=dict(MATERIAL_COLORS,tile=(176,91,62,255),corrugated=(144,150,155,255))


class _EnvelopeView:
    def __init__(self, data):self.data=data
    def to_dict(self):return self.data


def _ramp_mesh(part):
    """Closed wedge whose top line climbs from the street to the floor datum."""
    polygon=orient(shape(part['geometry']));ring=list(polygon.exterior.coords)[:-1]
    if len(ring)!=4:raise ValueError('Ramp footprint must have four corners')
    axis=shape(part['axis']);rise=part['rise_m'];length=axis.length
    vertices=[(x,y,0.) for x,y in ring]+[
        (x,y,.02+(rise-.02)*axis.project(Point(x,y))/length) for x,y in ring]
    faces=[(0,2,1),(0,3,2),(4,5,6),(4,6,7)]
    for i in range(4):
        j=(i+1)%4
        faces.extend(((i,j,j+4),(i,j+4,i+4)))
    return trimesh.Trimesh(vertices=np.asarray(vertices),faces=np.asarray(faces),process=True)


def solids(plan):
    envelope_meshes,_=envelope_solids(_EnvelopeView(plan.envelope))
    meshes=list(envelope_meshes)
    for part in plan.parts:
        for index,poly in enumerate(polygons(shape(part['geometry']))):
            if part.get('mesh_kind')=='ramp':mesh=_ramp_mesh(part)
            else:mesh=layered_mesh([(poly,part['bottom_m'],part['top_m'])])
            name=part['id'] if not index else part['id']+f'/{index}'
            meshes.append((name,part['material'],mesh))
    parts=plan.envelope['parts']+plan.parts
    geometries=[shape(p['geometry']) for p in parts]
    tree=STRtree(geometries);overlap=0.;clashes=[]
    for i,part in enumerate(parts):
        for j in tree.query(geometries[i]):
            if j<=i:continue
            other=parts[j]
            if part['material']==other['material']:continue
            area=geometries[i].intersection(geometries[j]).area
            if area<1e-6:continue
            depth=min(part['top_m'],other['top_m'])-max(part['bottom_m'],other['bottom_m'])
            if depth<=1e-6:continue
            overlap+=area*depth
            clashes.append(dict(a=part['id'],b=other['id'],volume_m3=round(area*depth,6)))
    audit=dict(watertight=all(m.is_watertight and m.volume>0 for _,_,m in meshes),
               non_watertight=[name for name,_,m in meshes if not(m.is_watertight and m.volume>0)][:12],
               group_overlap_m3=overlap,group_overlap_pairs=clashes[:12])
    return meshes,audit


def render_ground(data, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(7.2,7.2))
    parcel=shape({'type':'Polygon','coordinates':[data['request']['context']['parcel']]})
    mass=data['envelope']['interior']['massing']
    for geometry,color in ((shape(mass['site']['free']),'#e9eddf'),
                           (shape(mass['site']['occupied']),'#aaada6')):
        for poly in polygons(geometry):
            x,y=poly.exterior.xy;ax.fill(x,y,facecolor=color,edgecolor='none')
    for route in data['routes']:
        for poly in polygons(shape(route['geometry'])):
            x,y=poly.exterior.xy;ax.fill(x,y,facecolor='#cbbb9a' if route['kind']=='pedestrian' else '#adb8bc',alpha=.9)
    for part in data['parts']:
        if part['kind'] not in ('fence_wall','fence_base','fence_post','gate_post','fence_rail','gate_leaf','gate_bar'):continue
        for poly in polygons(shape(part['geometry'])):
            x,y=poly.exterior.xy
            ax.fill(x,y,facecolor='#4a5356' if 'gate' in part['kind'] else '#777b77',edgecolor='none')
    for gate in data['gates']:
        line=shape(gate['geometry']);ax.plot(*line.xy,linewidth=3,
                                             color='#278566' if gate['kind']=='pedestrian' else '#386f9a')
    x,y=parcel.exterior.xy;ax.plot(x,y,'k--',linewidth=1)
    ax.set_aspect('equal');ax.autoscale_view();ax.set_title('Sitio — cerco, accesos y planta baja')
    ax.set_xlabel('X (m)');ax.set_ylabel('Y (m)');fig.tight_layout()
    fig.savefig(output,dpi=130);plt.close(fig)


def export_site(plan, output, preview=True):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    data=plan.to_dict()
    (output/'plan.json').write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n')
    meshes,audit=solids(plan)
    report=dict(version=plan.version,site_parts=len(plan.parts),
                building_parts=len(plan.envelope['parts']),fence=plan.fence,
                gates=plan.gates,accesses=plan.accesses,routes=plan.routes,
                decisions=plan.decisions,pending=plan.pending,checks=plan.checks,audit=audit)
    (output/'summary.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    scene=trimesh.Scene()
    for name,material,mesh in meshes:
        mesh.visual.face_colors=np.tile(np.asarray(COLORS.get(material,(200,200,200,255))),(len(mesh.faces),1))
        scene.add_geometry(mesh,node_name=name,geom_name=name)
    scene.apply_transform(trimesh.transformations.rotation_matrix(-np.pi/2,[1,0,0]))
    scene.export(output/'site.glb')
    if preview:
        _render(meshes,output/'preview.png',view=(27,-125))
        render_ground(data,output/'ground.png')
        fronts=plan.envelope['interior']['massing']['fronts']
        primary=max(fronts,key=lambda name:fronts[name]['length_m'])
        render_elevation(meshes,fronts[primary],output/'front.png')
    return report
