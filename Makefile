# Aplicaciones locales A (catastro) y B (autor de thetas).
# Uso: `make a` y `make b` en terminales separadas, o `make both` en una sola.
PYTHON ?= python3
DATA ?= data/barranco
PORT_A ?= 8765
PORT_B ?= 8767

.PHONY: help install install-a install-b a b both test

help:
	@echo "Targets:"
	@echo "  make a          - App A (editor catastral) en http://127.0.0.1:$(PORT_A)"
	@echo "  make b          - App B (autor de thetas, mock) en http://127.0.0.1:$(PORT_B)"
	@echo "  make both       - A y B a la vez (B en primer plano; Ctrl+C detiene ambas)"
	@echo "  make install    - dependencias de A y B"
	@echo "  make test       - pruebas de A y B + chequeo JS"
	@echo "Variables: PORT_A=$(PORT_A) PORT_B=$(PORT_B) DATA=$(DATA) (ej: make b PORT_B=8770)"

install: install-a install-b

install-a:
	$(PYTHON) -m pip install -r apps/cadastral_editor/requirements.txt

install-b:
	$(PYTHON) -m pip install -r apps/theta_author/requirements.txt

a:
	$(PYTHON) -m apps.cadastral_editor.server --port $(PORT_A) --data $(DATA)

b:
	$(PYTHON) -m apps.theta_author.server --port $(PORT_B) --data $(DATA)

both:
	trap 'kill %1' EXIT INT TERM; \
	$(PYTHON) -m apps.cadastral_editor.server --port $(PORT_A) --data $(DATA) & \
	$(PYTHON) -m apps.theta_author.server --port $(PORT_B) --data $(DATA)

test:
	$(PYTHON) -m pytest apps/theta_author/tests apps/cadastral_editor/tests -q
	node --check apps/theta_author/static/shortcuts.js
	node --check apps/theta_author/static/app.js
	node --check packages/barranco_imaging/static/prism.js
