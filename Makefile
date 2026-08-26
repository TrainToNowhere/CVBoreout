# CVBoreout - resume builder for STEM professionals
PY      ?= python3
VENV    ?= .venv
BIN      = $(VENV)/bin
FILE    ?= data/resume.json
TARGET  ?= export/Resume.pdf
DOC     ?= resume        # resume | letter | both

.DEFAULT_GOAL := help
.PHONY: help setup run web pdf html sample test test-ui lint clean distclean

help: ## Show this overview
	@echo "CVBoreout - available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Variables: FILE=$(FILE)  TARGET=$(TARGET)  DOC=$(DOC)"

$(BIN)/python:
	@echo ">> Creating the virtual environment (with access to the system GTK bindings)"
	$(PY) -m venv --system-site-packages $(VENV)
	$(BIN)/pip install --upgrade pip

setup: $(BIN)/python ## Install dependencies
	$(BIN)/pip install -r requirements.txt
	@echo ">> Done. Start with: make run"

run: setup ## Start the app in a desktop window
	$(BIN)/python -m cvboreout --file $(FILE) --sample

web: setup ## Start the app in the default browser
	$(BIN)/python -m cvboreout --file $(FILE) --sample --web

pdf: setup ## Render a PDF without the interface (TARGET=... DOC=resume|letter|both)
	$(BIN)/python -m cvboreout --file $(FILE) --export $(TARGET) --doc $(DOC)

html: setup ## Write the intermediate HTML (handy for tweaking a template)
	$(BIN)/python -m cvboreout --file $(FILE) --html export/resume.html --doc $(DOC)

sample: setup ## Write the sample resume to $(FILE)
	@$(BIN)/python -c "from pathlib import Path; from cvboreout import model; \
	model.save(Path('$(FILE)'), model.normalize(model.SAMPLE))"
	@echo ">> $(FILE) created"

test: setup ## Self-test: documents, server routes and AI backends
	$(BIN)/python -m tests.smoke
	$(BIN)/python -m tests.server
	$(BIN)/python -m tests.providers

test-ui: setup ## Self-test of the editor in a real WebKit view (needs a display)
	$(BIN)/python -m tests.ui

lint: ## Byte-compile the sources as a syntax check
	$(PY) -m compileall -q cvboreout tests

clean: ## Remove build output
	rm -rf export __pycache__ */__pycache__ */*/__pycache__

distclean: clean ## Also remove the virtual environment
	rm -rf $(VENV)
