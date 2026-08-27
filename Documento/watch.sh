#!/bin/bash

# Este script mantiene una compilación continua (watch) usando latexmk.
# Funciona excelente con visores de PDF modernos (como Evince, Zathura o Okular en Arch Linux) 
# que actualizan el PDF en tiempo real cuando el archivo cambia.

echo "================================================================"
echo " Iniciando compilación CONTÍNUA (Watch Mode) con Docker"
echo " Presiona Ctrl+C para detener."
echo " Abre main.pdf en tu visor favorito; se actualizará solo."
echo "================================================================"

# latexmk -pvc (preview continuously) compilará cada vez que guardes un archivo tex/bib.
docker run --rm -it -v "$(pwd)":/workspace -w /workspace texlive/texlive latexmk -pdf -pvc -interaction=nonstopmode -view=none main.tex
