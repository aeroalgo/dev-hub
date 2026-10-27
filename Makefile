# Hub root Makefile — deploy + shared product helpers for this repo.

DEV_HUB := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
PROJECT_ROOT := $(CURDIR)

include $(DEV_HUB)/make/deploy.mk

.PHONY: help
help:
	@echo "Hub targets:"
	@echo "  make test               — run hub pytest"
	@echo "  make deploy             — tests → SSH → git pull same repo on server"
	@echo "  make deploy-skip-tests  — SSH pull only"
	@echo "  make deploy-info        — show detected repo / env"
	@echo ""
	@echo "Config: copy .deploy.env.example → .deploy.env"
