"""
Parser de GPS manual desde archivo CSV.

Para cuando el usuario tiene coordenadas de una fuente externa
(receptor GPS dedicado, post-procesamiento RTK, etc.).

Formato esperado del CSV:
    filename,lat,lon,alt
    frame_0001.jpg,-12.1234,-77.0345,150.2
    frame_0002.jpg,-12.1235,-77.0346,150.3
"""
import csv
import math


def latlon_to_ecef(lat: float, lon: float, alt: float) -> tuple:
    """Convierte lat/lon/alt a ECEF."""
    a = 6378137.0
    e2 = 0.00669437999014
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    N = a / math.sqrt(1 - e2 * math.sin(lat_rad) ** 2)
    x = (N + alt) * math.cos(lat_rad) * math.cos(lon_rad)
    y = (N + alt) * math.cos(lat_rad) * math.sin(lon_rad)
    z = (N * (1 - e2) + alt) * math.sin(lat_rad)
    return x, y, z


def generate_geo_priors(csv_path: str, output_path: str = "geo_priors.txt") -> int:
    """
    Genera geo_priors.txt a partir de un CSV manual.

    Args:
        csv_path: Ruta al archivo CSV con columnas filename,lat,lon,alt
        output_path: Ruta de salida para geo_priors.txt

    Returns:
        Número de líneas escritas
    """
    lines_written = 0
    with open(csv_path, 'r') as f_in, open(output_path, 'w') as f_out:
        reader = csv.DictReader(f_in)

        required = {'filename', 'lat', 'lon', 'alt'}
        if not required.issubset(set(reader.fieldnames or [])):
            raise ValueError(
                f"El CSV debe tener las columnas: {required}. "
                f"Columnas encontradas: {reader.fieldnames}"
            )

        for row in reader:
            lat = float(row['lat'])
            lon = float(row['lon'])
            alt = float(row['alt'])
            x, y, z = latlon_to_ecef(lat, lon, alt)
            f_out.write(f"{row['filename']} {x} {y} {z}\n")
            lines_written += 1

    return lines_written


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Uso: python manual_gps.py <archivo.csv>")
        print("Formato CSV: filename,lat,lon,alt")
        sys.exit(1)
    n = generate_geo_priors(sys.argv[1])
    print(f"[OK] geo_priors.txt generado con {n} coordenadas desde CSV")
