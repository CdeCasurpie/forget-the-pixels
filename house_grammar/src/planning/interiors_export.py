"""Phase 3 diagnostic floor plans: colored rooms, doors, windows and core.

Schematic interior zones and connections; not construction documentation.
"""
import json
from pathlib import Path

from shapely.geometry import shape, LineString

from planning.massing import polygons


ROOM_COLORS={
    'circulation':(206,209,214),
    'stairs':(141,153,174),
    'bathroom':(127,179,213),
    'bedroom':(242,215,164),
    'living':(205,224,182),
    'kitchen_dining':(240,178,122),
    'service':(213,198,224),
    'garage':(176,176,176),
    'shop':(245,183,177),
    'open_ground':(232,240,216),
    'unassigned':(238,238,238),
}


def summary(plan):
    data=plan.to_dict();floors=[]
    for f in data['floors']:
        kinds={}
        for room in f['rooms']:
            kinds[room['kind']]=kinds.get(room['kind'],0)+1
        floors.append(dict(floor=f['floor'],rooms=len(f['rooms']),kinds=kinds,
                           doors=len(f['doors']),windows=len(f['windows']),
                           corridor_width_m=f['corridor_width_m'],
                           coverage_error_m2=f['checks']['coverage_error_m2'],
                           room_areas={r['id']:round(r['area_m2'],2) for r in f['rooms']}))
    core=data['core']
    return dict(version=data['version'],
                floors=floors,core_flights=len(core['flights']),
                selected_alternative=core['selected_alternative'],
                alternatives=data['alternatives'],
                connections=len(data['connections']),
                checks=data['checks'],
                scope='schematic interior zones and circulation, not construction documents')


def export_interiors(plan, output, preview=True):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    data=plan.to_dict()
    (output/'plan.json').write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n')
    report=summary(plan)
    (output/'summary.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    if preview:render(data,output/'preview.png',output/'floors')
    return report


def _ring(ax, poly, **kwargs):
    from matplotlib.path import Path as PlotPath
    from matplotlib.patches import PathPatch
    from shapely.geometry.polygon import orient
    poly=orient(poly)
    verts=[];codes=[]
    for ring in [poly.exterior,*poly.interiors]:
        points=list(ring.coords);verts.extend(points)
        codes.extend([PlotPath.MOVETO]+[PlotPath.LINETO]*(len(points)-2)+[PlotPath.CLOSEPOLY])
    ax.add_patch(PathPatch(PlotPath(verts,codes),**kwargs))


def _floor_axes(ax, data, floor):
    ax.plot(*shape({'type':'Polygon','coordinates':[data['request']['context']['parcel']]}).exterior.xy,
            color='#666666',linestyle='--',linewidth=1)
    row=floor
    for room in row['rooms']:
        color=[c/255 for c in ROOM_COLORS.get(room['kind'],(238,238,238))]+[.85]
        for poly in polygons(shape(room['usable_geometry'])):
            _ring(ax,poly,facecolor=color,edgecolor='#7a7a7a',linewidth=.4)
        point=shape(room['geometry']).representative_point()
        ax.text(point.x,point.y,f"{room['kind']}\n{room['area_m2']:.0f} m2",ha='center',va='center',fontsize=6.5,color='#333333')
    for connection in row['connections']:
        if connection['kind']=='exterior_space':
            for poly in polygons(shape(connection['geometry'])):
                _ring(ax,poly,facecolor=(115/255,183/255,199/255,110/255),edgecolor='none')
    for poly in polygons(shape(row['service_shaft'])):
        _ring(ax,poly,facecolor=(90/255,90/255,90/255,200/255),edgecolor='none')
    for poly in polygons(shape(row['walls'])):
        _ring(ax,poly,facecolor=(59/255,59/255,59/255,230/255),edgecolor='none')
    for door in row['doors']:
        line=shape(door['geometry']);x,y=line.xy
        ax.plot(x,y,color='#b03a2e',linewidth=2.4,solid_capstyle='butt')
    for window in row['windows']:
        line=shape(window['geometry']);x,y=line.xy
        ax.plot(x,y,color='#1f6feb',linewidth=3.4,solid_capstyle='butt')
    for connection in row['connections']:
        if connection['kind'] in ('entrance','vehicle_entry'):
            line=shape(connection['geometry']);x,y=line.xy
            ax.plot(x,y,color='#2e8b57',linewidth=2.6,linestyle=(0,(3,2)))
    for name,frame in data['massing']['fronts'].items():
        import numpy as np
        a=np.array(frame['origin']);t=np.array(frame['right']);n=np.array(frame['inward'])
        p=a+t*frame['length_m']/2
        ax.text(*(p-n*.7),name,ha='center',color='#315e99',fontsize=8)
    ax.set_aspect('equal');ax.autoscale_view()
    ax.set_title(f"Piso {row['floor']} — circulación {row['corridor_width_m']:.2f} m")
    ax.set_xlabel('X (m)')


def render(data, output, floors_dir=None):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    floors=data['floors']
    if floors_dir is not None:
        floors_dir=Path(floors_dir);floors_dir.mkdir(parents=True,exist_ok=True)
    fig=plt.figure(figsize=(4.2*len(floors),5))
    for idx,row in enumerate(floors,1):
        ax=fig.add_subplot(1,len(floors),idx);_floor_axes(ax,data,row)
        if floors_dir is not None:
            single=plt.figure(figsize=(6.4,6.4))
            _floor_axes(single.add_subplot(1,1,1),data,row)
            single.tight_layout();single.savefig(floors_dir/f"floor{row['floor']}.png",dpi=130);plt.close(single)
    kinds=sorted({room['kind'] for row in floors for room in row['rooms']})
    handles=[Patch(facecolor=[c/255 for c in ROOM_COLORS.get(kind,(238,238,238))],label=kind) for kind in kinds]
    handles.extend([Patch(facecolor='#b03a2e',label='puerta'),Patch(facecolor='#1f6feb',label='ventana'),
                    Patch(facecolor='#2e8b57',label='acceso exterior'),Patch(facecolor='#73b7c7',label='logia/pórtico')])
    fig.legend(handles=handles,loc='lower center',ncol=min(6,len(handles)),fontsize=7,frameon=False)
    fig.tight_layout(rect=(0,.07,1,1));fig.savefig(output,dpi=120);plt.close(fig)
