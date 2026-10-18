# R2 — Ruta exterior sin habitaciones por defecto

`planning.envelope.plan_envelope(request)` compila masas articuladas, una
reserva de escalera y la fachada exterior. No genera cuartos, pasillos, muros
internos ni planos BSP. La vieja ruta con habitaciones solo se usa al pedir
`plan_envelope(request, interiors=True)`.

En un balcón/logia/portico/vestíbulo transitable descrito como operación, la
fachada incluye una puerta con `access_for` apuntando al espacio y cortada en
el muro de su desembarco; no basta una ventana visualmente cercana. La losa del
balcón conserva la silueta de la masa original. `surface_chart(plan,
enclosed=True)` usa la envolvente *cerrada* como soporte de puertas y ventanas,
sin atribuirlas al borde delantero del voladizo.

Pruebas: `PYTHONPATH=house_grammar/src python3 -m pytest
house_grammar/tests/test_exterior_envelope.py -q`. Incluyen 20 casos de masas,
exportación con vistas frontal/oblicua y ausencia de tabiques. El plan publica
`facade.sectors` (uso por frente y ejes en metros), `facade.floor_types`
(pisos superiores compatibles comparten retícula) y `facade.coronations` para
reservar el paño de un frontón solicitado sin dibujar un triángulo fijo.

Banco visual:

```bash
PYTHONPATH=house_grammar/src python3 house_grammar/experiments/r2/run.py \
  --output /tmp/opencode/r2-review
```

Escribe 11 casos con `front.png`, `preview.png` (oblicua), GLB y manifest:
vivienda individual/multifamiliar, comercio, uso mixto, oficina, balcón con
puerta, patio, retiro, esquina, desocupación y comercio con intención de cerco.
Las [vistas de revisión](review/) conservan los 22 PNG frontal/oblicuo y el
manifest del banco **antes del puente R3**, sin sobrescribir material histórico.
Si vuelves a ejecutar `run.py`, obtendrás carpintería de catálogo en el GLB y
las vistas nuevas. Entre los PNG históricos:
[balcón con acceso](review/balcony_access/front.png),
[uso mixto](review/mixed_use/front.png) y
[casa individual](review/single_family/front.png).

Los previews aún son sobrios: los cercos **no** se dibujan en R2. La
carpintería de estos PNG era la auxiliar; la ruta activa la sustituyó por el
catálogo en R3. Cercos/ornamento son R4 y cubierta R5. No son aceptación
arquitectónica.
