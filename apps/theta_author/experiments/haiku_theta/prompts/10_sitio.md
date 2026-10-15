# 10 · Cerco, accesos y suelo libre

Devuelve site y entrances. El perímetro de la parcela y la huella construida ya
están fijados. Una reja frontal con portón pertenece a site.runs, no a los vanos
de la pared del edificio. Los peldaños/rampas de entrances se anclan a una puerta
existente, no crean otra puerta.

Usa aristas CANÓNICAS DE PARCELA para FenceRun.edge; las de masa solo para entrances.
start_m/end_m recorren la arista, gate_u/garage_u son distancias desde el INICIO
DEL RUN (no fracciones ni distancias desde el vértice de parcela). Los cercos no
heredan el estilo global: su kind selecciona el estilo observado.

Patio/jardín/estacionamiento se ubican con regiones de parcela sobre suelo libre.
No coloques plantas en accesos ni pavimento encima de masas. La vegetación ocluye
la foto pero no justifica inventar forma de las ventanas que tapa. Las zonas no
añaden vehículos. No agregues un cerco si el edificio está a línea de calle.

Si la calle está a otra cota, anota incertidumbre: la cámara usa suelo plano de
referencia. No cambies origen Z/alturas humanas para hacer coincidir un escalón.
