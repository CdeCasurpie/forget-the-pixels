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
exportación con vistas frontal/oblicua y ausencia de tabiques. Los previews de
este primer corte siguen siendo sobrios: composición por ejes/pisos tipo,
tipologías y carpintería de los nueve catálogos quedan pendientes para R2.3 y
R3–R5; no son aceptación arquitectónica.
