from pathlib import Path
import pytest
import yaml
from loop.parallel.overlap import extract_shard_files, file_overlap_check


def create_shard(tmp_path: Path, filename: str, content: dict) -> Path:
    p = tmp_path / filename
    p.write_text(yaml.safe_dump(content), encoding="utf-8")
    return p


def test_no_overlap(tmp_path: Path):
    shard_a = create_shard(
        tmp_path,
        "s01.yaml",
        {
            "context": {"files": ["loop/a.py"]},
            "delta": ["loop/b.py"],
            "deletes": [],
        },
    )
    shard_b = create_shard(
        tmp_path,
        "s02.yaml",
        {
            "context": {"files": ["loop/c.py"]},
            "delta": ["loop/d.py"],
            "deletes": [],
        },
    )
    assert file_overlap_check(shard_a, shard_b) is False


def test_overlap_context_files(tmp_path: Path):
    shard_a = create_shard(
        tmp_path,
        "s01.yaml",
        {
            "context": {"files": ["loop/shared.py", "loop/a.py"]},
        },
    )
    shard_b = create_shard(
        tmp_path,
        "s02.yaml",
        {
            "context": {"files": ["loop/shared.py", "loop/b.py"]},
        },
    )
    assert file_overlap_check(shard_a, shard_b) is True


def test_overlap_delta_path(tmp_path: Path):
    shard_a = create_shard(
        tmp_path,
        "s01.yaml",
        {
            "context": {"files": ["loop/a.py"]},
            "delta": ["loop/shared.py"],
        },
    )
    shard_b = create_shard(
        tmp_path,
        "s02.yaml",
        {
            "context": {"files": ["loop/shared.py"]},
        },
    )
    assert file_overlap_check(shard_a, shard_b) is True


def test_overlap_deletes_path(tmp_path: Path):
    shard_a = create_shard(
        tmp_path,
        "s01.yaml",
        {
            "context": {"files": ["loop/a.py"]},
            "deletes": ["loop/shared.py"],
        },
    )
    shard_b = create_shard(
        tmp_path,
        "s02.yaml",
        {
            "delta": ["loop/shared.py"],
        },
    )
    assert file_overlap_check(shard_a, shard_b) is True


def test_empty_shard_no_overlap(tmp_path: Path):
    shard_a = create_shard(
        tmp_path,
        "s01.yaml",
        {},
    )
    shard_b = create_shard(
        tmp_path,
        "s02.yaml",
        {
            "context": {"files": ["loop/a.py"]},
        },
    )
    assert file_overlap_check(shard_a, shard_b) is False
