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

.PHONY: hub-info hub-link hub-unlink cursor-workspace loop

hub-info:
	@echo "DEV_HUB=$(DEV_HUB)"
	@echo "PROJECT_ROOT=$(PROJECT_ROOT)"
	@echo "links:"
	@ls -la "$(PROJECT_ROOT)/.cursor/rules" "$(PROJECT_ROOT)/.agents" "$(PROJECT_ROOT)/AGENTS.md" "$(PROJECT_ROOT)/CLAUDE.md" 2>/dev/null || true

hub-link:
	@DEV_HUB="$(DEV_HUB)" PROJECT_ROOT="$(PROJECT_ROOT)" "$(DEV_HUB)/bin/hub-link" --with-skills "$(PROJECT_ROOT)"

hub-unlink:
	@PROJECT_ROOT="$(PROJECT_ROOT)" "$(DEV_HUB)/bin/hub-unlink" "$(PROJECT_ROOT)"

cursor-workspace:
	@echo "Open product folder in Cursor: $(PROJECT_ROOT)"
	@echo "Do NOT open multi-root product+hub (two memory-bank/ confuse agents)."
	@echo "Or run: make hub-link  # then Reload Window"

loop:
	@set -- $(ARGS); \
	if [ "$$#" -lt 3 ] || [ "$$#" -gt 4 ]; then \
		echo 'Usage: make loop ARGS="codex <epic-id> <model> [effort]"' >&2; \
		echo '  effort: low|medium|high|xhigh (Codex model_reasoning_effort; default: ~/.codex/config.toml)' >&2; \
		exit 2; \
	fi; \
	runtime="$$1"; epic="$$2"; model="$$3"; effort="$${4:-}"; \
	case "$$runtime" in \
		codex|claude) ;; \
		*) echo "Unsupported loop runtime: $$runtime" >&2; exit 2 ;; \
	esac; \
	if [ -n "$$effort" ]; then \
		case "$$effort" in \
			low|medium|high|xhigh) ;; \
			*) echo "Unsupported effort: $$effort (use low|medium|high|xhigh)" >&2; exit 2 ;; \
		esac; \
	fi; \
	set -- env EPIC_RUNTIME="$$runtime" python3 "$(DEV_HUB)/bin/loop.py" run \
		--project "$(PROJECT_ROOT)" \
		--epic "$$epic" \
		--role auto \
		--runtime "$$runtime" \
		--model "$$model"; \
	if [ -n "$$effort" ]; then \
		set -- "$$@" --effort "$$effort"; \
	fi; \
	exec "$$@"

include $(DEV_HUB)/make/deploy.mk
