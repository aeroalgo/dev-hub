# Shared Make targets for product repos that use ~/…/dev-hub.
# Include from product Makefile:
#   include $(DEV_HUB)/make/product.mk
#
# Do not copy this file into products — only the thin root Makefile.

ifeq ($(strip $(DEV_HUB)),)
$(error DEV_HUB is empty. Set DEV_HUB=…, create .dev-hub, or place hub at ../dev-hub)
endif

DEV_HUB := $(abspath $(DEV_HUB))
PROJECT_ROOT := $(CURDIR)
LOOP_BIN := $(DEV_HUB)/bin/loop

ifeq ($(wildcard $(LOOP_BIN)),)
$(error loop runner not found: $(LOOP_BIN) — check DEV_HUB=$(DEV_HUB))
endif

# Extra args after target, e.g.: make loop ARGS="gpt"
# or: make loop-epic EPIC=decompose-T-013 MODEL=gpt
ARGS ?=
MODEL ?= gpt
EPIC ?=
MODE ?=

.PHONY: hub-info hub-link hub-unlink loop loop-status loop-help loop-epic cursor-workspace

hub-info:
	@echo "DEV_HUB=$(DEV_HUB)"
	@echo "PROJECT_ROOT=$(PROJECT_ROOT)"
	@echo "LOOP_BIN=$(LOOP_BIN)"
	@echo "links:"
	@ls -la "$(PROJECT_ROOT)/.cursor/rules" "$(PROJECT_ROOT)/.agents" "$(PROJECT_ROOT)/CLAUDE.md" 2>/dev/null || true

hub-link:
	@DEV_HUB="$(DEV_HUB)" PROJECT_ROOT="$(PROJECT_ROOT)" "$(DEV_HUB)/bin/hub-link" "$(PROJECT_ROOT)"

hub-unlink:
	@PROJECT_ROOT="$(PROJECT_ROOT)" "$(DEV_HUB)/bin/hub-unlink" "$(PROJECT_ROOT)"

cursor-workspace:
	@echo "Open product folder in Cursor: $(PROJECT_ROOT)"
	@echo "Do NOT open multi-root product+hub (two memory-bank/ confuse agents)."
	@echo "Or run: make hub-link  # then Reload Window"

loop-help:
	@echo "make hub-link          # Cursor: rules + skills + CLAUDE.md from hub"
	@echo "make hub-unlink"
	@echo "make loop ARGS='gpt'"
	@echo "make loop ARGS='decompose-T-013 gpt'"
	@echo "make loop-epic EPIC=decompose-T-013 MODEL=gpt"
	@echo "make loop-status"
	@echo "make hub-info"
	@echo ""
	@echo "DEV_HUB resolution: env DEV_HUB | file .dev-hub | sibling ../dev-hub"
	@"$(LOOP_BIN)" "$(PROJECT_ROOT)" --help 2>/dev/null || "$(DEV_HUB)/loop/loop.sh" --help

loop: hub-link
	@"$(LOOP_BIN)" "$(PROJECT_ROOT)" $(ARGS)

loop-status: hub-link
	@"$(LOOP_BIN)" "$(PROJECT_ROOT)" --status

loop-epic: hub-link
ifeq ($(strip $(EPIC)),)
	$(error set EPIC=decompose-<id> , e.g. make loop-epic EPIC=decompose-T-013)
endif
	@"$(LOOP_BIN)" "$(PROJECT_ROOT)" "$(EPIC)" "$(MODEL)" $(MODE)
