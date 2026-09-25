# Qué describen realmente los 5 ejemplos

Datos generados por `python steps/step18_theta_interface/audit_examples.py`.

| Ejemplo | Campos θ explícitos | Completados | Masas | Vanos resueltos | ξ |
|---|---:|---:|---:|---:|---|
| 01_simple.json | 8 | 19 | 1 | 6 | seed=18, cortinas=True |
| 02_republicano.json | 9 | 19 | 1 | 8 | seed=18, cortinas=True |
| 03_galeria.json | 9 | 20 | 1 | 6 | seed=18, cortinas=True |
| 04_mixed.json | 9 | 20 | 1 | 12 | seed=18, cortinas=True |
| 05_setback.json | 14 | 15 | 2 | 16 | seed=18, cortinas=True |

El JSON detallado enumera cada campo explícito, su valor completado y la regla de origen.
Las cotas de niveles se derivan de altura y pisos; las exposiciones/vanos repetidos se derivan de masas, familia y bays.
Ningún campo marcado `prior/completed` se convierte en `observed`.
