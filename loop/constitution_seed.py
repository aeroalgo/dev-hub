"""Seed constitution generator for product repositories."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def hub_root_guard(cwd_path: Path, hub_root_path: Path) -> None:
    if cwd_path.resolve() == hub_root_path.resolve():
        if os.getenv("DEV_HUB_CONSTITUTION_SEED") != "1":
            print(
                "Error: Cannot seed constitution directly into dev-hub root without DEV_HUB_CONSTITUTION_SEED=1",
                file=sys.stderr,
            )
            sys.exit(2)


def idempotency_guard(target_file: Path, force: bool) -> None:
    if target_file.exists() and not force:
        print(
            f"Error: {target_file} already exists. Use --force to overwrite.",
            file=sys.stderr,
        )
        sys.exit(2)


def seed_constitution(
    cwd: str | Path,
    force: bool = False,
    product_name: str | None = None,
    hub_root: str | Path | None = None,
) -> dict:
    cwd_path = Path(cwd).resolve()

    if hub_root is None:
        hub_root_path = Path(__file__).resolve().parents[1]
    else:
        hub_root_path = Path(hub_root).resolve()

    hub_root_guard(cwd_path, hub_root_path)

    mb_dir = cwd_path / "memory-bank"
    target_file = mb_dir / "constitution.md"

    idempotency_guard(target_file, force)

    mb_dir.mkdir(parents=True, exist_ok=True)

    template_file = hub_root_path / ".cursor" / "templates" / "constitution.md"
    if not template_file.is_file():
        print(f"Error: template not found at {template_file}", file=sys.stderr)
        sys.exit(2)

    name = product_name or cwd_path.name
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    content = template_file.read_text(encoding="utf-8")
    content = content.replace("[Product name]", name)
    content = content.replace("[constitution version]", "1.0")
    content = content.replace("[YYYY-MM-DD]", date_str)
    content = content.replace(
        "[product workflow, roles, hooks, and memory-bank artifacts covered by this constitution]",
        f"{name} workflow, roles, hooks, and memory-bank artifacts covered by this constitution",
    )

    target_file.write_text(content, encoding="utf-8")
    return {
        "ok": True,
        "path": str(target_file),
    }


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Seed product constitution")
    ap.add_argument("--cwd", default=".", help="Product root path")
    ap.add_argument("--force", action="store_true", help="Force overwrite")
    ap.add_argument("--product-name", default=None, help="Product name override")
    ap.add_argument("--hub-root", default=None, help="Hub root override")

    args = ap.parse_args()
    res = seed_constitution(
        cwd=args.cwd,
        force=args.force,
        product_name=args.product_name,
        hub_root=args.hub_root,
    )
    print(res)
    return 0


if __name__ == "__main__":
    sys.exit(main())
