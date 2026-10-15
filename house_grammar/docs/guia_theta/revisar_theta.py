"""Reproduce y diagnostica una solicitud theta en una carpeta nueva."""
import argparse
import cProfile
import hashlib
import json
from pathlib import Path
import pstats
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))

from domain.theta import from_json, canonical
from domain.architecture import ParcelContext
from pipeline.theta import reconstruct
from modeling.grammar import street_envelope
from modeling.validation import validate_mesh, analyze_topology
from modeling.exporters.glb_exporter import export_glb
from modeling.version import MATERIALIZER_VERSION
from shapely.geometry import Polygon


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def preview(mesh, path):
    """Vista geométrica con color base; no simula texturas PBR ni transparencia."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    import numpy as np

    triangles = mesh.vertices[mesh.faces]
    colors = np.array([m['color'] for m in mesh.materials])[mesh.face_materials]
    normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-12)
    light = np.array([-.4, -.6, .7])
    light /= np.linalg.norm(light)
    colors = np.clip(colors * (.55 + .45 * np.maximum(0, normals @ light))[:, None], 0, 1)
    low, high = mesh.vertices.min(axis=0), mesh.vertices.max(axis=0)
    fig = plt.figure(figsize=(15, 7), facecolor='#f6f3eb')
    for index, (elevation, azimuth, title) in enumerate(((18, -90, 'Frente'), (30, -60, 'Vista oblicua'))):
        ax = fig.add_subplot(1, 2, index + 1, projection='3d', facecolor='#f6f3eb')
        ax.add_collection3d(Poly3DCollection(triangles, facecolors=colors, edgecolors='none', linewidths=0))
        ax.set_xlim(low[0], high[0]); ax.set_ylim(low[1], high[1]); ax.set_zlim(0, high[2])
        ax.set_box_aspect((high[0]-low[0], high[1]-low[1], high[2]))
        ax.view_init(elev=elevation, azim=azimuth)
        ax.set_axis_off(); ax.set_title(title)
    fig.suptitle('Theta regenerado · vista geométrica con color base (sin texturas PBR)')
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('request', type=Path)
    parser.add_argument('--output', type=Path, required=True, help='Carpeta NUEVA para esta ejecución')
    parser.add_argument('--preview', action='store_true', help='Añadir imagen geométrica; requiere matplotlib')
    args = parser.parse_args()
    raw = args.request.read_text()
    request = from_json(raw)
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / 'request.json').write_text(raw)
    profiler = cProfile.Profile()
    started = time.perf_counter()
    profiler.enable()
    result = reconstruct(request)
    profiler.disable()
    elapsed = time.perf_counter() - started
    context = result.resolved.context
    envelope = street_envelope(ParcelContext(context.parcel, explicit_fronts=context.fronts))
    envelope = envelope.buffer(result.resolved.theta.massing.parcel_tolerance_m)
    validation = validate_mesh(result.mesh, Polygon(context.parcel), envelope=envelope)
    topology = analyze_topology(result.mesh)
    (args.output / 'resolved_theta.json').write_text(canonical(result.resolved) + '\n')
    write_json(args.output / 'validation.json', validation)
    topology_summary = {k: v for k, v in topology.items() if k != 'components'}
    write_json(args.output / 'topology_summary.json', topology_summary)
    calls = []
    for (filename, line, name), (_, total, self_time, cumulative, _) in pstats.Stats(profiler).stats.items():
        try:
            relative = Path(filename).relative_to(ROOT / 'src')
        except ValueError:
            continue
        calls.append(dict(file=str(relative), line=line, function=name, calls=total,
                          self_s=self_time, cumulative_s=cumulative))
    calls.sort(key=lambda c: -c['cumulative_s'])
    write_json(args.output / 'calls.json', calls)
    export_glb(result.mesh, args.output / 'building.glb', mode='runtime')
    if args.preview:
        preview(result.mesh, args.output / 'preview.png')
    summary = dict(materializer=MATERIALIZER_VERSION,
        request_sha256=hashlib.sha256(raw.encode()).hexdigest(),
        mesh_sha256=hashlib.sha256(result.mesh.vertices.tobytes()+result.mesh.faces.tobytes()).hexdigest(),
        generation_profiled_s=round(elapsed, 3), vertices=len(result.mesh.vertices),
        triangles=len(result.mesh.faces), parts=len(result.mesh.parts),
        masses=[dict(id=m.id, levels_m=m.floor_levels) for m in result.resolved.masses],
        walls=len(result.resolved.walls), openings=sum(len(w.facade.openings) for w in result.resolved.walls),
        crowns=[dict(id=c.controls.id, family=c.controls.design.family, reason=c.classification_reason)
                for c in result.resolved.crowns],
        balconies=len(result.resolved.balconies), members=len(result.resolved.vertical_members),
        trims=len(result.resolved.trims), envelope=validation['envelope_test'],
        topology_violations=len(topology['violations']), visited_modules=sorted({c['file'] for c in calls}))
    write_json(args.output / 'summary.json', summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
