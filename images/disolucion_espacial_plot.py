import osmnx as ox
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import Point, LineString
from shapely.ops import linemerge
import numpy as np
import pandas as pd

# Configuración visual
plt.style.use('seaborn-v0_8-white')
plt.rcParams['font.family'] = 'serif'

# 1. EXTRACCIÓN DEL GRAFO
lugar = "Avenida Pedro de Osma, Barranco, Lima, Peru"
G_raw = ox.graph_from_address(lugar, dist=250, network_type='drive', simplify=False)
G_raw = ox.project_graph(G_raw)
nodos, aristas = ox.graph_to_gdfs(G_raw)

def es_pedro_de_osma(nombre):
    if isinstance(nombre, str): return 'Pedro de Osma' in nombre
    if isinstance(nombre, list): return any('Pedro de Osma' in str(n) for n in nombre)
    return False

aristas['is_target'] = aristas['name'].apply(es_pedro_de_osma)
pedro_edges = aristas[aristas['is_target'] == True].copy()
otras_edges = aristas[aristas['is_target'] == False].copy()

# 2. GENERACIÓN DE EVENTOS (Crímenes)
num_crimes = 90
np.random.seed(42)

area_influencia = pedro_edges.unary_union.buffer(25)
minx, miny, maxx, maxy = area_influencia.bounds

crimes_geom = []
while len(crimes_geom) < num_crimes:
    pnt = Point(np.random.uniform(minx, maxx), np.random.uniform(miny, maxy))
    if area_influencia.contains(pnt):
        crimes_geom.append(pnt)

crimes_gdf = gpd.GeoDataFrame(geometry=crimes_geom, crs=aristas.crs)

# =============================================================
# FUNCIÓN GLOBAL DE DENSIDAD (Escala Ajustada)
# =============================================================
def get_density_style(count):
    if count == 0:
        return '#909090', 1.0, 2     # Gris (Sin crímenes)
    elif count <= 4:
        return '#2ca02c', 2.0, 3     # Verde (Seguro)
    elif count < 15:
        return '#ffeda0', 3.5, 4     # Amarillo (Precaución)
    else:
        return '#d62728', 6.0, 5     # Rojo Intenso (Crítico)

# 3. MAP MATCHING IZQUIERDA (Grafo Crudo)
counts_left = {i: 0 for i in range(len(pedro_edges))}
for pnt in crimes_geom:
    min_dist = float('inf')
    best_idx = 0
    for i, geom in enumerate(pedro_edges.geometry):
        d = pnt.distance(geom)
        if d < min_dist:
            min_dist = d
            best_idx = i
    counts_left[best_idx] += 1

# 4. COLAPSO TOPOLÓGICO Y ADAPTACIÓN DE CALLES (Derecha)
merged = linemerge(pedro_edges.unary_union)
centerline = max(merged.geoms, key=lambda x: x.length) if merged.geom_type == 'MultiLineString' else merged

snapped_otras_geoms = []
intersection_points = [0.0, centerline.length]
buffer_captura = pedro_edges.unary_union.buffer(15)

for geom in otras_edges.geometry:
    if isinstance(geom, pd.Series): geom = geom.iloc[0]
    if not isinstance(geom, LineString): continue
    
    new_coords = []
    for coord in geom.coords:
        pnt = Point(coord)
        if buffer_captura.contains(pnt):
            proj = centerline.project(pnt)
            snap_pnt = centerline.interpolate(proj)
            new_coords.append((snap_pnt.x, snap_pnt.y))
            intersection_points.append(proj)
        else:
            new_coords.append(coord)
            
    clean_coords = [new_coords[0]]
    for c in new_coords[1:]:
        if c != clean_coords[-1]: clean_coords.append(c)
    if len(clean_coords) >= 2:
        snapped_otras_geoms.append(LineString(clean_coords))

intersection_points = sorted(list(set(intersection_points)))
simplified_pedro_edges = []
for i in range(len(intersection_points)-1):
    d1, d2 = intersection_points[i], intersection_points[i+1]
    if d2 - d1 > 1.0:
        p1, p2 = centerline.interpolate(d1), centerline.interpolate(d2)
        simplified_pedro_edges.append(LineString([p1, p2]))

