# SSH deploy without Git-hosted CI.
# Local: copy .deploy.env.example → .deploy.env and set paths.
#
#   make test
#   make deploy              # tests → ssh → git pull (same repo basename)
#   make deploy-skip-tests   # pull only (explicit)

DEPLOY_PROJECT_ROOT ?= $(CURDIR)
_DEPLOY_MK_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
DEPLOY_SCRIPT ?= $(firstword \
  $(wildcard $(DEPLOY_PROJECT_ROOT)/scripts/deploy-remote.sh) \
  $(wildcard $(DEV_HUB)/scripts/deploy-remote.sh) \
  $(wildcard $(_DEPLOY_MK_DIR)/../scripts/deploy-remote.sh))

.PHONY: test deploy deploy-skip-tests deploy-info

test:
	@if [ -x "$(DEPLOY_PROJECT_ROOT)/bin/pytest" ]; then \
		cd "$(DEPLOY_PROJECT_ROOT)" && bin/pytest -q; \
	elif [ -x "$(DEPLOY_PROJECT_ROOT)/.venv/bin/pytest" ]; then \
		cd "$(DEPLOY_PROJECT_ROOT)" && .venv/bin/pytest -q; \
	else \
		cd "$(DEPLOY_PROJECT_ROOT)" && pytest -q; \
	fi

deploy:
	@test -n "$(DEPLOY_SCRIPT)" || { echo "deploy-remote.sh not found" >&2; exit 1; }
	@DEPLOY_PROJECT_ROOT="$(DEPLOY_PROJECT_ROOT)" bash "$(DEPLOY_SCRIPT)"

deploy-skip-tests:
	@test -n "$(DEPLOY_SCRIPT)" || { echo "deploy-remote.sh not found" >&2; exit 1; }
	@DEPLOY_PROJECT_ROOT="$(DEPLOY_PROJECT_ROOT)" bash "$(DEPLOY_SCRIPT)" --skip-tests

deploy-info:
	@echo "DEPLOY_PROJECT_ROOT=$(DEPLOY_PROJECT_ROOT)"
	@echo "DEPLOY_SCRIPT=$(DEPLOY_SCRIPT)"
	@echo "REPO=$$(basename "$$(git -C "$(DEPLOY_PROJECT_ROOT)" rev-parse --show-toplevel)")"
	@if [ -f "$(DEPLOY_PROJECT_ROOT)/.deploy.env" ]; then \
		echo "env=$(DEPLOY_PROJECT_ROOT)/.deploy.env"; \
	else \
		echo "env=MISSING — copy .deploy.env.example → .deploy.env"; \
	fi
