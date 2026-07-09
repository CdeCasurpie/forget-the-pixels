#!/bin/bash

# Este script utiliza latexmk dentro del contenedor texlive, 
# el cual automáticamente se encarga de ejecutar pdflatex y bibtex las veces que sean necesarias.

echo "==================================================="
echo "   Iniciando compilación de la Tesis con Docker    "
echo "==================================================="

# Ejecutar latexmk en docker
docker run --rm -v "$(pwd)":/workspace -w /workspace texlive/texlive latexmk -pdf -interaction=nonstopmode main.tex

echo "==================================================="
echo " Compilación finalizada. Revisa el archivo main.pdf"
echo "==================================================="
