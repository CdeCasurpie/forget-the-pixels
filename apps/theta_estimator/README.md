# Estimador con opencode (módulo standalone)

Llama a `opencode run` con fotos y devuelve el JSON del formulario de B
(pisos, altura por piso, primer piso diferente + altura, estilo, notas).
No toca B ni el catastro: la conexión se hará después contra `estimate()`.

## Probar

```sh
python3 -m apps.theta_estimator.cli dump-prompt --lot 1135018 --images 2
python3 -m apps.theta_estimator.cli probe --image <foto.jpg> --text "describe qué hay en la imagen"
python3 -m apps.theta_estimator.cli estimate --image a.jpg --image b.jpg --lot 1135018
python3 -m pytest apps/theta_estimator/tests -q -m "not live"
```

Opciones: `--model`, `--agent`, `--timeout`. Requiere `opencode` con sesión
válida; cada llamada abre sesión fresca (nunca `-c`).
