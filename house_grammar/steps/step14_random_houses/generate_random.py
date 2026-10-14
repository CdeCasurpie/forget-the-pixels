import sys
import numpy as np
from pathlib import Path
from shapely.geometry import Polygon, Point

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))
sys.path.insert(0, '.')

from domain.architecture import BuildingProgram, ParcelContext, SitePlan, MassSpec, BuildingSpecificationV4
from modeling.grammar import generate_v4_mesh
from steps.step12_city_generation.render import render
from modeling.exporters.glb_exporter import export_glb

def generate_random_parcel(rng, base_width=10, base_depth=20):
    shape_type = rng.choice(["rectangle", "trapezoid", "l_shape"])
    
    if shape_type == "rectangle":
        w = rng.uniform(base_width - 2, base_width + 4)
        d = rng.uniform(base_depth - 4, base_depth + 10)
        poly = Polygon([(0,0), (w,0), (w,d), (0,d)])
        return poly, w, d
    elif shape_type == "trapezoid":
        w1 = rng.uniform(base_width - 2, base_width + 2)
        w2 = rng.uniform(base_width - 2, base_width + 4)
        d = rng.uniform(base_depth - 4, base_depth + 10)
        poly = Polygon([(0,0), (w1,0), (w2,d), (0,d)])
        return poly, max(w1, w2), d
    else: # l_shape
        w1 = rng.uniform(base_width, base_width + 5)
        d1 = rng.uniform(base_depth, base_depth + 5)
        w2 = rng.uniform(w1 * 0.4, w1 * 0.6)
        d2 = rng.uniform(d1 * 0.4, d1 * 0.6)
        poly = Polygon([(0,0), (w1,0), (w1,d2), (w2,d2), (w2,d1), (0,d1)])
        return poly, w1, d1

def generate_random_house(seed, output_dir):
    rng = np.random.default_rng(seed)
    
    poly, max_w, max_d = generate_random_parcel(rng)
    ctx = ParcelContext(polygon=tuple(poly.exterior.coords))
    
    use = rng.choice(["residential", "commercial", "mixed"])
    placement = rng.choice(["flush", "front_setback"])
    finish = rng.choice(["raw", "plastered"])
    profile = rng.choice(["standard", "premium"])
    
    masses = []
    
    if rng.random() < 0.3 and use in ("mixed", "commercial"):
        podium_h = rng.integers(1, 3) * 4.0
        tower_h = podium_h + rng.integers(2, 6) * 4.0
        
        masses.append(MassSpec(
            id="podium", 
            footprint=tuple(poly.buffer(-0.1).exterior.coords),
            base_z=0.0, roof_z=podium_h, 
            floor_levels=tuple(np.linspace(0, podium_h, int(podium_h/4) + 1)),
            role="podium", roof_spec=None
        ))
        
        tower_poly = poly.intersection(Polygon([(0, max_d/2), (max_w, max_d/2), (max_w, max_d), (0, max_d)]))
        if tower_poly.geom_type == 'Polygon' and tower_poly.area > 20:
            masses.append(MassSpec(
                id="tower", 
                footprint=tuple(tower_poly.buffer(-0.5).exterior.coords),
                base_z=podium_h, roof_z=tower_h, 
                floor_levels=tuple(np.linspace(podium_h, tower_h, int((tower_h-podium_h)/4) + 1)),
                role="tower", roof_spec=None
            ))
    else:
        h = rng.integers(1, 6) * 4.0
        if placement == "front_setback":
            setback_dist = rng.uniform(2.0, 5.0)
            footprint_poly = poly.intersection(Polygon([(0, setback_dist), (max_w, setback_dist), (max_w, max_d), (0, max_d)]))
        else:
            footprint_poly = poly
            
        if footprint_poly.geom_type == 'Polygon' and footprint_poly.area > 15:
            masses.append(MassSpec(
                id="main", 
                footprint=tuple(footprint_poly.buffer(-0.2).exterior.coords),
                base_z=0.0, roof_z=h, 
                floor_levels=tuple(np.linspace(0, h, int(h/4) + 1)),
                role="tower", roof_spec=None
            ))

    if not masses:
        return
        
    site = SitePlan(masses=tuple(masses), free_space=(), access_nodes=(), boundaries=(), exclusion_zones=())
    
    color = (rng.uniform(0.3, 0.9), rng.uniform(0.3, 0.9), rng.uniform(0.3, 0.9))
    
    spec = BuildingSpecificationV4(
        program=BuildingProgram(
            use=use, occupancy="medium", placement=placement, 
            architectural_language="modern" if profile=="premium" else "vernacular",
            finish_profile=profile, 
            maintenance="average", construction_state="finished", 
            front_setback=3.0 if placement=="front_setback" else 0.0, side_setback=0.0,
            primary_color=color, 
            side_wall_finish=finish,
            seed=seed
        ),
        context=ctx, site_plan=site, facades=(), components=(), seed=seed
    )
    
    name = f"random_house_{seed}_{use}_{profile}"
    print(f"Generating {name}...")
    mesh_data = generate_v4_mesh(spec)
    render(mesh_data, str(output_dir / f"{name}.png"), clay=False)
    export_glb(mesh_data, str(output_dir / f"{name}.glb"))

def main():
    output_dir = Path("steps/step14_random_houses/outputs")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    seeds = [1042, 2042, 3042, 4042, 5042]
    for seed in seeds:
        generate_random_house(seed, output_dir)

if __name__ == "__main__":
    main()
