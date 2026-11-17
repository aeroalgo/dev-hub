import importlib.util
import json
from pathlib import Path


HUB_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = HUB_ROOT / "bin" / "devops-deploy.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("devops_deploy", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_secure_access_manifest_is_declarative_and_complete():
    manifest = json.loads(
        (HUB_ROOT / "projects" / "secure-access" / "deploy.json").read_text(encoding="utf-8")
    )
    assert manifest["schema"] == "dev-hub-deploy/v1"
    assert manifest["adapter"]["actions"] == {
        "check": "check",
        "status": "status",
        "apply": "apply",
        "rollback": "rollback",
    }
    assert {target["name"] for target in manifest["targets"]} == {"nl", "ru"}
    assert all(target["containers"] for target in manifest["targets"])

    runner = load_runner()
    runner.load_manifest(HUB_ROOT.parent / "SOKOL" / "secure-access")


def test_remote_probe_contract_rejects_unknown_listener_protocol():
    runner = load_runner()
    try:
        runner.validate_target(
            {
                "name": "bad",
                "ssh_host": "vps",
                "address": "192.0.2.1",
                "listeners": [{"protocol": "icmp", "port": 1}],
            }
        )
    except runner.DeployError:
        pass
    else:
        raise AssertionError("unknown listener protocol must fail closed")
