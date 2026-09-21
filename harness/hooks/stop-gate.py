from __future__ import annotations

from loop_guard import continue_event, hooks_enabled


def main() -> None:
    if hooks_enabled():
        continue_event()


if __name__ == "__main__":
    main()
