"""Diagnostic massing solids and plots. Not the detailed building materializer."""
import json
from pathlib import Path

import numpy as np
import trimesh
from shapely.geometry import shape

from planning.massing import polygons


COLORS=((208,171,129,255),(129,173,192,255),(184,190,142,255),(180,149,184,255))


def solids(plan):
    bodies=sorted({s['body'] for s in plan.storeys})
    meshes=[]
    for s in plan.storeys:
        bottom=s['bottom_m'] if s['kind']=='enclosed' else s['top_m']-.18
        for i,poly in enumerate(polygons(shape(s['geometry']))):
            mesh=trimesh.creation.extrude_polygon(poly,s['top_m']-bottom,engine='earcut')
            mesh.apply_translation([0,0,bottom])
            color=np.array(COLORS[bodies.index(s['body'])%len(COLORS)])
            color[:3]=np.clip(color[:3]*(1-.045*(s['floor']-1)),0,255)
            mesh.visual.face_colors=color
            meshes.append((s['id']+f'/{i}',mesh))
    for s in plan.supports:
        if s['kind']=='cantilever':continue  # already part of the mass
        for i,poly in enumerate(polygons(shape(s['geometry']))):
            mesh=trimesh.creation.extrude_polygon(poly,s['top_m']-s['bottom_m'],engine='earcut')
            mesh.apply_translation([0,0,s['bottom_m']]);mesh.visual.face_colors=[140,145,150,255]
            meshes.append((s['id']+f'/{i}',mesh))
    return meshes


def export_plan(plan, output, preview=True):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    (output/'plan.json').write_text(json.dumps(plan.to_dict(),indent=2,ensure_ascii=False)+'\n')
    meshes=solids(plan)
    scene=trimesh.Scene()
    for name,mesh in meshes:scene.add_geometry(mesh,node_name=name,geom_name=name)
    # Match glTF's Y-up convention, retaining Z-up in plan.json and plots.
    scene.apply_transform(trimesh.transformations.rotation_matrix(-np.pi/2,[1,0,0]))
    scene.export(output/'massing.glb')
    report={'components':len(meshes),'vertices':sum(len(m.vertices) for _,m in meshes),
            'triangles':sum(len(m.faces) for _,m in meshes),
            'all_components_watertight':all(m.is_watertight for _,m in meshes),
            'all_components_positive_volume':all(m.volume>0 for _,m in meshes),
            'all_components_winding_consistent':all(m.is_winding_consistent for _,m in meshes),
            'checks':plan.checks,'pending':plan.pending,
            'scope':'solid massing study, not a detailed or boolean-unified building'}
    (output/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    if preview:render(plan,meshes,output/'preview.png')
    return report


def render(plan, meshes, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.path import Path as PlotPath
    from matplotlib.patches import PathPatch
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    from shapely.geometry.polygon import orient
    floors=sorted({s['floor'] for s in plan.storeys})
    fig=plt.figure(figsize=(4*(len(floors)+1),5))
    parcel=shape({'type':'Polygon','coordinates':[plan.request['context']['parcel']]})
    bodies=sorted({s['body'] for s in plan.storeys})
    for idx,floor in enumerate(floors,1):
        ax=fig.add_subplot(1,len(floors)+1,idx)
        x,y=parcel.exterior.xy;ax.plot(x,y,color='#555555',linestyle='--')
        for row in plan.storeys:
            if row['floor']!=floor:continue
            color=np.array(COLORS[bodies.index(row['body'])%len(COLORS)])/255
            for poly in polygons(shape(row['geometry'])):
                poly=orient(poly)
                verts=[];codes=[]
                for ring in [poly.exterior,*poly.interiors]:
                    points=list(ring.coords);verts.extend(points)
                    codes.extend([PlotPath.MOVETO]+[PlotPath.LINETO]*(len(points)-2)+[PlotPath.CLOSEPOLY])
                ax.add_patch(PathPatch(PlotPath(verts,codes),facecolor=color,edgecolor='#444444',
                                       alpha=.35 if row['kind']=='open' else .9))
                point=poly.representative_point();ax.text(point.x,point.y,row['body'],ha='center',fontsize=8)
        for support in plan.supports:
            if support['kind']=='column' and abs(support['bottom_m']-plan.request['context']['levels_m'][floor-1])<1e-6:
                for poly in polygons(shape(support['geometry'])):
                    x,y=poly.exterior.xy;ax.fill(x,y,color='#333333')
        for name,frame in plan.fronts.items():
            a=np.array(frame['origin']);t=np.array(frame['right']);n=np.array(frame['inward'])
            p=a+t*frame['length_m']/2
            ax.text(*(p-n*.7),name,ha='center',color='#315e99')
        ax.set_aspect('equal');ax.autoscale_view();ax.set_title(f'Piso {floor}');ax.set_xlabel('X (m)')
    ax=fig.add_subplot(1,len(floors)+1,len(floors)+1,projection='3d')
    triangles=[];colors=[]
    for _,mesh in meshes:
        light=np.array([-1.,-2.,3.]);light/=np.linalg.norm(light)
        rgba=mesh.visual.face_colors.astype(float)/255
        rgba[:,:3]*=(.65+.35*np.maximum(0,mesh.face_normals@light))[:,None]
        triangles.extend(mesh.triangles);colors.extend(rgba)
    # One collection sorts faces globally; one per storey can paint a hidden
    # rear triangle over a front wall and misrepresent the solid geometry.
    ax.add_collection3d(Poly3DCollection(np.asarray(triangles),facecolors=np.asarray(colors),edgecolors='none'))
    vertices=np.vstack([m.vertices for _,m in meshes]);low=vertices.min(axis=0);high=vertices.max(axis=0)
    ax.set_xlim(low[0],high[0]);ax.set_ylim(low[1],high[1]);ax.set_zlim(low[2],high[2])
    ax.set_box_aspect(np.maximum(high-low,.1));ax.view_init(elev=27,azim=-125)
    ax.set_title('Maqueta volumetrica');ax.set_axis_off()
    fig.tight_layout();fig.savefig(output,dpi=120);plt.close(fig)
