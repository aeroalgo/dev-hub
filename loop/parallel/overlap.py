from pathlib import Path
import yaml


def extract_shard_files(shard_dict: dict) -> frozenset[str]:
    files: set[str] = set()

    context = shard_dict.get("context")
    if isinstance(context, dict):
        ctx_files = context.get("files")
        if isinstance(ctx_files, list):
            for f in ctx_files:
                if isinstance(f, str) and f.strip():
                    files.add(str(Path(f.strip())))

    for key in ("delta", "deletes"):
        val = shard_dict.get(key)
        if isinstance(val, list):
            for item in val:
                if isinstance(item, str) and item.strip():
                    files.add(str(Path(item.strip())))
                elif isinstance(item, dict):
                    path_val = item.get("path") or item.get("file")
                    if isinstance(path_val, str) and path_val.strip():
                        files.add(str(Path(path_val.strip())))

    return frozenset(files)


def file_overlap_check(shard_a: Path | str, shard_b: Path | str) -> bool:
    path_a = Path(shard_a)
    path_b = Path(shard_b)

    if not path_a.is_file():
        raise FileNotFoundError(f"Shard file not found: {shard_a}")
    if not path_b.is_file():
        raise FileNotFoundError(f"Shard file not found: {shard_b}")

    data_a = yaml.safe_load(path_a.read_text(encoding="utf-8")) or {}
    data_b = yaml.safe_load(path_b.read_text(encoding="utf-8")) or {}

    files_a = extract_shard_files(data_a)
    files_b = extract_shard_files(data_b)

    return bool(files_a & files_b)
