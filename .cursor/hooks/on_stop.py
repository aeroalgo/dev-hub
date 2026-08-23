#!/usr/bin/env python3
import json
import sys
from datetime import datetime, timezone

import _wf


def main() -> None:
    payload = json.load(sys.stdin)
    root = _wf.workspace_root(payload)
    status = payload.get("status") or ""
    art = _wf.artifacts_dir(root)
    lst = art / "session-edits.list"
    edited: list[str] = []
    if lst.is_file():
        edited = [line.strip() for line in lst.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]

    test_out, code = _wf.detect_and_run_tests(root)
    review = art / "review-request.md"
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    body = []
    body.append("# Конец прогона агента (Cursor hook `stop`)\n")
    body.append(f"Время: {ts}\n")
    body.append(f"Статус агента: `{status}`\n")
    body.append("\n## Файлы с правками за эту сессию\n")
    if edited:
        for p in edited:
            body.append(f"- `{p}`\n")
    else:
        body.append("(нет записей с `afterFileEdit` или всё в игнорируемых путях)\n")
    body.append("\n## Вывод тестов\n")
    body.append("```\n")
    body.append(test_out[:50000] if len(test_out) > 50000 else test_out)
    body.append("\n```\n")
    body.append(f"\nКод выхода тестов: `{code}`\n")
    body.append("\n## Ревью (следующий шаг)\n")
    body.append("1. Сверить изменения с формулировкой задачи (источник задачи — человек, не расширять скоуп).\n")
    body.append("2. Проверить краевые случаи и ошибки по затронутому коду.\n")
    body.append("3. При необходимости открыть этот файл в чате: `@.cursor/hooks-artifacts/review-request.md`.\n")
    review.write_text("".join(body), encoding="utf-8")

    if lst.is_file():
        lst.unlink()


if __name__ == "__main__":
    main()
