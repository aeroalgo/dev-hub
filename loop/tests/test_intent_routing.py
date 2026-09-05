"""Tests for intent routing loader and schema validation."""
from pathlib import Path
import pytest
import yaml

from loop.workflow.command_router import load_intent_routing
from loop.workflow.schemas import IntentRoutingTable


def test_intent_routing_yaml_schema():
    yaml_path = Path(__file__).resolve().parent.parent / "workflow" / "intent_routing.yaml"
    assert yaml_path.is_file(), f"File {yaml_path} does not exist"
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert data.get("schema") == "workflow-intent-routing/v1"
    assert "video_production" in data.get("intents", {})
    video_prod = data["intents"]["video_production"]
    assert video_prod["pack"] == "video-production"
    assert len(video_prod["pipeline"]) >= 3


def test_load_intent_routing_video_production():
    table = load_intent_routing()
    assert isinstance(table, IntentRoutingTable)
    assert table.schema_ == "workflow-intent-routing/v1"
    assert "video_production" in table.intents

    route = table.intents["video_production"]
    assert route.pack == "video-production"
    assert len(route.pipeline) >= 3
    commands = [step.command for step in route.pipeline]
    assert "SCRIPT PLAN" in commands
    assert "POST EDIT" in commands


def test_load_intent_routing_feature_full():
    table = load_intent_routing()
    assert "feature_full" in table.intents
    route = table.intents["feature_full"]
    assert route.pack == "dev-hub-software"
    assert route.pipeline == []


def test_load_intent_routing_content_factory():
    table = load_intent_routing()
    assert "content_factory" in table.intents
    route = table.intents["content_factory"]
    assert route.pack == "video-production"
    assert len(route.pipeline) >= 3


def test_unknown_intent_not_present():
    table = load_intent_routing()
    assert "non_existent_intent" not in table.intents
