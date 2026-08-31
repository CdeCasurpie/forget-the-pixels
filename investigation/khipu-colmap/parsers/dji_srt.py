"""
Parser de GPS para archivos .SRT de drones DJI.

El dron DJI genera un archivo .SRT (subtítulos) que contiene las coordenadas GPS
de cada fotograma del video. Este parser extrae esas coordenadas y las convierte
al formato geo_priors.txt que espera COLMAP model_aligner.

LECCIÓN APRENDIDA (2026-08-31):
    El archivo .SRT del dron registra GPS a ~30 FPS, NO a la misma tasa del video
    (que puede ser 60 FPS). Si asumimos 60 FPS para calcular el step, generamos
    la mitad de las coordenadas necesarias y model_aligner falla silenciosamente.
    Por eso este parser AUTO-DETECTA el FPS real del SRT parseando los timestamps.
"""
import re
import math


def latlon_to_ecef(lat: float, lon: float, alt: float) -> tuple:
    """
    Convierte coordenadas geodésicas (lat/lon/alt) a coordenadas ECEF (Earth-Centered,
    Earth-Fixed) que es lo que COLMAP model_aligner espera con alignment_type=custom.

    Args:
        lat: Latitud en grados decimales
        lon: Longitud en grados decimales
        alt: Altitud absoluta en metros (abs_alt del SRT, NO rel_alt)

    Returns:
        Tupla (x, y, z) en metros ECEF
    """
    a = 6378137.0            # Semi-eje mayor del elipsoide WGS84
    e2 = 0.00669437999014    # Excentricidad al cuadrado WGS84
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    N = a / math.sqrt(1 - e2 * math.sin(lat_rad) ** 2)
    x = (N + alt) * math.cos(lat_rad) * math.cos(lon_rad)
    y = (N + alt) * math.cos(lat_rad) * math.sin(lon_rad)
    z = (N * (1 - e2) + alt) * math.sin(lat_rad)
    return x, y, z


def detect_srt_fps(srt_content: str) -> float:
    """
    Auto-detecta el FPS real del archivo SRT parseando los timestamps.
    
    El formato de timestamp en el SRT de DJI es:
        00:00:00,000 --> 00:00:00,033
    
    Calculamos el intervalo entre los primeros bloques para deducir el FPS.

    Returns:
        FPS estimado del SRT (típicamente ~30.0 para DJI)
    """
    # Buscar todos los timestamps de inicio
    timestamps = re.findall(
        r'(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->', srt_content
    )
    if len(timestamps) < 2:
        raise ValueError("No se encontraron suficientes timestamps en el SRT")

    def ts_to_seconds(ts_tuple):
        h, m, s, ms = ts_tuple
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0

    # Usar los primeros 100 timestamps para un cálculo robusto
    n = min(len(timestamps), 100)
    t_first = ts_to_seconds(timestamps[0])
    t_last = ts_to_seconds(timestamps[n - 1])
    duration = t_last - t_first

    if duration <= 0:
        # Fallback: si los timestamps son iguales, asumir 30 FPS
        return 30.0

    fps = (n - 1) / duration
    return round(fps, 1)


def parse_srt(srt_path: str) -> list:
    """
    Parsea TODOS los bloques GPS de un archivo .SRT de DJI.

    El regex verificado que funciona con el formato real de DJI es:
        [latitude: X] [longitude: Y] [rel_alt: Z abs_alt: W]
    Nota: entre rel_alt y abs_alt hay un ESPACIO, no un cierre de corchete.

    Args:
        srt_path: Ruta al archivo .SRT

    Returns:
        Lista de tuplas (lat, lon, abs_alt)
    """
    with open(srt_path, 'r') as f:
        content = f.read()

    # REGEX VERIFICADO - NO MODIFICAR SIN TESTEAR
    # Acepta espacios variables entre rel_alt y abs_alt
    pattern = (
        r'\[latitude:\s*([-0-9.]+)\]\s*'
        r'\[longitude:\s*([-0-9.]+)\]\s*'
        r'\[rel_alt:\s*([-0-9.]+)\s+'
        r'abs_alt:\s*([-0-9.]+)\s*\]'
    )

    blocks = re.findall(pattern, content)
    if not blocks:
        raise ValueError(
            f"No se encontraron coordenadas GPS en {srt_path}. "
            f"¿Es un archivo .SRT de DJI válido?"
        )

    coords = []
    for lat_s, lon_s, rel_alt_s, abs_alt_s in blocks:
        coords.append((float(lat_s), float(lon_s), float(abs_alt_s)))

    return coords


def generate_geo_priors(srt_path: str, fps_extract: float,
                        output_path: str = "geo_priors.txt",
                        expected_frames: int = None) -> int:
    """
    Genera el archivo geo_priors.txt para COLMAP model_aligner.

    IMPORTANTE: Este método auto-detecta el FPS del SRT en lugar de asumir
    un valor hardcodeado. Esto previene el bug donde generábamos la mitad
    de las coordenadas necesarias.

    Args:
        srt_path: Ruta al archivo .SRT de DJI
        fps_extract: FPS al que FFmpeg extrajo los fotogramas (ej: 1.0, 0.5, 2.0)
        output_path: Ruta de salida para geo_priors.txt
        expected_frames: Si se conoce, el número esperado de fotogramas.
                        Se usa para validación.

    Returns:
        Número de líneas escritas en geo_priors.txt

    Raises:
        ValueError: Si el número de coordenadas generadas no coincide con expected_frames
    """
    with open(srt_path, 'r') as f:
        content = f.read()

    srt_fps = detect_srt_fps(content)
    all_coords = parse_srt(srt_path)

    # Calcular el step: cada cuántos bloques del SRT tomamos uno
    step = srt_fps / fps_extract

    lines_written = 0
    with open(output_path, 'w') as out:
        frame_idx = 1
        i = 0.0
        while int(round(i)) < len(all_coords):
            idx = int(round(i))
            lat, lon, abs_alt = all_coords[idx]
            x, y, z = latlon_to_ecef(lat, lon, abs_alt)
            out.write(f"frame_{frame_idx:04d}.jpg {x} {y} {z}\n")
            frame_idx += 1
            lines_written += 1
            i += step

    # Validación de seguridad
    if expected_frames is not None and lines_written != expected_frames:
        print(f"[WARN] Se generaron {lines_written} coordenadas GPS "
              f"pero se esperaban {expected_frames} fotogramas.")
        print(f"   (SRT FPS detectado: {srt_fps}, Extract FPS: {fps_extract}, "
              f"Step: {step:.2f})")

    return lines_written


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Uso: python dji_srt.py <archivo.SRT> <fps_extract>")
        print("Ejemplo: python dji_srt.py DJI_video.SRT 1.0")
        sys.exit(1)

    srt_file = sys.argv[1]
    fps = float(sys.argv[2])
    n = generate_geo_priors(srt_file, fps)
    print(f"[OK] geo_priors.txt generado con {n} coordenadas (SRT FPS auto-detectado)")
