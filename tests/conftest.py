from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_SRC = PROJECT_ROOT / "src"

if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_SRC),
    )
