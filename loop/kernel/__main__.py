from .cli import main
from loop.config import activate_loop_process

activate_loop_process()
raise SystemExit(main())
