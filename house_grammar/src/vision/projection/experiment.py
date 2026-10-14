"""Offline experiment runner consuming the saved camera-selection manifest."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path

import cv2
import numpy as np

from .rectilinear import PinholeCamera, extract_rectilinear


def main(step: int, output_default: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=f"Paso {step}: proyección rectilínea offline")
    parser.add_argument("--manifest", type=Path, default=root / "steps/step5_cylindrical_facade/outputs/lot_-12.135895_-77.019184/projection_metadata.json")
    parser.add_argument("--output", type=Path, default=output_default)
    parser.add_argument("--width", type=int, default=1200)
    parser.add_argument("--height", type=int, default=900)
    parser.add_argument("--horizontal-fov-deg", type=float, default=90)
    if step == 4:
        parser.add_argument("--pitches", type=float, nargs="+", default=[-30, 0, 30, 60])
    args = parser.parse_args()
    pitches = list(dict.fromkeys(args.pitches)) if step == 4 else [0.0]
    # Validate all requested configurations before writing any output.
    for pitch in pitches:
        PinholeCamera(args.width, args.height, args.horizontal_fov_deg, pitch_deg=pitch)
    manifest = args.manifest.resolve()
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    cameras = payload["cameras"]
    if not cameras:
        raise ValueError("El manifiesto no contiene cámaras")
    for entry in cameras:
        source = manifest.parent / entry["raw_image"]
        if not source.is_file():
            raise FileNotFoundError(f"Falta panorama local: {source}. Ejecuta make run-gsv-step5")
    args.output.mkdir(parents=True, exist_ok=True)
    records, rows = [], []
    for index, entry in enumerate(cameras, 1):
        source = manifest.parent / entry["raw_image"]
        panorama = cv2.imread(str(source))
        if panorama is None:
            raise ValueError(f"No se puede decodificar {source}")
        tiles = []
        for pitch in pitches:
            camera = PinholeCamera(args.width, args.height, args.horizontal_fov_deg,
                                   float(entry["relative_yaw_deg"]), pitch)
            view = extract_rectilinear(panorama, camera)
            name = f"{index:02d}_pitch_{pitch:+g}.png"
            if not cv2.imwrite(str(args.output / name), view):
                raise OSError(f"No se pudo guardar {name}")
            records.append({"pano_id": entry["pano_id"], "date": entry.get("date"),
                            "source_image": str(source), "image": name,
                            "target_bearing_deg": entry["target_bearing_deg"],
                            "camera": asdict(camera), "K": camera.intrinsics.tolist(),
                            "vertical_fov_deg": camera.vertical_fov_deg,
                            "camera_to_panorama": camera.camera_to_panorama.tolist()})
            thumb = cv2.resize(view, (400, round(400*args.height/args.width)))
            thumb = cv2.copyMakeBorder(thumb, 32, 0, 0, 0, cv2.BORDER_CONSTANT)
            cv2.putText(thumb, f"Cam {index} | pitch {pitch:+g} deg", (8, 22),
                        cv2.FONT_HERSHEY_SIMPLEX, .55, (255, 255, 255), 1, cv2.LINE_AA)
            tiles.append(thumb)
        rows.append(np.concatenate(tiles, axis=1))
        print(f"[{index}/{len(cameras)}] {entry['pano_id']}: {len(pitches)} vistas", flush=True)
    if not cv2.imwrite(str(args.output / "comparison.jpg"), np.concatenate(rows, axis=0)):
        raise OSError("No se pudo guardar comparison.jpg")
    report = {"schema_version": 1, "step": step, "projection": "rectilinear",
              "source_manifest": str(manifest), "target_objectid": payload.get("target_objectid"),
              "target_coordinate": payload.get("target_coordinate"),
              "orientation_assumption": "upright panorama; source pitch/roll not applied",
              "frame": "panorama X right Y up Z center; camera X right Y down Z forward",
              "views": records}
    (args.output / "projection_metadata.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(f"Resultados: {args.output.resolve()}")
