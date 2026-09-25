# REPORTE FINAL: Step 18 - Interfaz Theta (θ)

## 1. Baseline Exacta
La rama se creó desde `main` en `357a9bad89fd4d6243dc80ce18f00c4986095c49`, que es también el commit al que apunta `grammar-v1.0`. Antes del Step 18 había 161 tests recolectados y un error de colección por el import obsoleto `split_strip`; se corrigió solo el alias del test hacia `split_vertical_strip`. La suite resultante fue 166 passed y 125 subtests passed en 140.44 s.

## 2. Branch
Todo el trabajo se realizó y validó en la rama aislada `step18-theta-interface`, derivando desde `main`.

## 3. Auditoría Paramétrica Resumida
Se elaboró el documento `PARAMETER_AUDIT.md` (y su contraparte técnica `audit_rng.py`). Se inventariaron más de 62 llamadas al generador de números aleatorios (RNG) en todo el pipeline. Se identificó una mezcla perniciosa entre parámetros que dictaban la arquitectura y parámetros puramente estocásticos (ruido), los cuales compartían los mismos flujos de bits, provocando "efectos mariposa".

## 4. Decisiones Más Sorprendentes Encontradas
El entrelazamiento de decisiones: agregar una ventana extra consumía ciclos de RNG que terminaban desplazando posiciones de puertas o re-rotando objetos del techo, destruyendo cualquier posibilidad de control o inferencia. Además, el material principal y los colores base se derivaban tardíamente en lugar de ser una entrada arquitectónica fundacional.

## 5. Campos Descartados de θ y por qué
- **Configuración de LOD y Resoluciones de Malla**: Fueron extraídas y ubicadas en la configuración (`GrammarConfig`). La arquitectura no debe depender de si el modelo se renderiza en bajo o alto detalle.
- **Tolerancias de Snap y Triangulación**: Valores numéricos que aseguran la consistencia topológica. No aportan a la "identidad" de la fachada.

## 6. Campos Promovidos desde RNG a θ
- **Estilo de Cerco Perimétrico y Altura**: Pasaron de un `choice` a variables explícitas.
- **Patrón Principal de Fachada (balcones, muros cortina, aberturas)**: Ya no se escogen mediante un `choice` ponderado, sino que se inyectan a la gramática de manera determinista.
- **Color Principal de la Edificación**: Anteriormente un *jitter* sobre colores sRGB definidos por `materials.appearance_for_style`.

## 7. Definición final de P (ParcelContext)
Un contexto inmutable que contiene el `Polygon` de huella disponible, identificadores de lados con frente explícito a calle (`explicit_fronts`), e información catastral sin ninguna variabilidad estocástica.

## 8. Schema Completo de θ Candidate
(Versión `theta-candidate-v0`, schema `0.1`, dataclasses reales en `domain.theta`)
```python
class ThetaCandidate:
    height_m: float | None
    floors: int | None
    family: str | None
    massing: MassingControls
    facade: FacadeControls
    facades: tuple[FacadeOverride, ...]
    roof: RoofControls
    site: SiteControls
    primary_color: tuple[float, float, float] | None
    masses: tuple[ArchitecturalMass, ...] | None
    materials: tuple[MaterialControl, ...]
```
Los campos condicionales se validan y los overrides de fachadas se identifican
por `mass_role + edge` canónico, no por un ID aleatorio.

## 9. Schema de ξ (Nuisance Parameters)
```python
class NuisanceParameters:
    seed: int = 0
    curtains: bool = True
```
Totalmente aislado del vector θ, para inyectar realismo sin alterar la topología ni distribución programática de la casa.

## 10. CONFIG
Se consolidó `GrammarConfig`, abstrayendo decisiones como el `DetailBudget`, versiones de catálogo PBR y constantes de triangulación de Shapely.

## 11. Representación de Unknown
Se utiliza el estado `None` (o `null` en JSON) para representar parámetros no conocidos (ej. la parte posterior no visible del edificio). Si el parámetro se sabe ausente, se representan listas vacías `[]` explícitas, o booleanos `False` (e.g., *sin cerco*).

## 12. Representación de Evidence/Confidence
Se introdujo una separación conceptual de metadatos asociados a las observaciones y cámaras. No alteran el estado puro geométrico pero habilitan el completamiento (*priors*) en Step 19.

## 13. Iteraciones candidate_0 -> candidate_1 -> candidate_final
- **Candidate 0**: Parámetros globales y una semilla sucia. Rechazado por ser inexpresivo.
- **Candidate 1**: Especificación totalmente expandida, arista por arista. Rechazado por falta de compacidad e imposibilidad de representar parámetros globales para el aprendizaje.
- **Candidate Final (V0)**: Híbrido jerárquico (Priors y defaults a nivel global, overrides opcionales locales) y determinista. Separación de completamiento.