# MAP MATCHING DERECHA (Grafo Simplificado)
counts_right = {i: 0 for i in range(len(simplified_pedro_edges))}
for pnt in crimes_geom:
    min_dist = float('inf')
    best_idx = 0
    for i, geom in enumerate(simplified_pedro_edges):
        d = pnt.distance(geom)
        if d < min_dist:
            min_dist = d
            best_idx = i
    counts_right[best_idx] += 1

# -------------------------------------------------------------
# DIBUJO DE LA FIGURA
# -------------------------------------------------------------
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 9))
fig.suptitle('Resolución de Dilución Semántica: Mapeo bajo Regla de Densidad Global', fontsize=18, fontweight='bold', y=0.95)

COLOR_CONTEXTO = '#404040'
GROSOR_CONTEXTO = 0.5

# === A) GRAFO CRUDO ===
ax1.set_title('Grafo Crudo\n(La dispersión en paralelas diluye el nivel de amenaza)', fontsize=14, pad=15)
otras_edges.plot(ax=ax1, color=COLOR_CONTEXTO, linewidth=GROSOR_CONTEXTO, alpha=0.8, zorder=1)

for i, geom in enumerate(pedro_edges.geometry):
    count = counts_left[i]
    color, lw, z = get_density_style(count)
    
    x, y = geom.xy
    ax1.plot(x, y, color=color, linewidth=lw, alpha=0.9, zorder=z)
    
    if count > 0:
        c = geom.interpolate(0.5, normalized=True)
        txt_color = 'white' if color == '#d62728' else 'black'
        ax1.text(c.x, c.y, str(count), fontsize=9, fontweight='bold', color=txt_color,
                 ha='center', va='center', bbox=dict(facecolor=color if count >= 15 else 'white', alpha=0.9, edgecolor='none', pad=1), zorder=7)

crimes_gdf.plot(ax=ax1, color='black', markersize=10, alpha=0.5, zorder=6)
ax1.axis('off')

# === B) GRAFO SIMPLIFICADO ===
ax2.set_title('Grafo Simplificado (Topología Consolidada)\n(Revela el hotspot crítico real superando el umbral de 15)', fontsize=14, pad=15)

for geom in snapped_otras_geoms:
    x, y = geom.xy
    ax2.plot(x, y, color=COLOR_CONTEXTO, linewidth=GROSOR_CONTEXTO, alpha=0.8, zorder=1)

for i, geom in enumerate(simplified_pedro_edges):
    count = counts_right[i]
    color, lw, z = get_density_style(count)
    
    x, y = geom.xy
    ax2.plot(x, y, color=color, linewidth=lw, alpha=0.9, zorder=z)
    
    if count > 0:
        c = geom.interpolate(0.5, normalized=True)
        txt_color = 'white' if color == '#d62728' else 'black'
        ax2.text(c.x, c.y, str(count), fontsize=11, fontweight='bold', color=txt_color,
                 ha='center', va='center', bbox=dict(facecolor=color if count >= 15 else 'white', alpha=0.9, edgecolor='none', pad=2), zorder=7)

crimes_gdf.plot(ax=ax2, color='black', markersize=10, alpha=0.5, zorder=6)
ax2.axis('off')

# Leyenda global compartida
from matplotlib.lines import Line2D
legend_elements = [
    Line2D([0], [0], color='#2ca02c', lw=2.0, label='Seguro (<= 4)'),
    Line2D([0], [0], color='#ffeda0', lw=3.5, label='Precaución (5 - 14)'),
    Line2D([0], [0], color='#d62728', lw=6.0, label='Crítico (>= 15)')
]
fig.legend(handles=legend_elements, loc='lower center', ncol=3, fontsize=12, frameon=True, bbox_to_anchor=(0.5, 0.02))

plt.tight_layout(rect=[0, 0.08, 1, 0.95])
plt.show()