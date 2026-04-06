"""相容入口：保留 `chief.py` 作為主控啟動點。"""

from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import runtime.compat  # Apply global compatibility patches (e.g. subprocess utf-8 fix)
from pipeline.chief_runner import *  # noqa: F401,F403
from pipeline.entry import main


if __name__ == "__main__":
    raise SystemExit(main())
