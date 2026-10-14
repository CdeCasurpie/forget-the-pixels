"""Genera un GLB por lote con la gramatica, desde el theta foto-interpretado.

Cada lote necesita `lote_<i>/theta.json` (autoría manual desde sus fotos) con:
    {"theta": {...}, "nuisance": {"seed": N}, "evidence": {...}}

El contexto (parcela local + frentes) y las observaciones (vistas) salen de
`lot.json`. La salida va a `lote_<i>/salida/` (mismo formato que run.py:
building.glb, iso/street.png, manifest.json...).

Uso:
    python steps/step19_experimental/cuadra_fotos/generar_glb_cuadra.py --cuadra steps/step19_experimental/cuadra_fotos/cuadra_seed_123
    python steps/step19_experimental/cuadra_fotos/generar_glb_cuadra.py --cuadra ... --lot 1850
    python steps/step19_experimental/cuadra_fotos/generar_glb_cuadra.py --cuadra ... --lot 1850 --only-theta
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CUADRA_SCRIPTS = Path(__file__).resolve().parent
ROOT = CUADRA_SCRIPTS.parents[2]
sys.path.insert(0, str(ROOT / "steps" / "step10_procedural_generation_test"))
sys.path.insert(0, str(ROOT / "steps" / "step18_theta_interface"))
sys.path.insert(0, str(ROOT / "src"))

from run import run as run_theta  # noqa: E402
from modeling.geometry_constraints import apply_edge_setbacks, front_lines  # noqa: E402
from domain.architecture import ParcelContext as _ParcelContext  # noqa: E402
from shapely.geometry import Polygon as _Polygon  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402


def _round_ring(poly):
    import math as _math
    from shapely.geometry import Point as _Point
    centroid = poly.centroid
    pts = [[round(float(x), 4), round(float(y), 4)] for x, y in list(poly.exterior.coords)[:-1]]
    # 1) vertices redondeados fuera de la parcela -> 0.2 mm hacia adentro.
    for _ in range(5):
        bad = [i for i, (x, y) in enumerate(pts) if not poly.covers(_Point(x, y))]
        if not bad:
            break
        for i in bad:
            x, y = pts[i]
            dx, dy = centroid.x - x, centroid.y - y
            dist = _math.hypot(dx, dy) or 1.0
            pts[i] = [round(x + dx / dist * 2e-4, 4), round(y + dy / dist * 2e-4, 4)]
    # 2) micro-aristas (<15 cm, artefactos de retranqueo) -> fundir vertice.
    changed = True
    while changed and len(pts) > 4:
        changed = False
        for i in range(len(pts)):
            a, b = pts[i], pts[(i + 1) % len(pts)]
            if _math.hypot(b[0] - a[0], b[1] - a[1]) < 0.15:
                candidate = pts[:i] + pts[i + 1:]
                if poly.covers(_Polygon(candidate + [candidate[0]])):
                    pts = candidate
                    changed = True
                    break
    return pts + [pts[0]]


def _explicit_mass(parcel, fronts, height_m, floors, setback_m):
    """Masa en grilla 1e-4 (evita el fallo de exposicion parcial)."""
    poly = _Polygon(parcel)
    ctx = _ParcelContext(tuple(map(tuple, parcel)), explicit_fronts=list(fronts))
    # +1 mm de margen: el redondeo a la grilla (±5e-5) no puede sacar un
    # vertice fuera de la parcela y parcel.covers(masa) se cumple exacto.
    shrunk = apply_edge_setbacks(poly, front_lines(ctx), setback_m + 1e-3) if setback_m else poly
    if shrunk.is_empty or shrunk.geom_type != "Polygon" or shrunk.area < 6:
        shrunk = poly
    ring = _round_ring(shrunk)
    levels = [round(height_m * i / floors, 4) for i in range(floors + 1)]
    return ring, levels


def _explicit_split(parcel, fronts, height_m, floors, massing):
    """Replica _masses para front_tall_rear_low/front_low_rear_tall en grilla."""
    from shapely.ops import unary_union as _union  # noqa: F401
    poly = _Polygon(parcel)
    ctx = _ParcelContext(tuple(map(tuple, parcel)), explicit_fronts=list(fronts))
    lines = front_lines(ctx)
    setback = massing.get("front_setback_m", 0.0) or 0.0
    body = apply_edge_setbacks(poly, lines, setback + 1e-3) if setback else poly
    rear = body.intersection(apply_edge_setbacks(
        body, lines, massing["front_depth_m"] + setback + 1e-3))
    front = body.difference(rear)
    if front.is_empty or rear.is_empty or front.geom_type != "Polygon" or rear.geom_type != "Polygon":
        raise ValueError("split sin geometria util")
    tall_front = massing["pattern"] == "front_tall_rear_low"
    low = massing["low_floors"]
    fh = height_m / floors
    out = []
    for role, geom, hi in (("front", front, floors if tall_front else low),
                           ("rear", rear, low if tall_front else floors)):
        out.append({"role": role, "footprint": _round_ring(geom),
                    "levels_m": [round(i * fh, 4) for i in range(hi + 1)]})
    return out


def build_request(lot_dir: Path, theta_path: Path) -> Path:
    lot = json.loads((lot_dir / "lot.json").read_text())
    authored = json.loads(theta_path.read_text())
    # Truncar a la grilla 1e-4 como step3 (clean_geometry): si no, el
    # set_precision interno mueve aristas y falla el chequeo de exposicion.
    parcel = [[round(float(x), 4), round(float(y), 4)] for x, y in lot["parcel_local_m"]]
    views = []
    for rank, camera in enumerate(lot["cameras"], 1):
        vista = lot_dir / camera["vista"].split(f"lote_{lot['lot_index']}/")[-1]
        views.append({"view_id": f"vista_{rank:02d}",
                      "image_path": str(vista.relative_to(lot_dir))})
    request = {
        "context": {"parcel": parcel, "fronts": lot["fronts"],
                    "crs": lot.get("crs", "EPSG:32718")},
        "observations": views,
        "theta": authored["theta"],
        "nuisance": authored.get("nuisance", {"seed": 7}),
        "evidence": authored.get("evidence", {}),
    }
    # single_block con retranqueo -> masa explicita en grilla (mismo volumen,
    # sin el error de exposicion parcial por coordenadas no-grilla).
    theta = request["theta"]
    massing = theta.get("massing", {})
    pattern = massing.get("pattern", "single_block")
    if (theta.get("masses") is None and theta.get("height_m") and theta.get("floors")
            and pattern in ("single_block", "front_tall_rear_low", "front_low_rear_tall")):
        if pattern == "single_block":
            ring, levels = _explicit_mass(parcel, lot["fronts"], theta["height_m"],
                                          theta["floors"], massing.get("front_setback_m", 0.0) or 0.0)
            theta["masses"] = [{"role": "main", "footprint": ring, "levels_m": levels}]
        else:
            theta["masses"] = _explicit_split(parcel, lot["fronts"], theta["height_m"],
                                              theta["floors"], massing)
        theta["massing"] = {"pattern": "explicit"}
        theta.pop("height_m", None)
        theta.pop("floors", None)
        # height/floors derivados: la evidencia pasa a unknown (valor nulo).
        for path in ("height_m", "floors"):
            if path in request["evidence"]:
                request["evidence"][path] = {"state": "unknown"}
    # theta.json puede traer evidence con view_ids genericos vista_01...; si el
    # autor uso otros ids, se reescriben a los reales en orden.
    used = [v["view_id"] for v in views]
    for key, entry in request["evidence"].items():
        ids = entry.get("view_ids", [])
        entry["view_ids"] = [used[i] if isinstance(i, int) else i for i in ids]
    out = lot_dir / "request.json"
    out.write_text(json.dumps(request, indent=2, ensure_ascii=False) + "\n")
    return out


def render_fachada(request_path: Path, salida: Path) -> None:
    """Render de la fachada real (normal del primer muro frontal con vanos)."""
    import json as _json
    from domain.theta import from_json as _from_json
    from pipeline.theta import reconstruct as _reconstruct
    from render import render as _render
    request = _from_json(request_path.read_text())
    result = _reconstruct(request)
    fronts = [w for w in result.resolved.walls if w.facade.is_front]
    wall = next((w for w in fronts if w.facade.openings), fronts[0])
    nx, ny = wall.facade.normal_xy
    _render(result.mesh, salida / "fachada.png",
            direction=(float(nx), float(ny), 0.15), size=720, clay=False)


def build_comparacion(lot_dir: Path, salida: Path, lot_index: int) -> None:
    """Vista real vs render de SU fachada, lado a lado (como generacion_mannual)."""
    vistas = sorted((lot_dir / "fotos").glob("vista_*.jpg"))
    fachada = salida / "fachada.png"
    if not fachada.exists() and (salida / "frontal.png").exists():
        fachada = salida / "frontal.png"
    if not vistas or not fachada.exists():
        return
    foto = Image.open(vistas[0]).convert("RGB")
    rend = Image.open(fachada).convert("RGB")
    h = 880

    def fit(im):
        return im.resize((int(im.width * h / im.height), h), Image.LANCZOS)

    foto, rend = fit(foto), fit(rend)
    gap, pad = 24, 24
    canvas = Image.new("RGB", (pad * 2 + foto.width + gap + rend.width, h + pad * 2 + 40), (245, 245, 245))
    canvas.paste(foto, (pad, pad + 36))
    canvas.paste(rend, (pad + foto.width + gap, pad + 36))
    draw = ImageDraw.Draw(canvas)
    draw.text((pad, 12), f"foto SV - lote_{lot_index}", fill=(30, 30, 30))
    draw.text((pad + foto.width + gap, 12), f"generacion theta - lote_{lot_index}", fill=(30, 30, 30))
    canvas.save(lot_dir / "comparacion.png")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cuadra", type=Path, required=True)
    parser.add_argument("--lot", type=int, default=None)
    parser.add_argument("--size", type=int, default=640)
    parser.add_argument("--only-theta", action="store_true",
                        help="valida que cada lote tenga theta.json, sin generar")
    args = parser.parse_args()
    cuadra = args.cuadra.resolve()
    lot_dirs = sorted(cuadra.glob("lote_*"))
    if args.lot is not None:
        lot_dirs = [cuadra / f"lote_{args.lot}"]
    missing, failed, done = [], [], []
    for lot_dir in lot_dirs:
        theta_path = lot_dir / "theta.json"
        if not theta_path.exists():
            missing.append(lot_dir.name)
            continue
        if args.only_theta:
            done.append(lot_dir.name)
            continue
        try:
            request = build_request(lot_dir, theta_path)
            run_theta(request, lot_dir / "salida", size=args.size)
            render_fachada(request, lot_dir / "salida")
            build_comparacion(lot_dir, lot_dir / "salida", int(lot_dir.name.split("_")[1]))
            done.append(lot_dir.name)
            print(f"{lot_dir.name}: OK", flush=True)
        except Exception as error:
            failed.append((lot_dir.name, f"{type(error).__name__}: {error}"))
            print(f"{lot_dir.name}: FALLO {type(error).__name__}: {error}", flush=True)
    print(f"hechos={len(done)} sin_theta={len(missing)} fallidos={len(failed)}")
    for name in missing:
        print(f"  sin theta: {name}")
    for name, error in failed:
        print(f"  fallo: {name}: {error}")


if __name__ == "__main__":
    main()
