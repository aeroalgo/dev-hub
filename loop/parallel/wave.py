from pathlib import Path
import yaml
from loop.schemas.decompose_index import DecomposeIndex


def compute_ready_wave(index_path: Path | str) -> list[str]:
    path = Path(index_path)
    if not path.is_file():
        raise FileNotFoundError(f"Decompose index file not found: {index_path}")

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    idx = DecomposeIndex.model_validate(data)

    done_step_ids = {
        step.id for step in idx.steps if step.status in ("done", "completed")
    }

    ready_steps: list[str] = []
    for step in idx.steps:
        if step.status in ("done", "completed", "in_progress"):
            continue
        if all(dep in done_step_ids for dep in step.depends_on):
            ready_steps.append(step.id)

    return ready_steps
