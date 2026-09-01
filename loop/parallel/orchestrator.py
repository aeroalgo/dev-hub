import os
import sys
import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

HOOKS = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))

from epic_index import load_index_yaml, dump_index_yaml, set_step_status_in_doc, mirror_status_to_md  # noqa: E402
from loop.parallel.wave import compute_ready_wave  # noqa: E402
from loop.parallel.overlap import file_overlap_check  # noqa: E402
from loop.parallel.worktree import create_worktree, destroy_worktree  # noqa: E402


@dataclass
class ParallelResult:
    wave: list[str]
    spawned: list[str]
    failed: list[str]


def filter_non_overlapping(ready_wave: list[str], decompose_dir: Path) -> list[str]:
    """
    Given a list of step IDs ready in the wave, returns a subset of step IDs
    that do not overlap with any previously selected step in this wave.
    If step_b overlaps with any selected step_a, step_b is excluded (sequential fallback).
    """
    selected: list[str] = []
    shards: dict[str, Path] = {}

    for step_id in ready_wave:
        shard_path = decompose_dir / f"{step_id}.yaml"
        if not shard_path.is_file():
            candidates = list(decompose_dir.glob(f"{step_id}*.yaml"))
            if candidates:
                shard_path = candidates[0]
        shards[step_id] = shard_path

    for step_id in ready_wave:
        shard_a = shards.get(step_id)
        if not shard_a or not shard_a.is_file():
            selected.append(step_id)
            continue

        has_overlap = False
        for sel_id in selected:
            shard_b = shards.get(sel_id)
            if shard_b and shard_b.is_file() and file_overlap_check(shard_a, shard_b):
                has_overlap = True
                break

        if not has_overlap:
            selected.append(step_id)

    return selected


def update_step_status_flock(index_path: Path, step_id: str, status: str) -> None:
    """Updates index.yaml (and mirrors index.md if present) with file locking."""
    import fcntl

    lock_file = index_path.parent / ".index.lock"
    with open(lock_file, "a+") as lf:
        fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
        try:
            doc = load_index_yaml(index_path)
            if doc:
                set_step_status_in_doc(doc, step_id, status)
                index_path.write_text(dump_index_yaml(doc), encoding="utf-8")
                md_path = index_path.parent / "index.md"
                if md_path.is_file():
                    mirror_status_to_md(md_path, step_id, status)
        finally:
            fcntl.flock(lf.fileno(), fcntl.LOCK_UN)


async def run_parallel_wave_async(
    epic_id: str,
    index_path: Path | str,
    repo_root: Path | str,
    env: Mapping[str, str] | None = None,
) -> ParallelResult | None:
    if env is None:
        env = os.environ

    if env.get("EPIC_PARALLEL_SNN") != "1":
        return None

    idx_path = Path(index_path)
    root = Path(repo_root)

    try:
        max_parallel = int(env.get("EPIC_PARALLEL_MAX", "2"))
    except ValueError:
        max_parallel = 2

    ready_wave = compute_ready_wave(idx_path)
    if not ready_wave:
        return ParallelResult(wave=[], spawned=[], failed=[])

    decompose_dir = idx_path.parent
    batch = filter_non_overlapping(ready_wave, decompose_dir)
    batch = batch[:max_parallel]

    spawned: list[str] = []
    failed: list[str] = []

    worktrees: dict[str, Path] = {}
    tasks: dict[str, asyncio.Task] = {}

    for step_id in batch:
        try:
            wt_path = create_worktree(epic_id, step_id, root)
            worktrees[step_id] = wt_path
            update_step_status_flock(idx_path, step_id, "in_progress")
        except Exception:
            failed.append(step_id)

    async def _run_subproc(step_id: str, wt_path: Path) -> tuple[str, int]:
        sub_env = dict(env)
        sub_env["EPIC_PARALLEL_SNN"] = "0"  # avoid recursive wave spawn in worktrees
        proc = await asyncio.create_subprocess_exec(
            "bash",
            "loop/loop.sh",
            cwd=str(wt_path),
            env=sub_env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, _ = await proc.communicate()
        return step_id, proc.returncode

    for step_id, wt_path in worktrees.items():
        task = asyncio.create_task(_run_subproc(step_id, wt_path))
        tasks[step_id] = task

    if tasks:
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        for res in results:
            if isinstance(res, Exception):
                continue
            s_id, code = res
            if code == 0:
                spawned.append(s_id)
                update_step_status_flock(idx_path, s_id, "completed")
            else:
                failed.append(s_id)
                update_step_status_flock(idx_path, s_id, "pending")

    for step_id, wt_path in worktrees.items():
        try:
            destroy_worktree(wt_path, root)
        except Exception:
            pass

    return ParallelResult(wave=ready_wave, spawned=spawned, failed=failed)


def run_parallel_wave(
    epic_id: str,
    index_path: Path | str,
    repo_root: Path | str,
    env: Mapping[str, str] | None = None,
) -> ParallelResult | None:
    if env is None:
        env = os.environ

    if env.get("EPIC_PARALLEL_SNN") != "1":
        return None

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import nest_asyncio
        nest_asyncio.apply()
        return loop.run_until_complete(run_parallel_wave_async(epic_id, index_path, repo_root, env))
    else:
        return asyncio.run(run_parallel_wave_async(epic_id, index_path, repo_root, env))
