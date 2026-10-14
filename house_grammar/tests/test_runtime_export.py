"""Runtime batching preserves actual attributed triangles, not only counts."""
import json
import struct
import numpy as np
import trimesh
from shapely.geometry import box
from modeling.mesh_builder import MeshBuilder
from modeling.exporters.glb_exporter import export_glb


def tree(path):
    data=path.read_bytes()
    return json.loads(data[20:20+struct.unpack_from('<I',data,12)[0]])


def attributed_triangles(path):
    scene=trimesh.load(path,force='scene',process=False)
    records=[]
    for name in scene.graph.nodes_geometry:
        transform,geom=scene.graph[name]
        mesh=scene.geometry[geom]
        vertices=trimesh.transform_points(mesh.vertices,transform)
        for tri in mesh.faces:
            corners=tuple(sorted(tuple(np.round(np.r_[vertices[i],mesh.visual.uv[i]],6)) for i in tri))
            records.append((mesh.visual.material.name,corners))
    return sorted(records)


def test_runtime_preserves_triangles_uv_materials_and_source(tmp_path):
    mb=MeshBuilder(box(-10,-10,10,10))
    for i in range(20):
        with mb.assembly('lot_7/window_'+str(i)):
            mb.box([0,0],[1,0],[0,-1],i*.1,i*.1+.03,0,2,-.1,0,'metal','bar')
    mesh=mb.finish()
    before=mesh.vertices.copy(),mesh.faces.copy(),mesh.corner_uv.copy(),tuple(mesh.parts)
    author=tmp_path/'author.glb';runtime=tmp_path/'runtime.glb'
    export_glb(mesh,author,library=False)
    export_glb(mesh,runtime,library=False,mode='runtime')
    assert len(tree(author)['nodes'])==20
    assert len(tree(runtime)['nodes'])==1
    assert attributed_triangles(author)==attributed_triangles(runtime)
    for current,saved in zip((mesh.vertices,mesh.faces,mesh.corner_uv),before[:3]):
        np.testing.assert_array_equal(current,saved)
    assert tuple(mesh.parts)==before[3]
