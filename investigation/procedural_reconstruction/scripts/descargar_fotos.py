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
    if args.max_n is not None:
        ids = ids[:args.max_n]
    FOTOS.mkdir(parents=True, exist_ok=True)
    print(f"poses objetivo: {len(ids)} (zoom {args.zoom})", flush=True)
    ok, fallo = 0, 0
    for n, pano_id in enumerate(ids, 1):
        destino = FOTOS / f"{pano_id}.jpg"
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
            print(f"  [{n}/{len(ids)}] {pano_id} FALLO: {error}", flush=True)
            continue
        if n % 25 == 0 or n == len(ids):
            tmp = META.with_suffix(".tmp")
            tmp.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, META)
            print(f"  [{n}/{len(ids)}] ok={ok} fallo={fallo} (progreso guardado)", flush=True)
    print(f"listo: ok={ok} fallo={fallo}", flush=True)


if __name__ == "__main__":
    main()
