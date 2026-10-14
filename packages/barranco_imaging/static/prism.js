'use strict';
// angular-enu-v1: same sampling as packages/barranco_imaging/angular.py.
function paintPrism(target, spec, height, firstFloorHeight = null) {
    const c = target.getContext('2d');
    c.clearRect(0, 0, target.width, target.height);
    c.lineWidth = 3.2;
    c.lineJoin = 'round';
    c.lineCap = 'round';
    const wrap = a => ((a + Math.PI) % (2*Math.PI) + 2*Math.PI) % (2*Math.PI) - Math.PI;
    function project(p) {
        const yaw = Math.atan2(p[0], p[1]);
        const pitch = Math.atan2(p[2]-spec.camera_height_m, Math.hypot(p[0], p[1]));
        return [(wrap(yaw-spec.yaw_rad)/spec.fov_rad+.5)*spec.width,
            (spec.top_rad-pitch)/(spec.top_rad-spec.bottom_rad)*spec.height];
    }
    function line(a,b,color) {
        c.strokeStyle = color;
        c.beginPath();
        let previous = null;
        for (let i=0;i<80;i++) {
            const t=i/79, p=project(a.map((v,j)=>v+(b[j]-v)*t));
            if (previous && Math.hypot(p[0]-previous[0],p[1]-previous[1]) < Math.max(spec.width,spec.height)/2) {
                c.moveTo(...previous); c.lineTo(...p);
            }
            previous=p;
        }
        c.stroke();
    }
    const vertices=spec.vertices_relative_xy;
    for (let i=0;i<vertices.length-1;i++) {
        const a=vertices[i],b=vertices[i+1];
        line([...a,0],[...b,0],'#ffff00');
        line([...a,height],[...b,height],'#ff50ff');
        line([...a,0],[...a,height],'#28b4ff');
        if (firstFloorHeight !== null && firstFloorHeight <= height) {
            line([...a,firstFloorHeight],[...b,firstFloorHeight],'#59ffb0');
        }
    }
}
