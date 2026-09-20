#!/usr/bin/env python3

from __future__ import annotations

import sys
from pathlib import Path


_PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)

_SRC_ROOT = (
    _PROJECT_ROOT
    / "src"
)

if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(_SRC_ROOT),
    )

from performance_engineering.execution.governed_engine_runner import (
    main,
)


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
