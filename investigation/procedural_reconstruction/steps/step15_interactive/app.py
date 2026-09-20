import sys
import numpy as np
from pathlib import Path
from shapely.geometry import Polygon
import gradio as gr

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))
sys.path.insert(0, '.')

from domain.architecture import BuildingProgram, ParcelContext, SitePlan, MassSpec, BuildingSpecificationV4
from procedural_modeling.grammar import generate_v4_mesh
from steps.step12_city_generation.render import render
from exporters.glb_exporter import export_glb

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16)/255.0 for i in (0, 2, 4))

LOT_PRESETS = {
    "Rectangular":       lambda w, d: [(0,0),(w,0),(w,d),(0,d)],
    "Rectangular Largo": lambda w, d: [(0,0),(w*0.6,0),(w*0.6,d*1.5),(0,d*1.5)],
    "Esquina (Corner)":  lambda w, d: [(0,0),(w,0),(w,d),(0,d)],
    "Forma L":           lambda w, d: [(0,0),(w,0),(w,d*0.5),(w*0.5,d*0.5),(w*0.5,d),(0,d)],
    "Forma T":           lambda w, d: [(w*0.2,0),(w*0.8,0),(w*0.8,d*0.4),(w,d*0.4),(w,d*0.6),(w*0.8,d*0.6),(w*0.8,d),(w*0.2,d),(w*0.2,d*0.6),(0,d*0.6),(0,d*0.4),(w*0.2,d*0.4)],
    "Trapezoidal":       lambda w, d: [(w*0.1,0),(w*0.9,0),(w,d),(0,d)],
}

def generate_interactive(seed, use, lot_type, arch_lang, profile, side_finish, floors, lot_w, lot_d, color_hex, front_setback, voladizo, has_fence, fence_type):
    rgb = hex_to_rgb(color_hex)
    seed = int(seed)
    floors = int(floors)

    # ── 1. Build lot polygon ─────────────────────────────────────────
    lot_coords = LOT_PRESETS[lot_type](lot_w, lot_d)
    lot_poly = Polygon(lot_coords)
    ctx = ParcelContext(polygon=tuple(lot_poly.exterior.coords))

    total_h = floors * 3.5
    buf = 0.0  # Removing artificial buffer so building perfectly masks lot lines

    # ── 2. Build masses ──────────────────────────────────────────────
    masses = []

    if floors >= 2 and voladizo > 0.05:
        # VOLADIZO MODE: ground floor is recessed, upper floors sit at parcel edge.
        # This creates the cantilever naturally.
        ground_setback = front_setback + voladizo
        upper_setback  = front_setback

        # Ground floor polygon (recessed inward by voladizo)
        ground_clip = lot_poly.intersection(
            Polygon([(-50, ground_setback), (lot_w+50, ground_setback),
                     (lot_w+50, lot_d+50), (-50, lot_d+50)])
        ).buffer(-buf)

        # Upper floors polygon (at normal position)
        upper_clip = lot_poly.intersection(
            Polygon([(-50, upper_setback), (lot_w+50, upper_setback),
                     (lot_w+50, lot_d+50), (-50, lot_d+50)])
        ).buffer(-buf)

        if not ground_clip.is_empty and ground_clip.area > 1:
            masses.append(MassSpec(
                id="ground", footprint=tuple(ground_clip.exterior.coords),
                base_z=0.0, roof_z=3.5, floor_levels=(0.0, 3.5),
                role="podium", roof_spec=None
            ))
        if not upper_clip.is_empty and upper_clip.area > 1:
            masses.append(MassSpec(
                id="upper", footprint=tuple(upper_clip.exterior.coords),
                base_z=3.5, roof_z=total_h,
                floor_levels=tuple(np.linspace(3.5, total_h, floors)),
                role="tower", roof_spec=None
            ))
    else:
        # SIMPLE MODE: single mass, optionally set back
        clip = lot_poly.intersection(
            Polygon([(-50, front_setback), (lot_w+50, front_setback),
                     (lot_w+50, lot_d+50), (-50, lot_d+50)])
        ).buffer(-buf)
        if not clip.is_empty and clip.area > 1:
            masses.append(MassSpec(
                id="main", footprint=tuple(clip.exterior.coords),
                base_z=0.0, roof_z=total_h,
                floor_levels=tuple(np.linspace(0, total_h, floors + 1)),
                role="tower", roof_spec=None
            ))

    if not masses:
        raise gr.Error("El lote es demasiado pequeño para esos parámetros")

    site = SitePlan(masses=tuple(masses), free_space=(),
                    access_nodes=(), boundaries=(), exclusion_zones=())

    # If setback is 0, use flush placement (no fence at all)
    actual_placement = "flush" if front_setback < 0.5 else "front_setback"

    spec = BuildingSpecificationV4(
        program=BuildingProgram(
            use=use, occupancy="medium", placement=actual_placement,
            architectural_language=arch_lang, finish_profile=profile,
            maintenance="average", construction_state="finished",
            front_setback=front_setback, side_setback=0.0,
            primary_color=rgb, side_wall_finish=side_finish, seed=seed,
            has_fence=(has_fence and front_setback >= 1.0),
            fence_type=fence_type,
            is_corner=(lot_type == "Esquina (Corner)")
        ),
        context=ctx, site_plan=site, facades=(), components=(), seed=seed
    )

    mesh_data = generate_v4_mesh(spec)

    out_dir = Path("steps/step15_interactive/outputs")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_glb = str(out_dir / "preview.glb")
    out_png = str(out_dir / "preview.png")

    export_glb(mesh_data, out_glb)
    render(mesh_data, out_png, clay=False)
    return out_glb, out_png


