"""render_active_context implementation."""

import yaml
from harness.hooks.epic.core import validate_active_context_shape
from loop.mb_finish.schemas import HandoffBody, LoadNowItem, LoopHandoffMeta
from loop.schemas.active_context import normalize_gate_mode


def render_active_context(
    meta: LoopHandoffMeta,
    load_now: list[LoadNowItem],
    done: list[str],
    handoff: HandoffBody,
) -> str:
    """Render activeContext.md string and validate shape rules."""
    mode = normalize_gate_mode(handoff.mode, meta.role)
    meta = meta.model_copy(update={"mode": normalize_gate_mode(meta.mode, meta.role)})
    handoff = handoff.model_copy(update={"mode": mode})
    fm_dict = meta.model_dump_frontmatter()
    fm_yaml = yaml.safe_dump(fm_dict, sort_keys=False).strip()

    lines = [
        "---",
        fm_yaml,
        "---",
        "",
    ]

    if load_now:
        lines.append("## load_now")
        for idx, item in enumerate(load_now, start=1):
            lines.append(item.render(idx))
        lines.append("")

    step_str = f" — {handoff.step_id}" if handoff.step_id else ""
    lines.append(f"## Handoff {meta.role} {handoff.mode}{step_str}")
    if handoff.next_hint:
        lines.append(f"- **Дальше:** {handoff.next_hint}")
    for line in handoff.custom_lines:
        lines.append(line)
    lines.append("")

    if done:
        lines.append("## done")
        for item in done:
            if item.strip():
                lines.append(f"- {item.strip() if not item.strip().startswith('- ') else item.strip()[2:]}")
        lines.append("")

    content = "\n".join(lines).rstrip() + "\n"

    shape_errors = validate_active_context_shape(content)
    if shape_errors:
        raise ValueError(f"rendered activeContext has shape errors: {shape_errors}")

    return content
