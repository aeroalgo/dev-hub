import pytest
import yaml
from pathlib import Path
from loop.schemas.decompose_index import DecomposeIndex, DecomposeStep
from loop.parallel.wave import compute_ready_wave


def test_index_backward_compat(tmp_path: Path):
    raw_yaml = """
schema: epic-decompose-index/v1
plan_id: T-TEST-001
steps:
  - id: s01
    file: s01.yaml
    title: Step 1
    next_phase: BACK IMPLEMENT
    status: pending
"""
    data = yaml.safe_load(raw_yaml)
    idx = DecomposeIndex.model_validate(data)
    assert len(idx.steps) == 1
    assert idx.steps[0].id == "s01"
    assert idx.steps[0].depends_on == []


def test_compute_ready_wave_basic(tmp_path: Path):
    index_file = tmp_path / "index.yaml"
    raw_yaml = """
schema: epic-decompose-index/v1
plan_id: T-TEST-001
steps:
  - id: s01
    file: s01.yaml
    title: Step 1
    next_phase: BACK IMPLEMENT
    status: pending
  - id: s02
    file: s02.yaml
    title: Step 2
    next_phase: BACK IMPLEMENT
    status: pending
"""
    index_file.write_text(raw_yaml)
    ready = compute_ready_wave(index_file)
    assert ready == ["s01", "s02"]


def test_compute_ready_wave_blocked(tmp_path: Path):
    index_file = tmp_path / "index.yaml"
    raw_yaml = """
schema: epic-decompose-index/v1
plan_id: T-TEST-001
steps:
  - id: s01
    file: s01.yaml
    title: Step 1
    next_phase: BACK IMPLEMENT
    status: pending
  - id: s02
    file: s02.yaml
    title: Step 2
    next_phase: BACK IMPLEMENT
    status: pending
    depends_on: ["s01"]
"""
    index_file.write_text(raw_yaml)
    ready = compute_ready_wave(index_file)
    assert ready == ["s01"]


def test_compute_ready_wave_done_deps(tmp_path: Path):
    index_file = tmp_path / "index.yaml"
    raw_yaml = """
schema: epic-decompose-index/v1
plan_id: T-TEST-001
steps:
  - id: s01
    file: s01.yaml
    title: Step 1
    next_phase: BACK IMPLEMENT
    status: done
  - id: s02
    file: s02.yaml
    title: Step 2
    next_phase: BACK IMPLEMENT
    status: pending
    depends_on: ["s01"]
"""
    index_file.write_text(raw_yaml)
    ready = compute_ready_wave(index_file)
    assert ready == ["s02"]


def test_compute_ready_wave_skip_inprogress(tmp_path: Path):
    index_file = tmp_path / "index.yaml"
    raw_yaml = """
schema: epic-decompose-index/v1
plan_id: T-TEST-001
steps:
  - id: s01
    file: s01.yaml
    title: Step 1
    next_phase: BACK IMPLEMENT
    status: in_progress
"""
    index_file.write_text(raw_yaml)
    ready = compute_ready_wave(index_file)
    assert ready == []