with gr.Blocks(title="Generador Procedural Lima") as demo:
    gr.Markdown("# 🏘️ Generador Procedural de Casas Peruanas")

    with gr.Row():
        with gr.Column(scale=1):
            seed = gr.Slider(0, 10000, value=777, step=1, label="Semilla Aleatoria")

            gr.Markdown("### Lote")
            lot_type = gr.Dropdown(list(LOT_PRESETS.keys()), value="Rectangular", label="Tipo de Lote")
            lot_w = gr.Slider(4.0, 20.0, value=10.0, step=0.5, label="Ancho (m)")
            lot_d = gr.Slider(10.0, 40.0, value=20.0, step=0.5, label="Profundidad (m)")

            gr.Markdown("### Edificio")
            floors = gr.Slider(1, 8, value=3, step=1, label="Pisos")
            front_setback = gr.Slider(0.0, 10.0, value=0.0, step=0.5,
                                      label="Retranqueo Frontal (m)")
            voladizo = gr.Slider(0.0, 2.0, value=0.0, step=0.1,
                                 label="Voladizo (m) — 1er piso se hunde, superiores quedan al frente")
            
            gr.Markdown("### Cerco Frontal (Requiere Retranqueo >= 1.0m)")
            has_fence_ui = gr.Checkbox(value=True, label="Generar Cercado")
            fence_type_ui = gr.Dropdown(["reja", "ladrillos", "concreto", "concreto_bajo"], value="reja", label="Tipo de Cerco")

            gr.Markdown("### Estilo")
            use = gr.Dropdown(["residential", "commercial", "mixed"], value="residential", label="Uso")
            arch_lang = gr.Dropdown(["vernacular", "modern"], value="modern", label="Lenguaje")
            profile = gr.Dropdown(["standard", "premium"], value="standard", label="Acabados")
            side_finish = gr.Dropdown(["raw", "plastered"], value="raw", label="Laterales")
            color_hex = gr.ColorPicker(value="#e6cab8", label="Color Fachada")

            btn = gr.Button("🔨 Generar", variant="primary")

        with gr.Column(scale=2):
            out_model = gr.Model3D(label="Modelo 3D (GLB)")
            out_image = gr.Image(label="Render Isométrico")

    btn.click(
        fn=generate_interactive,
        inputs=[seed, use, lot_type, arch_lang, profile, side_finish,
                floors, lot_w, lot_d, color_hex, front_setback, voladizo, has_fence_ui, fence_type_ui],
        outputs=[out_model, out_image]
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False)