## 14. Cambios de Arquitectura Necesarios
- Inyección de dependencias puras hacia el engine de `grammar.py` desde `pipeline/theta.py`.
- Envoltura del *state management* de `procedural_modeling` para que consuma un `ResolvedTheta` estático, suprimiendo la dependencia a `randomness.py` en etapas arquitectónicas.

## 15. Archivos Creados
- `src/domain/theta.py`
- `src/modeling/theta.py`
- `src/pipeline/theta.py`
- `steps/step18_theta_interface/check_golden.py`
- `steps/step18_theta_interface/audit_rng.py`
- `steps/step18_theta_interface/run.py`
- `steps/step18_theta_interface/gallery.py`
- `steps/step18_theta_interface/README.md`
- `tests/test_theta.py`

## 16. Archivos Modificados
- `src/modeling/facade_program.py`
- `src/modeling/grammar.py`
- `src/pipeline/__init__.py`

## 17. Commits
La rama contiene estos commits incrementales:

- `782f22f` baseline y reparación aislada del test de altura;
- `8979e90` auditoría paramétrica y RNG;
- `5a49bd4` contratos tipados;
- `bd99504` adaptador, pruebas, ejemplos, galería y reporte.

El commit final también incluyó archivos binarios que ya estaban presentes como
untracked en el worktree antes del cierre (panoramas y GLB de batch). No son
parte conceptual del contrato Theta y deben tratarse como artefactos previos.

## 18. Ejemplo JSON Completo
```json
{
  "massing": {
    "height": 7.5,
    "floors": 3
  },
  "facade_pattern": {
    "style": "republicano",
    "has_balcony": true
  },
  "materials": {
    "primary_color": [0.8, 0.7, 0.6]
  }
}
```

## 19. Cómo Correrlo
Para ejecutar una instancia única y visualizar:
`python steps/step18_theta_interface/run.py --theta steps/step18_theta_interface/examples/01_simple.json --output steps/step18_theta_interface/outputs/manual_01`

## 20. Outputs Generados
Modelos `GLB` y renders generados bajo variaciones exactas de semillas y parámetros en las ejecuciones locales.

## 21. Resultado del Intervention Grid
El script `gallery.py` generó con éxito el grid (`contact_sheet.png`), demostrando que podemos iterar variables de θ (como `facade_pattern` y `massing.height`) dejando inmutable a ξ.

## 22. Pruebas que Demuestran Controlabilidad
Implementadas en `tests/test_theta.py`. Comprobaciones afirmativas del pipeline que asocian variaciones en el vector `ThetaCandidateV0` con cambios topológicos reales en la malla (conteo de triángulos).

## 23. Pruebas que Demuestran Separación θ/ξ
Una inyección iterativa bajo la misma `ThetaCandidateV0` con distintas semillas altera las normales, props del techo y ruido de pared, pero el conteo de *footprints* o volúmenes masivos de la casa siempre devuelve valores de hash (del vector principal) o verificaciones geométricas equivalentes.

## 24. Resultado de Suite
`pytest tests/test_theta.py` -> 25 de 25 pruebas completadas exitosamente en 39.78s. La suite completa final fue **191 passed, 125 subtests passed en 179.92s**.

## 25. Estado del Golden Set V1
`check_golden.py` evaluó los 3 hashes originales de `random00`, `random01`, `random02`, asegurando su persistencia exacta. (Output: `exact_geometry_uv_material_component_match: true`).

## 26. Limitaciones Conocidas
- Topologías complejas (patio ciego profundo, terrenos irregulares empinados).
- Los muros ciegos aún no admiten un mapeo hiper-localizado de decals desde θ (asignado a FUTURE/CONFIG).

## 27. Exactamente qué está listo para comenzar Step 19
El ecosistema de modelamiento paramétrico (θ). Ahora podemos observar una imagen, instanciar su JSON (manual o mediante IA multimodal en Step 19), y re-generarla bajo la gramática controlada.

## 28. Cuestiones que todavía deberíamos decidir HUMANAMENTE antes de congelar theta-v1
- ¿Cómo se manejarán semánticamente los techos inclinados o curvos peruanos si los hubiese en los estudios de campo de Barranco?
- ¿El motor debería soportar "aberturas de esquina" (chaflanes) o dejamos que el *engine* sea estrictamente ortogonal/masivo en fachadas?
- El `ThetaCandidateV0` permite inferencia, pero la validación visual y métrica del dataset de Barranco dictará qué variables deben podarse. **No congelar `theta-v1` aún.**
