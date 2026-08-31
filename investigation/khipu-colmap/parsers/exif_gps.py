"""
Parser de GPS para fotos con metadata EXIF (típico de celulares).

Cuando el usuario toma fotos con un celular (sin video ni .SRT), cada .jpg
contiene las coordenadas GPS embebidas en los tags EXIF. Este parser las
extrae y genera el geo_priors.txt para COLMAP.
"""
import os
import math
from pathlib import Path

try:
    from PIL import Image
    from PIL.ExifTags import TAGS, GPSTAGS
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


def latlon_to_ecef(lat: float, lon: float, alt: float) -> tuple:
    """Convierte lat/lon/alt a ECEF (misma función que en dji_srt.py)."""
    a = 6378137.0
    e2 = 0.00669437999014
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    N = a / math.sqrt(1 - e2 * math.sin(lat_rad) ** 2)
    x = (N + alt) * math.cos(lat_rad) * math.cos(lon_rad)
    y = (N + alt) * math.cos(lat_rad) * math.sin(lon_rad)
    z = (N * (1 - e2) + alt) * math.sin(lat_rad)
    return x, y, z


def _dms_to_decimal(dms_tuple, ref: str) -> float:
    """Convierte coordenadas DMS (degrees, minutes, seconds) a decimal."""
    degrees, minutes, seconds = dms_tuple
    decimal = float(degrees) + float(minutes) / 60.0 + float(seconds) / 3600.0
    if ref in ('S', 'W'):
        decimal = -decimal
    return decimal


def extract_gps_from_exif(image_path: str) -> tuple:
    """
    Extrae lat, lon, alt de los tags EXIF de una imagen.

    Returns:
        Tupla (lat, lon, alt) o None si no tiene GPS
    """
    if not HAS_PIL:
        raise ImportError("Se necesita Pillow: pip install Pillow")

    img = Image.open(image_path)
    exif_data = img._getexif()
    if exif_data is None:
        return None

    gps_info = {}
    for tag_id, value in exif_data.items():
        tag_name = TAGS.get(tag_id, tag_id)
        if tag_name == "GPSInfo":
            for gps_tag_id, gps_value in value.items():
                gps_tag_name = GPSTAGS.get(gps_tag_id, gps_tag_id)
                gps_info[gps_tag_name] = gps_value

    if not gps_info or 'GPSLatitude' not in gps_info:
        return None

    lat = _dms_to_decimal(gps_info['GPSLatitude'], gps_info.get('GPSLatitudeRef', 'N'))
    lon = _dms_to_decimal(gps_info['GPSLongitude'], gps_info.get('GPSLongitudeRef', 'E'))
    alt = float(gps_info.get('GPSAltitude', 0))

    # Verificar referencia de altitud (0 = sobre el nivel del mar, 1 = bajo)
    alt_ref = gps_info.get('GPSAltitudeRef', 0)
    if alt_ref == 1:
        alt = -alt

    return lat, lon, alt


def generate_geo_priors(image_dir: str, output_path: str = "geo_priors.txt") -> int:
    """
    Genera geo_priors.txt a partir de fotos con EXIF GPS.

    Args:
        image_dir: Directorio con las imágenes .jpg
        output_path: Ruta de salida para geo_priors.txt

    Returns:
        Número de imágenes con GPS encontradas
    """
    image_dir = Path(image_dir)
    extensions = {'.jpg', '.jpeg', '.png', '.tif', '.tiff'}
    images = sorted([
        f for f in image_dir.iterdir()
        if f.suffix.lower() in extensions
    ])

    if not images:
        raise ValueError(f"No se encontraron imágenes en {image_dir}")

    lines_written = 0
    skipped = 0
    with open(output_path, 'w') as out:
        for img_path in images:
            try:
                result = extract_gps_from_exif(str(img_path))
                if result is None:
                    skipped += 1
                    continue
                lat, lon, alt = result
                x, y, z = latlon_to_ecef(lat, lon, alt)
                out.write(f"{img_path.name} {x} {y} {z}\n")
                lines_written += 1
            except Exception as e:
                print(f"[ERROR] leyendo EXIF de {img_path.name}: {e}")
                skipped += 1

    print(f"[INFO] {lines_written} imágenes con GPS, {skipped} sin GPS (omitidas)")
    return lines_written


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Uso: python exif_gps.py <directorio_imagenes>")
        sys.exit(1)
    n = generate_geo_priors(sys.argv[1])
    print(f"[OK] geo_priors.txt generado con {n} coordenadas EXIF")
