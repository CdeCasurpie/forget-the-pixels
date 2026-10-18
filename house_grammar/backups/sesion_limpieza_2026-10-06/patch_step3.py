import sys
import re

path = "scripts/step3_generate_full_block.py"
with open(path, "r") as f:
    content = f.read()

# Replace the poly_safe logic
new_props_logic = """    # Auto-generar cosas en el techo (tanques, fierros)
    poly_safe = polygon.buffer(-3.0)
    props = []
    if not poly_safe.is_empty:
        minx, miny, maxx, maxy = poly_safe.bounds
        for kind in ["water_tank", "rebar_cluster", "laundry"]:
            if rng.random() > 0.4: continue
            for _ in range(20):
                x = rng.uniform(minx, maxx)
                y = rng.uniform(miny, maxy)
                if poly_safe.contains(Point(x, y)):
                    props.append(RoofObject(mass_role="main", kind=kind, xy=(round(x,2), round(y,2)), rotation_deg=round(rng.uniform(0,360),1)))
                    break
                    
    roof = RoofControls(props=tuple(props) if pattern == "single_block" else ())"""

content = re.sub(
    r'# Auto-generar cosas en el techo.*?roof = RoofControls\(.*?else \(\)\)',
    new_props_logic,
    content,
    flags=re.DOTALL
)

with open(path, "w") as f:
    f.write(content)
