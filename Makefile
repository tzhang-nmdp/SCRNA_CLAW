.PHONY: demo test list demo-all catalog demo-orchestrator demo-bulkrna \
        install install-spatial-domains install-full install-dev \
        install-sc oc-link \
        bot-telegram bot-feishu bot-multi bot-list \
        memory-server

## ── Virtual-environment + installation targets ──────────────────────────────

venv:
	python3 -m venv .venv
	@echo "Activate with: source .venv/bin/activate"

install:
	pip install -e .

install-spatial-domains:
	pip install -e ".[spatial-domains]"

install-full:
	pip install -e ".[full]"

install-dev:
	pip install -e ".[dev]"

# Install the package and register the `sc` short alias
# After this, both `scrna_claw` and `sc` commands are available system-wide.
install-oc:
	pip install -e .
	@echo ""
	@echo "✓ 'sc' command installed. Try: sc list"
	@echo "  sc interactive   → start interactive CLI"
	@echo "  sc tui           → start full-screen TUI"

# Quick symlink alternative (no pip needed, works for current user only)
# Creates ~/.local/bin/sc → project's scrna_claw.py
oc-link:
	@mkdir -p "$(HOME)/.local/bin"
	@printf '#!/usr/bin/env sh\nexec python "$(CURDIR)/scrna_claw.py" "$$@"\n' > "$(HOME)/.local/bin/sc"
	@chmod +x "$(HOME)/.local/bin/sc"
	@echo "✓ Symlink created: ~/.local/bin/sc → $(CURDIR)/scrna_claw.py"
	@echo "  Make sure ~/.local/bin is in your PATH."

# Convenience: create venv + core install in one step
setup: venv
	.venv/bin/pip install -e .

# Create venv + full install in one step
setup-full: venv
	.venv/bin/pip install -e ".[full]"

## ── Demo & test targets ──────────────────────────────────────────────────────

demo:
	python scrna_claw.py run preprocess --demo --output /tmp/scrna_claw_demo

test:
	python -m pytest -v

list:
	python scrna_claw.py list

catalog:
	python scripts/generate_catalog.py

demo-orchestrator:
	python scrna_claw.py run orchestrator --demo --output /tmp/scrna_claw_orchestrator_demo

demo-all:
	python scrna_claw.py run preprocess --demo --output /tmp/sc_preprocess
	python scrna_claw.py run domains --demo --output /tmp/sc_domains
	python scrna_claw.py run de --demo --output /tmp/sc_de
	python scrna_claw.py run genes --demo --output /tmp/sc_genes
	python scrna_claw.py run statistics --demo --output /tmp/sc_statistics
	python scrna_claw.py run annotate --demo --output /tmp/sc_annotate
	python scrna_claw.py run deconv --demo --output /tmp/sc_deconv
	python scrna_claw.py run communication --demo --output /tmp/sc_communication
	python scrna_claw.py run condition --demo --output /tmp/sc_condition
	python scrna_claw.py run velocity --demo --output /tmp/sc_velocity
	python scrna_claw.py run trajectory --demo --output /tmp/sc_trajectory
	python scrna_claw.py run enrichment --demo --output /tmp/sc_enrichment
	python scrna_claw.py run cnv --demo --output /tmp/sc_cnv
	python scrna_claw.py run integrate --demo --output /tmp/sc_integrate
	python scrna_claw.py run register --demo --output /tmp/sc_register
	python scrna_claw.py run orchestrator --demo --output /tmp/sc_orchestrator

demo-bulkrna:
	python scrna_claw.py run bulkrna-alignment --demo --output /tmp/bulkrna_alignment
	python scrna_claw.py run bulkrna-de --demo --output /tmp/bulkrna_de
	python scrna_claw.py run bulkrna-splicing --demo --output /tmp/bulkrna_splicing
	python scrna_claw.py run bulkrna-enrichment --demo --output /tmp/bulkrna_enrichment
	python scrna_claw.py run bulkrna-deconvolution --demo --output /tmp/bulkrna_deconv
	python scrna_claw.py run bulkrna-coexpression --demo --output /tmp/bulkrna_coexpr

## ── Bot targets ─────────────────────────────────────────────────────────────

bot-telegram:
	python -m bot.run --channels telegram

bot-feishu:
	python -m bot.run --channels feishu

# Multi-channel runner (runs multiple channels in one process)
# Usage: make bot-multi CHANNELS=telegram,feishu
bot-multi:
	python -m bot.run --channels $(CHANNELS)

bot-list:
	python -m bot.run --list

## ── Memory server ───────────────────────────────────────────────────────────

memory-server:
	python scrna_claw.py memory-server

