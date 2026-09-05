import ast
import json
import os
from dataclasses import dataclass
from pathlib import Path
import yaml


@dataclass
class RatchetResult:
    ok: bool
    delta: int
    message: str


@dataclass
class Violation:
    contract_id: str
    file_path: str
    line_number: int
    imported_module: str
    forbidden_pattern: str
    reason: str

    def format_message(self) -> str:
        return (
            f"[{self.contract_id}] Boundary violation in {self.file_path}:{self.line_number}\n"
            f"  Imported module: '{self.imported_module}' matches forbidden pattern '{self.forbidden_pattern}'\n"
            f"  Reason: {self.reason}\n"
            f"  Remediation hint: Remove or decouple the import to respect layer boundaries."
        )


def _get_layer_roots(root_dir: Path, layer_name: str) -> list[Path]:
    if layer_name == "loop":
        p = root_dir / "loop"
        return [p] if p.exists() else []
    elif layer_name == "hooks":
        res = []
        c_p = root_dir / ".claude" / "hooks"
        cur_p = root_dir / ".cursor" / "hooks"
        if c_p.exists():
            res.append(c_p)
        if cur_p.exists():
            res.append(cur_p)
        return res
    elif layer_name == "claude_hooks":
        c_p = root_dir / ".claude" / "hooks"
        return [c_p] if c_p.exists() else []
    elif layer_name == "product":
        # Check all python files in root except tests/ or loop/
        return [root_dir]
    return []


def _extract_imports(file_path: Path) -> list[tuple[int, str]]:
    imports = []
    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(file_path))
    except Exception:
        return imports

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append((node.lineno, node.module))
                for alias in node.names:
                    imports.append((node.lineno, f"{node.module}.{alias.name}"))
    return imports


def check_boundaries(root_dir: Path | str, boundaries_yaml_path: Path | str) -> list[Violation]:
    root_path = Path(root_dir).resolve()
    yaml_path = Path(boundaries_yaml_path).resolve()

    if not yaml_path.exists():
        raise FileNotFoundError(f"Boundaries YAML file not found: {yaml_path}")

    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    contracts = data.get("contracts", [])
    violations: list[Violation] = []

    for contract in contracts:
        contract_id = contract.get("id", "unknown")
        layer_name = contract.get("layer")
        forbids = contract.get("forbids", [])
        reason = contract.get("reason", "No reason provided")

        roots = _get_layer_roots(root_path, layer_name)
        for root in roots:
            if not root.exists():
                continue

            python_files = list(root.rglob("*.py")) if root.is_dir() else [root]
            for py_file in python_files:
                # Exclude tests directory and virtual environments/caches
                if any(part in py_file.parts for part in ("tests", ".venv", "venv", "site-packages", "__pycache__", ".git")):
                    continue

                rel_path = str(py_file.relative_to(root_path))
                imports = _extract_imports(py_file)

                for lineno, imp_name in imports:
                    for forbidden in forbids:
                        if imp_name == forbidden or imp_name.startswith(forbidden + "."):
                            violations.append(
                                Violation(
                                    contract_id=contract_id,
                                    file_path=rel_path,
                                    line_number=lineno,
                                    imported_module=imp_name,
                                    forbidden_pattern=forbidden,
                                    reason=reason,
                                )
                            )

    return violations


def check_ratchet(violations: list[Violation], ratchet_path: Path | str) -> RatchetResult:
    path = Path(ratchet_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Ratchet JSON file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f) or {}

    allowed = data.get("violations", 0)
    found = len(violations)
    delta = found - allowed

    if found > allowed:
        msg = f"RATCHET EXCEEDED: found {found}, allowed {allowed}; run update-ratchet to freeze new baseline"
        return RatchetResult(ok=False, delta=delta, message=msg)

    return RatchetResult(ok=True, delta=delta, message="")

