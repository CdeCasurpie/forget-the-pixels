"""Descarga fotos 360 de poses a data/fotos_barranco, marcando el JSON.

Lee data/poses_barranco/metadata.json y descarga todas o un subconjunto.
Cada pose descargada queda marcada (image_downloaded + image) con escritura
atomica, asi que se puede interrumpir y retomar.

Uso (NO ejecutar sin avisar: son miles de requests a Google):
    python scripts/descargar_fotos.py --max-n 20
    python scripts/descargar_fotos.py --todos --zoom 3
    python scripts/descargar_fotos.py --pano-ids aBc123 XyZ456
    python scripts/descargar_fotos.py --solo-faltantes --max-n 200
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import streetlevel.streetview as sv
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
META = ROOT / "data" / "poses_barranco" / "metadata.json"
FOTOS = ROOT / "data" / "fotos_barranco"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--todos", action="store_true")
    group.add_argument("--solo-faltantes", action="store_true")
    group.add_argument("--max-n", type=int, default=None)
    group.add_argument("--pano-ids", nargs="+", default=None)
    parser.add_argument("--reintentar-fallos", action="store_true",
                        help="reintenta poses marcadas como muertas")
    parser.add_argument("--zoom", type=int, default=3)
    parser.add_argument("--quality", type=int, default=92)
    args = parser.parse_args()

    metadata = json.loads(META.read_text())
    panos = metadata["panoramas"]
    if args.pano_ids:
        ids = [i for i in args.pano_ids if i in panos]
    elif args.solo_faltantes:
        ids = [k for k, v in panos.items() if not v.get("image_downloaded")]
    else:
        ids = list(panos.keys())
    if not args.reintentar_fallos:
        vivas = [i for i in ids if not panos[i].get("descarga_muerta")]
        muertas = len(ids) - len(vivas)
        if muertas:
            print(f"se omiten {muertas} poses marcadas muertas (usa --reintentar-fallos)", flush=True)
        ids = vivas
    if args.max_n is not None:
        ids = ids[:args.max_n]
    FOTOS.mkdir(parents=True, exist_ok=True)
    MB_POR_ZOOM = {1: 0.3, 2: 0.7, 3: 1.5, 4: 4.0, 5: 9.0}
    mediana_mb = MB_POR_ZOOM.get(args.zoom, 1.5)  # medido: zoom3 q92 ~1.5MB
    pendientes = [i for i in ids if not (FOTOS / f"{i}.jpg").exists()]
    estimado_mb = len(pendientes) * mediana_mb
    print(f"poses objetivo: {len(ids)} | ya en disco: {len(ids) - len(pendientes)} | "
          f"a descargar: {len(pendientes)} | estimado: ~{estimado_mb / 1024:.1f} GB", flush=True)
    ok, fallo = 0, 0
    barra = tqdm(ids, desc="descargando", unit="pano")
    try:
        for pano_id in barra:
            destino = FOTOS / f"{pano_id}.jpg"
            barra.set_postfix_str(f"ok={ok} fallo={fallo}")
            try:
                if not destino.exists():
                    image = sv.get_panorama(sv.find_panorama_by_id(pano_id), zoom=args.zoom)
                    if image is None:
                        raise RuntimeError("sin imagen")
                    image.save(destino, "JPEG", quality=args.quality)
                panos[pano_id]["image_downloaded"] = True
                panos[pano_id]["image"] = str(destino.relative_to(ROOT))
                ok += 1
            except Exception as error:
                fallo += 1
                panos[pano_id]["descarga_muerta"] = f"{type(error).__name__}: {error}"
                barra.write(f"  {pano_id} FALLO: {type(error).__name__}: {error}")
            if (ok + fallo) % 25 == 0:
                tmp = META.with_suffix(".tmp")
                tmp.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
                os.replace(tmp, META)
    except KeyboardInterrupt:
        barra.write("cancelado por el usuario: guardando estado...")
    finally:
        barra.close()
        tmp = META.with_suffix(".tmp")
        tmp.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, META)
        print(f"estado guardado: ok={ok} fallo={fallo} "
              f"(retoma con --solo-faltantes, lo descargado no se repite)", flush=True)


if __name__ == "__main__":
    main()
