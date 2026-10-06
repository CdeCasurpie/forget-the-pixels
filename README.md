# TesisLatex-Barranco3D | Estado (6 Oct 2026)

## Estado actual (6 Oct 2026)

- **Gramática congelada**: v1.0 + v1.1 (sparse manifold, −70/80 % triángulos).
- **Cuadra seed 123 cerrada**: 24/24 lotes con theta manual + `building.glb`
  (`envelope passed`) + comparativa foto-vs-render; `cuadra_completa.glb`
  (147 508 tris, origen único) + visor dual GSV-vs-modelo
  (`steps/step19_experimental/cuadra_fotos/`, `recorrido/`).
- **Reorganización**: catastro en `data/lotes/`, poses GSV en
  `data/poses_barranco/` (5 436), fotos en `data/fotos_barranco/`,
  `scripts/descargar_fotos.py` (baja todas/subset, retomable);
  experimentos viejos archivados en `steps/step19_experimental/`
  (incluye `cuadra_fotos/` y `generacion_mannual/`); era COLMAP en
  `backups/lotes_archivo_2026-10-06/` (no commiteado).
- **Pendiente**: descargar las ~5.5k fotos (medido: ~7 GB a q92);
  corregir thetas que marque el visor; decidir test roto
  (`choose_theta(..., polygon)` vs `test_block_progress.py:32`).


## Objetivos Actuales

### Objetivo Principal: 
Reconstruir edificios urbanos de barranco en 3D a partir de 

```
lote catastral
+ 1 o varias imágenes / Street View
+ cámaras / geometría conocida
+ estimaciones como altura
        ↓
sistema inverso
        ↓
representación procedural θ
        ↓
Grammar V1
        ↓
modelo 3D
```

> donde `θ` es el conjunto de parámetros que describe el edificio.


Es mucho más improtante que lo visible sea arquitectónicamente fiel, no es necesario que sea exactamente igual (pixel a pixel, lo que hace colmap).

> Forget the pixels

### Objetivos secundarios

- Inferencia estructuralmente coherente de lo no observable - parte trasera, techos, inferiores del lote.

- Distinguir entre **reconstrucción basada en evidencia** y **completada/inferida**.


## Estado del Generador

Nuestra primera gramática procedural ya se terminó y congeló:

```
grammar-v1.0
```

Nuestra arquitectura es:

```
parcela + programa + altura
        ↓
massing
        ↓
exposición entre masas
        ↓
fachadas
        ↓
vanos + relieve + prefabs
        ↓
cubiertas
        ↓
sitio/cerramientos
        ↓
MeshData
        ↓
GLB / OBJ + PBR
```


## Lista de pendientes

| Área | Estado |
|---|---|
| Gramática procedural | ✅ V1 congelada |
| Massing | ✅ 6 patrones + ampliaciones |
| Fachadas | ✅ familias, bays, ventanas, puertas, balcones, galerías, etc. |
| Roofscape | ✅ techos, parapetos, props |
| Site | ✅ cercos, accesos, patios/espacios |
| Materiales | ✅ PBR + catálogo real |
| Topología | ✅ source topology estable |
| Export | ✅ GLB + OBJ |
| Golden regression set | ✅ 3 modelos reproducibles |
| Tests | ✅ 161 tests del freeze |
| Inverse model | ❌ todavía no |
| Dataset sintético | ❌ todavía no |
| θ definitivo | ❌ este es el siguiente problema |


## Next Steps

1. Diseñar formalmente `θ` y la interfaz Grammar(P, θ, ξ)

    Donde:
    - `P`: Parcela conocida.
    - `θ`: Identidad arquitectónica reconstruible (edificio a reconstruir)
    - `ξ`: Detalles secundarios (nuisance / tonterias)

2. Expressivity: Intentar representar edificios reales de Barranco manualmente con `θ`.

3. Generación del dataset sintético. (`θ`, renders, depth, masks, cámaras...). 

