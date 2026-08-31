# T-HUB-021 Compatibility Matrix & Research Notes

## Environment & Pins
- **Python:** ≥ 3.11 (Validated with Python 3.12.11)
- **Requirements pin:** `requirements-hub.txt`
  - `pydantic-ai>=0.0.1`
  - `pydantic>=2.0.0`
  - `httpx>=0.27.0`

## OmniRoute & OpenAI-compatible Endpoints
- `pydantic-ai` `Agent` supports OpenAI-compatible endpoints via `OpenAIProvider` / `OpenAIModel` or custom base URL configuration.
- Target endpoints defined in `.claude/project.env`:
  - `PROJECT_OUTPUT_SUMMARY_URL` (OmniRoute base URL)
  - `MODEL` (e.g. `anthropic/claude-3-5-haiku` or configured model)
- Network calls use `httpx.AsyncClient` / `httpx.Client` pointing to `PROJECT_OUTPUT_SUMMARY_URL`.
