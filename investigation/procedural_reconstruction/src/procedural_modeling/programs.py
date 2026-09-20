from dataclasses import dataclass

@dataclass
class OpeningSpec:
    u: float
    v: float
    width: float
    height: float
    kind: str # window, door, shopfront

def generate_facade_openings(length: float, floor_levels: tuple[float, ...], program: str, z_bottom: float, z_top: float) -> list[OpeningSpec]:
    openings = []
    if not floor_levels:
        return openings
        
    for z_floor in floor_levels:
        if z_floor < z_bottom - 0.01 or z_floor >= z_top - 0.01:
            continue
            
        v_rel = z_floor - z_bottom
        is_ground = (z_floor < 1.0)
        
        if program == "commercial" and is_ground:
            # Subdivided Shopfronts
            margin = 0.5
            w = length - (margin * 2)
            if w > 2.0:
                bay_width = 3.0
                num_bays = int(w // bay_width)
                if num_bays > 0:
                    start_u = (length - (num_bays * bay_width)) / 2.0
                    for b in range(num_bays):
                        openings.append(OpeningSpec(
                            u=start_u + b * bay_width + 0.1, 
                            v=v_rel + 0.0, 
                            width=bay_width - 0.2, 
                            height=3.0, 
                            kind="shopfront"
                        ))
        else:
            # Residential windows
            window_w, window_h = 1.2, 1.5
            spacing = 2.5
            
            num_windows = int(length // spacing)
            if num_windows > 0:
                start_u = (length - (num_windows * window_w + (num_windows - 1) * (spacing - window_w))) / 2.0
                for i in range(num_windows):
                    u = start_u + i * spacing
                    openings.append(OpeningSpec(u=u, v=v_rel + 0.9, width=window_w, height=window_h, kind="window"))
                    
    return openings
