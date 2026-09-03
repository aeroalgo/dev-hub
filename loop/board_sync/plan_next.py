from dataclasses import dataclass
from pathlib import Path
import yaml

@dataclass(frozen=True)
class EpicNextOverride:
    epic_id: str
    role: str
    next_command: str

def parse_plan_next(plan_path: str | Path) -> EpicNextOverride | None:
    path = Path(plan_path)
    if not path.is_file():
        return None

    try:
        content = path.read_text(encoding="utf-8")
    except Exception:
        return None

    parts = content.split("\n---")
    if len(parts) < 2:
        return None

    for part in reversed(parts[1:]):
        try:
            parsed = yaml.safe_load(part)
        except Exception:
            continue

        if isinstance(parsed, dict) and "plan-next/v1" in parsed:
            data = parsed["plan-next/v1"]
            if isinstance(data, dict):
                epic_id = str(data.get("epic_id") or "").strip()
                role = str(data.get("role") or "").strip()
                next_command = str(data.get("next_command") or "").strip()
                if epic_id and role and next_command:
                    return EpicNextOverride(
                        epic_id=epic_id,
                        role=role,
                        next_command=next_command,
                    )
    return None

def write_plan_next(plan_path: str | Path, override: EpicNextOverride) -> None:
    path = Path(plan_path)
    if not path.is_file():
        raise FileNotFoundError(f"Plan file not found: {plan_path}")

    content = path.read_text(encoding="utf-8")

    block_data = {
        "plan-next/v1": {
            "epic_id": override.epic_id,
            "role": override.role,
            "next_command": override.next_command,
        }
    }
    block_yaml = yaml.safe_dump(block_data, sort_keys=False).strip()

    parts = content.split("\n---")
    updated = False
    new_parts = [parts[0]]

    for part in parts[1:]:
        try:
            parsed = yaml.safe_load(part)
        except Exception:
            parsed = None

        if isinstance(parsed, dict) and "plan-next/v1" in parsed:
            new_parts.append(block_yaml)
            updated = True
        else:
            new_parts.append(part.strip())

    if updated:
        new_content = "\n---\n".join(part for part in new_parts if part) + "\n"
    else:
        base = content.rstrip()
        new_content = f"{base}\n---\n{block_yaml}\n"

    if new_content != content:
        path.write_text(new_content, encoding="utf-8")

def validate_plan_next(override: EpicNextOverride, artifacts: dict[str, bool]) -> str | None:
    cmd = override.next_command.strip()
    parts = cmd.split()
    phase = parts[1].upper() if len(parts) > 1 else parts[0].upper()

    plan_exists = bool(artifacts.get("plan_exists", True))
    decompose_exists = bool(artifacts.get("decompose_exists", False))

    if phase == "DECOMPOSE" and not plan_exists:
        return f"Invalid plan-next override '{cmd}': plan file does not exist for epic {override.epic_id}"

    if phase == "IMPLEMENT" and not decompose_exists:
        return f"Invalid plan-next override '{cmd}': decompose shard index does not exist for epic {override.epic_id}"

    pending_steps = bool(artifacts.get("pending_steps") or artifacts.get("has_pending_steps", False))
    if phase in {"QA", "AUDIT", "BUGFIX"} and pending_steps:
        return f"Invalid plan-next override '{cmd}': cannot override to post-implement phase while implement steps pending for epic {override.epic_id}"

    return None
