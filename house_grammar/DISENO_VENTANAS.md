# Ventanas vinculadas — mejora_ventanas

## Entrada

`theta.architectural_style` elige `republicano`, `barroco`, `clasico`, `madera`
o `moderno`. Es independiente de `family`, que conserva sus reglas de composición.
Todas las ventanas usan exclusivamente `window_assembly.py`. Con estilo global
heredan ese perfil; un perfil contradictorio produce error. Sin estilo global
se respeta `frame_profile` explícito y, si falta, se completa con `moderno`.
No existe fallback antiguo. `balcony_window` usa la misma carpintería de catálogo.

Ejemplo de Opening dentro de `facades[].controls.openings`:

```json
{
  "kind": "window", "u_m": 1.2, "v_m": 0.9,
  "width_m": 1.4, "height_m": 2.0,
  "shape": "arch", "arch_rise_m": 0.6,
  "recess_m": 0.18, "prefab": "catalog",
  "frame_profile": "auto", "frame_width_m": 0.12,
  "frame_depth_m": 0.14, "sill": true,
  "grid_spacing_m": 0.4,
  "grille": true, "grille_pattern": "diamond",
  "grille_spacing_m": 0.14
}
```

Se reutilizan los campos existentes en lugar de introducir objetos `frame`,
`glazing_grid` y `grille` incompatibles con el booleano anterior.

## Geometría

- `rectangle`: ancho y alto independientes; iguales para cuadrado.
- `arch`: arco semicircular o elíptico/rebajado según `arch_rise_m`.
- `circle`: exige ancho igual a alto.
- `ellipse`: ancho y alto independientes.

El contorno de `opening_shape` determina el agujero del muro, el revelado,
los anillos del perfil, el vidrio, las divisiones y la reja. Las curvas se
discretizan en polígonos; no son texturas. El sweep del perfil se aproxima
mediante bandas estrechas de offset con profundidad variable. El marco se
aloja dentro del vano, sin imponer un rectángulo exterior a un arco.

`sill` agrega profundidad a la parte inferior del marco siguiendo su contorno.
No representa una repisa horizontal independiente debajo de un óculo.

Perfiles: moderno fino; clásico escalonado; republicano con labios y cambios
de relieve; barroco ondulado convexo/cóncavo; madera con rebajes y tapajuntas.
La primera versión no añade rosetas ni claves escultóricas independientes.

## Divisiones y rejas

`grid_spacing_m` activa conteo adaptativo por separación objetivo. Si es null,
se respetan `mullion_columns` y `mullion_rows`. El espacio sobrante se reparte
uniformemente. Las barras se intersectan con el interior del contorno.

`grille` activa una capa independiente de protección; patrones `vertical`,
`grid` y `diamond`. `grille_spacing_m` regula la separación. El grosor de las
piezas no se escala al agrandar la ventana. Se limitan los conteos para impedir
generaciones desmedidas.

La autoría nueva usa `prefab: catalog` (valor por defecto), u `open` sin vidrio
ni divisiones. Las muestras originales contienen `legacy`; ese nombre y los
antiguos nombres de vidrio `slim_window`/`storefront` se normalizan al catálogo,
sin ejecutar sus constructores anteriores. Persianas, lamas y screens antiguos
se rechazan, incluso sin estilo global. No forman parte de estas muestras.
Las hojas abatidas y cortinas de la ruta antigua no se reproducen en este ensamblaje.

## Materiales

`frame` gobierna los perfiles y carpintería, salvo `madera` que usa `wood`.
`glass` y `metal` gobiernan vidrio y reja. Se personalizan mediante los
`theta.materials` existentes: template físico y color seleccionable.

## Salidas sin imágenes

Ejecutar desde `house_grammar`:

```
python3 steps/step23_fresh_theta/generar_ventanas.py
```

- `catalogo_ventanas/`: 40 GLB aislados (20 formas/perfiles, con y sin reja) y sus descripciones de Opening.
- `lotes/1134299_casa_salmon_republicana/ventanas_vinculadas/`: request completo,
  GLB, validación y registro de molduras anteriores sustituidas.

La migración toma `base_simplificada_completa/request.json`, mantiene las
posiciones de vanos y elimina solo surrounds/alféizares asociados a ventanas.
Los cercos de esa fuente se conservan tal como estaban; no se reemplazan por
el catálogo nuevo de cercos durante esta prueba de ventanas.

Pruebas en `tests/test_window_assembly.py`: 20 combinaciones producen malla,
divisiones y rejas contenidas, círculo inválido, conflicto de estilo, ventana
pequeña y pipeline completo. La validación geométrica no sustituye revisión
visual; esta iteración no genera comparativas ni renders.
