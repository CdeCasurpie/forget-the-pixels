# Entradas y escaleras: catálogo métrico

## Generar y revisar

```bash
python3 steps/step23_fresh_theta/generar_entradas.py
```

Salida: `steps/step23_fresh_theta/catalogo_entradas/`. Diez GLB con request,
arquitectura resuelta, medidas y validación: ocho accesos nuevos y dos escaleras
altas del generador existente. Sin renders. El README del catálogo compara medidas.

## Controles nuevos

`theta.entrances` vincula cada acceso a un vano existente por `mass_ref`, `edge`
y `opening_index`. El ancho hereda el del vano si `width_m=0`. La cota superior
se toma de la base del vano; `ground_z_m` define el suelo de llegada.

```json
{
  "entrances": [{
    "id": "ingreso",
    "mass_ref": "house:0",
    "edge": 0,
    "opening_index": 0,
    "kind": "steps",
    "landing_m": 0.9,
    "tread_m": 0.30,
    "max_riser_m": 0.18,
    "nosing_m": 0.025,
    "cheek_height_m": 0.35,
    "material": "stone",
    "side_material": "plaster"
  }]
}
```

- `steps`: sección escalonada cerrada, descanso superior, boceles y mejillas
  opcionales. Número de contrahuellas calculado por redondeo hacia arriba y
  altura redistribuida uniformemente. Desarrollo = descanso + (N−1) huellas.
- `ramp`: `run_m` y `transition_m` determinan tres pendientes; las transiciones
  tienen la mitad de pendiente del tramo central. Pendiente central máxima
  admitida: 15 grados. Bordes elevados opcionales mediante `cheek_height_m`.
- `passage`: piso horizontal con laterales opcionales. Sirve para camino de
  acceso y paso abierto de zaguán. Exige igualdad entre cotas de llegada y puerta.
- `slab_m`: espesor bajo la cota inferior; `side_width_m`: espesor de laterales.

Se rechazan accesos fuera de la envolvente, superpuestos, dentro de otra masa,
en vanos ocultos o con medidas inválidas. Las medidas resueltas quedan en
`ResolvedArchitecture.entrances`. Los estilos siguen en puertas y materiales;
la huella y contrahuella dependen del desnivel, no de una etiqueta de estilo.

## Integración y alcance

El acceso explícito reemplaza `entrance_step` solo en su vano. El umbral usa
`DoorControls.threshold` y `threshold_material`, conservando una única pieza
de puerta. El contrato admite materiales personalizados de theta.

El catálogo incluye escaleras recta y de retorno existentes, con huella de
0.28 m, contrahuella de 0.18 m y ancho de tramo de 1.15 m. Su generador y
barandas existentes no se sustituyen en esta iteración.

El zaguán mostrado es un corredor exterior abierto; no excava interiores ni
añade automáticamente otro portón. La rampa se ancla a una puerta de fachada:
no se conecta automáticamente a `FenceRun`, a la pista o al terreno topográfico.
Estos valores son parámetros de modelado, no una certificación normativa.

Pruebas: cierre, orientación y volumen de sólidos, alturas, redistribución de
peldaños, roundtrip JSON, sustitución de grada automática y rechazo de entradas
incompatibles. La validación de envolvente no sustituye una revisión visual.
