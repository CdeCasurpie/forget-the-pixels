#!/usr/bin/env python3
"""
khipu-colmap: Mini-framework para ejecutar COLMAP en el clúster Khipu de UTEC.

Uso:
    python colmap_pipeline.py validate config.yaml   # Verifica todo antes de gastar GPU
    python colmap_pipeline.py run config.yaml         # Genera workspace + envía job SLURM

Nacido de 5 iteraciones fallidas y 7 bugs distintos. Cada validación que hace
este script previene un error real que nos costó horas de debugging.

Autor: César Perales (Tesis PFC1 - UTEC 2026)
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from string import Template

# ============================================================
# ANSI COLORS
# ============================================================
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

def print_ok(msg): print(f"{Colors.GREEN}[OK]{Colors.RESET} {msg}")
def print_err(msg): print(f"{Colors.RED}[ERROR]{Colors.RESET} {msg}")
def print_warn(msg): print(f"{Colors.YELLOW}[WARN]{Colors.RESET} {msg}")
def print_info(msg): print(f"{Colors.CYAN}[INFO]{Colors.RESET} {msg}")

# ============================================================
# CONSTANTES DE KHIPU (aprendidas con dolor)
# ============================================================
COLMAP_BIN = "/home/cesar.perales/.conda/envs/colmap_env/bin/colmap"
PYTHON_BIN = "/home/cesar.perales/.conda/envs/colmap_env/bin/python"
FFMPEG_BIN = "/home/cesar.perales/bin/ffmpeg"
COLMAP_VERSION = "3.13.0"
MAX_MEM_GB = 64  # QOSMaxMemoryPerUser en Khipu

# Flags que NO existen en COLMAP 3.13.0 (nos quemaron 2 veces)
BANNED_FLAGS = ["--robust_alignment"]

# ============================================================
# CARGA DE CONFIGURACIÓN
# ============================================================
def load_config(config_path: str) -> dict:
    """Carga un archivo de configuración YAML o JSON."""
    path = Path(config_path)
    if not path.exists():
        print_err(f"Archivo de configuración no encontrado: {config_path}")
        sys.exit(1)

    content = path.read_text()

    # Intentar YAML primero, luego JSON
    try:
        import yaml
        config = yaml.safe_load(content)
    except ImportError:
        try:
            config = json.loads(content)
        except json.JSONDecodeError:
            print_err("No se pudo parsear el config. Instala PyYAML o usa formato JSON.")
            print_info("pip install pyyaml")
            sys.exit(1)

    return config


# ============================================================
# VALIDADOR (El Guardián Anti-Bugs)
# ============================================================
class Validator:
    """Ejecuta las 10 validaciones aprendidas de nuestros errores."""

    def __init__(self, config: dict):
        self.config = config
        self.errors = []
        self.warnings = []

    def _err(self, msg: str):
        self.errors.append(msg)

    def _warn(self, msg: str):
        self.warnings.append(msg)

    def _ok(self, msg: str):
        print_ok(msg)

    def check_video_source(self):
        """[1/10] ¿El video fuente existe?"""
        src = os.path.expanduser(self.config.get("video_source", ""))
        if not src:
            self._err("[1/10] No se especificó 'video_source' en el config")
        elif not os.path.isfile(src):
            self._err(f"[1/10] Video no encontrado: {src}")
        else:
            size_mb = os.path.getsize(src) / (1024 * 1024)
            self._ok(f"[1/10] Video encontrado: {src} ({size_mb:.0f} MB)")

    def check_gps_source(self):
        """[2/10] ¿El archivo GPS existe y es parseable?"""
        gps = self.config.get("gps_source", {})
        gps_type = gps.get("type", "none")

        if gps_type == "none":
            self._ok("[2/10] Sin GPS (modo: coordenadas locales)")
            return

        gps_file = os.path.expanduser(gps.get("file", ""))
        if not gps_file:
            self._err(f"[2/10] gps_source.type='{gps_type}' pero no se especificó 'file'")
            return

        if not os.path.isfile(gps_file):
            self._err(f"[2/10] Archivo GPS no encontrado: {gps_file}")
            return

        self._ok(f"[2/10] Archivo GPS encontrado: {gps_file}")

    def check_gps_regex(self):
        """[3/10] ¿El parser de GPS detecta coordenadas?"""
        gps = self.config.get("gps_source", {})
        gps_type = gps.get("type", "none")

        if gps_type == "none":
            self._ok("[3/10] Sin GPS - omitiendo validación de regex")
            return

        gps_file = os.path.expanduser(gps.get("file", ""))
        if not os.path.isfile(gps_file):
            return  # Ya reportado en check_gps_source

        if gps_type == "dji_srt":
            try:
                sys.path.insert(0, str(Path(__file__).parent))
                from parsers.dji_srt import parse_srt, detect_srt_fps
                with open(gps_file, 'r') as f:
                    content = f.read()
                coords = parse_srt(gps_file)
                srt_fps = detect_srt_fps(content)
                self._ok(f"[3/10] SRT parseado: {len(coords)} bloques GPS, "
                         f"SRT FPS auto-detectado: {srt_fps}")
            except Exception as e:
                self._err(f"[3/10] Error parseando SRT: {e}")
        elif gps_type == "csv":
            import csv
            with open(gps_file, 'r') as f:
                reader = csv.DictReader(f)
                cols = set(reader.fieldnames or [])
                required = {'filename', 'lat', 'lon', 'alt'}
                if not required.issubset(cols):
                    self._err(f"[3/10] CSV no tiene columnas requeridas {required}. "
                              f"Tiene: {cols}")
                else:
                    rows = sum(1 for _ in reader)
                    self._ok(f"[3/10] CSV válido: {rows} filas de coordenadas")
        elif gps_type == "exif":
            self._ok("[3/10] EXIF GPS - se validará al procesar las imágenes")

    def check_workspace_clean(self):
        """[4/10] ¿El directorio de trabajo está limpio?"""
        name = self.config.get("experiment_name", "unnamed")
        base = os.path.expanduser(self.config.get("workspace_base",
                                                   "~/tesis_colmap"))
        workspace = os.path.join(base, name)

        if os.path.exists(workspace):
            contents = os.listdir(workspace)
            if "database.db" in contents or "sparse" in contents:
                self._warn(f"[4/10] Workspace tiene archivos residuales: {workspace}")
                self._warn("       Usa 'python colmap_pipeline.py run --clean config.yaml' "
                           "para borrar y empezar de cero")
            else:
                self._ok(f"[4/10] Workspace existe pero sin residuos: {workspace}")
        else:
            self._ok(f"[4/10] Workspace limpio (se creará): {workspace}")

    def check_colmap_binary(self):
        """[5/10] ¿El binario de COLMAP existe?"""
        if os.path.isfile(COLMAP_BIN):
            self._ok(f"[5/10] COLMAP encontrado: {COLMAP_BIN}")
        else:
            self._err(f"[5/10] COLMAP no encontrado: {COLMAP_BIN}")

    def check_ffmpeg_binary(self):
        """[6/10] ¿FFmpeg existe?"""
        if os.path.isfile(FFMPEG_BIN):
            self._ok(f"[6/10] FFmpeg encontrado: {FFMPEG_BIN}")
        else:
            self._err(f"[6/10] FFmpeg no encontrado: {FFMPEG_BIN}")

    def check_python_binary(self):
        """[7/10] ¿Python del conda env existe?"""
        if os.path.isfile(PYTHON_BIN):
            self._ok(f"[7/10] Python encontrado: {PYTHON_BIN}")
        else:
            self._err(f"[7/10] Python no encontrado: {PYTHON_BIN}")

    def check_memory_limit(self):
        """[8/10] ¿La memoria solicitada no excede el límite de Khipu?"""
        slurm = self.config.get("slurm", {})
        mem_str = slurm.get("mem", "64G")
        mem_gb = int(re.match(r'(\d+)', mem_str).group(1))
        if mem_gb > MAX_MEM_GB:
            self._err(f"[8/10] Memoria solicitada ({mem_gb}G) excede el límite "
                      f"de Khipu ({MAX_MEM_GB}G)")
        else:
            self._ok(f"[8/10] Memoria OK: {mem_gb}G <= {MAX_MEM_GB}G")

    def check_colmap_flags(self):
        """[9/10] ¿Los flags son compatibles con COLMAP 3.13.0?"""
        # Serializar todo el config a string y buscar flags baneados
        config_str = json.dumps(self.config)
        found_banned = [f for f in BANNED_FLAGS if f.lstrip('-') in config_str]
        if found_banned:
            self._err(f"[9/10] Flags incompatibles con COLMAP {COLMAP_VERSION}: "
                      f"{found_banned}")
        else:
            self._ok(f"[9/10] Flags compatibles con COLMAP {COLMAP_VERSION}")

    def check_gps_frame_sync(self):
        """[10/10] ¿El GPS generará suficientes coordenadas para los fotogramas?"""
        gps = self.config.get("gps_source", {})
        gps_type = gps.get("type", "none")
        extraction = self.config.get("extraction", {})
        fps = extraction.get("fps", 1.0)

        if gps_type == "none":
            self._ok("[10/10] Sin GPS - no hay sincronización que validar")
            return

        if gps_type != "dji_srt":
            self._ok("[10/10] Sincronización GPS/frames - N/A para este tipo de GPS")
            return

        gps_file = os.path.expanduser(gps.get("file", ""))
        if not os.path.isfile(gps_file):
            return

        try:
            from parsers.dji_srt import parse_srt, detect_srt_fps
            with open(gps_file, 'r') as f:
                content = f.read()
            all_coords = parse_srt(gps_file)
            srt_fps = detect_srt_fps(content)
            step = srt_fps / fps
            expected_gps = int(len(all_coords) / step)
            video_duration_s = len(all_coords) / srt_fps
            expected_frames = int(video_duration_s * fps)

            if abs(expected_gps - expected_frames) <= 2:
                self._ok(f"[10/10] Sincronización GPS/frames OK: "
                         f"~{expected_gps} coords para ~{expected_frames} frames "
                         f"(Video: {video_duration_s:.0f}s, SRT: {srt_fps} fps, "
                         f"Extract: {fps} fps)")
            else:
                self._warn(f"[10/10] Posible desincronización: {expected_gps} coords GPS "
                           f"vs {expected_frames} frames esperados")
        except Exception as e:
            self._warn(f"[10/10] No se pudo validar sincronización: {e}")

    def run_all(self) -> bool:
        """Ejecuta todas las validaciones. Retorna True si pasa todo."""
        print(f"{Colors.BOLD}{Colors.CYAN}============================================================{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}[INFO] VALIDACION PRE-SUBMIT (khipu-colmap){Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}============================================================{Colors.RESET}")

        self.check_video_source()
        self.check_gps_source()
        self.check_gps_regex()
        self.check_workspace_clean()
        self.check_colmap_binary()
        self.check_ffmpeg_binary()
        self.check_python_binary()
        self.check_memory_limit()
        self.check_colmap_flags()
        self.check_gps_frame_sync()

        print()
        if self.warnings:
            print(f"{Colors.YELLOW}{Colors.BOLD}[ADVERTENCIAS]{Colors.RESET}")
            for w in self.warnings:
                print_warn(w)
            print()

        if self.errors:
            print(f"{Colors.RED}{Colors.BOLD}[ERRORES CRITICOS (el job NO sera enviado)]{Colors.RESET}")
            for e in self.errors:
                print_err(e)
            print(f"\n{Colors.RED}[FAIL]{Colors.RESET} Validacion FALLIDA ({len(self.errors)} errores)")
            return False
        else:
            print(f"{Colors.GREEN}{Colors.BOLD}[SUCCESS]{Colors.RESET} Validacion EXITOSA! El job esta listo para ser enviado.")
            return True


# ============================================================
# GENERADOR DE SCRIPT SLURM
# ============================================================
def generate_slurm_script(config: dict, workspace: str) -> str:
    """Genera el contenido del script SLURM basado en el config."""
    extraction = config.get("extraction", {})
    pipeline = config.get("pipeline", {})
    slurm = config.get("slurm", {})
    gps = config.get("gps_source", {})

    fps = extraction.get("fps", 1.0)
    resolution = extraction.get("resolution", 1080)
    quality = extraction.get("quality", 2)
    preset = pipeline.get("preset", "sparse_only")
    camera_model = pipeline.get("camera_model", "OPENCV")
    single_camera = "1" if pipeline.get("single_camera", True) else "0"
    overlap = pipeline.get("sequential_overlap", 20)
    max_error = pipeline.get("alignment_max_error", 3.0)
    use_cache = pipeline.get("fusion_use_cache", True)
    cache_size = pipeline.get("fusion_cache_size", 32)
    gps_type = gps.get("type", "none")

    mem = slurm.get("mem", "64G")
    time_limit = slurm.get("time", "12:00:00")
    cpus = slurm.get("cpus", 16)
    partition = slurm.get("partition", "gpu")

    lines = []
    lines.append("#!/bin/bash")
    lines.append(f"#SBATCH --job-name=colmap_{config.get('experiment_name', 'exp')}")
    lines.append(f"#SBATCH --partition={partition}")
    lines.append("#SBATCH --gres=gpu:1")
    lines.append("#SBATCH --ntasks=1")
    lines.append(f"#SBATCH --cpus-per-task={cpus}")
    lines.append(f"#SBATCH --mem={mem}")
    lines.append(f"#SBATCH --time={time_limit}")
    lines.append("#SBATCH --output=colmap_log_%j.out")
    lines.append("")
    lines.append("# === Fail-fast: abortar ante cualquier error ===")
    lines.append("set -euo pipefail")
    lines.append("")
    lines.append(f'COLMAP="{COLMAP_BIN}"')
    lines.append(f'PYTHON="{PYTHON_BIN}"')
    lines.append(f'FFMPEG="{FFMPEG_BIN}"')
    lines.append(f'WORKDIR="{workspace}"')
    lines.append("cd $WORKDIR")
    lines.append("")
    lines.append(f'echo "=== KHIPU-COLMAP: {config.get("experiment_name", "")} ==="')
    lines.append(f'echo "Preset: {preset} | FPS: {fps} | Resolucion: {resolution}p"')
    lines.append(f'echo "Inicio: $(date)"')
    lines.append("")

    step = 1
    total = {"sparse_only": 7, "sparse_and_dense": 11, "dense_resume": 2}
    total_steps = total.get(preset, 7)

    if preset != "dense_resume":
        lines.append(f'echo "[{step}/{total_steps}] Extrayendo fotogramas ({fps} FPS, {resolution}p)..."')
        lines.append("mkdir -p images sparse/0")
        lines.append(f'if [ ! -f "images/frame_0001.jpg" ]; then')
        lines.append(f'    $FFMPEG -i *.MP4 -vf "fps={fps},scale=-1:{resolution}" '
                      f'-qscale:v {quality} images/frame_%04d.jpg')
        lines.append("fi")
        lines.append("")
        lines.append("# Guard: verificar que se extrajeron imágenes")
        lines.append('NUM_IMAGES=$(ls images/*.jpg 2>/dev/null | wc -l)')
        lines.append('if [ "$NUM_IMAGES" -eq 0 ]; then')
        lines.append('    echo "[ERROR] FFmpeg no extrajo ninguna imagen"')
        lines.append('    exit 1')
        lines.append("fi")
        lines.append('echo "[OK] $NUM_IMAGES fotogramas extraidos"')
        lines.append("")
        step += 1

        if gps_type != "none":
            lines.append(f'echo "[{step}/{total_steps}] Parseando metadata GPS..."')
            lines.append(f"$PYTHON -c \"")
            lines.append(f"import sys; sys.path.insert(0, '$WORKDIR')")

            if gps_type == "dji_srt":
                lines.append(f"from parsers.dji_srt import generate_geo_priors")
                lines.append(f"import glob")
                lines.append(f"srt = glob.glob('*.SRT')[0]")
                lines.append(f"n = generate_geo_priors(srt, {fps})")
                lines.append(f"print(f'[OK] GPS: {{n}} coordenadas generadas')")
            elif gps_type == "csv":
                csv_name = os.path.basename(gps.get("file", "gps.csv"))
                lines.append(f"from parsers.manual_gps import generate_geo_priors")
                lines.append(f"n = generate_geo_priors('{csv_name}')")
                lines.append(f"print(f'[OK] GPS: {{n}} coordenadas generadas')")
            elif gps_type == "exif":
                lines.append(f"from parsers.exif_gps import generate_geo_priors")
                lines.append(f"n = generate_geo_priors('images/')")
                lines.append(f"print(f'[OK] GPS: {{n}} coordenadas generadas')")

            lines.append(f"\"")
            lines.append("")
            lines.append("# Guard: verificar que geo_priors.txt no está vacío")
            lines.append('if [ ! -s geo_priors.txt ]; then')
            lines.append('    echo "[ERROR] geo_priors.txt esta vacio o no existe"')
            lines.append('    exit 1')
            lines.append("fi")
            lines.append("")
            step += 1

        feature_extractor = pipeline.get("feature_extractor", "sift")
        if feature_extractor == "sift":
            lines.append(f'echo "[{step}/{total_steps}] Extraccion de caracteristicas (SIFT)..."')
            lines.append(f"$COLMAP feature_extractor \")
            lines.append(f"    --database_path database.db \")
            lines.append(f"    --image_path images/ \")
            lines.append(f"    --ImageReader.camera_model {camera_model} \")
            lines.append(f"    --ImageReader.single_camera {single_camera}")
            lines.append("")
            step += 1

            lines.append(f'echo "[{step}/{total_steps}] Emparejamiento secuencial..."')
            lines.append(f"$COLMAP sequential_matcher \")
            lines.append(f"    --database_path database.db \")
            lines.append(f"    --SequentialMatching.overlap {overlap}")
            lines.append("")
            step += 1

            lines.append(f'echo "[{step}/{total_steps}] Bundle Adjustment (Mapper)..."')
            lines.append(f"$COLMAP mapper \")
            lines.append(f"    --database_path database.db \")
            lines.append(f"    --image_path images/ \")
            lines.append(f"    --output_path sparse/0/")
            lines.append("")
        else:
            lines.append(f'echo "[{step}/{total_steps}] Extraccion y Matching con hloc ({feature_extractor})..."')
            lines.append(f'cat << "EOF_HLOC" > run_hloc.py')
            lines.append("import sys, os")
            lines.append("from pathlib import Path")
            lines.append("from hloc import extract_features, match_features, reconstruction")
            lines.append("images = Path('images/')")
            lines.append("outputs = Path('hloc_outputs/')")
            lines.append("outputs.mkdir(exist_ok=True)")
            
            # Using sequential pairs if it's a video
            lines.append("sfm_pairs = outputs / 'pairs.txt'")
            lines.append("sfm_dir = Path('sparse/0')")
            lines.append("sfm_dir.mkdir(parents=True, exist_ok=True)")
            
            ext = feature_extractor.split('_')[0]
            if ext == "superpoint": ext = "superpoint_aachen"
            
            lines.append(f"feature_conf = extract_features.confs['{ext}']")
            lines.append(f"matcher_conf = match_features.confs['{feature_extractor}']")
            
            lines.append("from hloc import pairs_from_sequence")
            lines.append(f"pairs_from_sequence.main(sfm_pairs, images, features=None, overlap={overlap}, quadratic_overlap=False)")
            lines.append("features = extract_features.main(feature_conf, images, outputs)")
            lines.append("matches = match_features.main(matcher_conf, sfm_pairs, features, outputs)")
            
            lines.append("reconstruction.main(sfm_dir, images, sfm_pairs, features, matches, image_list=[p.name for p in sorted(images.iterdir())])")
            lines.append("EOF_HLOC")
            
            lines.append(f"~/hloc_env/bin/python run_hloc.py")
            lines.append("")
            
            step += 2
        lines.append("# Guard: Auto-detectar subcarpeta del mapper")
        lines.append('SPARSE_MODEL=$(find sparse/0/ -name "cameras.bin" -printf "%h\\n" '
                      '| head -1)')
        lines.append('if [ -z "$SPARSE_MODEL" ]; then')
        lines.append('    echo "[ERROR] Mapper no genero ningun modelo en sparse/0/"')
        lines.append('    exit 1')
        lines.append("fi")
        lines.append('echo "[OK] Modelo sparse encontrado en: $SPARSE_MODEL"')
        lines.append("")
        step += 1

        if gps_type != "none":
            lines.append(f'echo "[{step}/{total_steps}] Alineacion GPS (Model Aligner)..."')
            lines.append("mkdir -p sparse/0_aligned")
            lines.append(f"$COLMAP model_aligner \\")
            lines.append(f"    --input_path $SPARSE_MODEL \\")
            lines.append(f"    --output_path sparse/0_aligned/ \\")
            lines.append(f"    --ref_images_path geo_priors.txt \\")
            lines.append(f"    --transform_path align_transform.txt \\")
            lines.append(f"    --alignment_type custom \\")
            lines.append(f"    --ref_is_gps 0 \\")
            lines.append(f"    --alignment_max_error {max_error}")
            lines.append("")
            lines.append("# Guard: verificar que la alineación produjo output")
            lines.append('if [ ! -f sparse/0_aligned/cameras.bin ]; then')
            lines.append('    echo "[WARN] Model Aligner fallo. '
                          'Continuando con modelo sin GPS..."')
            lines.append('    FINAL_SPARSE="$SPARSE_MODEL"')
            lines.append("else")
            lines.append('    echo "[OK] Alineacion GPS exitosa"')
            lines.append('    FINAL_SPARSE="sparse/0_aligned"')
            lines.append("fi")
            lines.append("")
            step += 1
        else:
            lines.append('FINAL_SPARSE="$SPARSE_MODEL"')
            lines.append("")

        lines.append(f'echo "[{step}/{total_steps}] Exportando nube sparse a PLY..."')
        lines.append(f"$COLMAP model_converter \\")
        lines.append(f"    --input_path $FINAL_SPARSE \\")
        lines.append(f"    --output_path sparse_result.ply \\")
        lines.append(f"    --output_type PLY")
        lines.append('echo "[OK] Nube sparse exportada: sparse_result.ply"')
        lines.append("")
        step += 1

    if preset in ("sparse_and_dense", "dense_resume"):
        if preset == "dense_resume":
            lines.append("# Modo: Dense Resume (solo fusion + meshing)")
            lines.append('FINAL_SPARSE=$(find sparse/ -name "cameras.bin" -printf "%h\\n" '
                          '| head -1)')
            step = 1

        if preset == "sparse_and_dense":
            lines.append(f'echo "[{step}/{total_steps}] Correccion de lentes (Undistorter)..."')
            lines.append(f"$COLMAP image_undistorter \\")
            lines.append(f"    --image_path images/ \\")
            lines.append(f"    --input_path $FINAL_SPARSE \\")
            lines.append(f"    --output_path dense/ \\")
            lines.append(f"    --output_type COLMAP")
            lines.append("")
            step += 1

            lines.append(f'echo "[{step}/{total_steps}] PatchMatch Stereo (Fase Densa)..."')
            lines.append(f"$COLMAP patch_match_stereo \\")
            lines.append(f"    --workspace_path dense/ \\")
            lines.append(f"    --workspace_format COLMAP \\")
            dense_max_size = pipeline.get("dense_max_image_size", None)
        if dense_max_size:
            lines.append(f"    --PatchMatchStereo.max_image_size {dense_max_size} \\")
            
        lines.append(f"    --PatchMatchStereo.geom_consistency true")
            lines.append("")
            step += 1

        cache_flag = "--StereoFusion.use_cache 1" if use_cache else ""
        cache_size_flag = f"--StereoFusion.cache_size {cache_size}" if use_cache else ""

        lines.append(f'echo "[{step}/{total_steps}] Stereo Fusion (con cache anti-OOM)..."')
        lines.append(f"$COLMAP stereo_fusion \\")
        lines.append(f"    --workspace_path dense/ \\")
        lines.append(f"    --workspace_format COLMAP \\")
        lines.append(f"    --input_type geometric \\")
        lines.append(f"    --output_path dense/fused.ply \\")
        if dense_max_size:
            lines.append(f"    --StereoFusion.max_image_size {dense_max_size} \\")
        lines.append(f"    {cache_flag} \\")
        lines.append(f"    {cache_size_flag}")
        lines.append("")
        lines.append("# Guard: verificar fused.ply")
        lines.append('if [ ! -f dense/fused.ply ]; then')
        lines.append('    echo "[ERROR] stereo_fusion no genero fused.ply"')
        lines.append('    exit 1')
        lines.append("fi")
        lines.append("")
        step += 1

        lines.append(f'echo "[{step}/{total_steps}] Poisson Meshing..."')
        lines.append(f"$COLMAP poisson_mesher \\")
        lines.append(f"    --input_path dense/fused.ply \\")
        lines.append(f"    --output_path dense/meshed-poisson.ply")
        lines.append("")
        step += 1

    lines.append('echo "=== PIPELINE COMPLETADO EXITOSAMENTE ==="')
    lines.append(f'echo "Fin: $(date)"')
    lines.append('ls -lh sparse_result.ply dense/*.ply 2>/dev/null || true')

    return "\n".join(lines)


# ============================================================
# EJECUTOR (Workspace + Submit)
# ============================================================
def run_pipeline(config: dict, clean: bool = False):
    """Crea el workspace, genera el script SLURM y lo envia a la cola."""
    # --- ESTIMACIÓN DE TIEMPOS ---
    import subprocess, math
    video_src = os.path.expanduser(config["video_source"])
    fps = config.get("extraction", {}).get("fps", 1.0)
    preset = config.get("pipeline", {}).get("preset", "sparse_only")
    dense_max_size = config.get("pipeline", {}).get("dense_max_image_size", None)
    
    try:
        res = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", video_src], capture_output=True, text=True)
        duration = float(res.stdout.strip())
        num_images = int(math.ceil(duration * fps))
        
        print_info(f"=== ESTIMACIÓN DE TIEMPO Y RECURSOS ===")
        print_info(f"Video origen: {video_src} ({duration:.1f} segundos)")
        print_info(f"Fotogramas estimados a extraer: ~{num_images} (a {fps} FPS)")
        
        if preset in ["sparse_and_dense", "dense_resume"]:
            # Patch match: 480p ~3s/img, 1080p ~15s/img
            is_480p = dense_max_size and int(dense_max_size) <= 854
            time_per_img = 3.0 if is_480p else 15.0
            total_sec = num_images * time_per_img
            print_warn(f"Patch Match Stereo (Dense) a {'480p' if is_480p else 'Alta resolución'}: ~{total_sec/60.0:.1f} minutos (Ojo: 1 GPU en SLURM).")
        
        resp = input(f"[93m¿Deseas continuar con la ejecución? (y/N): [0m")
        if resp.lower() not in ['y', 'yes']:
            print_err("Operación cancelada por el usuario.")
            sys.exit(0)
    except Exception as e:
        print_warn(f"No se pudo estimar el tiempo (requiere ffprobe): {e}")
    # -------------------------------
    name = config.get("experiment_name", "unnamed")
    base = os.path.expanduser(config.get("workspace_base", "~/tesis_colmap"))
    workspace = os.path.join(base, name)
    gps = config.get("gps_source", {})

    if clean and os.path.exists(workspace):
        print_info(f"Borrando workspace anterior: {workspace}")
        shutil.rmtree(workspace)

    os.makedirs(workspace, exist_ok=True)
    print_info(f"Workspace: {workspace}")

    video_src = os.path.expanduser(config["video_source"])
    video_dst = os.path.join(workspace, os.path.basename(video_src))
    if not os.path.exists(video_dst):
        print_info(f"Copiando video...")
        shutil.copy2(video_src, video_dst)

    gps_type = gps.get("type", "none")
    if gps_type != "none" and gps_type != "exif":
        gps_file = os.path.expanduser(gps.get("file", ""))
        if os.path.isfile(gps_file):
            gps_dst = os.path.join(workspace, os.path.basename(gps_file))
            if not os.path.exists(gps_dst):
                print_info(f"Copiando metadata GPS...")
                shutil.copy2(gps_file, gps_dst)

    parsers_src = os.path.join(os.path.dirname(__file__), "parsers")
    parsers_dst = os.path.join(workspace, "parsers")
    if os.path.isdir(parsers_src):
        if os.path.exists(parsers_dst):
            shutil.rmtree(parsers_dst)
        shutil.copytree(parsers_src, parsers_dst)
        print_ok(f"Parsers copiados al workspace")

    script_content = generate_slurm_script(config, workspace)
    script_path = os.path.join(workspace, "colmap_job.sh")
    with open(script_path, 'w') as f:
        f.write(script_content)
    os.chmod(script_path, 0o755)
    print_ok(f"Script SLURM generado: colmap_job.sh")

    print(f"\n{Colors.BOLD}{Colors.CYAN}[INFO] Enviando job a SLURM...{Colors.RESET}")
    result = subprocess.run(
        ["sbatch", "colmap_job.sh"],
        cwd=workspace,
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        job_id = result.stdout.strip().split()[-1]
        print(f"{Colors.GREEN}{Colors.BOLD}[SUCCESS]{Colors.RESET} Job enviado exitosamente! ID: {job_id}")
        print_info(f"Monitorear: tail -f {workspace}/colmap_log_{job_id}.out")
    else:
        print_err(f"Error enviando job: {result.stderr}")
        sys.exit(1)


# ============================================================
# CLI
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="khipu-colmap: Framework para COLMAP en Khipu",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python colmap_pipeline.py validate mi_config.yaml
  python colmap_pipeline.py run mi_config.yaml
  python colmap_pipeline.py run --clean mi_config.yaml
        """
    )
    parser.add_argument("command", choices=["validate", "run"],
                        help="'validate' para verificar, 'run' para ejecutar")
    parser.add_argument("config", help="Ruta al archivo de configuracion YAML/JSON")
    parser.add_argument("--clean", action="store_true",
                        help="Borrar workspace anterior antes de ejecutar")

    args = parser.parse_args()
    config = load_config(args.config)

    if args.command == "validate":
        validator = Validator(config)
        success = validator.run_all()
        sys.exit(0 if success else 1)

    elif args.command == "run":
        validator = Validator(config)
        success = validator.run_all()
        if not success:
            print(f"\n{Colors.RED}[FAIL]{Colors.RESET} Corrige los errores antes de enviar el job.")
            sys.exit(1)

        print()
        run_pipeline(config, clean=args.clean)


if __name__ == "__main__":
    main()
